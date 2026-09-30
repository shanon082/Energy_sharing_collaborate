"""
ERA/UEDCL domestic tariff billing engine (Q4 2025 domestic end-user framework).

Tiered energy blocks (monthly cumulative):
  - Lifeline:      first 15 kWh @ 250 UGX/kWh (once per month; eligible consumers only)
  - Normal:        15.1–80 kWh @ 756.2 UGX/kWh
  - Cooking:       80.1–150 kWh @ 412.0 UGX/kWh
  - Super normal:  above 150 kWh @ 756.0 UGX/kWh

Fixed charges:
  - Service charge: 3,360 UGX/month
  - VAT: 18% of (energy + service charge)

Outstanding deductions (loans, pending utility bills) are removed from the payment
before energy units are calculated.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_EVEN
from typing import Optional

from django.db.models import Q, Sum
from django.utils import timezone

logger = logging.getLogger(__name__)

VAT_RATE = Decimal("0.18")
DEFAULT_SERVICE_CHARGE = Decimal("3360.00")
FALLBACK_ENERGY_RATE = Decimal("756.20")


@dataclass
class BillBreakdown:
    energy_units: Decimal
    energy_cost: Decimal
    service_charge: Decimal
    subtotal: Decimal
    vat: Decimal
    total: Decimal
    lifeline_applied: bool = False
    amount_deducted: Decimal = Decimal("0")
    net_payment: Decimal = Decimal("0")


# ---------------------------------------------------------------------------
# Tariff & eligibility
# ---------------------------------------------------------------------------

def get_active_domestic_tariff(on_date: Optional[date] = None):
    """Return the active DOMESTIC ElectricityTariff for a given date (today if None)."""
    from loan.models import ElectricityTariff

    on_date = on_date or timezone.localdate()

    qs = ElectricityTariff.objects.filter(is_active=True, tariff_type="DOMESTIC")

    versioned = (
        qs.filter(effective_from__isnull=False, effective_from__lte=on_date)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=on_date))
        .order_by("-effective_from")
        .first()
    )
    if versioned:
        return versioned

    return qs.order_by("-effective_date").first()


def get_monthly_units_consumed(user, month_date: Optional[date] = None) -> Decimal:
    """Purchased kWh for the cumulative purchase-based tariff bands.

    New settled purchases use their unique allocation source. Historical meter
    purchase rows use payment_reference when present (or row id when absent).
    UnitTransaction self-credits have no economic source identity and may also
    be loan disbursements, so they are never added as another purchase.
    """
    from meter.models import EnergyAllocation, Transaction as MeterTransaction

    month_date = month_date or timezone.localdate()
    allocations = EnergyAllocation.objects.filter(
        owner=user, purchase_intent__status="SETTLED",
        created_at__year=month_date.year,
        created_at__month=month_date.month,
    ).select_related("purchase_intent")
    purchased = Decimal("0")
    represented_references = set()
    for allocation in allocations:
        purchased += allocation.amount_kwh
        represented_references.add(str(allocation.purchase_intent.provider_reference))

    seen_legacy_references = set()
    meter_rows = MeterTransaction.objects.filter(
        user=user,
        transaction_type=MeterTransaction.TYPE_PURCHASE,
        status=MeterTransaction.STATUS_COMPLETED,
        create_date__year=month_date.year,
        create_date__month=month_date.month,
    ).order_by("pk")
    for row in meter_rows:
        reference = row.payment_reference.strip()
        if reference and (reference in represented_references or reference in seen_legacy_references):
            continue
        if reference:
            seen_legacy_references.add(reference)
        # No reference means the legacy row itself is the only stable identity;
        # the reconciliation report flags this weaker provenance.
        purchased += row.amount_kwh

    return purchased


def is_lifeline_eligible(user) -> bool:
    """Pilot: Profile.lifeline_eligible (default True). Production: 6-month avg ≤ 100 kWh/month."""
    try:
        return user.profile.lifeline_eligible
    except Exception:
        return True


def recompute_lifeline_eligibility(user) -> bool:
    """Rolling 6-month average ≤ 100 kWh/month → lifeline eligible."""
    from dateutil.relativedelta import relativedelta
    first_month = timezone.localdate().replace(day=1) - relativedelta(months=5)
    monthly = sum(
        get_monthly_units_consumed(user, first_month + relativedelta(months=step))
        for step in range(6)
    )
    avg_monthly = monthly / Decimal(6)
    eligible = avg_monthly <= Decimal("100")

    try:
        profile = user.profile
        profile.lifeline_eligible = eligible
        profile.save(update_fields=["lifeline_eligible"])
    except Exception as exc:
        logger.warning("Could not update lifeline_eligible for user %s: %s", user.pk, exc)

    return eligible


def get_outstanding_deductions(user) -> Decimal:
    """
    Amount to deduct from a payment before unit calculation.
    Covers disbursed loan balances; extend here for pending utility (negative) bills.
    """
    from loan.models import LoanApplication

    total = Decimal("0")
    for loan in LoanApplication.objects.filter(user=user, status="DISBURSED"):
        balance = Decimal(str(loan.outstanding_balance))
        if balance > 0:
            total += balance
    return total


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _service_charge(tariff, user=None, month_date: Optional[date] = None) -> Decimal:
    """Monthly service fee — charged once on the first purchase of each calendar month."""
    if user is not None and get_monthly_units_consumed(user, month_date) > 0:
        return Decimal("0")
    if tariff is not None:
        return Decimal(str(tariff.service_charge))
    return DEFAULT_SERVICE_CHARGE


def _block_capacity(block, already_bought: Decimal) -> Optional[Decimal]:
    """Units still purchasable in this cumulative monthly band."""
    block_min = Decimal(str(block.min_units))
    block_max = Decimal(str(block.max_units)) if block.max_units is not None else None

    if block_max is None:
        return None

    lower_bound = block_min - 1 if block_min > 0 else Decimal("0")
    return max(Decimal("0"), block_max - max(already_bought, lower_bound))


def _rate_for_block(block, eligible: bool) -> Decimal:
    if block.is_lifeline_block:
        if eligible:
            return Decimal(str(block.rate_per_unit))
        return Decimal(str(block.non_lifeline_rate or FALLBACK_ENERGY_RATE))
    return Decimal(str(block.rate_per_unit))


def _energy_cost_for_units(
    units: Decimal,
    user,
    tariff=None,
    month_date: Optional[date] = None,
) -> tuple[Decimal, bool]:
    """Energy-only cost for `units` kWh given monthly consumption so far."""
    if units <= 0:
        return Decimal("0"), False

    if tariff is None:
        tariff = get_active_domestic_tariff(month_date)

    if tariff is None or not tariff.blocks.exists():
        logger.warning("No active domestic tariff; using flat %.2f UGX/kWh", FALLBACK_ENERGY_RATE)
        return (units * FALLBACK_ENERGY_RATE).quantize(Decimal("0.01")), False

    already_bought = get_monthly_units_consumed(user, month_date)
    eligible = is_lifeline_eligible(user)
    remaining_units = units
    total_cost = Decimal("0")
    lifeline_applied = False

    for block in tariff.blocks.order_by("block_order"):
        if remaining_units <= 0:
            break

        capacity = _block_capacity(block, already_bought)
        if capacity is not None and capacity <= 0:
            continue

        rate = _rate_for_block(block, eligible)
        if block.is_lifeline_block and eligible and rate == Decimal(str(block.rate_per_unit)):
            lifeline_applied = True

        if capacity is not None:
            units_in_block = min(remaining_units, capacity)
        else:
            units_in_block = remaining_units

        total_cost += units_in_block * rate
        already_bought += units_in_block
        remaining_units -= units_in_block

    if remaining_units > 0:
        total_cost += remaining_units * FALLBACK_ENERGY_RATE

    return total_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN), lifeline_applied


def calculate_bill_for_units(
    units: Decimal,
    user,
    tariff=None,
    month_date: Optional[date] = None,
) -> BillBreakdown:
    """Full bill (energy + service + VAT) for a given kWh purchase."""
    energy_cost, lifeline_applied = _energy_cost_for_units(units, user, tariff, month_date)
    if tariff is None:
        tariff = get_active_domestic_tariff(month_date)

    service = _service_charge(tariff, user, month_date)
    subtotal = energy_cost + service
    vat = (subtotal * VAT_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    total = subtotal + vat

    return BillBreakdown(
        energy_units=units,
        energy_cost=energy_cost,
        service_charge=service,
        subtotal=subtotal,
        vat=vat,
        total=total,
        lifeline_applied=lifeline_applied,
    )


def calculate_units_from_payment(
    payment_ugx: Decimal,
    user,
    tariff=None,
    month_date: Optional[date] = None,
    outstanding_bills: Optional[Decimal] = None,
    apply_deductions: bool = True,
) -> tuple[Decimal, BillBreakdown]:
    """
    Convert a payment amount (UGX) to kWh using ERA tiered billing.

    Deducts outstanding bills/loans first, then finds the maximum kWh whose
  full bill (energy + service + VAT) does not exceed the net payment.
    """
    deductions = outstanding_bills if outstanding_bills is not None else Decimal("0")
    if apply_deductions and outstanding_bills is None:
        deductions = get_outstanding_deductions(user)

    net = Decimal(str(payment_ugx)) - deductions
    empty = BillBreakdown(
        energy_units=Decimal("0"),
        energy_cost=Decimal("0"),
        service_charge=Decimal("0"),
        subtotal=Decimal("0"),
        vat=Decimal("0"),
        total=Decimal("0"),
        amount_deducted=deductions,
        net_payment=net,
    )
    if net <= 0:
        return Decimal("0"), empty

    lo = Decimal("0")
    hi = Decimal("2000")
    best_units = Decimal("0")
    best_breakdown = empty

    for _ in range(90):
        mid = ((lo + hi) / 2).quantize(Decimal("0.0001"))
        breakdown = calculate_bill_for_units(mid, user, tariff, month_date)
        if breakdown.total <= net:
            best_units = mid
            best_breakdown = breakdown
            lo = mid
        else:
            hi = mid
        if hi - lo < Decimal("0.0001"):
            break

    # Truncate energy to the allocation quantum, then price that exact grant.
    # Nearest rounding could create energy whose bill exceeds a paid amount.
    granted_units = best_units.quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    if granted_units > 0:
        best_breakdown = calculate_bill_for_units(granted_units, user, tariff, month_date)
    best_breakdown.energy_units = granted_units
    best_breakdown.amount_deducted = deductions
    best_breakdown.net_payment = net
    if granted_units <= 0:
        # Surface fixed charges so the UI can explain why small payments yield 0 kWh.
        min_bill = calculate_bill_for_units(Decimal("0.01"), user, tariff, month_date)
        best_breakdown.service_charge = min_bill.service_charge
        best_breakdown.vat = min_bill.vat
        best_breakdown.subtotal = min_bill.subtotal
        best_breakdown.total = min_bill.total
    return granted_units, best_breakdown


def get_minimum_payment_for_units(
    user,
    tariff=None,
    month_date: Optional[date] = None,
) -> Decimal:
    """Lowest UGX payment that yields any energy under ERA billing rules."""
    bill = calculate_bill_for_units(Decimal("0.01"), user, tariff, month_date)
    return bill.total.quantize(Decimal("0.01"))


def get_monthly_tier_context(user, month_date: Optional[date] = None) -> dict:
    """
    Summarise where the consumer sits in the monthly tier ladder (ERA Code 10.1).
    Used by the estimate API so the UI can explain second-purchase yields.
    """
    month_date = month_date or timezone.localdate()
    already = get_monthly_units_consumed(user, month_date)
    eligible = is_lifeline_eligible(user)
    tariff = get_active_domestic_tariff(month_date)
    blocks = list(tariff.blocks.order_by("block_order")) if tariff else []
    lifeline_block = next((block for block in blocks if block.is_lifeline_block), None)
    lifeline_cap = Decimal(lifeline_block.max_units) if lifeline_block and lifeline_block.max_units is not None else Decimal("0")
    lifeline_remaining = (
        max(Decimal("0"), lifeline_cap - already) if eligible else Decimal("0")
    )
    service_due = _service_charge(tariff, user, month_date) > 0

    current = next((block for block in blocks if block.max_units is None or
                    already < Decimal(block.max_units)), None)
    current_band = ("lifeline" if current and current.is_lifeline_block and eligible else
                    current.block_name.lower().replace(" ", "_") if current else "unconfigured")

    return {
        "monthly_units_consumed": already.quantize(Decimal("0.01")),
        "lifeline_remaining_kwh": lifeline_remaining.quantize(Decimal("0.01")),
        "current_tier_band": current_band,
        "service_charge_due": service_due,
        "lifeline_eligible": eligible,
    }


# Backwards-compatible aliases used by older call sites
def calculate_units_from_cost(
    ugx_amount: Decimal,
    user,
    tariff=None,
    month_date: Optional[date] = None,
    outstanding_bills: Optional[Decimal] = None,
) -> tuple[Decimal, bool]:
    units, breakdown = calculate_units_from_payment(
        ugx_amount, user, tariff, month_date, outstanding_bills=outstanding_bills
    )
    return units, breakdown.lifeline_applied


def calculate_cost_from_units(
    units: Decimal,
    user,
    tariff=None,
    month_date: Optional[date] = None,
) -> tuple[Decimal, bool]:
    """Return total payable UGX (incl. service + VAT) for `units` kWh."""
    breakdown = calculate_bill_for_units(units, user, tariff, month_date)
    return breakdown.total.quantize(Decimal("0.01")), breakdown.lifeline_applied
