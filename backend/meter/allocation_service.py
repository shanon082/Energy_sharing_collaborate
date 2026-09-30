"""Source-bound energy accounting for new purchases and approved loans.

The allocation and delivery rows are authoritative for NEW entitlement.
UnitBalance remains a legacy/compatibility total and is never used to authorize
new meter delivery. All energy amounts use exact 0.01 kWh (10 Wh) increments.
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Sum

from meter.models import EnergyAllocation, Meter, MeterDelivery

QUANTUM_KWH = Decimal("0.01")


class AllocationError(ValueError):
    pass


def quantize_source_kwh(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise AllocationError("Energy amount is invalid.") from None
    if not amount.is_finite() or amount <= 0:
        raise AllocationError("Energy amount must be positive and finite.")
    result = amount.quantize(QUANTUM_KWH, rounding=ROUND_HALF_UP)
    if result <= 0:
        raise AllocationError("Energy amount is below the 0.01 kWh precision.")
    return result


def parse_requested_kwh(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise AllocationError("Provide a positive kWh amount.") from None
    if (not amount.is_finite() or amount <= 0 or
            amount != amount.quantize(QUANTUM_KWH)):
        raise AllocationError("Use a positive amount in 0.01 kWh increments.")
    return amount


def authorize_purchase_allocation(intent, units):
    from transactions.models import PaymentIntent

    if (intent.purpose != PaymentIntent.PURCHASE or intent.status != PaymentIntent.SETTLED or
            not intent.meter_id or not intent.purchase_id):
        raise AllocationError("A settled, meter-bound purchase is required.")
    meter = Meter.all_objects.get(pk=intent.meter_id)
    if meter.user_id != intent.owner_id:
        raise AllocationError("Meter ownership changed before allocation.")
    allocation, created = EnergyAllocation.objects.get_or_create(
        purchase_intent=intent,
        defaults={"owner_id": intent.owner_id, "meter": meter,
                  "amount_kwh": quantize_source_kwh(units)},
    )
    if not created:
        raise AllocationError("Purchase allocation already exists.")
    return allocation


def authorize_loan_allocation(disbursement, units):
    loan = disbursement.loan_application
    meter = Meter.all_objects.get(pk=disbursement.meter_id)
    if loan.status != "DISBURSED" or meter.user_id != loan.user_id:
        raise AllocationError("A disbursed loan and its assigned meter are required.")
    allocation, created = EnergyAllocation.objects.get_or_create(
        loan_disbursement=disbursement,
        defaults={"owner_id": loan.user_id, "meter": meter,
                  "amount_kwh": quantize_source_kwh(units)},
    )
    if not created:
        raise AllocationError("Loan allocation already exists.")
    return allocation


def reserve_for_delivery(*, owner, meter_no, amount_kwh):
    """Reserve exact new entitlement, split across source rows if needed."""
    amount = parse_requested_kwh(amount_kwh)
    with transaction.atomic():
        meter = Meter.objects.filter(
            user=owner, meter_no=meter_no, status=Meter.STATUS_ACTIVE,
            architecture=Meter.ARCH_AMI,
        ).first()
        if meter is None:
            raise AllocationError("Choose an active AMI meter assigned to your account.")
        allocations = list(EnergyAllocation.objects.select_for_update().filter(
            owner=owner, meter=meter,
        ).order_by("pk"))
        if not allocations:
            raise AllocationError("No attributable new entitlement exists for this meter; legacy balance needs reconciliation.")
        reserved = {
            row["allocation_id"]: row["total"]
            for row in MeterDelivery.objects.filter(allocation__in=allocations)
            .values("allocation_id").annotate(total=Sum("amount_kwh"))
        }
        remaining = amount
        planned = []
        for allocation in allocations:
            available = allocation.amount_kwh - reserved.get(allocation.pk, Decimal("0.00"))
            if available <= 0:
                continue
            take = min(available, remaining)
            planned.append((allocation, take))
            remaining -= take
            if remaining == 0:
                break
        if remaining != 0:
            raise AllocationError("Insufficient attributable entitlement for this meter.")
        return [MeterDelivery.objects.create(
            allocation=allocation, amount_kwh=take,
        ) for allocation, take in planned]


def entitlement_summary(owner, meter=None):
    allocations = EnergyAllocation.objects.filter(owner=owner)
    if meter is not None:
        allocations = allocations.filter(meter=meter)
    authorized = allocations.aggregate(total=Sum("amount_kwh"))["total"] or Decimal("0.00")
    deliveries = MeterDelivery.objects.filter(allocation__in=allocations)
    reserved = deliveries.aggregate(total=Sum("amount_kwh"))["total"] or Decimal("0.00")
    applied = deliveries.filter(status=MeterDelivery.APPLIED).aggregate(
        total=Sum("amount_kwh"))["total"] or Decimal("0.00")
    return {
        "available_kwh": authorized - reserved,
        "pending_kwh": reserved - applied,
        "confirmed_kwh": applied,
    }
