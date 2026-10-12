"""Dormant proposed contribution, never a per-payment bonus or financial ledger."""
from decimal import Decimal, ROUND_FLOOR
from django.conf import settings
from django.db.models import Sum, Max, Count, F
from transactions.models import PaymentIntent


def purchase_history_contribution(user):
    # Authoritative source identity is the settled intent, not its several
    # transaction/delivery representations. Exclusions only affect scoring.
    rows = PaymentIntent.objects.filter(
        owner=user, purpose=PaymentIntent.PURCHASE, status=PaymentIntent.SETTLED,
        provider="MTN_PRODUCTION", currency="UGX", settled_at__isnull=False,
        energy_allocation__owner=user, energy_allocation__meter_id=F("meter_id"), energy_allocation__amount_kwh__gt=0,
        purchase_billed_ugx__gt=0, score_exclusion__isnull=True,
    ).exclude(provider_transaction_id="")
    evidence = rows.aggregate(total=Sum("purchase_billed_ugx"), count=Count("pk"), latest=Max("settled_at"))
    total = evidence["total"] or Decimal("0")
    enabled = getattr(settings, "PURCHASE_HISTORY_SCORING_ENABLED", False) is True
    cap = getattr(settings, "PURCHASE_HISTORY_SCORE_CAP", None)
    basis = getattr(settings, "PURCHASE_HISTORY_UGX_PER_POINT", None)
    policy = getattr(settings, "PURCHASE_HISTORY_POLICY_ID", "")
    ready = bool(enabled and policy and cap is not None and basis is not None)
    points = min(cap, int((total / basis).to_integral_value(rounding=ROUND_FLOOR))) if ready else 0
    return {"enabled": ready, "points": points, "qualifying_billed_ugx": str(total),
            "source_count": evidence["count"], "policy_id": policy if ready else None,
            "evidence_updated_at": evidence["latest"].isoformat() if evidence["latest"] else None,
            "status": "ACTIVE" if ready else "AWAITING_BUSINESS_APPROVAL"}
