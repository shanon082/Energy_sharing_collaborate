"""
AMI unit delivery and offline reconciliation.

When a meter cannot be reached (or ThingsBoard rejects telemetry), credited kWh
are stored in ``meter.pending_units`` and retried automatically until delivery
succeeds. On success, units move from pending to the ledger (``meter.units``).

Delivery also updates the ThingsBoard ``remaining_units`` shared attribute so
"Check Units" reflects credits even when the physical device is offline.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import F

from meter.services import (
    increment_shared_remaining_units,
    push_units_to_thingsboard,
)

logger = logging.getLogger(__name__)


def attempt_ami_delivery(meter, units, reference_id=""):
    """
    Push kWh to ThingsBoard and sync the remaining_units shared attribute.
    Returns (success: bool, message: str).
    """
    units = Decimal(str(units))
    if units <= 0:
        return False, "Amount must be positive."

    push_ok, push_msg = push_units_to_thingsboard(meter, units, reference_id=reference_id)
    if not push_ok:
        return False, push_msg

    sync_ok, sync_msg = increment_shared_remaining_units(meter, units)
    if not sync_ok:
        logger.warning(
            "AMI delivery: telemetry accepted but remaining_units sync failed for meter %s: %s",
            meter.meter_no,
            sync_msg,
        )
        # Telemetry was accepted — treat as delivered; attribute sync can retry on read.
    return True, push_msg


def credit_ami_meter(
    meter,
    units,
    reference_id="",
    *,
    ledger_type=None,
    ledger_source=None,
    payment_reference="",
):
    """
    Try immediate AMI delivery. On failure, queue in pending_units.
    Always returns True when units are accounted for (delivered or queued).
    """
    units = Decimal(str(units))
    ok, msg = attempt_ami_delivery(meter, units, reference_id=reference_id)
    if ok:
        with transaction.atomic():
            meter.__class__.objects.filter(pk=meter.pk).update(
                units=F("units") + units,
            )
        meter.refresh_from_db(fields=["units", "pending_units"])
        from meter.ledger import record_meter_ledger_credit
        from meter.models import Transaction

        record_meter_ledger_credit(
            meter,
            units,
            ledger_type or Transaction.TYPE_CREDIT,
            source=ledger_source or "wallet_load",
            destination=meter.meter_no,
            payment_reference=payment_reference or reference_id or "",
        )
        logger.info(
            "AMI meter %s: delivered %.4f kWh (ledger %.4f)",
            meter.meter_no,
            units,
            meter.units,
        )
        return True

    with transaction.atomic():
        meter.__class__.objects.filter(pk=meter.pk).update(
            pending_units=F("pending_units") + units,
        )
    meter.refresh_from_db(fields=["units", "pending_units"])
    logger.warning(
        "AMI meter %s: queued %.4f kWh for delivery (pending %.4f): %s",
        meter.meter_no,
        units,
        meter.pending_units,
        msg,
    )
    return True


def retry_pending_for_meter(meter):
    """
    Attempt to deliver all pending_units for one AMI meter.
    Returns dict with delivered_kwh, remaining_pending_kwh, message.
    """
    meter.refresh_from_db(fields=["pending_units", "units", "architecture", "meter_no"])
    if meter.architecture != meter.ARCH_AMI:
        return {
            "delivered_kwh": 0.0,
            "remaining_pending_kwh": float(meter.pending_units),
            "message": "Not an AMI meter.",
        }

    pending = Decimal(str(meter.pending_units))
    if pending <= 0:
        return {
            "delivered_kwh": 0.0,
            "remaining_pending_kwh": 0.0,
            "message": "No pending delivery.",
        }

    ok, msg = attempt_ami_delivery(meter, pending, reference_id="pending-retry")
    if not ok:
        return {
            "delivered_kwh": 0.0,
            "remaining_pending_kwh": float(pending),
            "message": msg,
        }

    with transaction.atomic():
        meter.__class__.objects.filter(pk=meter.pk).update(
            units=F("units") + pending,
            pending_units=Decimal("0"),
        )
    meter.refresh_from_db(fields=["units", "pending_units"])
    from meter.ledger import record_meter_ledger_credit
    from meter.models import Transaction

    record_meter_ledger_credit(
        meter,
        pending,
        Transaction.TYPE_CREDIT,
        source="pending_delivery",
        destination=meter.meter_no,
        payment_reference="pending-retry",
    )
    logger.info(
        "AMI meter %s: reconciled %.4f kWh from pending (ledger %.4f)",
        meter.meter_no,
        pending,
        meter.units,
    )
    return {
        "delivered_kwh": float(pending),
        "remaining_pending_kwh": 0.0,
        "message": "Pending units delivered.",
    }


def retry_all_pending_ami_deliveries():
    """Retry delivery for every AMI meter with pending_units > 0."""
    from meter.models import Meter

    meters = Meter.objects.filter(
        architecture=Meter.ARCH_AMI,
        pending_units__gt=0,
        is_deleted=False,
    )
    delivered = 0
    still_pending = 0
    for meter in meters:
        result = retry_pending_for_meter(meter)
        if result["delivered_kwh"] > 0:
            delivered += 1
        elif result["remaining_pending_kwh"] > 0:
            still_pending += 1
    return {
        "meters_delivered": delivered,
        "meters_still_pending": still_pending,
    }
