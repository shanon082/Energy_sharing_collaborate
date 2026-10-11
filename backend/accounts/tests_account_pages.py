"""App-first browser actions, real isolated PostgreSQL and mocked SMTP only."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import os
import re
from threading import Barrier
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core import mail
from django.db import connections
from django.test import Client, SimpleTestCase, TransactionTestCase, override_settings

from accounts.account_actions import (
    InvalidAccountLink, account_email_link, complete_password_reset, confirm_account_email,
)
from accounts.email_outbox import drain_account_emails
from accounts.models import User
from utils.auth import reset_password_token_generator, token_generator


class HostedAccountConfigurationTests(SimpleTestCase):
    def test_profile_starts_without_a_frontend_and_retains_restrictions(self):
        if not getattr(settings, "ALWAYSDATA_TESTING", False):
            self.skipTest("Use the --profile isolated hosting runner")
        self.assertNotIn("FRONTEND_URL", os.environ)
        self.assertEqual(settings.ACCOUNT_PAGES_ORIGIN, "https://test.alwaysdata.net")
        self.assertEqual(settings.FRONTEND_URL, settings.ACCOUNT_PAGES_ORIGIN)
        self.assertEqual(settings.ROOT_URLCONF, "backend.alwaysdata_urls")
        self.assertFalse(settings.BACKGROUND_TASKS_AVAILABLE or settings.CELERY_TASK_ALWAYS_EAGER)
        self.assertFalse(settings.MOBILE_PAYMENT_ACTIONS_ENABLED or settings.SIMULATED_METER_ENABLED)
        self.assertTrue(all(not value for value in settings.FEATURE_FLAGS.values()))
        self.assertIn("http://localhost", settings.CORS_ALLOWED_ORIGINS)
        self.assertIn("https://localhost", settings.CORS_ALLOWED_ORIGINS)
        # Real production storage/WhiteNoise; no database or Next.js needed.
        css_url = staticfiles_storage.url("accounts/account-pages.css")
        css = self.client.get(css_url, HTTP_HOST=settings.ALLOWED_HOSTS[0], HTTP_X_FORWARDED_PROTO="https")
        self.assertEqual(css.status_code, 200)
        self.assertEqual(css["Content-Type"], "text/css; charset=\"utf-8\"")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class HostedAccountPageTests(TransactionTestCase):
    def setUp(self):
        if not getattr(settings, "ALWAYSDATA_TESTING", False):
            self.skipTest("Use the --profile isolated hosting runner")
        self.user = User.objects.create_user(email="browser-test@example.invalid", password="Initial-page-password-123")
        self.client = Client(enforce_csrf_checks=True, HTTP_HOST=settings.ALLOWED_HOSTS[0],
                             HTTP_X_FORWARDED_PROTO="https")

    def link(self, *, reset=False):
        return account_email_link(self.user, reset=reset)

    def args(self, link):
        return {key: values[0] for key, values in parse_qs(urlsplit(link).query).items()}

    def open_form(self, link):
        parsed = urlsplit(link)
        response = self.client.get(parsed.path, self.args(link))
        self.assertEqual(response.status_code, 200)
        self.assert_sensitive_headers(response)
        self.assertContains(response, f'action="{parsed.path}"')
        self.assertNotContains(response, "<script")
        self.assertNotContains(response, "https://")
        csrf = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', response.content.decode()).group(1)
        self.assertTrue(self.client.cookies[settings.CSRF_COOKIE_NAME]["secure"])
        return parsed.path, {**self.args(link), "csrfmiddlewaretoken": csrf}

    def submit(self, path, data, **headers):
        return self.client.post(path, data, HTTP_ORIGIN=settings.ACCOUNT_PAGES_ORIGIN, **headers)

    def assert_sensitive_headers(self, response):
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("private", response["Cache-Control"])
        self.assertEqual(response["Referrer-Policy"], "no-referrer")
        self.assertIn("noindex", response["X-Robots-Tag"])
        self.assertIn("default-src 'none'", response["Content-Security-Policy"])
        self.assertIn("form-action 'self'", response["Content-Security-Policy"])
        self.assertIn("frame-ancestors 'none'", response["Content-Security-Policy"])

    def test_verification_get_head_and_legacy_api_do_not_consume(self):
        link = self.link()
        path, data = self.open_form(link)
        self.assertEqual(self.client.head(path, self.args(link)).status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.profile.email_verified)
        api = self.client.get("/api/v1/auth/verify-email/", self.args(link))
        self.assertEqual(api.status_code, 405)
        self.assertEqual(api.json()["code"], "ACCOUNT_CONFIRMATION_REQUIRED")
        self.assertFalse(self.user.profile.email_verified)
        # Explicit checkbox confirmation is required in addition to CSRF.
        self.assertEqual(self.submit(path, data).status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.profile.email_verified)
        response = self.submit(path, {**data, "confirm": "on"})
        self.assertEqual(response.status_code, 200)
        self.assert_sensitive_headers(response)
        self.assertContains(response, "Email verified successfully.")
        self.assertNotContains(response, data["token"])
        self.assertNotIn(settings.SESSION_COOKIE_NAME, self.client.cookies)
        self.user.refresh_from_db()
        self.assertTrue(self.user.profile.email_verified)
        self.assertEqual(self.submit(path, {**data, "confirm": "on"}).status_code, 400)

    def test_csrf_required_and_untrusted_origin_rejected(self):
        link = self.link()
        path, data = self.open_form(link)
        no_csrf = self.submit(path, {**self.args(link), "confirm": "on"})
        self.assertEqual(no_csrf.status_code, 403)
        self.assert_sensitive_headers(no_csrf)
        foreign = self.client.post(path, {**data, "confirm": "on"}, HTTP_ORIGIN="https://unapproved.invalid")
        self.assertEqual(foreign.status_code, 403)
        self.assert_sensitive_headers(foreign)
        self.user.refresh_from_db()
        self.assertFalse(self.user.profile.email_verified)
        self.assertEqual(self.client.post(path, {**data, "confirm": "on"},
                                         HTTP_REFERER=link).status_code, 200)

    def test_reset_get_does_not_change_password_or_verify_and_post_is_single_use(self):
        link = self.link(reset=True)
        original = self.user.password
        path, data = self.open_form(link)
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, original)
        self.assertFalse(self.user.profile.email_verified)
        payload = {**data, "password": "New-page-password-234", "confirm_password": "New-page-password-234"}
        no_csrf = self.submit(path, {key: value for key, value in payload.items() if key != "csrfmiddlewaretoken"})
        self.assertEqual(no_csrf.status_code, 403)
        self.assert_sensitive_headers(no_csrf)
        self.assertEqual(self.user.password, original)
        response = self.submit(path, payload)
        self.assertEqual(response.status_code, 200)
        self.assert_sensitive_headers(response)
        self.assertContains(response, "Password reset successfully.")
        self.assertNotContains(response, data["token"])
        self.assertNotContains(response, payload["password"])
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(payload["password"]))
        # Preserve existing reset-by-email verification semantics.
        self.assertTrue(self.user.profile.email_verified)
        self.assertEqual(self.submit(path, payload).status_code, 400)

    def test_password_validation_and_confirmation_do_not_consume_reset(self):
        path, data = self.open_form(self.link(reset=True))
        original = self.user.password
        for password, confirmation in (("short", "short"), ("12345678", "12345678"),
                                       ("Long-page-password-123", "Mismatch-password-123")):
            response = self.submit(path, {**data, "password": password, "confirm_password": confirmation})
            self.assertEqual(response.status_code, 400)
            self.assert_sensitive_headers(response)
            self.assertNotContains(response, f'value="{password}"', status_code=400)
            self.user.refresh_from_db()
            self.assertEqual(self.user.password, original)
        self.assertEqual(self.submit(path, {**data, "password": "Valid-page-password-123",
                                           "confirm_password": "Valid-page-password-123"}).status_code, 200)

    def test_tampered_expired_and_wrong_purpose_links(self):
        for reset in (False, True):
            generator = reset_password_token_generator if reset else token_generator
            link = self.link(reset=reset)
            path, data = self.open_form(link)
            payload = {**data, "confirm": "on", "password": "New-page-password-234",
                       "confirm_password": "New-page-password-234"}
            self.assertEqual(self.submit(path, {**payload, "token": "tampered"}).status_code, 400)
            with patch.object(generator, "_now", return_value=generator._now() + timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT + 1)):
                expired = self.client.get(path, self.args(link))
                self.assertEqual(expired.status_code, 400)
                self.assert_sensitive_headers(expired)
                self.assertEqual(self.submit(path, payload).status_code, 400)
            wrong_path = "/account/verify-email/" if reset else "/account/reset-password/"
            self.assertEqual(self.client.get(wrong_path, self.args(link)).status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.profile.email_verified)
        self.assertTrue(self.user.check_password("Initial-page-password-123"))

    def test_invalid_and_inactive_links_are_generic_and_safe(self):
        for uid in ("not-base64", "", "x" * 257):
            response = self.client.get("/account/verify-email/", {"uid": uid, "token": "bad"})
            self.assertEqual(response.status_code, 400)
            self.assert_sensitive_headers(response)
        link = self.link(reset=True)
        self.user.profile.delete()
        self.assertEqual(self.client.get(urlsplit(link).path, self.args(link)).status_code, 400)
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.assertEqual(self.client.get(urlsplit(link).path, self.args(link)).status_code, 400)

    def test_emails_use_trusted_origin_even_with_allowed_host_alias_and_next_url(self):
        with override_settings(ALLOWED_HOSTS=[settings.ALLOWED_HOSTS[0], "alias.example.invalid"],
                               FRONTEND_URL="https://future-web.example.invalid"):
            request_client = Client(HTTP_HOST="alias.example.invalid", HTTP_X_FORWARDED_PROTO="https")
            responses = [request_client.post("/api/v1/auth/forgot-password/", {"email": email})
                         for email in (self.user.email, "missing@example.invalid")]
            self.assertEqual(responses[0].json(), responses[1].json())
            drain_account_emails(5)
            self.assertEqual(len(mail.outbox), 2)
            for message in mail.outbox:
                link = message.body.split(": ", 1)[1].split("\n", 1)[0]
                self.assertEqual(f"{urlsplit(link).scheme}://{urlsplit(link).netloc}", settings.ACCOUNT_PAGES_ORIGIN)
                self.assertTrue(urlsplit(link).path.startswith("/account/"))
                self.assertNotIn("alias.example.invalid", link)
                self.assertNotIn("future-web.example.invalid", link)

    def test_reset_revokes_existing_session_and_requires_new_password(self):
        self.user.profile.email_verified = True
        self.user.profile.save(update_fields=["email_verified"])
        api = Client(HTTP_HOST=settings.ALLOWED_HOSTS[0], HTTP_X_FORWARDED_PROTO="https")
        login = api.post("/api/v1/auth/login/", {"email": self.user.email, "password": "Initial-page-password-123"})
        self.assertEqual(login.status_code, 200)
        refresh, access = login.json()["refresh"], login.json()["access"]
        path, data = self.open_form(self.link(reset=True))
        self.assertEqual(self.submit(path, {**data, "password": "New-page-password-234",
                                           "confirm_password": "New-page-password-234"}).status_code, 200)
        self.assertEqual(api.post("/api/v1/auth/refresh/token/", {"refresh": refresh}).status_code, 401)
        self.assertEqual(api.get("/api/v1/auth/mobile-account/", HTTP_AUTHORIZATION=f"Bearer {access}").status_code, 401)
        self.assertEqual(api.post("/api/v1/auth/login/", {"email": self.user.email, "password": "Initial-page-password-123"}).status_code, 401)
        self.assertEqual(api.post("/api/v1/auth/login/", {"email": self.user.email, "password": "New-page-password-234"}).status_code, 200)

    def test_concurrent_confirmations_have_one_effect_for_each_action(self):
        self.assertEqual(connections["default"].vendor, "postgresql")
        for reset in (False, True):
            args = self.args(self.link(reset=reset))
            barrier = Barrier(2)
            def complete(_):
                try:
                    barrier.wait(timeout=10)
                    if reset:
                        complete_password_reset(args["uid"], args["token"], {
                            "password": "Concurrent-page-password-234", "confirm_password": "Concurrent-page-password-234",
                        })
                    else:
                        confirm_account_email(args["uid"], args["token"])
                    return "completed"
                except InvalidAccountLink:
                    return "rejected"
                finally:
                    connections.close_all()
            with ThreadPoolExecutor(max_workers=2) as executor:
                self.assertCountEqual(list(executor.map(complete, range(2))), ["completed", "rejected"])
            self.user.refresh_from_db()

    @override_settings(DJANGO_HOSTED_ACCOUNT_PAGES=False, FRONTEND_URL="https://web.example.invalid")
    def test_nextjs_link_generation_and_legacy_get_remain_available_outside_hosted_mode(self):
        link = self.link()
        self.assertEqual(urlsplit(link).netloc, "web.example.invalid")
        self.assertEqual(urlsplit(link).path, "/auth/verify-email")
        self.assertEqual(self.client.get("/api/v1/auth/verify-email/", self.args(link)).status_code, 200)
        reset = self.link(reset=True)
        self.assertEqual(urlsplit(reset).path, "/auth/reset-password/")
