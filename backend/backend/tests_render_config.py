"""No database or external systems required for deployment configuration checks."""

from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from backend.feature_config import FEATURE_ENV_VARS
from backend.render_config import (
    hostname, https_url, origin, redis_url, required, validate_testing_environment,
)


class RenderEnvironmentTests(SimpleTestCase):
    def test_missing_and_placeholder_values_fail_without_echoing_values(self):
        for value in ("", " ", "<private-placeholder>"):
            with self.assertRaises(ImproperlyConfigured) as caught:
                required({"DB_PASSWORD": value}, "DB_PASSWORD")
            self.assertIn("DB_PASSWORD", str(caught.exception))
            self.assertNotIn("private-placeholder", str(caught.exception))

    def test_passwords_preserve_significant_whitespace(self):
        self.assertEqual(required({"DB_PASSWORD": " synthetic "}, "DB_PASSWORD"), " synthetic ")
        self.assertEqual(required({"DB_PASSWORD": "synthetic<angle>characters"}, "DB_PASSWORD"), "synthetic<angle>characters")

    def test_all_deferred_flags_reject_enabled_or_ambiguous_values(self):
        validate_testing_environment({})
        for name in (*FEATURE_ENV_VARS.values(), "DEBUG", "SIMULATED_METER_ENABLED",
                     "MOBILE_PAYMENT_ACTIONS_ENABLED", "CELERY_TASK_ALWAYS_EAGER"):
            for value in ("true", "1", "on", "sometimes"):
                with self.subTest(name=name, value=value), self.assertRaises(ImproperlyConfigured):
                    validate_testing_environment({name: value})
            for value in ("false", "0", "OFF", "no"):
                validate_testing_environment({name: value})

    def test_provider_simulation_cannot_default_on(self):
        for value in ("true", "on", "off", " false ", ""):
            with self.assertRaises(ImproperlyConfigured):
                validate_testing_environment({"MTN_USE_SIMULATED_PAYMENTS": value})
        for value in ("false", "FALSE", "0", "no"):
            validate_testing_environment({"MTN_USE_SIMULATED_PAYMENTS": value})

    def test_provider_credentials_and_non_mock_gateways_rejected(self):
        for name in ("THINGSBOARD_TENANT_PASSWORD", "THINGSBOARD_WEBHOOK_SECRET",
                     "MTN_SUBSCRIPTION_KEY", "PRIMARY_KEY", "SECONDARY_KEY",
                     "MTN_API_KEY", "MTN_API_USER_ID", "AMI_GATEWAY", "CRB_PROVIDER"):
            with self.subTest(name=name), self.assertRaises(ImproperlyConfigured) as caught:
                validate_testing_environment({name: "sensitive-test-value"})
            self.assertNotIn("sensitive-test-value", str(caught.exception))

    def test_hosts_exclude_schemes_ports_and_wildcards(self):
        self.assertEqual(hostname(" Test.onrender.com ", "host"), "test.onrender.com")
        for value in ("*", "https://test.onrender.com", "test.onrender.com:443", "test/path"):
            with self.assertRaises(ImproperlyConfigured):
                hostname(value, "host")

    def test_origins_are_single_exact_origins(self):
        self.assertEqual(origin("http://localhost", "mobile", mobile=True), "http://localhost")
        self.assertEqual(origin("https://localhost", "mobile", mobile=True), "https://localhost")
        for value in ("http://192.168.1.2", "https://example.test/", "https://example.test/path",
                      "https://one.test,https://two.test", "https://user:pass@example.test"):
            with self.assertRaises(ImproperlyConfigured):
                origin(value, "origin", mobile=True)

    def test_api_always_https(self):
        self.assertEqual(https_url("https://api.example.test/api/v1/", "api"), "https://api.example.test/api/v1")
        for value in ("http://api.example.test/api/v1", "https://api.example.test/?token=x"):
            with self.assertRaises(ImproperlyConfigured):
                https_url(value, "api")

    def test_broker_urls_require_redis_scheme_without_echoing_values(self):
        redis_url("rediss://user:synthetic@redis.example.test:6379/0", "broker")
        with self.assertRaises(ImproperlyConfigured) as caught:
            redis_url("https://user:sensitive-test-value@example.test", "broker")
        self.assertNotIn("sensitive-test-value", str(caught.exception))


class RenderProfileTests(SimpleTestCase):
    """Run with --settings=backend.render_settings and synthetic environment."""

    def setUp(self):
        if settings.SETTINGS_MODULE != "backend.render_settings":
            self.skipTest("Render-profile integration requires the opt-in settings module")
        self.host = settings.ALLOWED_HOSTS[0]

    def get(self, path, **headers):
        return self.client.get(path, HTTP_HOST=self.host, HTTP_X_FORWARDED_PROTO="https", **headers)

    def test_https_proxy_health_and_host_rejection(self):
        self.assertEqual(self.get("/").status_code, 200)
        self.assertEqual(self.get("/", HTTP_ORIGIN=settings.MOBILE_APP_ORIGIN).status_code, 200)
        self.assertEqual(self.client.get("/", HTTP_HOST=self.host).status_code, 301)
        response = self.client.get("/", HTTP_HOST="unapproved.invalid", HTTP_X_FORWARDED_PROTO="https")
        self.assertEqual(response.status_code, 400)

    def test_features_stay_off_and_api_is_readable(self):
        from django.db import connection
        with patch.dict(connection.settings_dict, {"ATOMIC_REQUESTS": False}):
            response = self.get("/api/v1/features/", HTTP_ORIGIN=settings.MOBILE_APP_ORIGIN)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Access-Control-Allow-Origin"], settings.MOBILE_APP_ORIGIN)
        self.assertTrue(all(value is False for value in response.json()["features"].values()))
        self.assertTrue(all(value is False for value in response.json()["mobile_actions"].values()))
        self.assertNotIn("Access-Control-Allow-Origin", self.get("/", HTTP_ORIGIN="https://unapproved.invalid"))

    def test_preflight_allows_only_required_methods_and_headers(self):
        response = self.client.options(
            "/api/v1/auth/login/", HTTP_HOST=self.host, HTTP_X_FORWARDED_PROTO="https",
            HTTP_ORIGIN=settings.MOBILE_APP_ORIGIN, HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Access-Control-Allow-Origin"], settings.MOBILE_APP_ORIGIN)
        self.assertEqual(response["Access-Control-Allow-Methods"], "GET, POST, PATCH, OPTIONS")
        self.assertEqual(response["Access-Control-Allow-Headers"], "authorization, content-type")

    def test_login_400_and_account_401_have_cors(self):
        # Exercise actual middleware/error responses. Bypass ATOMIC_REQUESTS
        # only in this DB-free test; neither invalid request should query data.
        from django.db import connection
        with patch.dict(connection.settings_dict, {"ATOMIC_REQUESTS": False}):
            login = self.client.post(
                "/api/v1/auth/login/", data="{}", content_type="application/json",
                HTTP_HOST=self.host, HTTP_X_FORWARDED_PROTO="https", HTTP_ORIGIN=settings.MOBILE_APP_ORIGIN,
            )
            account = self.get(
                "/api/v1/auth/mobile-account/", HTTP_ORIGIN=settings.MOBILE_APP_ORIGIN,
                HTTP_AUTHORIZATION="Bearer diagnostic-invalid-token",
            )
        self.assertEqual(login.status_code, 400)
        self.assertEqual(account.status_code, 401)
        for response in (login, account):
            self.assertEqual(response["Access-Control-Allow-Origin"], settings.MOBILE_APP_ORIGIN)

    def test_secure_settings_and_no_automatic_integrations(self):
        self.assertFalse(settings.DEBUG)
        self.assertTrue(settings.SESSION_COOKIE_SECURE)
        self.assertTrue(settings.CSRF_COOKIE_SECURE)
        self.assertTrue(settings.SIMPLE_JWT["AUTH_COOKIE_SECURE"])
        self.assertEqual(settings.CSRF_TRUSTED_ORIGINS, [settings.PRODUCTION_ORIGIN])
        self.assertEqual(settings.CELERY_BEAT_SCHEDULE, {})
        self.assertFalse(settings.CELERY_TASK_ALWAYS_EAGER)
        self.assertEqual(settings.THINGSBOARD_BASE_URL, "https://devices.disabled.invalid")
        self.assertTrue(settings.DATABASES["default"]["ATOMIC_REQUESTS"])
        self.assertEqual(settings.DATABASES["default"]["OPTIONS"]["options"], "-c search_path=custom,public")
