"""Isolated prototype enrollment, ownership and EUR workflow regressions."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.management import call_command
from django.db import close_old_connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient

from accounts.models import User
from admin.models import AuditLog
from loan.sandbox_service import create_quote, apply_loan, owned_test_meter
from loan.tests_sandbox import SANDBOX
from meter.enrollment_review import review_enrollment
from meter.models import (Meter, MeterEnrollmentRequest, MeterEnrollmentReview,
    SandboxMeterEnrollment, EnergyAllocation, MeterDelivery, SimulatedMeter, DeletedMeterRecord)
from meter.sandbox_enrollment import enroll_sandbox_meter, MeterUnavailable, normalized_number, OWNERSHIP_NOTICE
from transactions.models import PaymentIntent
from transactions.sandbox_payments import create_payment
from transactions.payment_settlement import settle_from_provider_evidence
from wallet.models import Wallet, MeterBalance


class Fixtures:
    def setUp(self):
        self.owner = User.objects.create_user(email="self-meter-owner@example.invalid", password="test-only")
        self.other = User.objects.create_user(email="self-meter-other@example.invalid", password="test-only")
        self.staff = User.objects.create_user(email="self-meter-staff@example.invalid", password="test-only", user_role=User.OPERATOR, is_staff=True)
        for user in (self.owner, self.other, self.staff):
            user.profile.email_verified = True; user.profile.save(update_fields=["email_verified"])
        self.client = APIClient(); self.client.force_authenticate(self.owner)
        self.headers = {"HTTP_HOST": settings.ALLOWED_HOSTS[0], "HTTP_X_FORWARDED_PROTO": "https"}

    def post(self, number, path="sandbox-meter-enrollment/"):
        return self.client.post("/api/v1/meter/" + path, {"meter_no": number}, format="json", **self.headers)


@override_settings(**SANDBOX)
class SandboxEnrollmentTests(Fixtures, TestCase):
    def test_immediate_leading_zero_enrollment_has_honest_provenance_no_side_effects(self):
        wallet_count = Wallet.objects.count()
        with patch("mtn_momo.sandbox.MTNSandbox.initiate") as provider:
            response = self.post("  00001234  ")
            provider.assert_not_called()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["message"], OWNERSHIP_NOTICE)
        meter = Meter.objects.get(meter_no="00001234", user=self.owner)
        proof = meter.sandbox_enrollment
        self.assertEqual(proof.provenance, "SELF_DECLARED")
        self.assertEqual(proof.owner, self.owner)
        self.assertIsNotNone(proof.enrolled_at)
        self.assertIsNone(proof.prior_request_id)
        self.assertTrue(meter.sandbox_inventory)
        self.assertIsNone(meter.static_ip)
        self.assertIsNone(meter.iot_device_token)
        self.assertFalse(MeterEnrollmentRequest.objects.exists())
        self.assertFalse(MeterEnrollmentReview.objects.exists())
        self.assertFalse(AuditLog.objects.exists())
        self.assertEqual(Wallet.objects.count(), wallet_count)
        self.assertFalse(MeterBalance.objects.exists())
        self.assertFalse(EnergyAllocation.objects.exists())
        self.assertFalse(SimulatedMeter.objects.exists())

    def test_same_owner_retries_and_legacy_aliases_return_original_identity_timestamp(self):
        first = self.post("0003")
        stamp = first.data["meter"]["enrolled_at"]
        for alias in ("sandbox-meter-enrollment/", "mobile-meter-requests/", "register/"):
            response = self.post(" 0003 ", alias)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["meter"]["id"], first.data["meter"]["id"])
            self.assertEqual(response.data["meter"]["enrolled_at"], stamp)
        self.assertEqual(Meter.objects.count(), 1)
        self.assertEqual(SandboxMeterEnrollment.objects.count(), 1)

    def test_numbers_remain_text_without_utility_length_rule(self):
        for number in ("1", "0", "AMI-A/0009", "A" * 100):
            self.assertEqual(normalized_number(number), number)
        for value in (None, 1234, True, "", " " * 3, "A" * 101, "M\x00X", "M\x7fX"):
            with self.assertRaises(ValidationError): normalized_number(value)
        self.assertEqual(self.post(1234).status_code, 400)
        response = self.client.post("/api/v1/meter/sandbox-meter-enrollment/", ["0001"], format="json", **self.headers)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Meter.objects.exists())

    def test_foreign_number_unavailable_without_owner_disclosure_or_read_access(self):
        meter, _ = enroll_sandbox_meter(self.other, "FOREIGN-0001")
        before = meter.sandbox_enrollment.enrolled_at
        response = self.post("FOREIGN-0001")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "METER_UNAVAILABLE")
        self.assertNotIn(self.other.email, str(response.data))
        self.assertNotIn("meter", response.data)
        meter.refresh_from_db(); self.assertEqual(meter.user, self.other)
        self.assertEqual(meter.sandbox_enrollment.enrolled_at, before)
        with transaction.atomic():
            self.assertEqual(self.client.get(f"/api/v1/meter/mobile-meters/{meter.pk}/", **self.headers).status_code, 404)

    def test_core_owned_unowned_deleted_and_precreated_inventory_cannot_be_claimed(self):
        cases = [Meter(meter_no="CORE-FREE"), Meter(meter_no="CORE-OWN", user=self.owner),
            Meter(meter_no="TEST-FREE", sandbox_inventory=True),
            Meter(meter_no="DELETED", user=self.other, is_deleted=True),
            Meter(meter_no="  LEGACY-SPACES  ")]
        Meter.all_objects.bulk_create(cases)
        for meter in cases:
            before_owner = meter.user_id
            response = self.post(meter.meter_no.strip())
            self.assertEqual(response.status_code, 409)
            meter.refresh_from_db(); self.assertEqual(meter.user_id, before_owner)
        self.assertFalse(SandboxMeterEnrollment.objects.exists())

    def test_renamed_deleted_history_is_not_clean_inventory(self):
        DeletedMeterRecord.objects.create(original_meter_no="OLD-NUMBER", architecture="AMI",
            units_at_deletion=Decimal("1.00"), deleted_by_role="ADMIN")
        with self.assertRaises(MeterUnavailable): enroll_sandbox_meter(self.owner, "OLD-NUMBER")
        MeterBalance.objects.create(user=self.other, meter_number="OLD-BALANCE", balance=Decimal("3.00"))
        with self.assertRaises(MeterUnavailable): enroll_sandbox_meter(self.owner, "OLD-BALANCE")
        self.assertEqual(MeterBalance.objects.get(meter_number="OLD-BALANCE").balance, Decimal("3.00"))

    def test_pending_retry_records_transition_without_staff_approval(self):
        row = MeterEnrollmentRequest.objects.create(owner=self.owner, meter_no="PENDING-0001")
        response = self.post(row.meter_no)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(SandboxMeterEnrollment.objects.get().prior_request, row)
        self.assertFalse(MeterEnrollmentReview.objects.exists())
        data = self.client.get("/api/v1/meter/mobile-onboarding/", **self.headers).data
        self.assertEqual(data["requests"][0]["status"], "SELF_DECLARED")
        self.assertIn("transitioned_at", data["requests"][0])
        self.assertFalse(data["needs_meter"])
        with self.assertRaises(DjangoValidationError):
            review_enrollment(self.staff, {"request_id": str(row.request_id), "decision": "REJECTED", "consumer_reason": "Test"})
        self.assertFalse(MeterEnrollmentReview.objects.exists())

    def test_prior_rejection_is_not_silently_bypassed(self):
        row = MeterEnrollmentRequest.objects.create(owner=self.owner, meter_no="DECLINED-0001")
        decision = MeterEnrollmentReview.objects.create(request=row, decision="REJECTED", reviewed_by=self.staff,
            consumer_reason="Prior review declined this request.")
        response = self.post(row.meter_no)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "PRIOR_ENROLLMENT_REJECTED")
        self.assertFalse(Meter.objects.exists())
        self.assertFalse(SandboxMeterEnrollment.objects.exists())
        decision.refresh_from_db(); self.assertEqual(decision.decision, "REJECTED")

    def test_verified_consumer_only_and_no_request_flags_enable_profile(self):
        with override_settings(CONSUMER_SANDBOX_ENABLED=False):
            self.assertNotEqual(self.post("BLOCKED").status_code, 201)
            with self.assertRaises(PermissionDenied): enroll_sandbox_meter(self.owner, "BLOCKED")
        self.owner.profile.email_verified = False; self.owner.profile.save(update_fields=["email_verified"])
        self.assertEqual(self.post("UNVERIFIED").status_code, 403)
        self.owner.profile.email_verified = True; self.owner.profile.save(update_fields=["email_verified"])
        self.owner.is_suspended = True; self.owner.save(update_fields=["is_suspended"])
        self.assertEqual(self.post("SUSPENDED").status_code, 403)
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.post("STAFF").status_code, 403)
        self.assertFalse(SandboxMeterEnrollment.objects.exists())

    def test_assignment_change_inactive_and_foreign_provenance_do_not_authorize(self):
        meter, _ = enroll_sandbox_meter(self.owner, "BIND-001")
        Meter.all_objects.filter(pk=meter.pk).update(user=self.other)
        with self.assertRaises(PermissionDenied): owned_test_meter(self.other, meter.pk)
        with self.assertRaises(PermissionDenied): owned_test_meter(self.owner, meter.pk)
        Meter.all_objects.filter(pk=meter.pk).update(user=self.owner, status=Meter.STATUS_INACTIVE)
        with self.assertRaises(PermissionDenied): owned_test_meter(self.owner, meter.pk)
        with self.assertRaises(MeterUnavailable): enroll_sandbox_meter(self.owner, "BIND-001")

    def test_no_device_evidence_is_not_reported_as_physical_usage_or_credit(self):
        meter, _ = enroll_sandbox_meter(self.owner, "NO-HARDWARE")
        data = self.client.get(f"/api/v1/meter/mobile-meters/{meter.pk}/", **self.headers).data
        for field in ("last_meter_contact", "last_measurement_at", "reported_relay_state",
                      "meter_reported_remaining_wh", "simulator_remaining_wh"):
            self.assertIsNone(data[field])
        self.assertEqual(data["contact_status"], "UNAVAILABLE")
        self.assertEqual(data["meter"]["hardware_connection"], "PENDING")
        usage = self.client.get(f"/api/v1/meter/mobile-consumption/?meter_id={meter.pk}", **self.headers).data
        self.assertEqual(usage["daily_usage"], [])
        self.assertEqual(usage["simulator_telemetry"], [])

    def test_loan_purchase_and_repayment_work_without_inventory_or_staff_review(self):
        from loan.tests_sandbox import trusted_profile_fixture
        trusted_profile_fixture(self.owner)  # Historical EUR fixture, no starter bypass.
        meter, _ = enroll_sandbox_meter(self.owner, "000-SANDBOX-FLOW")
        quote = create_quote(self.owner, meter.pk, "2.00", "LOAN")
        loan, _ = apply_loan(self.owner, quote.pk, quote.terms_hash, uuid.uuid4())
        self.assertEqual(loan.status, "DISBURSED")
        self.assertEqual(EnergyAllocation.objects.filter(sandbox_loan=loan).count(), 1)
        purchase_quote = create_quote(self.owner, meter.pk, "1.00", "PURCHASE")
        purchase, _ = create_payment(self.owner, {"purpose": "PURCHASE", "quote_id": str(purchase_quote.pk),
            "terms_hash": purchase_quote.terms_hash, "accept_test_terms": True, "msisdn": "46733123499", "client_request_id": str(uuid.uuid4())})
        evidence = lambda intent: {"provider": "MTN_SANDBOX", "reference_id": str(intent.provider_reference),
            "external_id": intent.provider_external_id, "amount": str(intent.amount), "currency": "EUR",
            "transaction_id": "synthetic-self-enrollment-" + str(intent.pk), "payer": "46733123499", "status": "SUCCESS"}
        settle_from_provider_evidence(purchase.pk, evidence(purchase))
        settle_from_provider_evidence(purchase.pk, evidence(purchase))
        self.assertEqual(EnergyAllocation.objects.filter(purchase_intent=purchase).count(), 1)
        repayment, _ = create_payment(self.owner, {"purpose": "LOAN_REPAYMENT", "loan_id": str(loan.pk),
            "amount": str(loan.outstanding), "accept_test_terms": True, "msisdn": "46733123499", "client_request_id": str(uuid.uuid4())})
        settle_from_provider_evidence(repayment.pk, evidence(repayment))
        loan.refresh_from_db(); self.assertEqual(loan.status, "COMPLETED")
        self.assertEqual(loan.outstanding, Decimal("0.00"))
        self.assertEqual(EnergyAllocation.objects.count(), 2)
        self.assertFalse(MeterEnrollmentReview.objects.exists())
        self.assertFalse(MeterDelivery.objects.exists())
        self.assertFalse(SimulatedMeter.objects.exists())
        self.assertTrue(all(a.accounting_environment == "SANDBOX" for a in EnergyAllocation.objects.all()))
        self.assertEqual(PaymentIntent.objects.count(), 2)

    def test_capabilities_and_schema(self):
        data = self.client.get("/api/v1/features/", **self.headers).data
        self.assertTrue(data["consumer_capabilities"]["sandbox_self_enrollment"])
        self.assertTrue(data["sandbox"]["self_declared_meter_enrollment"])
        self.assertFalse(any(data["features"].values()))
        call_command("makemigrations", "meter", check=True, dry_run=True, verbosity=0)


@override_settings(**SANDBOX)
class ConcurrentSandboxEnrollmentTests(Fixtures, TransactionTestCase):
    def run_pair(self, owners):
        barrier = Barrier(2)
        def claim(owner_id):
            close_old_connections()
            try:
                owner = User.objects.get(pk=owner_id)
                barrier.wait(timeout=10)
                try:
                    meter, created = enroll_sandbox_meter(owner, "000-RACE")
                    return meter.pk, created
                except MeterUnavailable:
                    return "unavailable", False
            finally: close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(claim, owners))

    def test_same_owner_concurrency_one_identity_one_provenance(self):
        results = self.run_pair([self.owner.pk, self.owner.pk])
        self.assertEqual(results[0][0], results[1][0])
        self.assertEqual(sum(created for _, created in results), 1)
        self.assertEqual(Meter.objects.count(), 1)
        self.assertEqual(SandboxMeterEnrollment.objects.count(), 1)

    def test_distinct_owner_concurrency_global_unique_number(self):
        results = self.run_pair([self.owner.pk, self.other.pk])
        self.assertEqual(sum(value == "unavailable" for value, _ in results), 1)
        self.assertEqual(Meter.objects.filter(meter_no="000-RACE").count(), 1)
        self.assertEqual(SandboxMeterEnrollment.objects.count(), 1)
        meter = Meter.objects.get()
        self.assertEqual(meter.user_id, meter.sandbox_enrollment.owner_id)
