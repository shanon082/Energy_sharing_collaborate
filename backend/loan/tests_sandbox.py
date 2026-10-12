"""SANDBOX mocks only: no external payment or physical-meter operation."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from threading import Barrier
from unittest.mock import Mock, patch
import uuid

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.db import close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound
from rest_framework.test import APIClient

from accounts.models import User
from backend.sandbox_config import sandbox_configuration, BASE_URL
from loan.models import SandboxLoan, SandboxQuote, LoanApplication, PurchaseScoreExclusion
from loan.sandbox_service import create_quote, apply_loan, assessment
from meter.models import Meter, MeterEnrollmentRequest, EnergyAllocation
from meter.enrollment_review import review_enrollment
from meter.allocation_service import authorize_sandbox_loan_allocation
from transactions.models import PaymentIntent, SandboxSettlement
from transactions.payment_settlement import settle_from_provider_evidence, PaymentSettlementError, require_real_ugx_provider
from transactions.sandbox_payments import create_payment, reconcile_sandbox_payment
from mtn_momo.sandbox import MTNSandbox
from utils.billing import get_monthly_units_consumed

POLICY, _ = sandbox_configuration({})
CONFIG = {"BASE_URL": BASE_URL, "ENVIRONMENT": "sandbox", "CURRENCY": "EUR",
          "SUBSCRIPTION_KEY": "synthetic-test-only", "API_USER_ID": "00000000-0000-4000-8000-000000000001", "API_KEY": "synthetic-test-only"}
SANDBOX = {"CONSUMER_SANDBOX_ENABLED": True, "SANDBOX_POLICY": POLICY, "MTN_SANDBOX_CONFIG": CONFIG}


class Fixtures:
    def create_fixture(self):
        self.owner = User.objects.create_user(email="sandbox-owner@example.invalid", password="test-only")
        self.other = User.objects.create_user(email="sandbox-other@example.invalid", password="test-only")
        self.staff = User.objects.create_user(email="sandbox-staff@example.invalid", password="test-only", user_role=User.OPERATOR, is_staff=True)
        for user in (self.owner, self.other, self.staff):
            user.profile.email_verified = True; user.profile.save(update_fields=["email_verified"])
        self.meter = Meter.all_objects.bulk_create([Meter(meter_no="SANDBOX-TEST-1", sandbox_inventory=True, architecture="AMI")])[0]
        self.request = MeterEnrollmentRequest.objects.create(owner=self.owner, meter_no=self.meter.meter_no)
        review_enrollment(self.staff, {"request_id": str(self.request.request_id), "decision": "APPROVED",
            "evidence_type": "SANDBOX_AUTHORIZATION", "evidence_reference": "synthetic-consent-case-001",
            "ownership_verified": True, "consumer_reason": "Authorized for synthetic inventory; no household meter."})
        self.headers = {"HTTP_HOST": settings.ALLOWED_HOSTS[0], "HTTP_X_FORWARDED_PROTO": "https"}
        self.client = APIClient(); self.client.force_authenticate(self.owner)

    def loan(self, amount="2.00"):
        quote = create_quote(self.owner, self.meter.pk, amount, "LOAN")
        return apply_loan(self.owner, str(quote.pk), quote.terms_hash, uuid.uuid4())[0]

    def purchase(self, amount="2.00"):
        quote = create_quote(self.owner, self.meter.pk, amount, "PURCHASE")
        return create_payment(self.owner, {"purpose": "PURCHASE", "quote_id": str(quote.pk), "terms_hash": quote.terms_hash,
            "client_request_id": str(uuid.uuid4()), "msisdn": "46733123454", "accept_test_terms": True})[0]

    def repayment(self, loan, amount="1.00"):
        return create_payment(self.owner, {"purpose": "LOAN_REPAYMENT", "loan_id": str(loan.pk), "amount": amount,
            "accept_test_terms": True, "client_request_id": str(uuid.uuid4()), "msisdn": "46733123454", "accept_test_terms": True})[0]

    def evidence(self, intent, status="SUCCESS", **changes):
        return {"provider": "MTN_SANDBOX", "reference_id": str(intent.provider_reference), "external_id": intent.provider_external_id,
            "amount": str(intent.amount), "currency": "EUR", "transaction_id": "synthetic-financial-" + str(intent.provider_reference),
            "payer": "46733123454", "status": status, **changes}


@override_settings(**SANDBOX)
class SandboxWorkflowTests(Fixtures, TestCase):
    def setUp(self):
        self.create_fixture()

    def test_explicit_purchase_terms_and_nonfinite_amounts_rejected(self):
        for amount in ("NaN", "Infinity", "-1", "0", "1.001"):
            with self.assertRaises(ValidationError): create_quote(self.owner, self.meter.pk, amount, "LOAN")
        quote = create_quote(self.owner, self.meter.pk, "2", "PURCHASE")
        with self.assertRaises(ValidationError):
            create_payment(self.owner, {"purpose": "PURCHASE", "quote_id": str(quote.pk), "terms_hash": quote.terms_hash,
                "client_request_id": str(uuid.uuid4()), "msisdn": "46733123454"})
        self.assertFalse(PaymentIntent.objects.exists())

    def test_pending_and_failed_purchase_create_no_energy(self):
        intent = self.purchase()
        settle_from_provider_evidence(intent.pk, self.evidence(intent, status="PENDING"))
        self.assertFalse(EnergyAllocation.objects.exists())
        settle_from_provider_evidence(intent.pk, self.evidence(intent, status="FAILED"))
        self.assertFalse(EnergyAllocation.objects.exists()); self.assertFalse(SandboxSettlement.objects.exists())

    def test_quote_context_mismatch_and_owner_change_preserve_funded_uncertainty(self):
        intent = self.purchase()
        PaymentIntent.objects.filter(pk=intent.pk).update(sandbox_context={**intent.sandbox_context, "terms": {}})
        with self.assertRaises(PaymentSettlementError): settle_from_provider_evidence(intent.pk, self.evidence(intent))
        PaymentIntent.objects.filter(pk=intent.pk).update(sandbox_context=intent.sandbox_context)
        Meter.all_objects.filter(pk=self.meter.pk).update(user=self.other)
        with self.assertRaises(PermissionDenied): settle_from_provider_evidence(intent.pk, self.evidence(intent))
        intent.refresh_from_db(); self.assertEqual(intent.status, "PENDING"); self.assertFalse(EnergyAllocation.objects.exists())

    def test_cross_purpose_replay_and_core_receipt_currency_isolation(self):
        from transactions.api.mobile_views import owned_receipts
        loan = self.loan(); paid = self.repayment(loan)
        settle_from_provider_evidence(paid.pk, self.evidence(paid))
        purchase = self.purchase()
        with self.assertRaises(PaymentSettlementError):
            settle_from_provider_evidence(purchase.pk, self.evidence(purchase, transaction_id=self.evidence(paid)["transaction_id"]))
        self.assertFalse(owned_receipts(self.owner).exists())
        self.assertEqual(EnergyAllocation.objects.count(), 1)

    def test_policy_rejects_legacy_production_credentials(self):
        with self.assertRaises(ImproperlyConfigured): sandbox_configuration({"MTN_API_KEY": "synthetic-production-not-used"})

    def test_hosted_staff_visibility_denies_consumer_and_has_no_override(self):
        if not getattr(settings, "ALWAYSDATA_TESTING", False): self.skipTest("Hosting-profile page")
        self.loan()
        self.client.force_login(self.staff)
        view = self.client.get("/admin-panel/sandbox-decisions/", **self.headers)
        self.assertEqual(view.status_code, 200); self.assertIn(b"read-only staff decisions", view.content)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get("/admin-panel/sandbox-decisions/", **self.headers).status_code, 403)
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get("/api/v1/sandbox/staff/decisions/", **self.headers).status_code, 403)

    def test_full_api_application_purchase_and_repayment_sequence(self):
        meters = self.client.get("/api/v1/meter/mobile-meters/", **self.headers)
        self.assertTrue(meters.data["data"]["meters"][0]["sandbox_inventory"])
        quote = self.client.post("/api/v1/sandbox/quotes/", {"meter_id": self.meter.pk, "amount": "2.00", "purpose": "LOAN"}, format="json", **self.headers)
        self.assertEqual(quote.status_code, 201)
        payload = {"quote_id": quote.data["id"], "terms_hash": quote.data["terms_hash"], "accept_test_terms": True,
                   "client_request_id": str(uuid.uuid4()), "credit_score": 100, "status": "APPROVED"}
        response = self.client.post("/api/v1/sandbox/loans/", payload, format="json", **self.headers)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["loan"]["status"], "DISBURSED")
        self.assertIsNone(response.data["loan"]["assessment"]["score"])
        self.assertEqual(self.client.post("/api/v1/sandbox/loans/", payload, format="json", **self.headers).status_code, 200)
        loan = SandboxLoan.objects.get()
        self.assertEqual(EnergyAllocation.objects.count(), 1)
        with patch.object(MTNSandbox, "initiate", return_value="ACCEPTED"):
            paid = self.client.post("/api/v1/sandbox/payments/", {"purpose": "LOAN_REPAYMENT", "loan_id": str(loan.pk),
                "amount": "2.10", "msisdn": "46733123454", "accept_test_terms": True, "client_request_id": str(uuid.uuid4())}, format="json", **self.headers)
        self.assertEqual(paid.status_code, 202)
        intent = PaymentIntent.objects.get()
        self.assertEqual(loan.outstanding, Decimal("2.10"))
        settle_from_provider_evidence(intent.pk, self.evidence(intent))
        loan.refresh_from_db(); self.assertEqual(loan.status, "COMPLETED")
        purchase = self.purchase()
        settle_from_provider_evidence(purchase.pk, self.evidence(purchase))
        self.assertEqual(EnergyAllocation.objects.count(), 2)
        self.assertEqual(SandboxSettlement.objects.count(), 2)
        self.assertFalse(LoanApplication.objects.exists())

    def test_low_profile_rejected_despite_client_score_or_approval(self):
        from loan.scoring import LOAN_PROFILE_FIELDS
        for key in LOAN_PROFILE_FIELDS:
            setattr(self.owner, key, "test-answer")
        self.owner.payment_consistency = "Never paid"; self.owner.monthly_income = "<100,000 UGX"
        self.owner.consumption_level = "Very low (<50 kWh)"; self.owner.purchase_frequency = "Rarely"
        self.owner.save()
        loan = self.loan()
        self.assertEqual(loan.status, "REJECTED")
        self.assertIn("threshold", loan.decision_reason)
        self.assertFalse(EnergyAllocation.objects.exists())

    def test_acceptance_hash_expiry_and_request_conflicts(self):
        quote = create_quote(self.owner, self.meter.pk, "2", "LOAN")
        with self.assertRaises(ValidationError):
            apply_loan(self.owner, quote.pk, "wrong", uuid.uuid4())
        quote.expires_at = timezone.now()-timedelta(seconds=1); quote.save()
        with self.assertRaises(ValidationError):
            apply_loan(self.owner, quote.pk, quote.terms_hash, uuid.uuid4())
        self.assertFalse(SandboxLoan.objects.exists())

    def test_unverified_or_unapproved_meter_cannot_borrow(self):
        self.owner.profile.email_verified = False; self.owner.profile.save()
        with self.assertRaises(PermissionDenied):
            self.loan()
        self.owner.profile.email_verified = True; self.owner.profile.save()
        self.client.force_authenticate(self.other)
        result = self.client.post("/api/v1/sandbox/quotes/", {"meter_id": self.meter.pk, "amount": "2", "purpose": "LOAN"}, format="json", **self.headers)
        self.assertEqual(result.status_code, 403)

    def test_second_or_overdue_loan_rejected_and_disbursement_retry_no_duplicate(self):
        first = self.loan()
        authorize_sandbox_loan_allocation(first, Decimal("2.00"))
        second = self.loan(); self.assertEqual(second.status, "REJECTED")
        first.due_at = timezone.now()-timedelta(days=1); first.save()
        third = self.loan(); self.assertIn("overdue", third.decision_reason)
        self.assertEqual(EnergyAllocation.objects.count(), 1)

    def test_pending_failed_and_untrusted_success_do_not_settle(self):
        loan = self.loan(); payment = self.repayment(loan)
        self.assertFalse(settle_from_provider_evidence(payment.pk, {"status": "PENDING"})[1])
        self.assertEqual(loan.outstanding, Decimal("2.10"))
        settle_from_provider_evidence(payment.pk, self.evidence(payment, status="FAILED"))
        self.assertEqual(loan.outstanding, Decimal("2.10"))
        self.assertEqual(EnergyAllocation.objects.count(), 1)

    def test_wrong_reference_currency_amount_payer_purpose_provider_rejected(self):
        intent = self.purchase()
        for changes in ({"reference_id": str(uuid.uuid4())}, {"currency": "UGX"}, {"amount": "9"},
                        {"external_id": "repayment-other-purpose"}, {"payer": "0000000000"},
                        {"provider": "MTN_PRODUCTION"}, {"provider": "SIMULATED"}, {"transaction_id": ""}):
            with self.assertRaises(PaymentSettlementError):
                settle_from_provider_evidence(intent.pk, self.evidence(intent, **changes))
        self.assertFalse(SandboxSettlement.objects.exists()); self.assertFalse(EnergyAllocation.objects.exists())

    def test_duplicate_and_cross_intent_provider_transaction_replay(self):
        first = self.purchase(); evidence = self.evidence(first)
        self.assertTrue(settle_from_provider_evidence(first.pk, evidence)[1])
        self.assertFalse(settle_from_provider_evidence(first.pk, evidence)[1])
        second = self.purchase()
        with self.assertRaises(PaymentSettlementError):
            settle_from_provider_evidence(second.pk, self.evidence(second, transaction_id=evidence["transaction_id"]))
        self.assertEqual(EnergyAllocation.objects.count(), 1)

    def test_partial_repayment_closed_debt_never_reaccrues(self):
        loan = self.loan()
        first = self.repayment(loan, "1.01"); settle_from_provider_evidence(first.pk, self.evidence(first))
        self.assertEqual(loan.outstanding, Decimal("1.09"))
        second = self.repayment(loan, "1.09"); settle_from_provider_evidence(second.pk, self.evidence(second))
        loan.refresh_from_db(); self.assertIsNotNone(loan.closed_at)
        with patch("django.utils.timezone.now", return_value=timezone.now()+timedelta(days=1000)):
            self.assertEqual(loan.outstanding, 0)
        self.assertEqual(EnergyAllocation.objects.count(), 1)

    def test_self_repayment_remains_available_after_original_meter_is_reassigned(self):
        loan = self.loan()
        Meter.all_objects.filter(pk=self.meter.pk).update(user=self.other, status=Meter.STATUS_INACTIVE)
        intent = self.repayment(loan, "2.10")
        settle_from_provider_evidence(intent.pk, self.evidence(intent))
        loan.refresh_from_db(); self.assertEqual(loan.status, "COMPLETED")
        self.assertEqual(EnergyAllocation.objects.count(), 1)

    def test_remainder_full_receipt_and_tariff_score_isolation(self):
        from wallet.models import UnitBalance
        UnitBalance.objects.update_or_create(user=self.owner, defaults={"balance": Decimal("23.45")})
        changed = {**POLICY, "rate_per_kwh": "1.23", "id": "SANDBOX-REMAINDER-v1"}
        with override_settings(SANDBOX_POLICY=changed):
            intent = self.purchase("1.00")
        with override_settings(SANDBOX_POLICY={**POLICY, "rate_per_kwh": "99"}):
            settle_from_provider_evidence(intent.pk, self.evidence(intent))
        ledger = SandboxSettlement.objects.get(intent=intent)
        self.assertEqual(ledger.billed, Decimal("0.9963")); self.assertEqual(ledger.residual, Decimal("0.0037"))
        self.assertEqual(ledger.received, ledger.billed+ledger.residual)
        self.assertEqual(get_monthly_units_consumed(self.owner), 0)
        self.assertEqual(UnitBalance.objects.get(user=self.owner).balance, Decimal("23.45"))

    def test_purchase_bonus_aggregates_once_is_capped_refresh_cannot_earn(self):
        for amount in ("10", "10"):
            intent = self.purchase(amount); settle_from_provider_evidence(intent.pk, self.evidence(intent))
        self.assertEqual(assessment(self.owner)["purchase_points"], 2)
        self.assertEqual(assessment(self.owner)["purchase_points"], 2)
        PurchaseScoreExclusion.objects.create(intent=intent, reason="UNCERTAIN", reviewed_by=self.staff)
        self.assertEqual(assessment(self.owner)["purchase_points"], 1)
        with override_settings(SANDBOX_POLICY={**POLICY, "purchase_score_cap": 1}):
            self.assertEqual(assessment(self.owner)["purchase_points"], 1)

    def test_cross_account_payment_read_reconcile_and_loan_repayment_rejected(self):
        loan = self.loan(); intent = self.purchase()
        self.client.force_authenticate(self.other)
        # DRF marks ATOMIC_REQUESTS connections for rollback on API errors even
        # inside TestCase's outer transaction. Contain this expected 404 in its
        # own savepoint before separately checking the service authorization.
        with transaction.atomic():
            self.assertEqual(self.client.post(f"/api/v1/sandbox/payments/{intent.provider_reference}/", {}, **self.headers).status_code, 404)
        with self.assertRaises(NotFound):
            create_payment(self.other, {"purpose": "LOAN_REPAYMENT", "loan_id": str(loan.pk), "amount": "1", "msisdn": "46733123454",
                "accept_test_terms": True, "client_request_id": str(uuid.uuid4())})
        self.assertFalse(PaymentIntent.objects.filter(owner=self.other).exists())

    def test_durable_restart_submission_and_scheduler_dry_run_no_call(self):
        intent = self.purchase()
        output = StringIO()
        with patch.object(MTNSandbox, "initiate") as initiate:
            call_command("reconcile_sandbox_payments", stdout=output)
            initiate.assert_not_called()
        with patch.object(MTNSandbox, "initiate", return_value="ACCEPTED") as initiate:
            reconcile_sandbox_payment(intent.pk)
            reconcile_sandbox_payment(intent.pk)
            self.assertEqual(initiate.call_count, 1)
        PaymentIntent.objects.filter(pk=intent.pk).update(reconcile_after=timezone.now()-timedelta(seconds=1))
        with patch.object(MTNSandbox, "status", return_value=self.evidence(intent)):
            call_command("reconcile_sandbox_payments", run=True, stdout=output)
        intent.refresh_from_db(); self.assertEqual(intent.status, "SETTLED")
        self.assertEqual(EnergyAllocation.objects.count(), 1)

    def test_lost_initiation_ack_is_not_automatically_replayed(self):
        intent = self.purchase()
        with patch.object(MTNSandbox, "initiate", return_value="OUTCOME_UNKNOWN") as initiate:
            reconcile_sandbox_payment(intent.pk)
            PaymentIntent.objects.filter(pk=intent.pk).update(reconcile_after=timezone.now()-timedelta(seconds=1))
            with patch.object(MTNSandbox, "status", return_value=self.evidence(intent)):
                reconcile_sandbox_payment(intent.pk)
            self.assertEqual(initiate.call_count, 1)
        self.assertEqual(EnergyAllocation.objects.count(), 1)

    def test_expired_worker_lease_recovers_status_not_collection(self):
        intent = self.purchase()
        PaymentIntent.objects.filter(pk=intent.pk).update(submission_state="SUBMITTING", reconcile_lease_until=timezone.now()-timedelta(seconds=1))
        with patch.object(MTNSandbox, "initiate") as initiate, patch.object(MTNSandbox, "status", return_value=self.evidence(intent)):
            reconcile_sandbox_payment(intent.pk); initiate.assert_not_called()
        self.assertEqual(EnergyAllocation.objects.count(), 1)

    def test_isolation_missing_credentials_production_endpoint_and_no_fallback(self):
        with self.assertRaises(PaymentSettlementError): require_real_ugx_provider()
        with override_settings(MTN_SANDBOX_CONFIG={}):
            with self.assertRaises(PaymentSettlementError): self.purchase()
        with override_settings(MTN_SANDBOX_CONFIG={**CONFIG, "BASE_URL": "https://proxy.momoapi.mtn.com"}):
            with self.assertRaises(PaymentSettlementError): self.purchase()
        with self.assertRaises(ImproperlyConfigured): sandbox_configuration({"MTN_ENVIRONMENT": "production"})
        with self.assertRaises(ImproperlyConfigured): sandbox_configuration({"MTN_SANDBOX_CURRENCY": "UGX"})
        self.assertFalse(PaymentIntent.objects.exists())

    def test_real_profile_gates_still_apply_except_exact_sandbox_writes(self):
        if not getattr(settings, "ALWAYSDATA_TESTING", False): self.skipTest("--sandbox-profile required")
        features = self.client.get("/api/v1/features/", **self.headers).data
        self.assertFalse(any(features["features"].values()))
        self.assertTrue(features["sandbox"]["loans"])
        self.assertTrue(features["sandbox"]["purchases"])
        self.assertFalse(features["sandbox"]["physical_delivery"])
        for url in ("/api/v1/loans/mobile-apply/", "/api/v1/meter/mobile-buy-units/", "/api/v1/meter/deliver/", "/api/v1/admin/meters/"):
            self.assertEqual(self.client.post(url, {}, **self.headers).status_code, 503)

    def test_schema_complete(self):
        call_command("makemigrations", "loan", "meter", "transactions", check=True, dry_run=True, verbosity=0)


@override_settings(**SANDBOX)
class SandboxAdapterTests(TestCase):
    def test_actual_http_adapter_contract_has_no_fixed_one_eur_conversion(self):
        intent = Mock(amount=Decimal("2.34"), provider_reference=uuid.uuid4(), provider_external_id="sandbox-purchase-test",
                      purpose="PURCHASE", sandbox_context={"msisdn": "46733123454"})
        token = Mock(status_code=200); token.json.return_value = {"access_token": "synthetic-token"}
        accepted = Mock(status_code=202)
        with patch("mtn_momo.sandbox.requests.post", side_effect=[token, accepted]) as post:
            self.assertEqual(MTNSandbox().initiate(intent), "ACCEPTED")
            call = post.call_args
            self.assertEqual(call.args[0], BASE_URL + "/collection/v1_0/requesttopay")
            self.assertEqual(call.kwargs["json"]["amount"], "2.34")
            self.assertEqual(call.kwargs["json"]["currency"], "EUR")
            self.assertFalse(call.kwargs["allow_redirects"])
            self.assertEqual(call.kwargs["timeout"], (3, 7))


@override_settings(**SANDBOX)
class SandboxConcurrencyTests(Fixtures, TransactionTestCase):
    def setUp(self): self.create_fixture()

    def test_provider_io_is_outside_http_database_transaction(self):
        quote = create_quote(self.owner, self.meter.pk, "2", "PURCHASE")
        def initiate(intent):
            self.assertFalse(connection.in_atomic_block)
            return "ACCEPTED"
        with patch.object(MTNSandbox, "initiate", side_effect=initiate):
            response = self.client.post("/api/v1/sandbox/payments/", {"purpose": "PURCHASE", "quote_id": str(quote.pk),
                "terms_hash": quote.terms_hash, "accept_test_terms": True, "msisdn": "46733123454", "client_request_id": str(uuid.uuid4())}, format="json", **self.headers)
        self.assertEqual(response.status_code, 202)

    def test_overlapping_workers_claim_one_collection_without_holding_locks(self):
        from threading import Event
        intent = self.purchase(); entered, release = Event(), Event()
        def initiate(row):
            self.assertFalse(connection.in_atomic_block); entered.set(); self.assertTrue(release.wait(10)); return "ACCEPTED"
        def run():
            close_old_connections()
            try: return reconcile_sandbox_payment(intent.pk)
            finally: close_old_connections()
        with patch.object(MTNSandbox, "initiate", side_effect=initiate) as provider, ThreadPoolExecutor(max_workers=1) as executor:
            worker = executor.submit(run)
            try:
                self.assertTrue(entered.wait(10)); self.assertFalse(run()[1])
            finally: release.set()
            worker.result(timeout=10); self.assertEqual(provider.call_count, 1)
        intent.refresh_from_db(); self.assertEqual(intent.reconcile_attempts, 1)

    def pair(self, functions):
        barrier = Barrier(2)
        def run(fn):
            close_old_connections()
            try:
                barrier.wait(timeout=10); return fn()
            finally: close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor:
            return list(executor.map(run, functions))

    def test_concurrent_same_request_application_single_allocation(self):
        quote = create_quote(self.owner, self.meter.pk, "2", "LOAN"); key = uuid.uuid4()
        def apply(): return apply_loan(User.objects.get(pk=self.owner.pk), quote.pk, quote.terms_hash, key)[0].pk
        result = self.pair([apply, apply])
        self.assertEqual(result[0], result[1]); self.assertEqual(EnergyAllocation.objects.count(), 1)

    def test_distinct_concurrent_applications_only_one_active_loan(self):
        quotes = [create_quote(self.owner, self.meter.pk, "2", "LOAN") for _ in range(2)]
        def apply(quote): return lambda: apply_loan(User.objects.get(pk=self.owner.pk), quote.pk, quote.terms_hash, uuid.uuid4())[0].status
        result = self.pair([apply(quote) for quote in quotes])
        self.assertEqual(sorted(result), ["DISBURSED", "REJECTED"]); self.assertEqual(EnergyAllocation.objects.count(), 1)

    def test_duplicate_settlement_and_distinct_repayments_preserve_excess(self):
        loan = self.loan(); first = self.repayment(loan, "2.10")
        evidence = self.evidence(first)
        result = self.pair([lambda: settle_from_provider_evidence(first.pk, evidence)[1] for _ in range(2)])
        self.assertEqual(sorted(result), [False, True]); self.assertEqual(SandboxSettlement.objects.count(), 1)
        # A second previously authorized funded obligation can arrive late.
        quote = SandboxQuote.objects.create(owner=self.owner, meter=self.meter, purpose="LOAN_REPAYMENT", amount="2.10", terms=first.sandbox_quote.terms,
            terms_hash="synthetic", expires_at=timezone.now()+timedelta(minutes=15))
        second = PaymentIntent.objects.create(owner=self.owner, purpose="LOAN_REPAYMENT", amount="2.10", currency="EUR", provider="MTN_SANDBOX",
            sandbox_loan=loan, sandbox_quote=quote, sandbox_context=first.sandbox_context, provider_reference=uuid.uuid4(),
            provider_external_id="sandbox-late-repayment", client_request_id=uuid.uuid4())
        # Reset only the isolated test fixture to exercise two distinct arrivals.
        SandboxSettlement.objects.all().delete(); PaymentIntent.objects.filter(pk=first.pk).update(status="PENDING", provider_transaction_id="")
        SandboxLoan.objects.filter(pk=loan.pk).update(status="DISBURSED", closed_at=None)
        self.pair([lambda: settle_from_provider_evidence(first.pk, self.evidence(first)), lambda: settle_from_provider_evidence(second.pk, self.evidence(second))])
        rows = list(SandboxSettlement.objects.all())
        self.assertEqual(sum(row.received for row in rows), Decimal("4.20"))
        self.assertEqual(sum(row.applied for row in rows), Decimal("2.10"))
        self.assertEqual(sum(row.excess for row in rows), Decimal("2.10"))
        self.assertEqual(loan.outstanding, 0); self.assertEqual(EnergyAllocation.objects.count(), 1)
