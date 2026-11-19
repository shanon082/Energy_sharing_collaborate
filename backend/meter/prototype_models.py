"""Commissioned AC laboratory transport; credit remains in EnergyAllocation/MeterDelivery."""
import uuid
from django.conf import settings
from django.db import models


class PrototypeDevice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meter = models.ForeignKey('meter.Meter', on_delete=models.PROTECT, related_name='prototype_devices')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    provisioned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    credential_hash = models.CharField(max_length=128)
    credential_fingerprint = models.CharField(max_length=64, unique=True)
    storage_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    binding_epoch = models.PositiveIntegerField(default=1)
    environment = models.CharField(max_length=12, default='UGX_DEMO', editable=False)
    hardware_class = models.CharField(max_length=12, default='AC_LAB', editable=False)
    output_enabled = models.BooleanField(default=False, editable=False)
    active = models.BooleanField(default=True)
    revoked_at = models.DateTimeField(null=True)
    revoked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")
    last_contact_at = models.DateTimeField(null=True)
    boot_id = models.UUIDField(null=True)
    boot_counter = models.PositiveBigIntegerField(default=0)
    telemetry_sequence = models.PositiveBigIntegerField(default=0)
    application_counter = models.PositiveBigIntegerField(default=0)
    observed_application_counter = models.PositiveBigIntegerField(default=0)
    consumed_uwh = models.PositiveBigIntegerField(default=0)
    uncertain_uwh = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['meter'], condition=models.Q(active=True), name='one_active_ac_lab_per_meter'),
            models.CheckConstraint(condition=models.Q(environment__in=['UGX_DEMO', 'SANDBOX'], hardware_class='AC_LAB', output_enabled=False), name='ac_lab_output_disabled'),
        ]


class PrototypeBoot(models.Model):
    device = models.ForeignKey(PrototypeDevice, on_delete=models.PROTECT)
    boot_id = models.UUIDField()
    boot_counter = models.PositiveBigIntegerField()
    initialized_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['device', 'boot_id'], name='ac_lab_boot_identity'),
                       models.UniqueConstraint(fields=['device', 'boot_counter'], name='ac_lab_boot_counter')]


class PrototypeCommand(models.Model):
    delivery = models.OneToOneField('meter.MeterDelivery', on_delete=models.PROTECT, related_name='prototype_command')
    device = models.ForeignKey(PrototypeDevice, on_delete=models.PROTECT, related_name='commands')
    sequence = models.PositiveBigIntegerField()
    receipt_id = models.UUIDField(null=True, unique=True)
    applied_at = models.DateTimeField(null=True)
    received_at = models.DateTimeField(null=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['device', 'sequence'], name='ac_lab_command_sequence'),
                       models.UniqueConstraint(fields=['device'], condition=models.Q(receipt_id__isnull=True), name='ac_lab_one_pending_command')]


class PrototypeTelemetry(models.Model):
    device = models.ForeignKey(PrototypeDevice, on_delete=models.PROTECT, related_name='telemetry')
    boot_id = models.UUIDField()
    sequence = models.PositiveBigIntegerField()
    measured_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField()
    class Meta:
        constraints = [models.UniqueConstraint(fields=['device', 'boot_id', 'sequence'], name='ac_lab_telemetry_identity')]
