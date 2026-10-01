from django.test import SimpleTestCase, TestCase, override_settings


@override_settings(
    CORS_ALLOW_ALL_ORIGINS=False,
    CORS_ALLOWED_ORIGINS=["http://localhost", "http://localhost:3000"],
)
class MobileCorsTests(SimpleTestCase):
    def preflight(self, origin, method="POST", headers="content-type"):
        return self.client.options(
            "/api/v1/auth/login/",
            HTTP_ORIGIN=origin,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD=method,
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS=headers,
        )

    def test_debug_webview_login_preflight_is_narrow(self):
        response = self.preflight("http://localhost")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Access-Control-Allow-Origin"], "http://localhost")
        self.assertEqual(response["Access-Control-Allow-Methods"], "GET, POST, PATCH, OPTIONS")
        self.assertEqual(response["Access-Control-Allow-Headers"], "authorization, content-type")

    def test_unapproved_origin_has_no_cors_grant(self):
        response = self.preflight("http://unapproved.invalid")
        self.assertNotIn("Access-Control-Allow-Origin", response)

    def test_authorized_reads_can_request_bearer_header(self):
        response = self.preflight("http://localhost", method="GET", headers="authorization")
        self.assertEqual(response["Access-Control-Allow-Origin"], "http://localhost")

    def test_profile_patch_preflight_is_narrow(self):
        response = self.preflight("http://localhost", method="PATCH", headers="authorization,content-type")
        self.assertEqual(response["Access-Control-Allow-Origin"], "http://localhost")


@override_settings(
    CORS_ALLOW_ALL_ORIGINS=False,
    CORS_ALLOWED_ORIGINS=["http://localhost", "http://localhost:3000"],
)
class MobileCorsResponseTests(TestCase):
    def test_expected_login_400_is_readable_to_webview(self):
        response = self.client.post(
            "/api/v1/auth/login/", data="{}", content_type="application/json",
            HTTP_ORIGIN="http://localhost",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response["Access-Control-Allow-Origin"], "http://localhost")

    def test_account_401_is_readable_to_webview(self):
        response = self.client.get(
            "/api/v1/auth/mobile-account/",
            HTTP_ORIGIN="http://localhost",
            HTTP_AUTHORIZATION="Bearer diagnostic-invalid-token",
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["Access-Control-Allow-Origin"], "http://localhost")
