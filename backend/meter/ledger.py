"""Meter ledger history — credits that build ``meter.units``."""
from __future__ import annotations

from decimal import Decimal

from meter.models import Transaction


LEDGER_CREDIT_TYPES = (
    Transaction.TYPE_CREDIT,
    Transaction.TYPE_TRANSFER_IN,
    Transaction.TYPE_GENERATE_TOKEN,
    Transaction.TYPE_REFUND,
)

TYPE_LABELS = {
    Transaction.TYPE_CREDIT: "Load from wallet",
    Transaction.TYPE_TRANSFER_IN: "Units shared to you",
    Transaction.TYPE_GENERATE_TOKEN: "STS token load",
    Transaction.TYPE_REFUND: "Refund",
    Transaction.TYPE_PURCHASE: "Purchase",
}


def record_meter_ledger_credit(
    meter,
    amount_kwh,
    transaction_type,
    *,
    user=None,
    channel=None,
    source="",
    destination="",
    payment_reference="",
    status=None,
):
    """Append an audit row when kWh is credited to a meter ledger."""
    amount = Decimal(str(amount_kwh))
    if amount <= 0:
        return None

    owner = user or meter.user
    if not owner:
        return None

    return Transaction.objects.create(
        user=owner,
        meter=meter,
        transaction_type=transaction_type,
        amount_kwh=amount,
        status=status or Transaction.STATUS_COMPLETED,
        channel=channel or Transaction.CHANNEL_WEB,
        source=source or "",
        destination=destination or meter.meter_no,
        payment_reference=payment_reference or "",
    )


def get_meter_ledger_history(meter, *, limit=50):
    """
    Return ledger events for a meter plus running totals.
    """
    qs = (
        Transaction.objects.filter(
            meter=meter,
            transaction_type__in=LEDGER_CREDIT_TYPES,
            status=Transaction.STATUS_COMPLETED,
        )
        .order_by("-create_date")[:limit]
    )

    events = []
    events_total = Decimal("0")
    for row in qs:
        amount = Decimal(str(row.amount_kwh or 0))
        events_total += amount
        events.append(
            {
                "id": str(row.transaction_id),
                "transaction_type": row.transaction_type,
                "label": TYPE_LABELS.get(row.transaction_type, row.transaction_type),
                "amount_kwh": float(amount),
                "status": row.status,
                "channel": row.channel,
                "source": row.source or "",
                "destination": row.destination or "",
                "payment_reference": row.payment_reference or "",
                "created_at": row.create_date.isoformat() if row.create_date else None,
            }
        )

    ledger_balance = Decimal(str(meter.units or 0))
    note = None
    if events and abs(events_total - ledger_balance) > Decimal("0.01"):
        note = (
            "Some older ledger credits may not appear in this list. "
            "The ledger total is the authoritative balance."
        )
    elif not events and ledger_balance > 0:
        note = (
            "No individual ledger events recorded yet for this meter. "
            "Future loads and shares will appear here."
        )

    return {
        "meter_no": meter.meter_no,
        "units_balance_kwh": float(ledger_balance),
        "pending_delivery_kwh": float(meter.pending_units or 0),
        "events_total_kwh": float(events_total),
        "events": events,
        "note": note,
    }
