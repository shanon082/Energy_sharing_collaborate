from __future__ import annotations

from decimal import Decimal

from django.utils import timezone

from meter.models import Meter, MeterNotification


def create_system_notification(
    *,
    user,
    notification_type: str,
    message: str,
    meter: Meter | None = None,
    units_kwh: Decimal | float | int = Decimal("0"),
):
    """
    Create an in-app dashboard alert for non-meter-specific events like loans.
    """
    return MeterNotification.objects.create(
        user=user,
        meter=meter,
        device_token=(meter.iot_device_token or "")[:128] if meter else "",
        notification_type=notification_type,
        units_kwh=Decimal(str(units_kwh)),
        occurred_at=timezone.now(),
        message=message,
    )
