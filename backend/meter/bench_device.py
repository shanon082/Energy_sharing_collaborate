"""Online keypad protocol v1 for an isolated software bench, NOT household control."""
import hashlib
import json
import re
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.db import IntegrityError, connection, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.debug import sensitive_variables
from rest_framework.exceptions import APIException

from meter.energy_tokens import authorized_source, digest_token
from meter.models import (BenchApplicationReceipt, BenchDevice, DeviceAttemptBucket,
                          EnergyAllocation, EnergyKeypadToken, Meter, MeterDelivery)


class BenchError(APIException):
    def __init__(self, code="TOKEN_UNAVAILABLE", message="Token unavailable for this device.", status=404):
        self.status_code = status
        super().__init__({"code": code, "message": message})


def require_bench():
    db = connection.settings_dict
    if (getattr(settings, "BENCH_DEVICE_ENABLED", False) is not True
            or getattr(settings, "DEVICE_BENCH_ISOLATED", False) is not True
            or getattr(settings, "ALWAYSDATA_TESTING", False)
            or db["HOST"] not in {"127.0.0.1", "localhost", "::1"}
            or not db["NAME"].startswith(("gpawa_bench_", "test_gpawa_bench_"))):
        raise BenchError("BENCH_DISABLED", "Device testing requires the separate isolated bench profile/database.", 404)


def rate_attempt(identity, limit):
    """One PostgreSQL bucket per identity, shared across processes/restarts."""
    key = hashlib.sha256(identity.encode()).hexdigest()
    now = timezone.now()
    with transaction.atomic():
        DeviceAttemptBucket.objects.get_or_create(key=key, defaults={"started_at": now})
        row = DeviceAttemptBucket.objects.select_for_update().get(pk=key)
        if now - row.started_at >= timedelta(minutes=1):
            row.started_at, row.count = now, 0
        if row.count >= limit:
            raise BenchError("DEVICE_RATE_LIMITED", "Too many attempts. Retry after one minute.", 429)
        row.count += 1
        row.save(update_fields=["started_at", "count"])


@sensitive_variables()
def authenticate_device(request):
    require_bench()
    rate_attempt("ip:" + str(request.META.get("REMOTE_ADDR", "unknown")), 120)
    try:
        identity = uuid.UUID(str(request.headers.get("X-Bench-Device-Id")))
    except (ValueError, TypeError):
        raise BenchError("DEVICE_UNAUTHORIZED", "Device authentication failed.", 401) from None
    credential = request.headers.get("X-Bench-Device-Token") or ""
    device = BenchDevice.objects.select_related("meter").filter(pk=identity).first()
    if (not device or not credential or not check_password(credential, device.credential_hash)
            or not device.active or device.revoked_at or device.meter.is_deleted
            or device.meter.status != "ACTIVE" or device.meter.user_id != device.owner_id):
        raise BenchError("DEVICE_UNAUTHORIZED", "Device authentication failed.", 401)
    rate_attempt("device:" + str(device.pk), 30)
    return device


def payload_digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def bound(device, token, allocation):
    meter = Meter.all_objects.get(pk=allocation.meter_id)
    if (not device.active or device.revoked_at or meter.is_deleted or meter.status != "ACTIVE"
            or device.meter_id != token.meter_id or token.meter_id != allocation.meter_id
            or meter.meter_no != token.meter_number or meter.user_id != token.owner_id
            or allocation.owner_id != token.owner_id or device.owner_id != token.owner_id
            or token.environment != allocation.accounting_environment or device.environment != token.environment
            or meter.sandbox_inventory != (token.environment != "CORE")
            or token.amount_wh != allocation.amount_kwh * 1000 or not authorized_source(allocation)):
        raise BenchError()


@sensitive_variables()
def redeem(device, body):
    require_bench()
    if (not isinstance(body, dict) or type(body.get("contract_version")) is not int
            or body.get("contract_version") != 1 or set(body) != {"contract_version", "token"}
            or not isinstance(body.get("token"), str) or not re.fullmatch(r"[0-9]{15}", body["token"])):
        raise BenchError("REQUEST_INVALID", "Use protocol v1 and a 15-digit token.", 400)
    row = EnergyKeypadToken.objects.filter(lookup_digest=digest_token(body["token"])).first()
    if row is None:
        raise BenchError()
    with transaction.atomic():
        device = BenchDevice.objects.select_for_update().get(pk=device.pk)
        allocation = EnergyAllocation.objects.select_for_update().get(pk=row.allocation_id)
        token = EnergyKeypadToken.objects.select_for_update().get(pk=row.pk)
        bound(device, token, allocation)
        if device.storage_identity is None:
            raise BenchError("DEVICE_STORAGE_REQUIRED", "Initialize the durable software journal first.", 409)
        if token.state == "APPLIED":
            raise BenchError("TOKEN_ALREADY_USED", "Token already used.", 409)
        if token.delivery_id:
            delivery = MeterDelivery.objects.get(pk=token.delivery_id)
            if delivery.bench_device_id != device.pk or delivery.transport != "KEYPAD_BENCH":
                raise BenchError()
            return delivery.command_payload
        if token.state != "ISSUED" or allocation.deliveries.exists():
            raise BenchError("RESERVATION_CONFLICT", "Allocation requires delivery reconciliation.", 409)
        delivery = MeterDelivery.objects.create(allocation=allocation, amount_kwh=allocation.amount_kwh,
            command_id=token.command_id, transport="KEYPAD_BENCH", bench_device=device,
            status=MeterDelivery.DISPATCHED, dispatched_at=timezone.now(), attempt_count=1)
        payload = {"contract_version": 1, "type": "BENCH_CREDIT", "bench_only": True,
            "device_id": str(device.pk), "meter_number": token.meter_number,
            "binding_epoch": device.binding_epoch, "environment": token.environment,
            "storage_id": str(device.storage_identity),
            "allocation_id": allocation.pk, "delivery_id": delivery.pk,
            "command_id": str(delivery.command_id), "credit_wh": token.amount_wh}
        payload["payload_digest"] = payload_digest(payload)
        delivery.command_payload = payload
        delivery.save(update_fields=["command_payload"])
        token.delivery = delivery
        token.state = "DELIVERY_PENDING"
        token.save(update_fields=["delivery", "state"])
        return payload


@sensitive_variables()
def acknowledge(device, body):
    require_bench()
    try:
        required = {"contract_version", "type", "device_id", "command_id", "delivery_id", "allocation_id",
                    "binding_epoch", "environment", "storage_id", "credit_wh", "payload_digest", "receipt_id",
                    "application_counter", "applied_at"}
        if not isinstance(body, dict) or set(body) != required or body["type"] != "BENCH_APPLIED":
            raise ValueError
        for key in ("contract_version", "delivery_id", "allocation_id", "binding_epoch", "credit_wh", "application_counter"):
            if type(body[key]) is not int or not 0 < body[key] <= 2**63 - 1:
                raise ValueError
        if not isinstance(body["receipt_id"], str) or not isinstance(body["applied_at"], str):
            raise ValueError
        receipt_id = uuid.UUID(body["receipt_id"])
        measured = parse_datetime(body["applied_at"])
        if measured is None or timezone.is_naive(measured) or measured > timezone.now() + timedelta(minutes=5):
            raise ValueError
    except (ValueError, TypeError):
        raise BenchError("RECEIPT_INVALID", "Application receipt is invalid.", 400) from None
    with transaction.atomic():
        device = BenchDevice.objects.select_for_update().get(pk=device.pk)
        row = EnergyKeypadToken.objects.filter(delivery_id=body["delivery_id"]).first()
        if not row:
            raise BenchError()
        allocation = EnergyAllocation.objects.select_for_update().get(pk=row.allocation_id)
        token = EnergyKeypadToken.objects.select_for_update().get(pk=row.pk)
        bound(device, token, allocation)
        delivery = MeterDelivery.objects.select_for_update().get(pk=token.delivery_id)
        command = delivery.command_payload
        keys = ("contract_version", "device_id", "command_id", "delivery_id", "allocation_id", "binding_epoch", "environment", "storage_id", "credit_wh", "payload_digest")
        if (delivery.transport != "KEYPAD_BENCH" or delivery.bench_device_id != device.pk
                or any(body[key] != command.get(key) for key in keys)
                or measured < delivery.created_at - timedelta(minutes=5)):
            raise BenchError("RECEIPT_BINDING_MISMATCH", "Application receipt does not match its command.", 409)
        existing = BenchApplicationReceipt.objects.filter(delivery=delivery).first()
        if existing:
            if (existing.receipt_id != receipt_id or existing.application_counter != body["application_counter"]
                    or existing.applied_at != measured or existing.payload_digest != body["payload_digest"]):
                raise BenchError("RECEIPT_CONFLICT", "Receipt identity or content changed.", 409)
            return False
        if (token.state != "DELIVERY_PENDING" or delivery.status not in {"DISPATCHED", "OUTCOME_UNKNOWN"}
               ):
            raise BenchError("RECONCILIATION_REQUIRED", "Application counter/order needs reconciliation.", 409)
        try:
            with transaction.atomic():
                BenchApplicationReceipt.objects.create(delivery=delivery, device=device, receipt_id=receipt_id,
                    payload_digest=body["payload_digest"], application_counter=body["application_counter"], applied_at=measured)
        except IntegrityError:
            raise BenchError("RECEIPT_CONFLICT", "Receipt identity was already used.", 409) from None
        token.state = "APPLIED"
        token.save(update_fields=["state"])
        delivery.status, delivery.applied_at = MeterDelivery.APPLIED, measured
        delivery.save(update_fields=["status", "applied_at"])
        device.last_application_counter = max(device.last_application_counter, body["application_counter"])
        device.save(update_fields=["last_application_counter"])
        return True


def device_session(device, body):
    require_bench()
    try:
        if (not isinstance(body, dict) or set(body) != {"contract_version", "storage_id", "initialize", "application_counter"}
                or type(body["contract_version"]) is not int or body["contract_version"] != 1
                or type(body["initialize"]) is not bool or type(body["application_counter"]) is not int
                or not 0 <= body["application_counter"] <= 2**63 - 1 or not isinstance(body["storage_id"], str)):
            raise ValueError
        storage_id = uuid.UUID(body["storage_id"])
    except (ValueError, TypeError):
        raise BenchError("REQUEST_INVALID", "Invalid durable-journal handshake.", 400) from None
    with transaction.atomic():
        device = BenchDevice.objects.select_for_update().get(pk=device.pk)
        if not device.active or device.revoked_at:
            raise BenchError("DEVICE_UNAUTHORIZED", "Device authentication failed.", 401)
        if device.storage_identity is None:
            if not body["initialize"] or body["application_counter"] != 0 or MeterDelivery.objects.filter(bench_device=device).exists():
                raise BenchError("RECONCILIATION_REQUIRED", "Journal initialization requires a fresh unused device binding.", 409)
            device.storage_identity = storage_id
            device.save(update_fields=["storage_identity"])
        if device.storage_identity != storage_id or body["application_counter"] < device.last_application_counter:
            raise BenchError("DEVICE_STORAGE_RESET", "Device journal changed or regressed. Reconciliation required.", 409)
        return {"bench_only": True, "device_id": str(device.pk), "storage_id": str(storage_id),
                "environment": device.environment, "meter_number": device.meter.meter_no,
                "binding_epoch": device.binding_epoch}
