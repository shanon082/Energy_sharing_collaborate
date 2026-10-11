"""Hosting configuration and PostgreSQL account-mail tests; external I/O mocked."""

from concurrent.futures import ThreadPoolExecutor
from io import StringIO
import os
from pathlib import Path
import tempfile
from threading import Barrier
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections, connection, connections, transaction
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient

from backend.hosting_environment import load_private_environment, positive_integer
from backend.render_config import validate_testing_environment


class PrivateEnvironmentTests(SimpleTestCase):
    def test_permissions_literal_secrets_and_environment_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "backend.env"
            path.write_text("SECRET_KEY='literal${NOT_EXPANDED}'\nDB_NAME=file_database\n")
            path.chmod(0o600)
            environ = {"ALWAYSDATA_ENV_FILE": str(path), "DB_NAME": "explicit_database"}
            load_private_environment(environ)
            self.assertEqual(environ["SECRET_KEY"], "literal${NOT_EXPANDED}")
            self.assertEqual(environ["DB_NAME"], "explicit_database")
            path.chmod(0o644)
            with self.assertRaises(ImproperlyConfigured):
                load_private_environment(environ)
            path.chmod(0o600)
            Path(directory).chmod(0o755)
            with self.assertRaises(ImproperlyConfigured):
                load_private_environment(environ)

    def test_missing_relative_symlink_and_project_files_rejected(self):
        for value in ("", "relative.env", str(Path(settings.BASE_DIR) / "alwaysdata.env.example")):
            with self.assertRaises(ImproperlyConfigured):
                load_private_environment({"ALWAYSDATA_ENV_FILE": value})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "backend.env"
            path.write_text("SECRET_KEY=synthetic\n")
            path.chmod(0o600)
            link = Path(directory) / "link.env"
            link.symlink_to(path)
            with self.assertRaises(ImproperlyConfigured):
                load_private_environment({"ALWAYSDATA_ENV_FILE": str(link)})

    def test_flags_and_integer_errors_do_not_echo_values(self):
        for value in ("true", "perhaps"):
            with self.assertRaises(ImproperlyConfigured):
                validate_testing_environment({"FEATURE_USSD_ENABLED": value}, profile="alwaysdata")
        for value in ("secret-test-value", "0", "65536"):
            with self.assertRaises(ImproperlyConfigured) as caught:
                positive_integer({"DB_PORT": value}, "DB_PORT", 5432, maximum=65535)
            self.assertNotIn(value, str(caught.exception))


@override_settings(ACCOUNT_EMAIL_OUTBOX_ENABLED=True, BACKGROUND_TASKS_AVAILABLE=False,
                   EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AccountMailOutboxTests(TransactionTestCase):
    def setUp(self):
        from accounts.models import AccountEmailDelivery, User
        self.Job = AccountEmailDelivery
        self.User = User
        self.user = User.objects.create_user(email="hosting-test@example.invalid", password="Hosting-test-only-123")
        self.client = APIClient()

    def test_account_and_queue_roll_back_together(self):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                self.User.objects.create_user(email="rollback-host@example.invalid", password="Hosting-test-only-123")
                raise RuntimeError("synthetic rollback")
        self.assertEqual(self.Job.objects.count(), 1)
        self.assertFalse(self.User.objects.filter(email="rollback-host@example.invalid").exists())

    def test_registration_and_resend_truthfully_queue_without_smtp(self):
        with patch("utils.email.EmailMessage.send") as smtp, patch("loan.scoring.get_or_create_dummy_credit_signal"):
            response = self.client.post("/api/v1/auth/register/", {
                "first_name": "Test", "last_name": "Consumer", "email": "new-host@example.invalid",
                "phone_number": "+256700009555", "gender": "MALE", "password": "Hosting-test-only-123",
                "confirm_password": "Hosting-test-only-123",
            }, format="json")
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.data["verification_delivery"], "queued")
            resend = self.client.get("/api/v1/auth/resend-email-link/", {"email": self.user.email})
            self.assertEqual(resend.status_code, 202)
            self.assertIn("queued", resend.data["message"])
            smtp.assert_not_called()

    def test_reset_is_non_enumerating_and_never_claims_sent(self):
        with patch("utils.email.EmailMessage.send") as smtp:
            responses = [self.client.post("/api/v1/auth/forgot-password/", {"email": email})
                         for email in (self.user.email, "missing-host@example.invalid")]
            self.assertEqual([x.status_code for x in responses], [200, 200])
            self.assertEqual(responses[0].data, responses[1].data)
            self.assertIn("queued", responses[0].data["message"])
            smtp.assert_not_called()
        self.assertEqual(self.Job.objects.filter(kind=self.Job.PASSWORD_RESET).count(), 1)

    def test_dry_run_no_send_acceptance_and_no_replay(self):
        output = StringIO()
        with patch("utils.email.EmailMessage.send") as smtp:
            call_command("drain_account_emails", stdout=output)
            smtp.assert_not_called()
        self.assertIn("QUEUED: 1", output.getvalue())
        call_command("drain_account_emails", send=True, stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)
        job = self.Job.objects.get()
        self.assertEqual(job.status, self.Job.SENT)
        call_command("drain_account_emails", send=True, stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(connection.in_atomic_block)

    def test_smtp_failure_is_visible_redacted_and_not_retried(self):
        with patch("utils.email.EmailMessage.send", side_effect=TimeoutError("secret-test-token")):
            with self.assertLogs("utils.email", level="WARNING") as logs, self.assertRaises(CommandError):
                call_command("drain_account_emails", send=True, stdout=StringIO())
        self.assertNotIn("secret-test-token", "".join(logs.output))
        self.assertEqual(self.Job.objects.get().status, self.Job.OUTCOME_UNKNOWN)
        with patch("utils.email.EmailMessage.send") as smtp:
            call_command("drain_account_emails", send=True, stdout=StringIO())
            smtp.assert_not_called()

    def test_interrupted_send_is_retained_and_stale_security_work_is_skipped(self):
        from accounts.email_outbox import drain_account_emails
        job = self.Job.objects.get()
        job.status = self.Job.SENDING
        job.save(update_fields=["status"])
        with patch("utils.email.EmailMessage.send") as smtp:
            self.assertEqual(drain_account_emails(5), [])
            smtp.assert_not_called()
        job.status = self.Job.QUEUED
        job.save(update_fields=["status"])
        self.user.set_password("Changed-host-test-only-123")
        self.user.save(update_fields=["password"])
        self.assertEqual(drain_account_emails(5), [(job.pk, self.Job.SKIPPED)])

    def test_concurrent_drains_send_one_message_outside_database_locks(self):
        from accounts.email_outbox import drain_account_emails
        self.assertEqual(connection.vendor, "postgresql")
        barrier = Barrier(2)
        def drain(_):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return drain_account_emails(1)
            finally:
                connections.close_all()
        def accept(*args, **kwargs):
            self.assertFalse(connection.in_atomic_block)
            return True, "accepted"
        with patch("accounts.email_outbox.send_email", side_effect=accept) as smtp:
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(drain, range(2)))
            self.assertEqual(sum(len(x) for x in results), 1)
            smtp.assert_called_once()

    def test_celery_dispatch_and_direct_async_paths_explicitly_reject(self):
        from accounts.tasks import handle_send_email_verification
        from meter.tasks import snapshot_ami_meter_balances
        from utils.general import dispatch_task
        from utils.hosting_tasks import BackgroundTaskUnavailable
        from backend import celery_app
        with patch("meter.tasks.snapshot_all_ami_meters") as device:
            with self.assertRaises(BackgroundTaskUnavailable):
                dispatch_task(snapshot_ami_meter_balances)
            with self.assertRaises(BackgroundTaskUnavailable):
                snapshot_ami_meter_balances.delay()
            with self.assertRaises(BackgroundTaskUnavailable):
                handle_send_email_verification.delay(self.user.pk)
            with self.assertRaises(BackgroundTaskUnavailable):
                celery_app.send_task("transactions.tasks.reconcile_pending_payments")
            device.assert_not_called()

    def test_queued_verification_and_reset_links_keep_one_time_security(self):
        from accounts.email_outbox import drain_account_emails, enqueue_account_email
        drain_account_emails(5)
        query = parse_qs(urlsplit(mail.outbox[-1].body.split(": ", 1)[1]).query)
        verification = "/api/v1/auth/verify-email/"
        args = {key: values[0] for key, values in query.items()}
        self.assertEqual(self.client.get(verification, args).status_code, 200)
        self.assertNotEqual(self.client.get(verification, args).status_code, 200)
        enqueue_account_email(self.user, self.Job.PASSWORD_RESET)
        drain_account_emails(5)
        link = mail.outbox[-1].body.split(": ", 1)[1].split("\n", 1)[0]
        reset = "/api/v1/auth/reset-password/?" + urlsplit(link).query
        payload = {"password": "New-host-password-test-123", "confirm_password": "New-host-password-test-123"}
        self.assertEqual(self.client.patch(reset, payload).status_code, 200)
        self.assertNotEqual(self.client.patch(reset, payload).status_code, 200)

    def test_expired_and_already_verified_emails_are_not_sent(self):
        from datetime import timedelta
        from django.utils import timezone
        from accounts.email_outbox import drain_account_emails
        self.Job.objects.update(created_at=timezone.now() - timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT + 1))
        with patch("utils.email.EmailMessage.send") as smtp:
            drain_account_emails(5)
            smtp.assert_not_called()
        self.assertEqual(self.Job.objects.get().status, self.Job.SKIPPED)


class AlwaysdataProfileTests(SimpleTestCase):
    def setUp(self):
        if not getattr(settings, "ALWAYSDATA_TESTING", False):
            self.skipTest("Requires the opt-in alwaysdata profile")
        self.assertTrue(settings.SECURE_SSL_REDIRECT and settings.ACCOUNT_EMAIL_OUTBOX_ENABLED)
        self.headers = {"HTTP_HOST": settings.ALLOWED_HOSTS[0], "HTTP_X_FORWARDED_PROTO": "https"}

    def test_https_hosts_cors_and_cookie_security(self):
        self.assertEqual(self.client.get("/", **self.headers).status_code, 200)
        self.assertEqual(self.client.get("/", HTTP_HOST=settings.ALLOWED_HOSTS[0]).status_code, 301)
        self.assertEqual(self.client.get("/", HTTP_HOST="unapproved.invalid", HTTP_X_FORWARDED_PROTO="https").status_code, 400)
        self.assertTrue(settings.SESSION_COOKIE_SECURE and settings.CSRF_COOKIE_SECURE)
        self.assertTrue(settings.SIMPLE_JWT["AUTH_COOKIE_SECURE"])
        self.assertFalse(settings.DEBUG or settings.CELERY_TASK_ALWAYS_EAGER)
        self.assertEqual(settings.CELERY_BEAT_SCHEDULE, {})
        self.assertIsNone(settings.CELERY_BROKER_URL)
        self.assertTrue(all(not value for value in settings.FEATURE_FLAGS.values()))
        self.assertEqual(settings.DATABASES["default"]["OPTIONS"]["options"], "-c search_path=custom,public")
        self.assertLessEqual(settings.EMAIL_TIMEOUT, 30)
        self.assertEqual(settings.CSRF_TRUSTED_ORIGINS, [settings.PRODUCTION_ORIGIN])
        with patch.dict(connection.settings_dict, {"ATOMIC_REQUESTS": False}):
            for origin in ("http://localhost", "https://localhost"):
                response = self.client.post("/api/v1/auth/login/", data="{}", content_type="application/json", HTTP_ORIGIN=origin, **self.headers)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response["Access-Control-Allow-Origin"], origin)
                response = self.client.options("/api/v1/auth/login/", HTTP_ORIGIN=origin,
                    HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST", HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type", **self.headers)
                self.assertEqual(response["Access-Control-Allow-Headers"], "authorization, content-type")
        response = self.client.get("/", HTTP_ORIGIN="https://unapproved.invalid", **self.headers)
        self.assertNotIn("Access-Control-Allow-Origin", response)

    def test_financial_device_and_polling_routes_stop_before_views(self):
        for path in ("/api/v1/meter/buy-units/", "/api/v1/meter/deliver/", "/api/v1/loans/disburse/1/", "/webhooks/thingsboard/low-units"):
            response = self.client.post(path, data="{}", content_type="application/json", **self.headers)
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["code"], "TESTING_OPERATION_UNAVAILABLE")
        for path in ("/api/v1/meter/check-payment-status/", "/api/v1/meter/ami-status/", "/api/v1/transactions/statement/email/"):
            self.assertEqual(self.client.get(path, **self.headers).status_code, 503)

    def test_health_probes_are_honest_and_do_not_contact_brokers_or_providers(self):
        from admin.health_checks import check_redis, check_celery_dispatch, check_cvs_sts_api, check_mtn_momo
        with patch("requests.sessions.Session.request", side_effect=AssertionError("External HTTP prohibited")):
            for check in (check_redis, check_celery_dispatch, check_cvs_sts_api, check_mtn_momo):
                self.assertEqual(check()["status"], "AMBER")

    def test_database_check_rejects_wrong_target_before_connection(self):
        with patch("accounts.management.commands.check_alwaysdata_database.connection") as database:
            with self.assertRaises(CommandError):
                call_command("check_alwaysdata_database")
            database.cursor.assert_not_called()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AlwaysdataAuthenticationFlowTests(TransactionTestCase):
    def test_verified_login_account_refresh_and_logout_with_hosted_middleware(self):
        if not getattr(settings, "ALWAYSDATA_TESTING", False):
            self.skipTest("Requires the opt-in alwaysdata profile")
        self.assertTrue(settings.SECURE_SSL_REDIRECT and settings.ACCOUNT_EMAIL_OUTBOX_ENABLED)
        from accounts.models import User
        from accounts.email_outbox import drain_account_emails
        user = User.objects.create_user(email="hosted-flow@example.invalid", password="Hosted-flow-test-123")
        client = APIClient(HTTP_HOST=settings.ALLOWED_HOSTS[0], HTTP_X_FORWARDED_PROTO="https", HTTP_ORIGIN="http://localhost")
        login = {"email": user.email, "password": "Hosted-flow-test-123"}
        rejected = client.post("/api/v1/auth/login/", login)
        self.assertEqual(rejected.status_code, 400)
        self.assertNotIn("access", rejected.data)
        drain_account_emails(5)
        query = parse_qs(urlsplit(mail.outbox[-1].body.split(": ", 1)[1]).query)
        args = {key: value[0] for key, value in query.items()}
        self.assertEqual(client.get("/account/verify-email/", args).status_code, 200)
        self.assertEqual(client.post("/account/verify-email/", {**args, "confirm": "on"}).status_code, 200)
        response = client.post("/api/v1/auth/login/", login)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Access-Control-Allow-Origin"], "http://localhost")
        refreshed = client.post("/api/v1/auth/refresh/token/", {"refresh": response.data["refresh"]})
        self.assertEqual(refreshed.status_code, 200)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {refreshed.data["access"]}')
        self.assertEqual(client.get("/api/v1/auth/mobile-account/").status_code, 200)
        self.assertEqual(client.post("/api/v1/auth/mobile-logout/", {"refresh": refreshed.data["refresh"]}).status_code, 204)
        client.credentials()
        self.assertEqual(client.post("/api/v1/auth/refresh/token/", {"refresh": refreshed.data["refresh"]}).status_code, 401)
