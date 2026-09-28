"""
AMI low-units monitoring: poll ThingsBoard and raise user alerts.

When remaining_units falls at or below the configured threshold (default 5 kWh),
creates an in-app ``MeterNotification`` and queues an email (if the user has one).

Alert rules (avoids spam on every poll tick):
  - Notify when balance crosses from above threshold to at or below threshold.
  - While still low, send a reminder only after the cooldown window (default 6 hours).
"""
from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from meter.models import Meter, MeterBalanceSnapshot, MeterNotification
from meter.services import query_latest_units_from_thingsboard, record_balance_snapshot

logger = logging.getLogger(__name__)


def low_units_threshold_kwh() -> Decimal:
    return Decimal(str(getattr(settings, "AMI_LOW_UNITS_THRESHOLD_KWH", 5)))


def low_units_cooldown() -> timedelta:
    hours = int(getattr(settings, "AMI_LOW_UNITS_ALERT_COOLDOWN_HOURS", 6))
    return timedelta(hours=max(1, hours))


def should_send_low_units_alert(
    meter: Meter, current: Decimal, previous: Decimal | None
) -> bool:
    """True when balance is low and we should create a notification (not on cooldown)."""
    threshold = low_units_threshold_kwh()
    if current > threshold:
        return False
    if previous is None or previous > threshold:
        return True
    return not _recent_low_notification(meter)


def create_low_units_notification(
    meter: Meter,
    units_kwh,
    *,
    source: str = "poll",
    occurred_at=None,
):
    """
    Persist dashboard notification and queue email for a low-units event.
    Returns the created ``MeterNotification`` or None if meter has no user.
    """
    from accounts.tasks import handle_send_low_units_alert_email
    from utils.general import dispatch_task

    user = meter.user
    if not user:
        return None

    units = Decimal(str(units_kwh))
    occurred_at = occurred_at or timezone.now()
    message = (
        f"Low units alert: meter {meter.meter_no} has {float(units):.2f} kWh remaining."
    )

    notification = MeterNotification.objects.create(
        user=user,
        meter=meter,
        device_token=(meter.iot_device_token or "")[:128],
        notification_type=MeterNotification.TYPE_LOW_UNITS,
        units_kwh=units,
        occurred_at=occurred_at,
        message=message,
    )

    if user.email:
        dispatch_task(
            handle_send_low_units_alert_email,
            user.id,
            meter.meter_no,
            float(units),
            notification.id,
        )

    logger.info(
        "Low-units alert (%s): user=%s meter=%s units=%s notification=%s",
        source,
        user.id,
        meter.meter_no,
        units,
        notification.id,
    )
    return notification


def _recent_low_notification(meter: Meter) -> bool:
    return MeterNotification.objects.filter(
        meter=meter,
        notification_type=MeterNotification.TYPE_LOW_UNITS,
        occurred_at__gte=timezone.now() - low_units_cooldown(),
    ).exists()


def check_meter_low_units(meter: Meter) -> dict:
    """
    Read ThingsBoard, snapshot balance, and raise alert if threshold logic matches.
    """
    if meter.architecture != Meter.ARCH_AMI or meter.status != Meter.STATUS_ACTIVE:
        return {"meter_no": meter.meter_no, "skipped": True, "reason": "not_active_ami"}

    token = (meter.iot_device_token or "").strip()
    if not token:
        return {"meter_no": meter.meter_no, "skipped": True, "reason": "no_device_token"}

    previous_snap = (
        MeterBalanceSnapshot.objects.filter(meter=meter)
        .order_by("-recorded_at")
        .first()
    )
    previous = (
        Decimal(str(previous_snap.remaining_kwh)) if previous_snap is not None else None
    )

    ok, msg, data = query_latest_units_from_thingsboard(meter)
    if not ok or not data:
        return {"meter_no": meter.meter_no, "ok": False, "error": msg}

    current = Decimal(str(data["units_kwh"]))
    record_balance_snapshot(
        meter,
        current,
        source=data.get("source", "thingsboard"),
    )

    threshold = low_units_threshold_kwh()
    result = {
        "meter_no": meter.meter_no,
        "units_kwh": float(current),
        "threshold_kwh": float(threshold),
        "low": current <= threshold,
        "alert_sent": False,
    }

    if should_send_low_units_alert(meter, current, previous):
        notification = create_low_units_notification(meter, current, source="poll")
        result["alert_sent"] = notification is not None
        if notification:
            result["notification_id"] = notification.id

    return result


def poll_all_ami_low_units() -> dict:
    """Poll every active AMI meter; used by Celery beat (default every 2 seconds)."""
    meters = Meter.objects.filter(
        architecture=Meter.ARCH_AMI,
        status=Meter.STATUS_ACTIVE,
        is_deleted=False,
    ).select_related("user")

    checked = 0
    alerts = 0
    errors = 0
    for meter in meters:
        outcome = check_meter_low_units(meter)
        if outcome.get("skipped"):
            continue
        checked += 1
        if outcome.get("ok") is False:
            errors += 1
        if outcome.get("alert_sent"):
            alerts += 1

    return {
        "meters_checked": checked,
        "alerts_sent": alerts,
        "errors": errors,
        "threshold_kwh": float(low_units_threshold_kwh()),
    }
