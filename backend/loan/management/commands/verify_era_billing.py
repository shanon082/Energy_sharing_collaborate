"""
Verify ERA Q4 2025 billing examples from the domestic consumer tariff summary.

Run: python manage.py verify_era_billing
"""
from decimal import Decimal
from types import SimpleNamespace

from django.core.management.base import BaseCommand
from django.utils import timezone

from loan.models import ElectricityTariff, TariffBlock
from utils.billing import (
    DEFAULT_SERVICE_CHARGE,
    VAT_RATE,
    calculate_bill_for_units,
    calculate_units_from_payment,
    get_active_domestic_tariff,
)


def _mock_user(lifeline_eligible=True, monthly_units=Decimal("0")):
    user = SimpleNamespace(profile=SimpleNamespace(lifeline_eligible=lifeline_eligible))

    def _monthly(_user, _date=None):
        return monthly_units

    return user, _monthly


CASES = [
    {"payment": "20000", "expected_units": "28.00", "monthly": "0", "lifeline": True},
    {"payment": "5000", "expected_units": "3.51", "monthly": "0", "lifeline": True},
    {"payment": "80000", "expected_units": "107.99", "monthly": "0", "lifeline": True},
    {"payment": "150000", "expected_units": "163.70", "monthly": "150", "lifeline": True},
    # Second purchase in same month (service already paid; tiers continue from prior kWh)
    {"payment": "5000", "expected_units": "13.29", "monthly": "3.51", "lifeline": True},
    {"payment": "5000", "expected_units": "5.60", "monthly": "28", "lifeline": True},
]


class Command(BaseCommand):
    help = "Verify ERA Q4 2025 billing examples against utils.billing"

    def handle(self, *args, **options):
        import utils.billing as billing_mod

        tariff = get_active_domestic_tariff()
        if tariff is None:
            self.stdout.write(self.style.WARNING("No tariff in DB — using in-memory Q4 2025 blocks"))
            tariff = SimpleNamespace(service_charge=DEFAULT_SERVICE_CHARGE, blocks=SimpleNamespace())
        else:
            self.stdout.write(f"Using tariff: {tariff.tariff_code}")

        ok = 0
        for case in CASES:
            user, monthly_fn = _mock_user(case["lifeline"], Decimal(case["monthly"]))
            original = billing_mod.get_monthly_units_consumed
            billing_mod.get_monthly_units_consumed = monthly_fn

            try:
                units, breakdown = calculate_units_from_payment(
                    Decimal(case["payment"]),
                    user,
                    apply_deductions=False,
                )
                expected = Decimal(case["expected_units"])
                delta = abs(units - expected)
                passed = delta <= Decimal("0.05")
                status = self.style.SUCCESS("PASS") if passed else self.style.ERROR("FAIL")
                self.stdout.write(
                    f"{status}  UGX {case['payment']} -> {units} kWh "
                    f"(expected {expected}, energy={breakdown.energy_cost}, "
                    f"service={breakdown.service_charge}, vat={breakdown.vat}, total={breakdown.total})"
                )
                if passed:
                    ok += 1
            finally:
                billing_mod.get_monthly_units_consumed = original

        self.stdout.write(f"\n{ok}/{len(CASES)} examples matched.")
        if ok < len(CASES):
            self.stdout.write(
                self.style.WARNING('Run "python manage.py seed_era_tariff" if blocks are missing.')
            )
