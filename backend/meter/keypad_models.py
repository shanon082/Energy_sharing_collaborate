"""Encrypted consumer tokens and isolated software-bench identities/receipts."""
import uuid
from django.conf import settings
from django.db import models


class EnergyKeypadToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    allocation = models.OneToOneField("meter.EnergyAllocation", on_delete=models.PROTECT, related_name="keypad_token")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    meter = models.ForeignKey("meter.Meter", on_delete=models.PROTECT)
    meter_number = models.CharField(max_length=100)
    environment = models.CharField(max_length=12)
    amount_wh = models.BigIntegerField()
    lookup_digest = models.CharField(max_length=64, unique=True)
    ciphertext = models.TextField()
    # Issuance freezes command identity even if a DB restore loses its delivery.
    command_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    state = models.CharField(max_length=20, default="ISSUED", choices=[(s, s) for s in ("ISSUED", "DELIVERY_PENDING", "APPLIED")])
    delivery = models.OneToOneField("meter.MeterDelivery", null=True, blank=True, on_delete=models.PROTECT, related_name="keypad_token")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(amount_wh__gt=0), name="keypad_positive_wh"),
            models.CheckConstraint(condition=models.Q(environment__in=["CORE", "SANDBOX", "UGX_DEMO"]), name="keypad_known_environment"),
            models.CheckConstraint(condition=(models.Q(state="ISSUED", delivery__isnull=True) | models.Q(state__in=["DELIVERY_PENDING", "APPLIED"], delivery__isnull=False)), name="keypad_delivery_state")]


class BenchDevice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meter = models.ForeignKey("meter.Meter", on_delete=models.PROTECT, related_name="bench_devices")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    environment = models.CharField(max_length=12)
    binding_epoch = models.PositiveIntegerField(default=1)
    storage_identity = models.UUIDField(null=True, blank=True)
    credential_hash = models.CharField(max_length=128)
    active = models.BooleanField(default=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_application_counter = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["meter"], condition=models.Q(active=True), name="one_active_bench_device_per_meter"),
            models.CheckConstraint(condition=models.Q(environment__in=["CORE", "SANDBOX", "UGX_DEMO"]), name="bench_known_environment")]


class BenchApplicationReceipt(models.Model):
    delivery = models.OneToOneField("meter.MeterDelivery", on_delete=models.PROTECT, related_name="bench_receipt")
    device = models.ForeignKey(BenchDevice, on_delete=models.PROTECT)
    receipt_id = models.UUIDField(unique=True)
    payload_digest = models.CharField(max_length=64)
    application_counter = models.BigIntegerField()
    applied_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["device", "application_counter"], name="bench_device_application_counter"),
            models.CheckConstraint(condition=models.Q(application_counter__gt=0), name="bench_counter_positive")]


class DeviceAttemptBucket(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    started_at = models.DateTimeField()
    count = models.PositiveIntegerField(default=0)
