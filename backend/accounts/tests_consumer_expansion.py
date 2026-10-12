"""Isolated synthetic consumer data; providers and devices are never contacted."""
from decimal import Decimal
from io import StringIO
from unittest.mock import patch
import uuid

from django.core.management import call_command
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User, Wallet
from accounts.api.serializers import CreateUserSerializer
from accounts.phones import normalize_ugandan_phone
from loan.models import LoanApplication, PurchaseScoreExclusion, CreditScoreHistory
from loan.scoring import LOAN_PROFILE_FIELDS
from loan.services import reconcile_user_loan_statuses, disburse_loan, LoanOperationError
from loan.purchase_scoring import purchase_history_contribution
from meter.models import Meter, MeterEnrollmentRequest, EnergyAllocation, SimulatedMeter
from transactions.models import PaymentIntent, Transaction


class ConsumerExpansionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="expansion-owner@example.invalid", password="test-only")
        self.other = User.objects.create_user(email="expansion-other@example.invalid", password="test-only")
        for user in (self.owner, self.other):
            user.profile.email_verified = True
            user.profile.save(update_fields=["email_verified"])
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.foreign = Meter.objects.create(user=self.other, meter_no="EXP-FOREIGN")

    def intent(self, *, amount="1000", status="SETTLED", provider="MTN_PRODUCTION", allocate=True):
        meter, _ = Meter.objects.get_or_create(user=self.owner, meter_no="EXP-OWN")
        wallet, _ = Wallet.objects.get_or_create(user=self.owner)
        purchase = Transaction.objects.create(wallet=wallet, amount=Decimal(amount), phone_number="+256771000111")
        reference = uuid.uuid4()
        intent = PaymentIntent.objects.create(owner=self.owner, purpose="PURCHASE", status=status,
            amount=Decimal(amount), meter=meter, purchase=purchase, provider=provider,
            provider_reference=reference, provider_external_id=str(reference), client_request_id=uuid.uuid4(),
            provider_transaction_id=uuid.uuid4().hex, settled_at=timezone.now() if status == "SETTLED" else None,
            purchase_billed_ugx=Decimal(amount))
        if allocate:
            EnergyAllocation.objects.create(owner=self.owner, meter=meter, purchase_intent=intent, amount_kwh=Decimal("1"))
        return intent

    def test_phone_forms_and_strict_invalid_input(self):
        for value in ("0771000111", "256771000111", "+256771000111", " 0771000111 \n"):
            self.assertEqual(normalize_ugandan_phone(value), "+256771000111")
        for value in ("771000111", "077100011", "07710001111", "25677100011", "+2560771000111",
                      "0771 000111", "0771-000111", "0771000111x", "٠771000111", None):
            with self.assertRaises(ValueError):
                normalize_ugandan_phone(value)

    def test_new_phone_alias_cannot_duplicate_historical_raw_local_value(self):
        User.objects.filter(pk=self.other.pk).update(phone_number="0771000111")
        serializer = CreateUserSerializer()
        with self.assertRaises(Exception) as caught:
            serializer.validate_phone_number("256771000111")
        self.assertIn("already in use", str(caught.exception))
        self.assertEqual(str(User.objects.get(pk=self.other.pk).phone_number), "0771000111")

    def test_phone_audit_is_read_only_and_does_not_print_values(self):
        User.objects.filter(pk=self.owner.pk).update(phone_number="0771000111")
        User.objects.filter(pk=self.other.pk).update(phone_number="+256771000111")
        output = StringIO()
        call_command("audit_phone_formats", stdout=output)
        self.assertIn("collision_groups=1", output.getvalue())
        self.assertNotIn("771000111", output.getvalue())
        self.assertEqual(str(User.objects.get(pk=self.owner.pk).phone_number), "0771000111")

    def test_new_account_onboarding_has_no_score_meter_or_phone_ownership_claim(self):
        state = self.client.get("/api/v1/meter/mobile-onboarding/").data
        self.assertTrue(state["needs_meter"])
        self.assertEqual(state["meters"], [])
        self.assertFalse(state["phone_ownership_verified"])
        score = self.client.get("/api/v1/loans/mobile-eligibility/").data
        self.assertIsNone(score["score"])
        self.assertIsNone(score["factors"])
        self.assertFalse(score["can_apply"])

    def test_claim_is_pending_retry_safe_and_does_not_enumerate_or_grant_access(self):
        url = "/api/v1/meter/mobile-meter-requests/"
        existing = self.client.post(url, {"meter_no": self.foreign.meter_no, "user_id": self.other.pk,
                                          "status": "ACTIVE", "iot_device_token": "ignored-synthetic"})
        unknown = self.client.post(url, {"meter_no": "EXP-UNKNOWN"})
        duplicate = self.client.post(url, {"meter_no": self.foreign.meter_no})
        self.assertEqual((existing.status_code, unknown.status_code, duplicate.status_code), (202, 202, 202))
        self.assertEqual(existing.data["message"], unknown.data["message"])
        self.assertEqual(existing.data["request_id"], duplicate.data["request_id"])
        self.assertEqual(MeterEnrollmentRequest.objects.filter(owner=self.owner).count(), 2)
        self.assertFalse(Meter.objects.filter(user=self.owner).exists())
        self.foreign.refresh_from_db()
        self.assertEqual(self.foreign.user_id, self.other.pk)
        self.assertEqual(self.client.get(f"/api/v1/meter/mobile-meters/{self.foreign.pk}/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/v1/meter/mobile-consumption/?meter_id={self.foreign.pk}").status_code, 404)
        self.assertEqual(self.client.get(f"/api/v1/meter/mobile-deliveries/?meter_id={self.foreign.pk}").status_code, 404)

    def test_legacy_registration_queues_and_staff_assignment_is_required(self):
        result = self.client.post("/api/v1/meter/register/", {"meter_no": "EXP-REQUEST"})
        self.assertEqual(result.status_code, 202)
        state = self.client.get("/api/v1/meter/mobile-onboarding/").data
        self.assertEqual(state["requests"][0]["status"], "PENDING")
        # Synthetic stand-in for the existing staff-only verified assignment.
        Meter.objects.create(user=self.owner, meter_no="EXP-REQUEST")
        state = self.client.get("/api/v1/meter/mobile-onboarding/").data
        self.assertFalse(state["needs_meter"])
        self.assertEqual(state["requests"][0]["status"], "LINKED")
        foreign_client = APIClient(); foreign_client.force_authenticate(self.other)
        self.assertEqual(foreign_client.get("/api/v1/meter/mobile-onboarding/").data["requests"], [])

    def test_onboarding_requires_verified_consumer(self):
        self.owner.profile.email_verified = False
        self.owner.profile.save(update_fields=["email_verified"])
        self.assertEqual(self.client.post("/api/v1/meter/register/", {"meter_no": "EXP-NO"}).status_code, 403)
        self.assertFalse(MeterEnrollmentRequest.objects.exists())

    def complete_profile(self):
        for name in LOAN_PROFILE_FIELDS:
            setattr(self.owner, name, User._meta.get_field(name).choices[0][0])
        self.owner.save(update_fields=list(LOAN_PROFILE_FIELDS))

    def test_eligibility_refresh_is_stable_and_does_not_reconcile_approved_loans(self):
        self.complete_profile()
        LoanApplication.objects.create(user=self.owner, amount_requested=Decimal("10000"),
                                       amount_approved=Decimal("10000"), status="APPROVED", purpose="Electricity")
        with patch("loan.services.reconcile_user_loan_statuses") as reconcile:
            first = self.client.get("/api/v1/loans/mobile-eligibility/").data
            second = self.client.get("/api/v1/loans/mobile-eligibility/").data
            reconcile.assert_not_called()
        self.assertIsNotNone(first["evidence_updated_at"])
        self.assertEqual(first["score"], second["score"])
        self.assertEqual(first["evidence_updated_at"], second["evidence_updated_at"])
        self.assertIsNotNone(first["factors"])
        self.assertFalse(first["can_apply"])
        self.assertFalse(CreditScoreHistory.objects.exists())
        self.assertFalse(EnergyAllocation.objects.exists())

    @override_settings(ALWAYSDATA_TESTING=True)
    def test_hosted_shared_reconciliation_and_disbursement_are_contained(self):
        with patch("loan.services.disburse_loan") as disburse:
            self.assertEqual(reconcile_user_loan_statuses(self.owner), 0)
            disburse.assert_not_called()
        with self.assertRaises(LoanOperationError):
            disburse_loan(self.owner)

    def test_blocked_loan_retries_do_not_create_applications_or_disburse(self):
        for _ in range(2):
            response = self.client.post("/api/v1/loans/mobile-apply/", {"client_request_id": str(uuid.uuid4())})
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.data["code"], "LOAN_POLICY_APPROVAL_REQUIRED")
        self.assertFalse(LoanApplication.objects.exists())
        self.assertFalse(EnergyAllocation.objects.exists())

    @override_settings(PURCHASE_HISTORY_SCORING_ENABLED=False)
    def test_purchase_contribution_disabled_and_qualifying_sources_count_once(self):
        intent = self.intent()
        self.intent(status="PENDING"); self.intent(status="FAILED"); self.intent(provider="SIMULATED")
        self.intent(allocate=False)
        first = purchase_history_contribution(self.owner)
        second = purchase_history_contribution(self.owner)
        self.assertEqual(first, second)
        self.assertEqual((first["points"], first["source_count"], first["qualifying_billed_ugx"]), (0, 1, "1000.00"))
        PurchaseScoreExclusion.objects.create(intent=intent, reason="REVERSED", reviewed_by=self.other)
        self.assertEqual(purchase_history_contribution(self.owner)["source_count"], 0)
        intent.refresh_from_db()
        self.assertEqual(intent.status, "SETTLED")  # exclusion cannot refund/alter the allocation
        self.assertEqual(EnergyAllocation.objects.get(purchase_intent=intent).amount_kwh, Decimal("1"))

    @override_settings(PURCHASE_HISTORY_SCORING_ENABLED=True, PURCHASE_HISTORY_POLICY_ID="TEST-ONLY",
                       PURCHASE_HISTORY_SCORE_CAP=3, PURCHASE_HISTORY_UGX_PER_POINT=Decimal("1000"))
    def test_proposed_purchase_score_aggregates_money_instead_of_payment_count(self):
        self.intent(amount="500"); self.intent(amount="500")
        self.assertEqual(purchase_history_contribution(self.owner)["points"], 1)
        self.intent(amount="10000")
        self.assertEqual(purchase_history_contribution(self.owner)["points"], 3)

    def test_recovery_finds_old_request_without_polling_or_settlement(self):
        intent = self.intent(status="PENDING", allocate=False)
        for _ in range(31):
            self.intent(status="FAILED", allocate=False)
        query = f"purpose=PURCHASE&meter_no=EXP-OWN&client_request_id={intent.client_request_id}"
        with patch("transactions.payment_settlement.reconcile_payment") as reconcile:
            response = self.client.get(f"/api/v1/transactions/mobile-payment-recovery/?{query}")
            reconcile.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["pending"])
        self.assertEqual(response.data["receipt"]["external_id"], str(intent.provider_reference))
        self.assertFalse(response.data["provider_polled"])
        self.assertFalse(EnergyAllocation.objects.exists())

    def test_recovery_cannot_read_another_account_or_wrong_purpose(self):
        intent = self.intent()
        client = APIClient(); client.force_authenticate(self.other)
        response = client.get(f"/api/v1/transactions/mobile-payment-recovery/?purpose=PURCHASE&meter_no=EXP-FOREIGN&client_request_id={intent.client_request_id}")
        self.assertIsNone(response.data["receipt"])
        self.assertEqual(client.get("/api/v1/transactions/mobile-payment-recovery/?purpose=PURCHASE&meter_no=EXP-OWN").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/transactions/mobile-payment-recovery/?purpose=OTHER").status_code, 400)

    def test_repayment_recovery_is_loan_bound_and_cannot_create_energy_or_reduce_debt(self):
        from loan.models import LoanRepayment
        loan = LoanApplication.objects.create(user=self.owner, amount_requested=Decimal("10000"),
            amount_approved=Decimal("10000"), status="DISBURSED", interest_rate=0, tenure_months=1, purpose="Electricity")
        repayment = LoanRepayment.objects.create(loan=loan, amount_paid=Decimal("1000"), units_paid=0,
            payment_reference=uuid.uuid4().hex, payment_status="PENDING")
        ref = uuid.uuid4()
        intent = PaymentIntent.objects.create(owner=self.owner, purpose="LOAN_REPAYMENT", repayment=repayment,
            amount=Decimal("1000"), provider_reference=ref, provider_external_id=str(ref), client_request_id=uuid.uuid4())
        before = loan.outstanding_balance
        url = f"/api/v1/transactions/mobile-payment-recovery/?purpose=LOAN_REPAYMENT&loan_id={loan.loan_id}&client_request_id={intent.client_request_id}"
        for _ in range(2):
            response = self.client.get(url)
            self.assertTrue(response.data["pending"])
            self.assertEqual(response.data["receipt"]["purpose"], "LOAN_REPAYMENT")
        foreign = APIClient(); foreign.force_authenticate(self.other)
        self.assertEqual(foreign.get(url).status_code, 404)
        loan.refresh_from_db()
        self.assertEqual(loan.outstanding_balance, before)
        self.assertFalse(EnergyAllocation.objects.exists())

    def test_receipt_distinguishes_paid_allocated_and_acknowledged_energy(self):
        intent = self.intent()
        row = self.client.get(f"/api/v1/transactions/mobile-receipts/{intent.provider_reference}/").data["receipt"]
        self.assertTrue(row["settlement_recorded"])
        self.assertEqual(row["allocated_energy_kwh"], "1.00")
        self.assertEqual(Decimal(row["delivery_confirmed_kwh"]), 0)

    def test_models_have_no_unrecorded_migrations(self):
        call_command("makemigrations", "meter", "loan", check=True, dry_run=True, verbosity=0)

    @override_settings(DEBUG=True, SIMULATED_METER_ENABLED=True, MOBILE_METER_STALE_SECONDS=120)
    def test_meter_state_uses_accepted_delta_ledger_and_reports_staleness(self):
        meter = Meter.objects.create(user=self.owner, meter_no="EXP-SIM")
        device = SimulatedMeter.objects.create(meter=meter, credential_hash="synthetic",
            applied_kwh=Decimal("1.00"), consumed_wh=7, last_counter_wh=900000,
            last_contact_at=timezone.now()-timezone.timedelta(minutes=3), reported_relay_state="OPEN")
        data = self.client.get(f"/api/v1/meter/mobile-meters/{meter.pk}/").data
        self.assertEqual(data["simulator_remaining_wh"], "993")
        self.assertEqual(data["contact_status"], "STALE")
        self.assertEqual(data["reported_relay_state"], "OPEN")
        self.assertIsNone(data["meter_reported_remaining_wh"])
        device.refresh_from_db()
        self.assertEqual(device.consumed_wh, 7)
        device.reset_count = 1
        device.save(update_fields=["reset_count"])
        data = self.client.get(f"/api/v1/meter/mobile-meters/{meter.pk}/").data
        self.assertTrue(data["consumption_reconciliation_required"])
        self.assertIsNone(data["simulator_remaining_wh"])


class ConcurrentEnrollmentTests(TransactionTestCase):
    def test_distinct_connections_record_one_pending_request(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections
        owner = User.objects.create_user(email="enrollment-race@example.invalid", password="test-only")
        owner.profile.email_verified = True
        owner.profile.save(update_fields=["email_verified"])
        barrier = Barrier(2)

        def submit():
            close_old_connections()
            try:
                user = User.objects.get(pk=owner.pk)
                client = APIClient(); client.force_authenticate(user)
                barrier.wait(timeout=10)
                response = client.post("/api/v1/meter/mobile-meter-requests/", {"meter_no": "RACE-PENDING"})
                return response.status_code, response.data["request_id"]
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: submit(), range(2)))
        self.assertEqual([status for status, _ in results], [202, 202])
        self.assertEqual(results[0][1], results[1][1])
        self.assertEqual(MeterEnrollmentRequest.objects.filter(owner=owner).count(), 1)
        self.assertFalse(Meter.objects.filter(user=owner).exists())
