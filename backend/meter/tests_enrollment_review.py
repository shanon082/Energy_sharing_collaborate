"""Isolated ownership review regressions: no network, finances or devices."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import Mock
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import close_old_connections
from django.test import Client, TestCase, TransactionTestCase
from rest_framework.test import APIClient

from accounts.models import User
from admin.models import AuditLog
from meter.enrollment_review import review_enrollment
from meter.models import Meter, MeterEnrollmentRequest, MeterEnrollmentReview, MeterUsageDaily


class ReviewFixtures:
    def setup_review(self):
        self.owner = User.objects.create_user(email="review-owner@example.invalid", password="test-only")
        self.other = User.objects.create_user(email="review-other@example.invalid", password="test-only")
        self.staff = User.objects.create_user(email="review-staff@example.invalid", password="test-only",
                                             user_role=User.OPERATOR, is_staff=True)
        for user in (self.owner, self.other, self.staff):
            user.profile.email_verified = True
            user.profile.save(update_fields=["email_verified"])
        # Clean pre-provisioned inventory; deliberately no legacy post_save
        # balance mirroring. No device credentials or hardware operations.
        self.meter = Meter.all_objects.bulk_create([Meter(meter_no="REVIEW-INVENTORY")])[0]
        self.row = MeterEnrollmentRequest.objects.create(owner=self.owner, meter_no=self.meter.meter_no)

    def data(self, **overrides):
        return {"request_id": str(self.row.request_id), "decision": "APPROVED", "ownership_verified": True,
                "evidence_type": "UTILITY_ACCOUNT", "evidence_reference": "synthetic-verified-case-001",
                "consumer_reason": "Verified assignment.", **overrides}


class EnrollmentReviewTests(ReviewFixtures, TestCase):
    def setUp(self):
        self.setup_review()
        self.headers = {"HTTP_HOST": settings.ALLOWED_HOSTS[0], "HTTP_X_FORWARDED_PROTO": "https"}

    def test_evidence_required_no_assignment_or_audit_on_missing_proof(self):
        with self.assertRaises(ValidationError):
            review_enrollment(self.staff, self.data(evidence_reference="", ownership_verified=False))
        self.meter.refresh_from_db()
        self.assertIsNone(self.meter.user_id)
        self.assertFalse(MeterEnrollmentReview.objects.exists())
        self.assertFalse(AuditLog.objects.exists())

    def test_consumer_and_customer_service_cannot_review(self):
        for user in (self.owner, self.other):
            with self.assertRaises(PermissionDenied):
                review_enrollment(user, self.data())
        self.staff.user_role = User.CUSTOMER_SERVICE
        with self.assertRaises(PermissionDenied):
            review_enrollment(self.staff, self.data())

    def test_inactive_unverified_suspended_and_initial_password_staff_denied(self):
        for field in ("is_active", "is_suspended", "must_change_password"):
            original = getattr(self.staff, field)
            setattr(self.staff, field, field != "is_active")
            with self.assertRaises(PermissionDenied):
                review_enrollment(self.staff, self.data())
            setattr(self.staff, field, original)
        self.staff.profile.email_verified = False
        with self.assertRaises(PermissionDenied):
            review_enrollment(self.staff, self.data())

    def test_configured_staff_2fa_cannot_be_bypassed(self):
        self.staff.totp_enabled = True
        self.staff.totp_secret = "JBSWY3DPEHPK3PXP"  # synthetic, not a credential
        with self.assertRaises(PermissionDenied):
            review_enrollment(self.staff, self.data(otp=""))

    def test_configured_2fa_uses_existing_verifier_before_any_write(self):
        self.staff.totp_enabled = True
        self.staff.totp_secret = "JBSWY3DPEHPK3PXP"
        verifier = Mock()
        verifier.verify.return_value = False
        module = SimpleNamespace(TOTP=Mock(return_value=verifier))
        with patch.dict("sys.modules", {"pyotp": module}):
            with self.assertRaises(PermissionDenied):
                review_enrollment(self.staff, self.data(otp="000000"))
            self.assertFalse(MeterEnrollmentReview.objects.exists())
            verifier.verify.assert_called_once_with("000000", valid_window=1)
            verifier.verify.return_value = True
            review_enrollment(self.staff, self.data(otp="000000"))
        self.assertEqual(MeterEnrollmentReview.objects.count(), 1)

    def test_approval_audited_idempotent_and_private_evidence_not_in_consumer_response(self):
        result = review_enrollment(self.staff, self.data())
        self.assertEqual(review_enrollment(self.staff, self.data()).pk, result.pk)
        self.assertEqual(AuditLog.objects.count(), 1)
        self.meter.refresh_from_db()
        self.assertEqual(self.meter.user_id, self.owner.pk)
        self.assertEqual(self.meter.units, 0)
        self.assertFalse(self.owner.energy_allocations.exists())
        client = APIClient(); client.force_authenticate(self.owner)
        response = client.get("/api/v1/meter/mobile-onboarding/", **self.headers)
        self.assertEqual(response.data["requests"][0]["status"], "LINKED")
        self.assertNotIn("synthetic-verified-case", response.content.decode())
        client.force_authenticate(self.other)
        self.assertEqual(client.get(f"/api/v1/meter/mobile-meters/{self.meter.pk}/", **self.headers).status_code, 404)

    def test_rejection_no_access_final_and_reason_visible_only_to_owner(self):
        review_enrollment(self.staff, self.data(decision="REJECTED", consumer_reason="Please contact staff."))
        with self.assertRaises(ValidationError):
            review_enrollment(self.staff, self.data())
        client = APIClient(); client.force_authenticate(self.owner)
        state = client.get("/api/v1/meter/mobile-onboarding/", **self.headers).data
        self.assertEqual(state["requests"][0]["status"], "REJECTED")
        self.assertTrue(state["needs_meter"])
        self.assertEqual(client.get(f"/api/v1/meter/mobile-meters/{self.meter.pk}/", **self.headers).status_code, 404)
        client.force_authenticate(self.other)
        self.assertEqual(client.get("/api/v1/meter/mobile-onboarding/", **self.headers).data["requests"], [])

    def test_foreign_owned_unknown_inactive_meters_never_created_or_transferred(self):
        for changes in ({"user_id": self.other.pk}, {"status": Meter.STATUS_INACTIVE}, {"is_deleted": True}):
            Meter.all_objects.filter(pk=self.meter.pk).update(**changes)
            with self.assertRaises(ValidationError):
                review_enrollment(self.staff, self.data())
            Meter.all_objects.filter(pk=self.meter.pk).update(user=None, status=Meter.STATUS_ACTIVE, is_deleted=False)
        self.row.meter_no = "NOT-IN-INVENTORY"; self.row.save(update_fields=["meter_no"])
        with self.assertRaises(ValidationError):
            review_enrollment(self.staff, self.data())
        self.assertEqual(Meter.all_objects.count(), 1)

    def test_old_history_not_exposed_by_reassignment(self):
        MeterUsageDaily.objects.create(meter=self.meter, usage_date="2026-01-01", kwh_used="1")
        with self.assertRaises(ValidationError):
            review_enrollment(self.staff, self.data())
        self.meter.refresh_from_db(); self.assertIsNone(self.meter.user_id)

    def test_existing_owner_assignment_and_history_preserved(self):
        Meter.all_objects.filter(pk=self.meter.pk).update(user=self.owner)
        MeterUsageDaily.objects.create(meter=self.meter, usage_date="2026-01-01", kwh_used="1")
        review_enrollment(self.staff, self.data())
        self.assertEqual(MeterUsageDaily.objects.get().kwh_used, 1)

    def test_audit_failure_rolls_back_assignment_and_decision(self):
        with patch("meter.enrollment_review.AuditLog.objects.create", side_effect=RuntimeError("synthetic audit failure")):
            with self.assertRaises(RuntimeError):
                review_enrollment(self.staff, self.data())
        self.meter.refresh_from_db(); self.assertIsNone(self.meter.user_id)
        self.assertFalse(MeterEnrollmentReview.objects.exists())

    def test_profile_page_csrf_and_exact_write_exception(self):
        if not getattr(settings, "ALWAYSDATA_TESTING", False):
            self.skipTest("Run with --profile for real hosted middleware/URLs")
        client = Client(enforce_csrf_checks=True); client.force_login(self.staff)
        url = "/admin-panel/meter-link-requests/"
        page = client.get(url, **self.headers)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'name="csrfmiddlewaretoken"')
        self.assertIn("no-store", page["Cache-Control"])
        self.assertEqual(page["Referrer-Policy"], "strict-origin")
        self.assertEqual(client.post(url, self.data(), **self.headers).status_code, 403)
        csrf = client.cookies["csrftoken"].value
        self.assertEqual(client.post(url, self.data(), HTTP_X_CSRFTOKEN=csrf,
            HTTP_ORIGIN="https://" + settings.ALLOWED_HOSTS[0], **self.headers).status_code, 302)
        self.assertEqual(client.post("/api/v1/admin/meters/", {}, **self.headers).status_code, 503)
        self.assertEqual(client.post("/api/v1/loans/mobile-apply/", {}, **self.headers).status_code, 503)
        client.force_login(self.owner)
        self.assertEqual(client.get(url, **self.headers).status_code, 403)

    def test_additive_model_migrations_complete(self):
        call_command("makemigrations", "meter", "loan", check=True, dry_run=True, verbosity=0)

    def test_profile_onboarding_score_monitoring_allowed_financial_actions_blocked(self):
        if not getattr(settings, "ALWAYSDATA_TESTING", False):
            self.skipTest("Run with --profile for real hosted restrictions")
        client = APIClient(); client.force_authenticate(self.owner)
        response = client.post("/api/v1/meter/mobile-meter-requests/", {"meter_no": self.meter.meter_no}, **self.headers)
        if getattr(settings, "CONSUMER_SANDBOX_ENABLED", False):
            # New prototype enrollment never attaches to pre-created inventory.
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.data["code"], "METER_UNAVAILABLE")
        else:
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.data["status"], "PENDING")
        self.assertEqual(client.get(f"/api/v1/meter/mobile-meters/{self.meter.pk}/", **self.headers).status_code, 404)
        review_enrollment(self.staff, self.data())
        for url in ("meter/mobile-onboarding/", "loans/mobile-eligibility/",
                    f"meter/mobile-meters/{self.meter.pk}/",
                    f"meter/mobile-consumption/?meter_id={self.meter.pk}",
                    f"meter/mobile-deliveries/?meter_id={self.meter.pk}"):
            self.assertEqual(client.get("/api/v1/" + url, **self.headers).status_code, 200, url)
        score = client.get("/api/v1/loans/mobile-eligibility/", **self.headers).data
        self.assertIsNone(score["score"])
        features = client.get("/api/v1/features/", **self.headers).data
        self.assertEqual(len(features["features"]), 7)
        self.assertFalse(any(features["features"].values()))
        self.assertFalse(features["consumer_capabilities"]["purchase_history_scoring"])
        self.assertFalse(features["consumer_capabilities"]["physical_meter"])
        self.assertFalse(features["consumer_capabilities"]["simulator_delivery_environment"])
        self.assertNotEqual(client.post("/api/v1/loans/mobile-quote/", {}, **self.headers).status_code, 503)
        for url in ("loans/mobile-apply/", "meter/deliver/", "meter/mobile-buy-units/"):
            self.assertEqual(client.post("/api/v1/" + url, {}, **self.headers).status_code, 503)


class ConcurrentEnrollmentReviewTests(ReviewFixtures, TransactionTestCase):
    def setUp(self):
        self.setup_review()

    def run_pair(self, data):
        barrier = Barrier(2)
        def run(values):
            close_old_connections()
            try:
                staff = User.objects.get(pk=self.staff.pk)
                barrier.wait(timeout=10)
                try:
                    return review_enrollment(staff, values).pk
                except ValidationError:
                    return "blocked"
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as workers:
            return list(workers.map(run, data))

    def test_duplicate_concurrent_review_one_assignment_and_audit(self):
        results = self.run_pair([self.data(), self.data()])
        self.assertEqual(results[0], results[1])
        self.assertEqual(MeterEnrollmentReview.objects.count(), 1)
        self.assertEqual(AuditLog.objects.count(), 1)

    def test_distinct_consumer_claims_one_owner_no_transfer(self):
        other_row = MeterEnrollmentRequest.objects.create(owner=self.other, meter_no=self.meter.meter_no)
        results = self.run_pair([self.data(), self.data(request_id=str(other_row.request_id))])
        self.assertEqual(results.count("blocked"), 1)
        self.assertEqual(MeterEnrollmentReview.objects.count(), 1)
        self.assertEqual(AuditLog.objects.count(), 1)
