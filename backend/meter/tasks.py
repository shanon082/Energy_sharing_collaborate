from datetime import timedelta

from celery import shared_task
from django.utils import timezone
from django.conf import settings
from django.db.models import Q

from meter.models import Meter, MeterDelivery
from meter.usage_service import snapshot_all_ami_meters, sync_meter_usage


@shared_task(name="meter.tasks.snapshot_ami_meter_balances")
def snapshot_ami_meter_balances():
    """Periodic task: record remaining_units for all active AMI meters."""
    return snapshot_all_ami_meters()


@shared_task(name="meter.tasks.aggregate_daily_ami_usage")
def aggregate_daily_ami_usage():
    """Periodic task: aggregate yesterday's usage from snapshots / ThingsBoard."""
    yesterday = timezone.localdate() - timedelta(days=1)
    start = yesterday - timedelta(days=7)
    count = 0
    for meter in Meter.objects.filter(architecture=Meter.ARCH_AMI, status=Meter.STATUS_ACTIVE):
        sync_meter_usage(meter, start, yesterday)
        count += 1
    return count


@shared_task(name="meter.tasks.retry_pending_ami_deliveries")
def retry_pending_ami_deliveries():
    """Retry queued AMI unit deliveries when meters come back online."""
    from meter.ami_delivery import retry_all_pending_ami_deliveries

    return retry_all_pending_ami_deliveries()


@shared_task(name="meter.tasks.dispatch_simulated_outbox")
def dispatch_simulated_outbox():
    """Poll durable reservations; never invoke physical gateway code."""
    if not settings.DEBUG or not getattr(settings, "SIMULATED_METER_ENABLED", False):
        return 0
    from meter.simulation import dispatch_delivery

    stale = timezone.now() - timedelta(seconds=30)
    ids = list(MeterDelivery.objects.filter(
        Q(status__in=[MeterDelivery.QUEUED, MeterDelivery.OUTCOME_UNKNOWN])
        | Q(status=MeterDelivery.DISPATCHED, dispatched_at__lte=stale)
    ).order_by("created_at").values_list("pk", flat=True)[:100])
    for delivery_id in ids:
        dispatch_delivery(delivery_id)
    return len(ids)


@shared_task(name="meter.tasks.poll_ami_low_units", ignore_result=True, expires=1)
def poll_ami_low_units():
    """Poll ThingsBoard every few seconds; alert when remaining_units <= threshold."""
    from meter.low_units_alerts import poll_all_ami_low_units

    return poll_all_ami_low_units()
