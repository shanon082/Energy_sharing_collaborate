"""PostgreSQL isolation and concurrency checks for verified payment settlement."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch
import uuid

from django.db import close_old_connections, connection
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User, Wallet as AccountWallet
from loan.models import ElectricityTariff, LoanApplication, LoanRepayment, TariffBlock
from loan.services import disburse_loan
from meter.models import EnergyAllocation, Meter, MeterToken, Transaction as MeterLedgerTransaction
from transactions.models import PaymentIntent, Transaction, TransactionLog, TransactionType
from transactions.payment_settlement import (
    PaymentSettlementError, create_purchase_intent, create_repayment_intent,
    reconcile_payment, settle_from_provider_evidence,
)
from transactions.tasks import reconcile_pending_payments
from wallet.models import UnitBalance, Wallet as LegacyMoneyWallet


REAL_PROVIDER = {
    "ENVIRONMENT": "production",
    "SUBSCRIPTION_KEY": "test-only",
    "API_USER_ID": "test-only",
    "API_KEY": "test-only",
    "BASE_URL": "https://invalid.example",
}


@override_settings(MTN_MOMO_CONFIG=REAL_PROVIDER, MTN_USE_SIMULATED_PAYMENTS=False)
class VerifiedSettlementTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.owner = User.objects.create_user(email="owner@example.invalid", password="test-only")
        self.other = User.objects.create_user(email="other@example.invalid", password="test-only")
        self.meter = Meter.objects.create(user=self.owner, meter_no="OWN-001", architecture=Meter.ARCH_AMI)
        self.other_meter = Meter.objects.create(user=self.other, meter_no="OTHER-001", architecture=Meter.ARCH_AMI)
        self.account_wallet = AccountWallet.objects.create(user=self.owner)
        self.client = APIClient()
        self.client.force_authenticate(user=self.owner)

    def purchase_intent(self, amount="10000.00"):
        reference = uuid.uuid4()
        purchase = Transaction.objects.create(
            wallet=self.account_wallet, amount=Decimal(amount),
            phone_number="+256700000001", status="PENDING",
            transaction_reference=str(reference),
        )
        return create_purchase_intent(
            owner=self.owner, meter=self.meter, transaction=purchase,
            amount=Decimal(amount), reference=reference,
        )

    def loan(self, *, status="DISBURSED"):
        return LoanApplication.objects.create(
            user=self.owner, amount_requested=Decimal("10000.00"),
            amount_approved=Decimal("10000.00"), tenure_months=1,
            interest_rate=Decimal("0.00"), status=status, purpose="Electricity",
            intended_meter=self.meter,
        )

    def repayment_intent(self):
        loan = self.loan()
        repayment = LoanRepayment.objects.create(
            loan=loan, amount_paid=Decimal("4000.00"), units_paid=0,
            payment_reference=f"TEST-{uuid.uuid4().hex}",
            payment_status="PENDING", payment_method="MOBILE_MONEY",
        )
        return create_repayment_intent(owner=self.owner, repayment=repayment), loan

    def evidence(self, intent, **changes):
        result = {
            "provider": "MTN_PRODUCTION",
            "reference_id": str(intent.provider_reference),
            "external_id": intent.provider_external_id,
            "status": "SUCCESS",
            "amount": str(intent.amount),
            "currency": "UGX",
            "transaction_id": "provider-test-transaction",
        }
        result.update(changes)
        return result

    def test_pending_or_failed_provider_status_never_credits_energy_or_reduces_debt(self):
        purchase = self.purchase_intent()
        repayment, loan = self.repayment_intent()
        starting_debt = loan.outstanding_balance
        self.assertEqual(loan.amount_paid, 0)
        for intent in (purchase, repayment):
            _, applied = settle_from_provider_evidence(intent.pk, {"status": "PENDING"})
            self.assertFalse(applied)
        self.assertEqual(UnitBalance.objects.get(user=self.owner).balance, 0)
        loan.refresh_from_db()
        self.assertEqual(loan.outstanding_balance, starting_debt)
        _, applied = settle_from_provider_evidence(purchase.pk, self.evidence(purchase, status="FAILED"))
        self.assertFalse(applied)
        self.assertEqual(UnitBalance.objects.get(user=self.owner).balance, 0)

    def test_purchase_settles_once_and_never_reduces_loan_debt(self):
        loan = self.loan()
        starting_debt = loan.outstanding_balance
        intent = self.purchase_intent()
        _, applied = settle_from_provider_evidence(intent.pk, self.evidence(intent))
        self.assertTrue(applied)
        _, applied_again = settle_from_provider_evidence(intent.pk, self.evidence(intent))
        self.assertFalse(applied_again)
        self.assertGreater(UnitBalance.objects.get(user=self.owner).balance, 0)
        self.assertEqual(TransactionLog.objects.filter(
            transaction_type=TransactionType.UNIT_PURCHASE,
            reference_id=str(intent.provider_reference),
        ).count(), 1)
        loan.refresh_from_db()
        self.assertEqual(loan.outstanding_balance, starting_debt)
        self.assertEqual(LoanRepayment.objects.filter(loan=loan).count(), 0)

    def test_purchase_receipt_equals_billed_energy_plus_reconciliation_residual(self):
        tariff = ElectricityTariff.objects.create(
            pk=(ElectricityTariff.objects.order_by("-pk").values_list("pk", flat=True).first() or 0) + 1,
            tariff_code="PAY-TEST", tariff_name="Payment test", tariff_type="DOMESTIC",
            voltage_level="LV", service_charge=Decimal("3360.00"),
        )
        TariffBlock.objects.create(
            pk=(TariffBlock.objects.order_by("-pk").values_list("pk", flat=True).first() or 0) + 1,
            tariff=tariff, block_name="First", block_order=1, min_units=0,
            max_units=15, rate_per_unit=Decimal("250.00"),
        )
        intent = self.purchase_intent("5000.00")
        _, applied = settle_from_provider_evidence(intent.pk, self.evidence(intent))
        self.assertTrue(applied)
        intent.refresh_from_db()
        self.assertEqual(intent.purchase_billed_ugx + intent.purchase_residual_ugx, intent.amount)
        self.assertEqual(intent.purchase_calculation["billed_ugx"], str(intent.purchase_billed_ugx))
        self.assertEqual(intent.purchase_calculation["tariff_code"], tariff.tariff_code)
        self.assertEqual(intent.purchase_calculation["tariff_service_charge_ugx"], "3360.00")
        allocation = EnergyAllocation.objects.get(purchase_intent=intent)
        self.assertEqual(allocation.amount_kwh, Decimal("3.50"))
        self.assertEqual(intent.purchase_billed_ugx, Decimal("4997.30"))
        self.assertEqual(intent.purchase_residual_ugx, Decimal("2.70"))
        ledger = MeterLedgerTransaction.objects.get(payment_reference=str(intent.provider_reference))
        self.assertEqual(ledger.amount_ugx, intent.purchase_billed_ugx)
        log = TransactionLog.objects.get(reference_id=str(intent.provider_reference))
        self.assertEqual(log.amount, intent.amount)
        self.assertEqual(log.details["residual_ugx"], "2.70")
        response = self.client.post("/api/v1/meter/check-payment-status/", {"transaction_id": intent.purchase_id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["amount_received_ugx"], "5000.00")
        self.assertEqual(response.data["purchase_residual_ugx"], "2.70")

    def test_small_verified_receipt_is_preserved_without_energy_allocation(self):
        intent = self.purchase_intent("1.00")
        _, applied = settle_from_provider_evidence(intent.pk, self.evidence(intent))
        self.assertTrue(applied)
        intent.refresh_from_db()
        self.assertEqual(intent.status, PaymentIntent.SETTLED)
        self.assertEqual(intent.purchase_billed_ugx, Decimal("0.00"))
        self.assertEqual(intent.purchase_residual_ugx, intent.amount)
        self.assertFalse(EnergyAllocation.objects.filter(purchase_intent=intent).exists())
        self.assertEqual(UnitBalance.objects.get(user=self.owner).balance, 0)
        self.assertEqual(TransactionLog.objects.get(reference_id=str(intent.provider_reference)).status, "RECONCILE")
        response = self.client.post("/api/v1/meter/check-payment-status/", {"transaction_id": intent.purchase_id})
        self.assertEqual(response.data["units_purchased"], 0)
        self.assertTrue(response.data["requires_reconciliation"])

    def test_repayment_reduces_debt_without_creating_energy(self):
        intent, loan = self.repayment_intent()
        starting_debt = loan.outstanding_balance
        _, applied = settle_from_provider_evidence(intent.pk, self.evidence(intent))
        self.assertTrue(applied)
        loan.refresh_from_db()
        self.assertEqual(loan.outstanding_balance, starting_debt - 4000)
        self.assertEqual(loan.amount_paid, 4000)
        self.assertEqual(UnitBalance.objects.get(user=self.owner).balance, 0)
        self.assertEqual(MeterToken.objects.count(), 0)

    def test_overdue_loan_remains_repayable(self):
        intent, loan = self.repayment_intent()
        loan.status = "DEFAULTED"
        loan.save(update_fields=["status"])
        before = loan.outstanding_balance
        _, applied = settle_from_provider_evidence(intent.pk, self.evidence(intent))
        self.assertTrue(applied)
        loan.refresh_from_db()
        self.assertEqual(loan.outstanding_balance, before - 4000)

    def test_amount_currency_reference_purpose_and_simulation_mismatch_rejected(self):
        intent = self.purchase_intent()
        bad_evidence = (
            {"amount": "9999.00"},
            {"currency": "EUR"},
            {"reference_id": str(uuid.uuid4())},
            {"external_id": "gpawa-repayment-wrong"},
            {"provider": "MTN_SANDBOX"},
        )
        for changes in bad_evidence:
            with self.subTest(changes=changes), self.assertRaises(PaymentSettlementError):
                settle_from_provider_evidence(intent.pk, self.evidence(intent, **changes))
        self.assertEqual(UnitBalance.objects.get(user=self.owner).balance, 0)
        intent.refresh_from_db()
        self.assertEqual(intent.status, PaymentIntent.PENDING)

    def test_provider_transaction_cannot_settle_purchase_and_loan(self):
        purchase = self.purchase_intent()
        repayment, loan = self.repayment_intent()
        debt_before = loan.outstanding_balance
        settle_from_provider_evidence(purchase.pk, self.evidence(purchase))
        with self.assertRaises(PaymentSettlementError):
            settle_from_provider_evidence(repayment.pk, self.evidence(repayment))
        repayment.refresh_from_db()
        self.assertEqual(repayment.status, PaymentIntent.PENDING)
        loan.refresh_from_db()
        self.assertEqual(loan.outstanding_balance, debt_before)

    def test_concurrent_cross_intent_replay_has_one_effect(self):
        purchase = self.purchase_intent()
        repayment, loan = self.repayment_intent()
        debt_before = loan.outstanding_balance
        barrier = Barrier(2)

        def settle_in_thread(intent):
            close_old_connections()
            barrier.wait(timeout=10)
            try:
                try:
                    return settle_from_provider_evidence(intent.pk, self.evidence(intent))[1]
                except PaymentSettlementError:
                    return False
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(settle_in_thread, (purchase, repayment)))
        self.assertEqual(sorted(outcomes), [False, True])
        purchase.refresh_from_db()
        repayment.refresh_from_db()
        loan.refresh_from_db()
        self.assertEqual(PaymentIntent.objects.filter(status=PaymentIntent.SETTLED).count(), 1)
        self.assertEqual(
            PaymentIntent.objects.exclude(provider_transaction_id="").count(), 1,
        )
        if purchase.status == PaymentIntent.SETTLED:
            self.assertGreater(UnitBalance.objects.get(user=self.owner).balance, 0)
            self.assertEqual(loan.outstanding_balance, debt_before)
        else:
            self.assertEqual(UnitBalance.objects.get(user=self.owner).balance, 0)
            self.assertEqual(loan.outstanding_balance, debt_before - 4000)

    @override_settings(MTN_USE_SIMULATED_PAYMENTS=True)
    def test_simulation_cannot_initiate_or_reconcile_real_provider_payment(self):
        intent = self.purchase_intent()
        with patch("transactions.payment_settlement.MTNMoMoService.get_payment_status") as provider:
            with self.assertRaises(PaymentSettlementError):
                reconcile_payment(intent.pk)
            response = self.client.post("/api/v1/meter/buy-units/", {
                "amount": "10000", "phone_number": "256700000001",
            }, format="json")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(PaymentIntent.objects.count(), 1)
        provider.assert_not_called()

    def test_real_provider_poll_is_outside_atomic_block(self):
        intent = self.purchase_intent()
        def provider_status(reference):
            self.assertFalse(connection.in_atomic_block)
            self.assertEqual(reference, str(intent.provider_reference))
            return self.evidence(intent)
        with patch("transactions.payment_settlement.MTNMoMoService.get_payment_status", side_effect=provider_status):
            _, applied = reconcile_payment(intent.pk)
        self.assertTrue(applied)

    def test_concurrent_confirmations_have_one_effect(self):
        intent = self.purchase_intent()
        evidence = self.evidence(intent)
        barrier = Barrier(2)
        def settle_in_thread():
            close_old_connections()
            barrier.wait(timeout=10)
            try:
                return settle_from_provider_evidence(intent.pk, evidence)[1]
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _: settle_in_thread(), range(2)))
        self.assertEqual(sorted(outcomes), [False, True])
        self.assertEqual(TransactionLog.objects.filter(
            transaction_type=TransactionType.UNIT_PURCHASE,
            reference_id=str(intent.provider_reference),
        ).count(), 1)

    def test_concurrent_repayment_confirmations_reduce_debt_once(self):
        intent, loan = self.repayment_intent()
        starting_debt = loan.outstanding_balance
        evidence = self.evidence(intent)
        barrier = Barrier(2)
        def settle_in_thread():
            close_old_connections()
            barrier.wait(timeout=10)
            try:
                return settle_from_provider_evidence(intent.pk, evidence)[1]
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _: settle_in_thread(), range(2)))
        self.assertEqual(sorted(outcomes), [False, True])
        loan.refresh_from_db()
        self.assertEqual(loan.outstanding_balance, starting_debt - 4000)
        self.assertEqual(TransactionLog.objects.filter(
            transaction_type=TransactionType.LOAN_REPAYMENT,
            reference_id=str(intent.provider_reference),
        ).count(), 1)

    @override_settings(DEBUG=True, SIMULATED_METER_ENABLED=True)
    def test_cross_account_purchase_and_loan_operations_are_denied(self):
        with patch("transactions.api.payment_views.request_payment") as provider, patch(
            "meter.api.views.apply_units_to_meter"
        ) as device:
            response = self.client.post("/api/v1/meter/buy-units/", {
                "amount": "10000", "phone_number": "256700000001",
                "meter_no": self.other_meter.meter_no,
            }, format="json")
            self.assertEqual(response.status_code, 400)
            load = self.client.post("/api/v1/meter/apply-wallet-units/", {
                "amount": "1", "meter_no": self.other_meter.meter_no,
            }, format="json")
            self.assertEqual(load.status_code, 409)
            self.assertEqual(load.data["code"], "ENTITLEMENT_UNAVAILABLE")
            loan = self.loan()
            self.client.force_authenticate(user=self.other)
            response = self.client.post(f"/api/v1/loans/repay/momo/{loan.pk}/", {
                "amount": "1000", "phone_number": "256700000002",
            }, format="json")
            self.assertEqual(response.status_code, 404)
            self.assertEqual(PaymentIntent.objects.count(), 0)
            provider.assert_not_called()
            device.assert_not_called()

    def test_new_purchase_and_repayment_remain_pending_without_provider_success(self):
        def provider_request(intent, phone):
            self.assertFalse(connection.in_atomic_block)
            return {"status": "PENDING"}
        with patch("transactions.api.payment_views.request_payment", side_effect=provider_request):
            purchase = self.client.post("/api/v1/meter/buy-units/", {
                "amount": "10000", "phone_number": "256700000001",
                "payment_source": "PHONE", "meter_no": self.meter.meter_no,
                "payment_status": "SUCCESS", "success": True,
            }, format="json")
            self.assertEqual(purchase.status_code, 200, purchase.data)
            loan = self.loan()
            repayment = self.client.post(f"/api/v1/loans/repay/momo/{loan.pk}/", {
                "amount": "4000", "phone_number": "256700000001",
                "payment_status": "SUCCESS", "success": True,
            }, format="json")
            self.assertEqual(repayment.status_code, 200, repayment.data)
        self.assertEqual(PaymentIntent.objects.filter(status=PaymentIntent.PENDING).count(), 2)
        self.assertEqual(UnitBalance.objects.get(user=self.owner).balance, 0)
        self.assertEqual(loan.amount_paid, 0)
        self.assertEqual(self.client.get(f"/api/v1/loans/payment-status/{repayment.data['external_id']}/").data["payment_status"], "PENDING")

    def test_background_reconciliation_settles_after_browser_is_closed(self):
        intent = self.purchase_intent()
        PaymentIntent.objects.filter(pk=intent.pk).update(
            initiated_at=timezone.now() - timedelta(minutes=2),
        )
        with patch("transactions.payment_settlement.MTNMoMoService.get_payment_status", return_value=self.evidence(intent)):
            self.assertEqual(reconcile_pending_payments(), 1)
        intent.refresh_from_db()
        self.assertEqual(intent.status, PaymentIntent.SETTLED)

    def test_status_routes_do_not_expose_other_accounts_or_invalid_references(self):
        purchase = self.purchase_intent()
        repayment, _ = self.repayment_intent()
        self.client.force_authenticate(user=self.other)
        self.assertEqual(self.client.post("/api/v1/meter/check-payment-status/", {
            "transaction_id": purchase.purchase_id,
        }, format="json").status_code, 404)
        self.assertEqual(self.client.get(
            f"/api/v1/loans/payment-status/{repayment.provider_reference}/",
        ).status_code, 404)
        self.assertEqual(self.client.get("/api/v1/loans/payment-status/invalid/").status_code, 404)

    def test_legacy_unverified_routes_and_public_tokens_cannot_mutate(self):
        loan = self.loan()
        debt = loan.outstanding_balance
        self.assertEqual(self.client.post("/api/v1/transactions/buy-units/", {}, format="json").status_code, 409)
        self.assertEqual(self.client.post(f"/api/v1/loans/repay/{loan.pk}/", {"amount": 100}, format="json").status_code, 409)
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.post("/api/v1/webhooks/token/", {"token": "x"}, format="json").status_code, 410)
        self.assertEqual(self.client.post("/api/v1/loans/verify-token/", {"token": "x"}, format="json").status_code, 410)
        loan.refresh_from_db()
        self.assertEqual(loan.outstanding_balance, debt)
        self.assertEqual(UnitBalance.objects.get(user=self.owner).balance, 0)

    def test_approved_loan_still_allocates_authorized_energy_once(self):
        loan = self.loan(status="APPROVED")
        response = self.client.post(f"/api/v1/loans/disburse/{loan.pk}/", {}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertGreater(UnitBalance.objects.get(user=self.owner).balance, 0)
        loan.refresh_from_db()
        self.assertEqual(loan.status, "DISBURSED")
        second = self.client.post(f"/api/v1/loans/disburse/{loan.pk}/", {}, format="json")
        self.assertNotEqual(second.status_code, 200)
        self.assertEqual(MeterToken.objects.count(), 0)
        loans = self.client.get("/api/v1/loans/my-loans/")
        self.assertEqual(loans.status_code, 200)
        self.assertIsNone(loans.data[0]["disbursement_token"])

    def test_auto_disbursement_allocates_kwh_without_ugx_or_device_mutation(self):
        loan = self.loan(status="APPROVED")
        with patch("loan.services.dispatch_task"), patch("meter.services.push_units_to_thingsboard") as push:
            result = disburse_loan(self.owner, loan.pk, channel="TEST")
        self.assertGreater(UnitBalance.objects.get(user=self.owner).balance, 0)
        self.assertEqual(LegacyMoneyWallet.objects.get(user=self.owner).balance, 0)
        self.assertFalse(result["meter_push_ok"])
        push.assert_not_called()

    @override_settings(THINGSBOARD_WEBHOOK_SECRET="", DEBUG=False)
    def test_missing_webhook_secret_and_test_push_are_closed(self):
        self.client.force_authenticate(user=None)
        response = self.client.post("/webhooks/thingsboard/low-units", {}, format="json")
        self.assertEqual(response.status_code, 401)
        self.client.force_authenticate(user=self.owner)
        response = self.client.post("/api/v1/meter/test-meter-push/", {"amount": 10}, format="json")
        self.assertEqual(response.status_code, 403)
