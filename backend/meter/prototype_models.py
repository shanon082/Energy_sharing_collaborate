"""Commissioned AC laboratory transport; credit remains in EnergyAllocation/MeterDelivery."""
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
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
    recovery_enabled = models.BooleanField(default=False)
    recovery_pending = models.BooleanField(default=False)
    recovery_target_consumed_uwh = models.PositiveBigIntegerField(default=0)
    recovery_target_wh = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['meter'], condition=models.Q(active=True), name='one_active_ac_lab_per_meter'),
            models.CheckConstraint(condition=models.Q(environment__in=['UGX_DEMO', 'SANDBOX'], hardware_class='AC_LAB'), name='ac_lab_device_domain'),
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
    checkpoint_required = models.BooleanField(default=False)
    credit_checkpoint = models.JSONField(null=True)
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
    recovery_settled = models.BooleanField(default=False)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['device', 'boot_id', 'sequence'], name='ac_lab_telemetry_identity')]


class PrototypeMeasurementTransition(models.Model):
    """Idempotent server receipt for the credit-only to metered baseline transition."""
    PREPARED = 'PREPARED'
    COMMITTED = 'COMMITTED'
    STATES = [(PREPARED, 'Prepared'), (COMMITTED, 'Committed')]

    device = models.OneToOneField(PrototypeDevice, on_delete=models.PROTECT,
                                  related_name='measurement_transition')
    transition_id = models.UUIDField(unique=True)
    receipt_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    state = models.CharField(max_length=9, choices=STATES, default=PREPARED)
    had_baseline = models.BooleanField()
    old_baseline_wh = models.PositiveBigIntegerField(null=True)
    baseline_wh = models.PositiveBigIntegerField()
    application_counter = models.PositiveBigIntegerField()
    credited_uwh = models.PositiveBigIntegerField()
    consumed_uwh = models.PositiveBigIntegerField()
    uncertain_uwh = models.PositiveBigIntegerField()
    payload = models.JSONField()
    prepared_at = models.DateTimeField(auto_now_add=True)
    committed_at = models.DateTimeField(null=True)


class PrototypeOutputAuthorization(models.Model):
    ACTIVE = 'ACTIVE'
    REVOKED = 'REVOKED'
    EXPIRED = 'EXPIRED'
    STATES = [(ACTIVE, 'Active'), (REVOKED, 'Revoked'), (EXPIRED, 'Expired')]
    AUTO = 'AUTO'
    MANUAL = 'MANUAL'
    RESTART_POLICIES = [(AUTO, 'Automatic after safety checks'), (MANUAL, 'Manual arming required')]

    device = models.ForeignKey(PrototypeDevice, on_delete=models.PROTECT,
                               related_name='output_authorizations')
    state = models.CharField(max_length=8, choices=STATES, default=ACTIVE)
    restart_policy = models.CharField(max_length=6, choices=RESTART_POLICIES, default=MANUAL)
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    granted_by = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='+')
    reason = models.CharField(max_length=240)
    evidence = models.JSONField()
    revoked_at = models.DateTimeField(null=True)
    revoked_by = models.ForeignKey('accounts.User', on_delete=models.PROTECT, null=True, related_name='+')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['device'], condition=models.Q(state='ACTIVE'),
                                    name='one_active_output_authorization_per_device'),
        ]
        indexes = [models.Index(fields=['device', 'state', '-expires_at'])]


class PrototypeOutputAuthorizationEvent(models.Model):
    GRANTED = 'GRANTED'
    REVOKED = 'REVOKED'
    EXPIRED = 'EXPIRED'
    ACTIONS = [(GRANTED, 'Granted'), (REVOKED, 'Revoked'), (EXPIRED, 'Expired')]

    authorization = models.ForeignKey(PrototypeOutputAuthorization, on_delete=models.PROTECT,
                                      related_name='events')
    device = models.ForeignKey(PrototypeDevice, on_delete=models.PROTECT,
                               related_name='output_authorization_events')
    actor = models.ForeignKey('accounts.User', on_delete=models.PROTECT, null=True, related_name='+')
    action = models.CharField(max_length=7, choices=ACTIONS)
    occurred_at = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=240)
    details = models.JSONField(default=dict)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['authorization', 'action'],
                                    name='one_output_authorization_event_per_action'),
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError('Output authorization events are immutable.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Output authorization events are immutable.')
