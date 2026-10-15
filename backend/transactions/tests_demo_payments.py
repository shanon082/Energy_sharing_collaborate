"""Whole-UGX local demo integration; isolated PostgreSQL and no external I/O."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from threading import Barrier
from unittest.mock import patch
import uuid

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.db import close_old_connections, transaction, IntegrityError
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound
from rest_framework.test import APIClient

from accounts.models import User
from backend.demo_config import demo_configuration
from loan.models import SandboxLoan, SandboxQuote, ElectricityTariff, TariffBlock
from loan.sandbox_service import create_quote, apply_loan, assessment
from meter.models import EnergyAllocation, MeterDelivery
from meter.sandbox_enrollment import enroll_sandbox_meter
from transactions.models import PaymentIntent, SandboxSettlement
from transactions.sandbox_payments import create_payment, receipt, reconcile_sandbox_payment
from transactions.demo_payments import complete_demo_payment, DemoNotReady
from transactions.payment_settlement import settle_from_provider_evidence, PaymentSettlementError
from loan.tests_sandbox import SANDBOX
from mtn_momo.sandbox import MTNSandbox
from wallet.models import UnitBalance

DEMO = {**SANDBOX, "PROTOTYPE_PAYMENT_PROVIDER": "LOCAL_DEMO", "DEMO_POLICY": demo_configuration({})[1]}


class Fixtures:
    def setUp(self):
        # Synthetic flat tariff and zero VAT isolate payment regressions. The
        # meter/tariff tests separately exercise actual billing VAT and bands.
        vat = patch("utils.billing.VAT_RATE", Decimal("0")); vat.start(); self.addCleanup(vat.stop)
        ElectricityTariff.objects.update(is_active=False)
        tariff = ElectricityTariff.objects.create(tariff_code="DEMO-FIXTURE", tariff_name="Synthetic payment regression tariff",
            tariff_type="DOMESTIC", voltage_level="LV", service_charge=0)
        TariffBlock.objects.create(tariff=tariff, block_order=1, min_units=0, max_units=None, rate_per_unit=1000)
        self.owner = User.objects.create_user(email="demo-owner@example.invalid", password="test-only")
        self.other = User.objects.create_user(email="demo-other@example.invalid", password="test-only")
        for user in (self.owner, self.other):
            user.profile.email_verified = True; user.profile.save(update_fields=["email_verified"])
        self.meter = enroll_sandbox_meter(self.owner, "00001234")[0]
        self.client = APIClient(); self.client.force_authenticate(self.owner)
        self.headers = {"HTTP_HOST": settings.ALLOWED_HOSTS[0], "HTTP_X_FORWARDED_PROTO": "https"}

    def purchase(self, amount="1003"):
        quote = create_quote(self.owner, self.meter.pk, amount, "PURCHASE")
        return create_payment(self.owner, {"purpose": "PURCHASE", "quote_id": str(quote.pk), "terms_hash": quote.terms_hash,
            "accept_test_terms": True, "client_request_id": str(uuid.uuid4())})[0]

    def loan(self):
        quote = create_quote(self.owner, self.meter.pk, "1000", "LOAN")
        return apply_loan(self.owner, quote.pk, quote.terms_hash, uuid.uuid4())[0]

    def repayment(self, loan, amount):
        return create_payment(self.owner, {"purpose": "LOAN_REPAYMENT", "loan_id": str(loan.pk), "amount": amount,
            "accept_test_terms": True, "client_request_id": str(uuid.uuid4())})[0]

    def settle(self, intent):
        with patch("django.utils.timezone.now", return_value=intent.demo_eligible_at + timedelta(seconds=1)):
            return complete_demo_payment(intent.pk, owner=self.owner)


@override_settings(**DEMO)
class DemoPaymentTests(Fixtures, TestCase):
    def test_five_second_deadline_early_confirmation_and_read_only_get(self):
        intent = self.purchase()
        self.assertGreaterEqual(intent.demo_eligible_at - intent.initiated_at, timedelta(seconds=5))
        with self.assertRaises(DemoNotReady): complete_demo_payment(intent.pk, owner=self.owner)
        with patch("django.utils.timezone.now", return_value=intent.demo_eligible_at + timedelta(seconds=1)):
            response = self.client.get(f"/api/v1/sandbox/payments/{intent.provider_reference}/", **self.headers)
        self.assertEqual(response.status_code, 200); self.assertEqual(response.data["payment"]["status"], "PENDING")
        self.assertFalse(SandboxSettlement.objects.exists()); self.assertFalse(EnergyAllocation.objects.exists())
        with transaction.atomic():
            response = self.client.post(f"/api/v1/sandbox/payments/{intent.provider_reference}/", {"success": True}, format="json", **self.headers)
            self.assertEqual(response.status_code, 409)
        self.assertFalse(SandboxSettlement.objects.exists())

    def test_schema_enforces_minimum_deadline(self):
        intent = self.purchase()
        with self.assertRaises(IntegrityError), transaction.atomic():
            PaymentIntent.objects.filter(pk=intent.pk).update(demo_eligible_at=intent.initiated_at + timedelta(seconds=4))

    def test_purchase_exactly_once_and_remainder_preserved_no_core_or_device_effect(self):
        prior = UnitBalance.objects.get(user=self.owner).balance
        intent = self.purchase()
        row, effect = self.settle(intent); self.assertTrue(effect)
        self.assertFalse(self.settle(intent)[1])
        ledger = SandboxSettlement.objects.get(intent=row)
        self.assertEqual((ledger.currency, ledger.environment), ("UGX", "UGX_DEMO"))
        self.assertEqual((ledger.received, ledger.billed, ledger.residual), (Decimal(1003), Decimal(1000), Decimal(3)))
        allocation = EnergyAllocation.objects.get(purchase_intent=row)
        self.assertEqual(allocation.amount_kwh, Decimal("1.00")); self.assertEqual(allocation.accounting_environment, "UGX_DEMO")
        self.assertFalse(MeterDelivery.objects.exists()); self.assertEqual(UnitBalance.objects.get(user=self.owner).balance, prior)
        self.assertFalse(receipt(row)["meter_application_confirmed"])

    def test_provider_success_dictionary_cannot_authorize_demo(self):
        intent = self.purchase()
        with self.assertRaises(PaymentSettlementError):
            settle_from_provider_evidence(intent.pk, {"status": "SUCCESS", "provider": "LOCAL_DEMO", "currency": "UGX"})
        self.assertFalse(SandboxSettlement.objects.exists())

    def test_partial_full_repayment_closure_and_overdue_do_not_reopen(self):
        loan = self.loan(); original_energy = EnergyAllocation.objects.count()
        first = self.repayment(loan, "300"); self.settle(first)
        self.assertEqual(loan.outstanding, Decimal(750))
        final = self.repayment(loan, "750"); self.settle(final)
        loan.refresh_from_db(); self.assertEqual(loan.status, "COMPLETED"); self.assertIsNotNone(loan.closed_at)
        with patch("django.utils.timezone.now", return_value=loan.due_at + timedelta(days=90)):
            self.assertEqual(loan.outstanding, 0); self.assertTrue(assessment(self.owner, meter_id=self.meter.pk)["eligible"])
            with self.assertRaises(ValidationError): self.repayment(loan, "1")
        self.assertEqual(EnergyAllocation.objects.count(), original_energy)
        self.assertEqual(sum(row.received for row in SandboxSettlement.objects.all()), Decimal(1050))

    def test_owner_and_meter_binding_rejected(self):
        intent = self.purchase()
        with self.assertRaises(NotFound): complete_demo_payment(intent.pk, owner=self.other)
        loan = self.loan()
        with self.assertRaises(NotFound):
            create_payment(self.other, {"purpose": "LOAN_REPAYMENT", "loan_id": str(loan.pk), "amount": "100", "accept_test_terms": True, "client_request_id": str(uuid.uuid4())})
        self.client.force_authenticate(self.other)
        with transaction.atomic():
            self.assertEqual(self.client.post(f"/api/v1/sandbox/payments/{intent.provider_reference}/", {}, **self.headers).status_code, 404)
        from meter.models import Meter
        Meter.all_objects.filter(pk=self.meter.pk).update(user=self.other)
        with self.assertRaises(PermissionDenied): self.settle(intent)
        self.assertFalse(SandboxSettlement.objects.exists())

    def test_mismatched_currency_environment_terms_and_purpose_rejected(self):
        intent = self.purchase()
        for field, value in (("environment", "MTN_SANDBOX"), ("currency", "EUR"), ("purpose", "LOAN_REPAYMENT"), ("owner_id", self.other.pk)):
            PaymentIntent.objects.filter(pk=intent.pk).update(sandbox_context={**intent.sandbox_context, field: value})
            with self.assertRaises(PaymentSettlementError): self.settle(intent)
        PaymentIntent.objects.filter(pk=intent.pk).update(sandbox_context=intent.sandbox_context)
        SandboxQuote.objects.filter(pk=intent.sandbox_quote_id).update(currency="EUR", environment="MTN_SANDBOX")
        with self.assertRaises(PaymentSettlementError): self.settle(intent)
        self.assertFalse(SandboxSettlement.objects.exists())

    def test_eur_history_remains_readable_and_separate_active_demo_allowed(self):
        with override_settings(**SANDBOX):
            from loan.tests_sandbox import trusted_profile_fixture
            trusted_profile_fixture(self.owner)
            quote = create_quote(self.owner, self.meter.pk, "2", "LOAN")
            old = apply_loan(self.owner, quote.pk, quote.terms_hash, uuid.uuid4())[0]
        new = self.loan(); self.assertEqual(new.environment, "UGX_DEMO")
        with self.assertRaises(ValidationError): self.repayment(old, "1")
        rows = self.client.get("/api/v1/sandbox/loans/", **self.headers).data["loans"]
        self.assertEqual({row["currency"] for row in rows}, {"EUR", "UGX"})
        old.refresh_from_db(); self.assertEqual(old.status, "DISBURSED"); self.assertEqual(old.total_due, Decimal("2.10"))

    def test_no_network_and_paused_mtn_including_cached_adapter(self):
        with override_settings(**SANDBOX): adapter = MTNSandbox()
        with patch("requests.sessions.Session.request", side_effect=AssertionError("No external provider request")) as request:
            intent = self.purchase(); self.settle(intent)
            with self.assertRaises(PermissionDenied): adapter.token()
            with self.assertRaises(PermissionDenied): reconcile_sandbox_payment(intent.pk)
            request.assert_not_called()
        with override_settings(CONSUMER_SANDBOX_ENABLED=False):
            with self.assertRaises(PermissionDenied): complete_demo_payment(intent.pk, owner=self.owner)

    def test_restart_scheduled_completion_dry_run_and_batch_limit(self):
        intent = self.purchase(); output = StringIO()
        with patch("django.utils.timezone.now", return_value=intent.demo_eligible_at + timedelta(seconds=1)):
            call_command("complete_demo_payments", stdout=output)
            self.assertFalse(SandboxSettlement.objects.exists())
            call_command("complete_demo_payments", run=True, limit=1, stdout=output)
            call_command("complete_demo_payments", run=True, limit=1, stdout=output)
        self.assertEqual(SandboxSettlement.objects.count(), 1)
        recovery = self.client.get(f"/api/v1/sandbox/payment-recovery/{intent.client_request_id}/", **self.headers).data["payment"]
        self.assertEqual(recovery["status"], "SETTLED")
        self.assertIn("DRY_RUN", output.getvalue())

    def test_current_features_preserve_restrictions_and_show_demo(self):
        result = self.client.get("/api/v1/features/", **self.headers).data
        self.assertEqual(result["sandbox"]["provider"], "LOCAL_DEMO"); self.assertEqual(result["sandbox"]["currency"], "UGX")
        self.assertTrue(result["sandbox"]["purchases"]); self.assertTrue(result["sandbox"]["repayments"])
        self.assertFalse(any(result["features"].values())); self.assertFalse(result["sandbox"]["physical_delivery"])
        self.assertFalse(result["mobile_actions"]["purchase"])

    def test_whole_amount_policy_and_pin_rejection(self):
        for amount in ("1.5", "NaN", "Infinity", "0", "-1"):
            with self.assertRaises(ValidationError): create_quote(self.owner, self.meter.pk, amount, "PURCHASE")
        with self.assertRaises(ValidationError): create_payment(self.owner, {"pin": "test-only"})
        with self.assertRaises(ImproperlyConfigured): demo_configuration({"DEMO_RATE_PER_KWH": "1.5"})
        self.assertFalse(PaymentIntent.objects.exists())

    def test_http_initiation_is_pending_and_ignores_success_flag(self):
        quote = create_quote(self.owner, self.meter.pk, "1000", "PURCHASE")
        payload = {"purpose": "PURCHASE", "quote_id": str(quote.pk), "terms_hash": quote.terms_hash,
                   "accept_test_terms": True, "client_request_id": str(uuid.uuid4()), "success": True}
        response = self.client.post("/api/v1/sandbox/payments/", payload, format="json", **self.headers)
        self.assertEqual(response.status_code, 202); self.assertEqual(response.data["payment"]["status"], "PENDING")
        self.assertFalse(EnergyAllocation.objects.exists())
        repeated = self.client.post("/api/v1/sandbox/payments/", payload, format="json", **self.headers)
        self.assertEqual(repeated.status_code, 200); self.assertEqual(PaymentIntent.objects.count(), 1)


@override_settings(**DEMO)
class DemoConcurrencyTests(Fixtures, TransactionTestCase):
    def pair(self, functions):
        barrier = Barrier(2)
        def run(fn):
            close_old_connections()
            try: barrier.wait(timeout=10); return fn()
            finally: close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor:
            return list(executor.map(run, functions))

    def test_duplicate_completion_one_effect(self):
        intent = self.purchase()
        with patch("django.utils.timezone.now", return_value=intent.demo_eligible_at + timedelta(seconds=1)):
            effects = self.pair([lambda: complete_demo_payment(intent.pk)[1] for _ in range(2)])
        self.assertEqual(sorted(effects), [False, True]); self.assertEqual(SandboxSettlement.objects.count(), 1)
        self.assertEqual(EnergyAllocation.objects.count(), 1)

    def test_distinct_repayments_preserve_full_received_and_excess(self):
        loan = self.loan(); first = self.repayment(loan, "800")
        # A separately authorized older pending obligation, not another UI initiation.
        quote = SandboxQuote.objects.create(owner=self.owner, meter=self.meter, purpose="LOAN_REPAYMENT", amount=first.amount,
            currency="UGX", environment="UGX_DEMO", terms=first.sandbox_quote.terms, terms_hash="synthetic",
            expires_at=timezone.now()+timedelta(minutes=15))
        second = PaymentIntent.objects.create(owner=self.owner, purpose=first.purpose, amount=first.amount, currency="UGX",
            provider="LOCAL_DEMO", sandbox_loan=loan, sandbox_quote=quote, sandbox_context=first.sandbox_context,
            provider_reference=uuid.uuid4(), provider_external_id="demo-distinct-pending-test",
            initiated_at=first.initiated_at, demo_eligible_at=first.demo_eligible_at)
        with patch("django.utils.timezone.now", return_value=first.demo_eligible_at + timedelta(seconds=1)):
            self.pair([lambda: complete_demo_payment(first.pk), lambda: complete_demo_payment(second.pk)])
        rows = list(SandboxSettlement.objects.all())
        self.assertEqual(sum(row.received for row in rows), Decimal(1600))
        self.assertEqual(sum(row.applied for row in rows), Decimal(1050))
        self.assertEqual(sum(row.excess for row in rows), Decimal(550))
        loan.refresh_from_db(); self.assertEqual(loan.status, "COMPLETED"); self.assertEqual(loan.outstanding, 0)
        self.assertEqual(EnergyAllocation.objects.count(), 1)

    def test_concurrent_same_initiation_and_loan_decision_keep_one_identity(self):
        quote = create_quote(self.owner, self.meter.pk, "1000", "LOAN"); key = uuid.uuid4()
        def apply(): return apply_loan(User.objects.get(pk=self.owner.pk), quote.pk, quote.terms_hash, key)[0].pk
        loans = self.pair([apply, apply])
        self.assertEqual(loans[0], loans[1]); self.assertEqual(EnergyAllocation.objects.count(), 1)
        quote = create_quote(self.owner, self.meter.pk, "1000", "PURCHASE"); key = uuid.uuid4()
        data = {"purpose": "PURCHASE", "quote_id": str(quote.pk), "terms_hash": quote.terms_hash,
                "client_request_id": str(key), "accept_test_terms": True}
        def initiate(): return create_payment(User.objects.get(pk=self.owner.pk), data)
        payments = self.pair([initiate, initiate])
        self.assertEqual(payments[0][0].pk, payments[1][0].pk)
        self.assertEqual(sorted(created for _, created in payments), [False, True])
        self.assertEqual(PaymentIntent.objects.count(), 1); self.assertEqual(SandboxSettlement.objects.count(), 0)


class DemoConfigurationTests(TestCase):
    def test_dormant_mtn_keys_are_preserved_without_requiring_a_valid_user_uuid(self):
        from backend.sandbox_config import sandbox_configuration
        raw = {"MTN_SANDBOX_API_USER_ID": "not-configured-yet", "MTN_SANDBOX_API_KEY": "synthetic-only"}
        _, config = sandbox_configuration(raw, validate_credentials=False)
        self.assertEqual(config["API_USER_ID"], raw["MTN_SANDBOX_API_USER_ID"])
        self.assertEqual(config["API_KEY"], raw["MTN_SANDBOX_API_KEY"])
        with self.assertRaises(ImproperlyConfigured): sandbox_configuration(raw)
        with self.assertRaises(ImproperlyConfigured): sandbox_configuration({"MTN_BASE_URL": "https://production.example.invalid"}, validate_credentials=False)

    def test_only_explicit_provider_modes_and_versioned_demo_values_are_accepted(self):
        self.assertEqual(demo_configuration({})[0], "LOCAL_DEMO")
        for values in ({"PROTOTYPE_PAYMENT_PROVIDER": "MTN_PRODUCTION"}, {"DEMO_POLICY_VERSION": "utility-approved"},
                       {"DEMO_MINIMUM": "1.5"}, {"DEMO_STARTER_LIMIT": "1"}, {"DEMO_INTEREST_PERCENT": "NaN"}):
            with self.assertRaises(ImproperlyConfigured): demo_configuration(values)

    def test_schema_is_complete(self):
        call_command("makemigrations", "loan", "meter", "transactions", check=True, dry_run=True, verbosity=0)
