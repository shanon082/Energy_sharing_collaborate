"""Exact billing/debt tests on isolated PostgreSQL with no live integrations."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from io import StringIO
import json
from threading import Barrier
from unittest import expectedFailure
from unittest.mock import patch
import uuid

from django.core.management import call_command
from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User, Wallet
from loan.api.serializers import LoanApplicationSerializer
from loan.api.views import LoanApplicationView
from loan.financial import loan_charges, outstanding_debt
from loan.models import ElectricityTariff, LoanApplication, LoanDisbursement, LoanRepayment, LoanTier, TariffBlock
from meter.models import EnergyAllocation, Meter, Transaction as MeterTransaction
from transactions.models import PaymentIntent, Transaction, UnitTransaction
from transactions.payment_settlement import create_purchase_intent, create_repayment_intent, settle_from_provider_evidence
from utils.billing import calculate_bill_for_units, calculate_units_from_payment, get_monthly_tier_context, get_monthly_units_consumed
from wallet.models import UnitBalance


class FinancialCorrectnessTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="billing@example.invalid", password="test-only")
        self.meter = Meter.objects.create(user=self.user, meter_no="BILL-001", architecture=Meter.ARCH_AMI)
        self.wallet = Wallet.objects.create(user=self.user)

    def loan(self, *, principal="10000.00", rate="0.00", tenure=1):
        return LoanApplication.objects.create(
            user=self.user, amount_requested=Decimal(principal),
            amount_approved=Decimal(principal), interest_rate=Decimal(rate),
            tenure_months=tenure, status="DISBURSED", purpose="Electricity",
            intended_meter=self.meter,
        )

    def intent(self, loan, amount):
        repayment = LoanRepayment.objects.create(
            loan=loan, amount_paid=Decimal(amount), units_paid=0,
            payment_reference=f"FIN-{uuid.uuid4().hex}",
            payment_status="PENDING", payment_method="MOBILE_MONEY",
        )
        return create_repayment_intent(owner=self.user, repayment=repayment)

    def evidence(self, intent):
        return {"provider": "MTN_PRODUCTION", "reference_id": str(intent.provider_reference),
                "external_id": intent.provider_external_id, "status": "SUCCESS",
                "amount": str(intent.amount), "currency": "UGX",
                "transaction_id": f"financial-{intent.pk}"}

    def tariff(self):
        tariff = ElectricityTariff.objects.create(
            tariff_code="FIN-TEST", tariff_name="Financial test", tariff_type="DOMESTIC",
            voltage_level="LV", service_charge=Decimal("3360.00"),
        )
        TariffBlock.objects.create(tariff=tariff, block_name="First", block_order=1,
                                   min_units=0, max_units=15, rate_per_unit=Decimal("250.00"))
        TariffBlock.objects.create(tariff=tariff, block_name="Second", block_order=2,
                                   min_units=16, max_units=80, rate_per_unit=Decimal("756.20"))
        return tariff

    def test_tariff_boundary_and_paid_energy_floor(self):
        tariff = self.tariff()
        with patch("utils.billing.get_monthly_units_consumed", return_value=Decimal("14.99")):
            bill = calculate_bill_for_units(Decimal("0.02"), self.user, tariff)
        self.assertEqual(bill.energy_cost, Decimal("10.06"))
        with patch("utils.billing.get_monthly_units_consumed", return_value=Decimal("0")):
            units, breakdown = calculate_units_from_payment(Decimal("5000"), self.user, tariff,
                                                             apply_deductions=False)
            self.assertEqual(units.as_tuple().exponent, -2)
            self.assertLessEqual(breakdown.total, Decimal("5000"))
            next_bill = calculate_bill_for_units(units + Decimal("0.01"), self.user, tariff)
            self.assertGreater(next_bill.total, Decimal("5000"))

    def test_configured_zero_service_and_band_context(self):
        tariff = self.tariff()
        tariff.service_charge = Decimal("0.00")
        tariff.save(update_fields=["service_charge"])
        first = tariff.blocks.get(block_order=1)
        first.is_lifeline_block = True
        first.save(update_fields=["is_lifeline_block"])
        with patch("utils.billing.get_monthly_units_consumed", return_value=Decimal("14.99")):
            bill = calculate_bill_for_units(Decimal("0.01"), self.user, tariff)
            context = get_monthly_tier_context(self.user)
        self.assertEqual(bill.service_charge, Decimal("0.00"))
        self.assertEqual(context["lifeline_remaining_kwh"], Decimal("0.01"))
        self.assertEqual(context["current_tier_band"], "lifeline")

    def test_loan_quote_uses_the_same_full_bill_as_allocation(self):
        tariff = self.tariff()
        loan = self.loan(principal="5000.00")
        loan.tariff = tariff
        units, bill = calculate_units_from_payment(Decimal("5000"), self.user, tariff,
                                                    apply_deductions=False)
        quote = LoanApplicationView().get_cost_breakdown(loan, Decimal("5000"))
        self.assertEqual(quote["energy_units_kwh"], str(units))
        self.assertEqual(quote["total_ugx"], str(bill.total))
        self.assertEqual(quote["vat_ugx"], str(bill.vat))

    def test_no_tariff_loan_keeps_legacy_units_without_false_vat_quote(self):
        loan = self.loan(principal="5000.00")
        self.assertEqual(loan.calculate_units_from_amount(), Decimal("10.00"))
        self.assertIsNone(LoanApplicationView().get_cost_breakdown(loan, Decimal("5000")))

    def test_purchase_representations_count_once_and_loan_self_credit_does_not(self):
        ref = uuid.uuid4()
        purchase = Transaction.objects.create(wallet=self.wallet, amount=Decimal("10000"),
            phone_number="+256700000001", status="COMPLETED", transaction_reference=str(ref))
        intent = PaymentIntent.objects.create(owner=self.user, purpose=PaymentIntent.PURCHASE,
            amount=Decimal("10000"), currency="UGX", provider="MTN_PRODUCTION",
            provider_reference=ref, provider_external_id=f"gpawa-purchase-{ref}",
            purchase=purchase, meter=self.meter, status=PaymentIntent.SETTLED)
        EnergyAllocation.objects.create(owner=self.user, meter=self.meter,
            purchase_intent=intent, amount_kwh=Decimal("3.50"))
        for _ in range(2):
            MeterTransaction.objects.create(user=self.user, meter=self.meter,
                transaction_type=MeterTransaction.TYPE_PURCHASE, amount_kwh=Decimal("3.50"),
                amount_ugx=Decimal("10000"), status=MeterTransaction.STATUS_COMPLETED,
                payment_reference=str(ref))
        UnitTransaction.objects.create(sender=self.user, receiver=self.user, meter=self.meter,
            units=3.5, direction="IN", status="COMPLETED")
        UnitTransaction.objects.create(sender=self.user, receiver=self.user, meter=self.meter,
            units=2.0, direction="IN", status="COMPLETED", message="Loan disbursement")
        self.assertEqual(get_monthly_units_consumed(self.user), Decimal("3.50"))
        out = StringIO()
        call_command("reconcile_financial_history", stdout=out)
        report = json.loads(out.getvalue())
        self.assertEqual(report["mode"], "dry_run")
        self.assertEqual(report["duplicate_purchase_representations"]["meter_rows_also_represented_by_allocation"], 2)
        self.assertEqual(get_monthly_units_consumed(self.user), Decimal("3.50"))

    def test_fractional_interest_rounds_once_and_partial_payment_is_exact(self):
        loan = self.loan(principal="100.00", rate="0.06")
        self.assertEqual(loan_charges(loan), Decimal("0.00"))  # exact 0.005 UGX, half-even
        self.assertEqual(loan.total_amount_due, Decimal("100.00"))
        self.assertEqual(loan.outstanding_balance, Decimal("100.00"))
        intent = self.intent(loan, "40.00")
        settle_from_provider_evidence(intent.pk, self.evidence(intent))
        self.assertEqual(loan.amount_paid, Decimal("40.00"))
        self.assertEqual(loan.outstanding_balance, Decimal("60.00"))
        self.assertEqual(LoanApplicationSerializer(loan).data["outstanding_balance"], Decimal("60.00"))

    def test_fractional_debt_receives_whole_ugx_and_preserves_excess(self):
        loan = self.loan(principal="101.00", rate="0.06")
        self.assertEqual(loan_charges(loan), Decimal("0.01"))
        self.assertEqual(loan.outstanding_balance, Decimal("101.01"))
        intent = self.intent(loan, "102.00")
        settle_from_provider_evidence(intent.pk, self.evidence(intent))
        repayment = intent.repayment
        repayment.refresh_from_db()
        self.assertEqual(repayment.amount_paid, Decimal("102.00"))
        self.assertEqual(repayment.amount_applied_ugx, Decimal("101.01"))
        self.assertEqual(repayment.excess_ugx, Decimal("0.99"))
        self.assertEqual(loan.outstanding_balance, Decimal("0.00"))
        self.assertEqual(UnitBalance.objects.get(user=self.user).balance, Decimal("0"))
        client = APIClient()
        client.force_authenticate(user=self.user)
        status = client.get(f"/api/v1/loans/payment-status/{intent.provider_reference}/")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.data["amount_applied_ugx"], "101.01")
        self.assertEqual(status.data["excess_ugx"], "0.99")
        self.assertEqual(Decimal(status.data["outstanding_balance"]), loan.outstanding_balance)
        self.assertIn("reconciliation", status.data["message"])

    def test_disbursed_rate_does_not_change_when_score_is_saved(self):
        LoanTier.objects.create(name="GOLD", display_name="Gold", min_score=90,
            max_score=100, max_amount=Decimal("100000"), interest_rate=Decimal("12.00"))
        loan = self.loan(principal="10000.00", rate="9.00")
        original_debt = loan.outstanding_balance
        loan.credit_score = 95
        loan.save()
        loan.refresh_from_db()
        self.assertEqual(loan.interest_rate, Decimal("9.00"))
        self.assertEqual(loan.outstanding_balance, original_debt)

    def test_api_and_serializer_use_the_same_debt(self):
        loan = self.loan(principal="101.00", rate="0.06")
        client = APIClient()
        client.force_authenticate(user=self.user)
        stats = client.get("/api/v1/loans/stats/")
        self.assertEqual(stats.status_code, 200)
        self.assertEqual(Decimal(str(stats.data["outstanding_balance"])), loan.outstanding_balance)
        self.assertIn("max_eligible_amount", stats.data)
        self.assertIn("interest_rate", stats.data)
        self.assertIn("is_loan_eligible", stats.data)
        serialized = LoanApplicationSerializer(loan).data
        self.assertEqual(serialized["outstanding_balance"], loan.outstanding_balance)
        self.assertEqual(serialized["total_amount_due"], loan.total_amount_due)
        self.assertEqual(serialized["amount_paid"], loan.amount_paid)

    @expectedFailure
    def test_completed_loan_stays_closed_when_overdue_clock_advances(self):
        # The existing debt calculation has no immutable close timestamp.
        # Keep the desired invariant visible until closure timing is approved.
        loan = self.loan()
        disbursement = LoanDisbursement.objects.create(
            loan_application=loan, disbursed_amount=Decimal("10000.00"),
            units_disbursed=0, meter=self.meter,
        )
        LoanDisbursement.objects.filter(pk=disbursement.pk).update(
            disbursement_date=timezone.now() - timedelta(days=32),
        )
        loan.refresh_from_db()
        received = loan.outstanding_balance.to_integral_value()
        intent = self.intent(loan, str(received))
        settle_from_provider_evidence(intent.pk, self.evidence(intent))
        loan.refresh_from_db()
        self.assertEqual(loan.status, "COMPLETED")
        self.assertEqual(outstanding_debt(loan, as_of=timezone.now() + timedelta(days=3)), Decimal("0.00"))

    def test_distinct_concurrent_repayments_apply_only_remaining_debt(self):
        loan = self.loan()
        intents = [self.intent(loan, "7000.00") for _ in range(2)]
        barrier = Barrier(2)

        def settle(intent):
            close_old_connections()
            barrier.wait(timeout=10)
            try:
                return settle_from_provider_evidence(intent.pk, self.evidence(intent))[1]
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(settle, intents))
        self.assertEqual(results, [True, True])
        rows = list(LoanRepayment.objects.filter(loan=loan).order_by("id"))
        self.assertEqual(sum((r.amount_paid for r in rows), Decimal("0")), Decimal("14000"))
        self.assertEqual(sum((r.amount_applied_ugx for r in rows), Decimal("0")), Decimal("10000"))
        self.assertEqual(sum((r.excess_ugx for r in rows), Decimal("0")), Decimal("4000"))
        self.assertEqual(loan.outstanding_balance, Decimal("0.00"))
        self.assertEqual(UnitBalance.objects.get(user=self.user).balance, Decimal("0"))
        out = StringIO()
        call_command("reconcile_financial_history", stdout=out)
        self.assertEqual(json.loads(out.getvalue())["uncertain_repayments"]["verified_excess_total_ugx"], "4000.00")

    def test_concurrent_purchases_on_distinct_meters_advance_bands_once(self):
        self.tariff()
        other_meter = Meter.objects.create(user=self.user, meter_no="BILL-002", architecture=Meter.ARCH_AMI)
        intents = []
        for meter in (self.meter, other_meter):
            reference = uuid.uuid4()
            purchase = Transaction.objects.create(wallet=self.wallet, amount=Decimal("5000"),
                phone_number="+256700000001", status="PENDING", transaction_reference=str(reference))
            intents.append(create_purchase_intent(owner=self.user, meter=meter, transaction=purchase,
                                                  amount=Decimal("5000"), reference=reference))
        barrier = Barrier(2)

        def settle(intent):
            close_old_connections()
            barrier.wait(timeout=10)
            try:
                return settle_from_provider_evidence(intent.pk, self.evidence(intent))[1]
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(settle, intents)), [True, True])
        grants = sorted(EnergyAllocation.objects.filter(purchase_intent__in=intents)
                        .values_list("amount_kwh", flat=True))
        self.assertEqual(grants, [Decimal("3.50"), Decimal("13.30")])
        self.assertEqual(get_monthly_units_consumed(self.user), Decimal("16.80"))
