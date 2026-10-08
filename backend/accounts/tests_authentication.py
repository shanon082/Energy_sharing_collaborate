"""Consumer authentication boundaries on isolated PostgreSQL and mocked mail."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

from django.conf import settings
from django.db import close_old_connections, connection
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.utils import datetime_from_epoch

from accounts.api.serializers import CreateUserSerializer
from accounts.models import User, Profile, UserAccountDetails
from accounts.utils import b64encode_user
from utils.auth import token_generator, reset_password_token_generator


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ConsumerAuthenticationTests(TransactionTestCase):
    def setUp(self):
        mail = patch("accounts.signals.dispatch_task")
        self.send_mail = mail.start()
        self.addCleanup(mail.stop)
        self.owner = User.objects.create_user(email="auth-owner@example.invalid", password="Auth-test-only-123")
        self.owner.profile.email_verified = True
        self.owner.profile.save(update_fields=["email_verified"])
        self.public = APIClient()

    def login(self, user=None, **extra):
        user = user or self.owner
        return self.public.post("/api/v1/auth/login/", {
            "email": user.email, "password": "Auth-test-only-123", **extra,
        }, format="json")

    def authorized(self, user=None):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user or self.owner).access_token}")
        return client

    def test_registration_creates_only_consumer_and_dispatches_after_commit(self):
        self.send_mail.reset_mock()
        with patch("loan.scoring.get_or_create_dummy_credit_signal"):
            response = self.public.post("/api/v1/auth/register/", {
                "first_name": "Consumer", "last_name": "Test", "email": "new-auth@example.invalid",
                "phone_number": "+256700001111", "gender": "FEMALE", "password": "New-test-only-123",
                "confirm_password": "New-test-only-123", "user_role": User.ADMIN,
                "is_staff": True, "is_superuser": True, "email_verified": True,
            }, format="json")
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email="new-auth@example.invalid")
        self.assertEqual(user.user_role, User.CLIENT)
        self.assertFalse(user.is_staff or user.is_superuser or user.profile.email_verified)
        self.assertTrue(user.check_password("New-test-only-123"))
        self.assertEqual(Profile.objects.filter(user=user).count(), 1)
        self.assertEqual(UserAccountDetails.objects.filter(user=user).count(), 1)
        self.send_mail.assert_called_once()
        self.assertEqual(self.send_mail.call_args.args[1], user.pk)
        self.assertNotIn("password", response.data)
        self.assertNotIn("password", CreateUserSerializer(user).data)

    def test_registration_rejects_invalid_choices_passwords_and_duplicate_domain(self):
        data = {"first_name": "Consumer", "last_name": "Test", "email": "bad-auth@example.invalid",
                "phone_number": "+256700001112", "gender": "invalid",
                "password": "New-test-only-123", "confirm_password": "New-test-only-123"}
        self.assertEqual(self.public.post("/api/v1/auth/register/", data).status_code, 400)
        data.update(gender="MALE", password=" New-test-only-123", confirm_password=" New-test-only-123")
        self.assertEqual(self.public.post("/api/v1/auth/register/", data).status_code, 400)
        data.update(email="auth-owner@EXAMPLE.INVALID", password="New-test-only-123", confirm_password="New-test-only-123")
        self.assertEqual(self.public.post("/api/v1/auth/register/", data).status_code, 400)
        self.assertEqual(User.objects.count(), 1)

    def test_registration_rollback_does_not_dispatch_verification(self):
        self.send_mail.reset_mock()
        with patch("accounts.signals.UserAccountDetails.objects.create", side_effect=RuntimeError("synthetic failure")):
            with self.assertRaises(RuntimeError):
                self.public.post("/api/v1/auth/register/", {
                    "first_name": "Consumer", "last_name": "Test", "email": "rollback@example.invalid",
                    "phone_number": "+256700001113", "gender": "MALE",
                    "password": "New-test-only-123", "confirm_password": "New-test-only-123",
                })
        self.assertFalse(User.objects.filter(email="rollback@example.invalid").exists())
        self.send_mail.assert_not_called()

    def test_concurrent_duplicate_registration_creates_one_account(self):
        barrier = Barrier(2)
        original = CreateUserSerializer.create
        self.send_mail.reset_mock()

        def create(serializer, data):
            barrier.wait(timeout=10)  # Both requests passed pre-insert validation.
            return original(serializer, data)

        def register(_):
            close_old_connections()
            try:
                return APIClient().post("/api/v1/auth/register/", {
                    "first_name": "Race", "last_name": "Test", "email": "registration-race@example.invalid",
                    "phone_number": "+256700001114", "gender": "FEMALE",
                    "password": "New-test-only-123", "confirm_password": "New-test-only-123",
                }).status_code
            finally:
                close_old_connections()

        with patch.object(CreateUserSerializer, "create", create), patch("loan.scoring.get_or_create_dummy_credit_signal"):
            with ThreadPoolExecutor(max_workers=2) as executor:
                self.assertEqual(sorted(executor.map(register, range(2))), [201, 400])
        self.assertEqual(User.objects.filter(email="registration-race@example.invalid").count(), 1)
        self.send_mail.assert_called_once()

    def test_login_mints_one_pair_and_remember_me_row_keeps_same_expiry(self):
        response = self.login(remember_me=True)
        self.assertEqual(response.status_code, 200)
        token = RefreshToken(response.data["refresh"])
        self.assertEqual(OutstandingToken.objects.filter(user=self.owner).count(), 1)
        row = OutstandingToken.objects.get(jti=token["jti"])
        self.assertEqual(row.expires_at, datetime_from_epoch(token["exp"]))
        self.assertEqual(token["exp"] - token["iat"], int(timedelta(days=settings.REMEMBER_ME_REFRESH_DAYS).total_seconds()))
        self.assertEqual(response.data["user"]["id"], self.owner.pk)
        self.assertEqual(self.authorized().get("/api/v1/auth/mobile-account/").status_code, 200)

    def test_unverified_inactive_and_invalid_login_issue_no_tokens(self):
        self.owner.profile.email_verified = False
        self.owner.profile.save(update_fields=["email_verified"])
        self.assertEqual(self.login().status_code, 400)
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        self.assertEqual(self.login().status_code, 401)
        self.assertEqual(self.public.post("/api/v1/auth/login/", {
            "email": self.owner.email, "password": "wrong",
        }).status_code, 401)
        self.assertFalse(OutstandingToken.objects.filter(user=self.owner).exists())

    def test_login_password_is_not_trimmed(self):
        self.assertEqual(self.login(password=" Auth-test-only-123 ").status_code, 401)
        self.assertFalse(OutstandingToken.objects.filter(user=self.owner).exists())

    def test_staff_challenge_does_not_mint_tokens_and_parses_false(self):
        self.owner.user_role = User.ADMIN
        self.owner.totp_enabled = True
        self.owner.save(update_fields=["user_role", "totp_enabled"])
        response = self.login(remember_me="false")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["requires_2fa"])
        self.assertNotIn("access", response.data)
        self.assertFalse(OutstandingToken.objects.filter(user=self.owner).exists())
        from django.core import signing
        payload = signing.loads(response.data["challenge_token"], salt="2fa_login_challenge")
        self.assertFalse(payload["remember_me"])

    def test_mobile_permission_rejects_staff_even_with_client_role(self):
        self.owner.is_staff = True
        self.owner.save(update_fields=["is_staff"])
        response = self.authorized().get("/api/v1/auth/mobile-account/")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "CONSUMER_ONLY")

    def test_account_state_restrictions_apply_to_direct_and_shared_jwt_routes(self):
        client = self.authorized()
        self.owner.must_change_password = True
        self.owner.save(update_fields=["must_change_password"])
        self.assertEqual(client.get("/api/v1/auth/mobile-account/").status_code, 200)
        for path in ("/api/v1/auth/mobile-profile/", "/api/v1/loans/mobile-overview/",
                     "/api/v1/meter/my-meter/", "/api/v1/meter/allocation-status/",
                     "/api/v1/transactions/history/", "/api/v1/transactions/mobile-receipts/"):
            response = client.get(path)
            self.assertEqual(response.status_code, 403, path)
            self.assertEqual(response.data["code"], "PASSWORD_CHANGE_REQUIRED")
        with patch("meter.api.delivery_views.reserve_delivery_response") as reserve:
            self.assertEqual(client.post("/api/v1/meter/deliver/", {"amount": "1.00"}).status_code, 403)
        reserve.assert_not_called()
        self.owner.must_change_password = False
        self.owner.profile.email_verified = False
        self.owner.profile.save(update_fields=["email_verified"])
        for path in ("/api/v1/auth/mobile-account/", "/api/v1/auth/mobile-profile/", "/api/v1/meter/my-meter/"):
            response = client.get(path)
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.data["code"], "UNVERIFIED")

    def test_password_change_rejects_all_old_access_and_refresh_tokens(self):
        login = self.login()
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        response = client.post("/api/v1/auth/mobile-password/", {
            "current_password": "Auth-test-only-123", "new_password": "Changed-test-only-123",
            "confirm_password": "Changed-test-only-123",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(client.get("/api/v1/auth/mobile-account/").status_code, 401)
        self.assertEqual(self.public.post("/api/v1/auth/refresh/token/", {"refresh": login.data["refresh"]}).status_code, 401)
        self.assertEqual(self.login(password="Changed-test-only-123").status_code, 200)

    def test_email_verification_then_login_and_reset_invalidate_old_sessions(self):
        self.owner.profile.email_verified = False
        self.owner.profile.save(update_fields=["email_verified"])
        uid = b64encode_user(str(self.owner.pk))
        verify_url = f"/api/v1/auth/verify-email/?uid={uid}&token={token_generator.make_token(self.owner)}"
        self.assertEqual(self.public.get(verify_url).status_code, 200)
        self.assertNotEqual(self.public.get(verify_url).status_code, 200)
        login = self.login()
        self.assertEqual(login.status_code, 200)
        self.owner.refresh_from_db()
        self.owner.must_change_password = True
        self.owner.save(update_fields=["must_change_password"])
        reset = reset_password_token_generator.make_token(self.owner)
        url = f"/api/v1/auth/reset-password/?uid={uid}&token={reset}"
        self.assertEqual(self.public.patch(url, {"password": "Reset-test-only-123", "confirm_password": "Reset-test-only-123"}).status_code, 200)
        self.owner.refresh_from_db()
        self.assertFalse(self.owner.must_change_password)
        self.assertEqual(self.public.post("/api/v1/auth/refresh/token/", {"refresh": login.data["refresh"]}).status_code, 401)
        self.assertNotEqual(self.public.patch(url, {"password": "Another-test-only-123", "confirm_password": "Another-test-only-123"}).status_code, 200)

    def test_refresh_rejects_unverified_inactive_deleted_and_legacy_sessions(self):
        token = RefreshToken.for_user(self.owner)
        self.owner.profile.email_verified = False
        self.owner.profile.save(update_fields=["email_verified"])
        self.assertEqual(self.public.post("/api/v1/auth/refresh/token/", {"refresh": str(token)}).status_code, 401)
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        self.assertEqual(self.public.post("/api/v1/auth/refresh/token/", {"refresh": str(token)}).status_code, 401)
        self.owner.is_active = True
        self.owner.profile.email_verified = True
        self.owner.profile.save(update_fields=["email_verified"])
        self.owner.save(update_fields=["is_active"])
        del token["hash_password"]
        self.assertEqual(self.public.post("/api/v1/auth/refresh/token/", {"refresh": str(token)}).status_code, 401)
        self.owner.delete()
        self.assertEqual(self.public.post("/api/v1/auth/refresh/token/", {"refresh": str(token)}).status_code, 401)

    def test_concurrent_refresh_rotates_once_and_replay_is_rejected(self):
        self.assertEqual(connection.vendor, "postgresql")
        token = str(RefreshToken.for_user(self.owner))
        barrier = Barrier(2)

        def confirm(_):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                response = APIClient().post("/api/v1/auth/refresh/token/", {"refresh": token})
                return response.status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = sorted(executor.map(confirm, range(2)))
        self.assertEqual(statuses, [200, 401])
        self.assertEqual(OutstandingToken.objects.filter(user=self.owner).count(), 2)
        self.assertEqual(self.public.post("/api/v1/auth/refresh/token/", {"refresh": token}).status_code, 401)
