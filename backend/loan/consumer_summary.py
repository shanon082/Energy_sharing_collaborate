"""Read-only, exact projections over the whole owner/environment ledger."""
from decimal import Decimal
from django.db.models import DecimalField, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from loan.models import SandboxLoan
from transactions.models import SandboxSettlement
from meter.allocation_service import entitlement_summary


def loans_with_applied(rows):
    paid = SandboxSettlement.objects.filter(intent__sandbox_loan_id=OuterRef("pk")).values(
        "intent__sandbox_loan_id").annotate(total=Sum("applied")).values("total")
    return rows.annotate(_applied_repayments=Coalesce(Subquery(paid), Value(Decimal("0")),
        output_field=DecimalField(max_digits=24, decimal_places=6)))


def consumer_summary(owner, environment, meter=None):
    currency = "UGX" if environment == "UGX_DEMO" else "EUR"
    rows = SandboxLoan.objects.filter(owner=owner, environment=environment, currency=currency)
    if meter is not None:
        rows = rows.filter(meter=meter)
    totals = {key: Decimal("0") for key in ("principal", "total_due", "applied_repayments", "outstanding")}
    active = count = 0
    for loan in loans_with_applied(rows).iterator():
        count += 1
        if loan.status == "REJECTED":
            continue
        active += loan.status == "DISBURSED"
        for key in totals:
            totals[key] += getattr(loan, key)
    energy = entitlement_summary(owner, meter, "UGX_DEMO" if environment == "UGX_DEMO" else "SANDBOX")
    return {"owner_id": owner.pk, "environment": environment, "currency": currency,
        "scope": "METER" if meter else "OWNER", "meter_id": meter.pk if meter else None,
        "loan_count": count, "active_loan_count": active,
        **{key: str(value) for key, value in totals.items()},
        "energy": {key: str(value) for key, value in energy.items()}}
