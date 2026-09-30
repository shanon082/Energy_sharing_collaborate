"""Isolated, persistent simulated meter contract v1. No physical I/O."""

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from meter.models import (
    Meter, MeterDelivery, SimulatedCommand, SimulatedMeter, SimulatedTelemetry,
)


class SimulationError(ValueError):
    pass


def require_simulation():
    if not settings.DEBUG or not getattr(settings, "SIMULATED_METER_ENABLED", False):
        raise SimulationError("Simulated meter delivery is disabled in this environment.")


def _bound_device(delivery, device):
    allocation = delivery.allocation
    meter = Meter.all_objects.get(pk=allocation.meter_id)
    if (device.meter_id != meter.pk or meter.user_id != allocation.owner_id or
            meter.is_deleted or meter.status != Meter.STATUS_ACTIVE or
            meter.architecture != Meter.ARCH_AMI):
        raise SimulationError("Device, allocation and current meter assignment do not match.")


def apply_simulated_command(delivery_id, device_id):
    """Persist application before returning a receipt; deduplicate by command ID."""
    require_simulation()
    with transaction.atomic():
        device = SimulatedMeter.objects.select_for_update().get(device_id=device_id)
        delivery = MeterDelivery.objects.select_related("allocation").get(pk=delivery_id)
        _bound_device(delivery, device)
        if delivery.status not in {MeterDelivery.DISPATCHED, MeterDelivery.OUTCOME_UNKNOWN, MeterDelivery.APPLIED}:
            raise SimulationError("Command was not dispatched.")
        command = SimulatedCommand.objects.filter(command_id=delivery.command_id).first()
        if command:
            if (command.device_id != device.pk or command.delivery_id != delivery.pk or
                    command.amount_kwh != delivery.amount_kwh):
                raise SimulationError("Replayed command payload does not match the applied command.")
        else:
            command = SimulatedCommand.objects.create(
                device=device, delivery=delivery, command_id=delivery.command_id,
                amount_kwh=delivery.amount_kwh,
            )
            device.applied_kwh += delivery.amount_kwh
        device.last_contact_at = timezone.now()
        # Reported feedback is derived from simulated local energy, never from
        # a requested relay state sent by a consumer.
        device.reported_relay_state = (
            "CLOSED" if device.applied_kwh * 1000 > device.consumed_wh else "OPEN"
        )
        device.save(update_fields=["applied_kwh", "last_contact_at", "reported_relay_state"])
        return {
            "contract_version": 1,
            "device_id": str(device.device_id),
            "command_id": str(command.command_id),
            "delivery_id": delivery.pk,
            "amount_kwh": str(command.amount_kwh),
            "applied_at": command.applied_at.isoformat(),
            "reported_relay_state": device.reported_relay_state,
        }


def acknowledge_application(*, device_id, command_id, delivery_id, amount_kwh):
    """Accept only a receipt backed by the simulator's durable command row."""
    require_simulation()
    with transaction.atomic():
        delivery = MeterDelivery.objects.select_for_update().select_related("allocation").get(pk=delivery_id)
        device = SimulatedMeter.objects.get(device_id=device_id)
        _bound_device(delivery, device)
        if (str(delivery.command_id) != str(command_id) or
                delivery.amount_kwh != Decimal(str(amount_kwh))):
            raise SimulationError("Acknowledgement command or amount does not match the reservation.")
        command = SimulatedCommand.objects.filter(
            command_id=delivery.command_id, delivery=delivery, device=device,
            amount_kwh=delivery.amount_kwh,
        ).first()
        if command is None:
            raise SimulationError("No durable simulated application exists for this command.")
        if delivery.status == MeterDelivery.APPLIED:
            return delivery, False
        if delivery.status not in {MeterDelivery.DISPATCHED, MeterDelivery.OUTCOME_UNKNOWN}:
            raise SimulationError("Delivery is not awaiting an acknowledgement.")
        delivery.status = MeterDelivery.APPLIED
        delivery.applied_at = command.applied_at
        delivery.last_error = ""
        delivery.save(update_fields=["status", "applied_at", "last_error"])
        return delivery, True


def dispatch_delivery(delivery_id):
    """Outbox worker: commit dispatch state before any simulator operation."""
    require_simulation()
    with transaction.atomic():
        delivery = MeterDelivery.objects.select_for_update().select_related("allocation").get(pk=delivery_id)
        if delivery.status == MeterDelivery.APPLIED:
            return delivery, False
        if delivery.status in {MeterDelivery.FAILED, MeterDelivery.EXPIRED}:
            return delivery, False
        device = SimulatedMeter.objects.filter(meter_id=delivery.allocation.meter_id).first()
        if device is None:
            delivery.status = MeterDelivery.FAILED
            delivery.last_error = "SIMULATOR_NOT_ENROLLED"
            delivery.save(update_fields=["status", "last_error"])
            return delivery, False
        try:
            _bound_device(delivery, device)
        except SimulationError:
            delivery.status = MeterDelivery.FAILED
            delivery.last_error = "METER_BINDING_CHANGED"
            delivery.save(update_fields=["status", "last_error"])
            return delivery, False
        delivery.status = MeterDelivery.DISPATCHED
        delivery.attempt_count += 1
        delivery.dispatched_at = timezone.now()
        delivery.save(update_fields=["status", "attempt_count", "dispatched_at"])
        device_id = device.device_id
        command_id = delivery.command_id
        amount = delivery.amount_kwh

    try:
        apply_simulated_command(delivery_id, device_id)
        # This step may be lost after durable application; retry uses command_id.
        acknowledged, changed = acknowledge_application(
            device_id=device_id, command_id=command_id,
            delivery_id=delivery_id, amount_kwh=amount,
        )
        return acknowledged, changed
    except Exception:
        with transaction.atomic():
            delivery = MeterDelivery.objects.select_for_update().get(pk=delivery_id)
            if delivery.status == MeterDelivery.DISPATCHED:
                delivery.status = MeterDelivery.OUTCOME_UNKNOWN
                delivery.last_error = "APPLICATION_OUTCOME_UNCONFIRMED"
                delivery.save(update_fields=["status", "last_error"])
        return delivery, False


def record_telemetry(*, device, event_id, boot_id, sequence, cumulative_wh,
                     measured_at, reported_relay_state):
    """Store event identity and preserve measurement order without guessing loss."""
    require_simulation()
    if (sequence < 0 or cumulative_wh < 0 or
            reported_relay_state not in {"OPEN", "CLOSED", "UNKNOWN"}):
        raise SimulationError("Invalid simulator telemetry.")
    with transaction.atomic():
        device = SimulatedMeter.objects.select_for_update().get(pk=device.pk)
        existing = SimulatedTelemetry.objects.filter(device=device, event_id=event_id).first()
        if existing:
            if (existing.boot_id != boot_id or existing.sequence != sequence or
                    existing.cumulative_wh != cumulative_wh or
                    existing.measured_at != measured_at or
                    existing.reported_relay_state != reported_relay_state):
                raise SimulationError("Reused telemetry event identity has a different payload.")
            return existing, False
        prior_boot = device.boot_id
        prior_sequence = device.last_sequence
        prior_counter = device.last_counter_wh
        if prior_boot is None:
            classification = "INITIAL"
        elif prior_boot != boot_id:
            if device.last_measured_at is not None and measured_at <= device.last_measured_at:
                classification = "DELAYED"
            else:
                classification = "RESET"
                device.reset_count += 1
        elif prior_sequence is not None and sequence <= prior_sequence:
            classification = "REORDERED"
        elif device.last_measured_at is not None and measured_at < device.last_measured_at:
            classification = "DELAYED"
        elif prior_counter is not None and cumulative_wh < prior_counter:
            classification = "DISCONTINUITY"
        elif prior_sequence is not None and sequence > prior_sequence + 1:
            classification = "GAP"
        else:
            classification = "ACCEPTED"
        event = SimulatedTelemetry.objects.create(
            device=device, event_id=event_id, boot_id=boot_id, sequence=sequence,
            cumulative_wh=cumulative_wh, measured_at=measured_at,
            reported_relay_state=reported_relay_state, classification=classification,
        )
        if classification not in {"REORDERED", "DELAYED", "DISCONTINUITY"}:
            if prior_boot == boot_id and prior_counter is not None:
                device.consumed_wh += cumulative_wh - prior_counter
            device.boot_id = boot_id
            device.last_sequence = sequence
            device.last_counter_wh = cumulative_wh
            device.last_measured_at = measured_at
            device.reported_relay_state = reported_relay_state
        elif classification == "DISCONTINUITY":
            device.last_sequence = sequence
        device.last_contact_at = timezone.now()
        device.save()
        return event, True


def simulate_consumption(device_id, amount_wh):
    """Local simulator enforcement; never a Django credit decision."""
    require_simulation()
    if not isinstance(amount_wh, int) or amount_wh <= 0:
        raise SimulationError("Consumption must be positive whole Wh.")
    with transaction.atomic():
        device = SimulatedMeter.objects.select_for_update().get(device_id=device_id)
        available_wh = int(device.applied_kwh * 1000) - device.consumed_wh
        if amount_wh > available_wh:
            raise SimulationError("Simulated relay is open: insufficient applied energy.")
        if device.boot_id is None:
            record_telemetry(
                device=device, event_id=uuid.uuid4(), boot_id=uuid.uuid4(),
                sequence=0, cumulative_wh=0, measured_at=timezone.now(),
                reported_relay_state="CLOSED",
            )
            device.refresh_from_db()
        boot_id = device.boot_id or uuid.uuid4()
        return record_telemetry(
            device=device, event_id=uuid.uuid4(), boot_id=boot_id,
            sequence=(device.last_sequence or 0) + 1,
            cumulative_wh=(device.last_counter_wh or 0) + amount_wh,
            measured_at=timezone.now(),
            reported_relay_state="CLOSED" if amount_wh < available_wh else "OPEN",
        )
