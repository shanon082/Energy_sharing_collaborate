import random
import string
import uuid
from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils import timezone

from accounts.models import User, TimestampMixin


def generate_numeric_token(length=10):
    """
    Generate a token with ONLY numbers (digits 0-9)
    """
    return ''.join(random.choices(string.digits, k=length))
from accounts.models import User, TimestampMixin


class ActiveMeterQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_deleted=False)


class ActiveMeterManager(models.Manager.from_queryset(ActiveMeterQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


def generate_random_string(length):
    # Keep original for backward compatibility
    characters = string.ascii_uppercase.replace('i', '').replace('O', '') + '123456789'
    random_string = ''.join(random.choice(characters) for _ in range(length))
    return random_string


class Meter(TimestampMixin):
    """
    Model for ESP32 Device to store static IP and other device-related information
    """
    meter_no = models.CharField(max_length=100, unique=True)
    static_ip = models.GenericIPAddressField()
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='devices')
   
    STATUS_ACTIVE = "ACTIVE"
    STATUS_INACTIVE = "INACTIVE"
    STATUS_SUSPENDED = "SUSPENDED"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_INACTIVE, "Inactive"),
        (STATUS_SUSPENDED, "Suspended"),
    ]

    ARCH_STS = "STS"
    ARCH_AMI = "AMI"
    ARCHITECTURE_CHOICES = [
        (ARCH_STS, "STS (token-based)"),
        (ARCH_AMI, "AMI (networked)"),
    ]

    meter_no = models.CharField(max_length=100, unique=True)
    static_ip = models.GenericIPAddressField(null=True, blank=True)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='devices', null=True, blank=True
    )
    units = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    iot_device_token = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        help_text="ThingsBoard device access token used to push purchased units."
    )
    # STS pending units: credited but not yet loaded via STS token.
    # AMI: kWh queued when ThingsBoard delivery fails (auto-retried).
    pending_units = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text=(
            "STS: units waiting for token generation. "
            "AMI: units queued for ThingsBoard delivery when the meter is offline."
        )
    )
    architecture = models.CharField(
        max_length=3,
        choices=ARCHITECTURE_CHOICES,
        default=ARCH_STS,
        help_text="STS = token keypad entry; AMI = networked, direct balance update"
    )
    # Spec additions — Section 4.3
    label = models.CharField(max_length=50, blank=True, default='Home')
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    deactivation_reason = models.CharField(max_length=50, null=True, blank=True)
    deactivation_note = models.TextField(null=True, blank=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    deactivated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='deactivated_meters'
    )
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='meters_deleted_by_user'
    )
    deleted_reason = models.TextField(blank=True, default="")

    objects = ActiveMeterManager()
    all_objects = models.Manager()

    def __str__(self):
        return f"{self.meter_no} - {self.label} ({self.architecture}/{self.status})"


class DeletedMeterRecord(TimestampMixin):
    """
    Immutable audit row created when a meter is removed from a user account.
    The live Meter row is soft-deleted (renamed meter_no) so the number can be
    registered again later.
    """

    ROLE_USER = "USER"
    ROLE_ADMIN = "ADMIN"
    ROLE_CHOICES = [
        (ROLE_USER, "Customer"),
        (ROLE_ADMIN, "Admin"),
    ]

    original_meter_no = models.CharField(max_length=100, db_index=True)
    meter = models.ForeignKey(
        Meter,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deletion_records",
    )
    former_user_id = models.IntegerField(null=True, blank=True, db_index=True)
    former_user_email = models.EmailField(blank=True, default="")
    former_user_phone = models.CharField(max_length=32, blank=True, default="")
    architecture = models.CharField(max_length=3)
    label = models.CharField(max_length=50, blank=True, default="")
    static_ip = models.GenericIPAddressField(null=True, blank=True)
    units_at_deletion = models.DecimalField(max_digits=20, decimal_places=2)
    pending_units_at_deletion = models.DecimalField(
        max_digits=20, decimal_places=2, default=Decimal("0.00")
    )
    had_iot_token = models.BooleanField(default=False)
    status_at_deletion = models.CharField(max_length=12, blank=True, default="")
    deleted_at = models.DateTimeField(default=timezone.now, db_index=True)
    deleted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="meter_deletions_performed",
    )
    deleted_by_role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    reason = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-deleted_at"]
        indexes = [
            models.Index(fields=["original_meter_no", "-deleted_at"]),
            models.Index(fields=["former_user_id", "-deleted_at"]),
        ]

    def __str__(self):
        return f"Deleted {self.original_meter_no} @ {self.deleted_at:%Y-%m-%d}"


class MeterNotification(TimestampMixin):
    """Low-units and other meter alerts (e.g. from ThingsBoard webhooks)."""

    TYPE_LOW_UNITS = "LOW_UNITS"
    TYPE_LOAN_APPLICATION = "LOAN_APPLICATION"
    TYPE_LOAN_DISBURSEMENT = "LOAN_DISBURSEMENT"
    TYPE_LOAN_REPAYMENT = "LOAN_REPAYMENT"
    TYPE_CHOICES = [
        (TYPE_LOW_UNITS, "Low units"),
        (TYPE_LOAN_APPLICATION, "Loan application"),
        (TYPE_LOAN_DISBURSEMENT, "Loan disbursement"),
        (TYPE_LOAN_REPAYMENT, "Loan repayment"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="meter_notifications"
    )
    meter = models.ForeignKey(
        Meter, on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications"
    )
    device_token = models.CharField(max_length=128, blank=True, default="")
    notification_type = models.CharField(
        max_length=32, choices=TYPE_CHOICES, default=TYPE_LOW_UNITS
    )
    units_kwh = models.DecimalField(max_digits=12, decimal_places=4)
    occurred_at = models.DateTimeField()
    is_read = models.BooleanField(default=False)
    message = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["-occurred_at", "-create_date"]
        indexes = [
            models.Index(fields=["user", "is_read", "-occurred_at"]),
            models.Index(fields=["device_token"]),
        ]

    def __str__(self):
        return f"{self.notification_type} — {self.user_id} — {self.units_kwh} kWh"


class MeterBalanceSnapshot(TimestampMixin):
    """Point-in-time remaining kWh reading from ThingsBoard (AMI meters)."""

    meter = models.ForeignKey(
        Meter, on_delete=models.CASCADE, related_name="balance_snapshots"
    )
    remaining_kwh = models.DecimalField(max_digits=14, decimal_places=4)
    recorded_at = models.DateTimeField(db_index=True)
    source = models.CharField(max_length=32, default="thingsboard")

    class Meta:
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(fields=["meter", "-recorded_at"]),
        ]

    def __str__(self):
        return f"{self.meter.meter_no} @ {self.recorded_at}: {self.remaining_kwh} kWh"


class MeterUsageDaily(TimestampMixin):
    """Aggregated daily energy consumption (kWh used) for an AMI meter."""

    SOURCE_SNAPSHOT = "SNAPSHOT"
    SOURCE_THINGSBOARD = "THINGSBOARD"
    SOURCE_WEBHOOK = "WEBHOOK"
    SOURCE_STUB = "STUB"
    SOURCE_CHOICES = [
        (SOURCE_SNAPSHOT, "Balance snapshots"),
        (SOURCE_THINGSBOARD, "ThingsBoard telemetry"),
        (SOURCE_WEBHOOK, "ThingsBoard webhook"),
        (SOURCE_STUB, "Development stub"),
    ]

    meter = models.ForeignKey(
        Meter, on_delete=models.CASCADE, related_name="daily_usage"
    )
    usage_date = models.DateField(db_index=True)
    kwh_used = models.DecimalField(max_digits=12, decimal_places=4)
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES, default=SOURCE_SNAPSHOT)

    class Meta:
        ordering = ["-usage_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["meter", "usage_date"],
                name="unique_meter_usage_date",
            )
        ]
        indexes = [
            models.Index(fields=["meter", "-usage_date"]),
        ]

    def __str__(self):
        return f"{self.meter.meter_no} {self.usage_date}: {self.kwh_used} kWh"



class MeterToken(TimestampMixin):
    TOKEN_SOURCE_CHOICES = [
        ('PURCHASE', 'Purchase'),
        ('LOAN', 'Loan'),
        ('SHARE', 'Share'),
        ('TRANSFER', 'Transfer'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=10, unique=True) 
    units = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    meter = models.ForeignKey('Meter', on_delete=models.CASCADE, related_name='tokens')
    is_used = models.BooleanField(default=False)
    source = models.CharField(max_length=10, choices=TOKEN_SOURCE_CHOICES, default='PURCHASE')
    loan_application = models.ForeignKey('loan.LoanApplication', on_delete=models.SET_NULL, null=True, blank=True, related_name='tokens')
    share_transaction_id = models.CharField(max_length=20, null=True, blank=True)
    share_sender = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='share_tokens_sent'
    )

    def save(self, *args, **kwargs):
        # Ensure token only contains numbers if not already set
        if not self.token:
            self.token = generate_numeric_token(10)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Token: {self.token} | Units: {self.units}"


# --------------------------------------------------------------------------- #
#  Transaction model — Section 6.1 (all 9 transaction types)                  #
# --------------------------------------------------------------------------- #
class Transaction(TimestampMixin):
    """
    Unified transaction record for all money/kWh movements in the system.
    Covers all types defined in spec Section 6.1.
    """
    TYPE_PURCHASE = "PURCHASE"
    TYPE_GENERATE_TOKEN = "GENERATE_TOKEN"
    TYPE_TRANSFER_OUT = "TRANSFER_OUT"
    TYPE_TRANSFER_IN = "TRANSFER_IN"
    TYPE_CREDIT = "CREDIT"
    TYPE_REPAYMENT_AUTO = "REPAYMENT_AUTO"
    TYPE_REPAYMENT_DIRECT = "REPAYMENT_DIRECT"
    TYPE_PENALTY = "PENALTY"
    TYPE_REFUND = "REFUND"

    TRANSACTION_TYPES = [
        (TYPE_PURCHASE, "Purchase"),
        (TYPE_GENERATE_TOKEN, "Generate Token"),
        (TYPE_TRANSFER_OUT, "Transfer Out"),
        (TYPE_TRANSFER_IN, "Transfer In"),
        (TYPE_CREDIT, "Credit"),
        (TYPE_REPAYMENT_AUTO, "Repayment (Auto)"),
        (TYPE_REPAYMENT_DIRECT, "Repayment (Direct)"),
        (TYPE_PENALTY, "Penalty"),
        (TYPE_REFUND, "Refund"),
    ]

    STATUS_COMPLETED = "COMPLETED"
    STATUS_FAILED = "FAILED"
    STATUS_PENDING = "PENDING"
    STATUS_REVERSED = "REVERSED"

    STATUS_CHOICES = [
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_PENDING, "Pending"),
        (STATUS_REVERSED, "Reversed"),
    ]

    CHANNEL_USSD = "USSD"
    CHANNEL_APP = "MOBILE_APP"
    CHANNEL_WEB = "WEB_PORTAL"
    CHANNEL_ADMIN = "ADMIN"

    CHANNEL_CHOICES = [
        (CHANNEL_USSD, "USSD"),
        (CHANNEL_APP, "Mobile App"),
        (CHANNEL_WEB, "Web Portal"),
        (CHANNEL_ADMIN, "Admin"),
    ]

    transaction_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    amount_kwh = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    amount_ugx = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    source = models.CharField(max_length=100, blank=True, default='')  # wallet, purchase, credit
    destination = models.CharField(max_length=100, blank=True, default='')  # meter number, wallet, loan
    meter = models.ForeignKey(Meter, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    sts_token = models.CharField(max_length=30, blank=True, default='')  # 20-digit STS token if applicable
    payment_reference = models.CharField(max_length=100, blank=True, default='')  # Mobile Money ref
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    channel = models.CharField(max_length=12, choices=CHANNEL_CHOICES, default=CHANNEL_USSD)
    failure_reason = models.CharField(max_length=200, blank=True, default='')
    # Link to related loan if applicable
    loan = models.ForeignKey(
        'loan.LoanApplication', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='transactions'
    )
    # Fraud flag
    is_flagged = models.BooleanField(default=False)
    flag_reason = models.CharField(max_length=200, blank=True, default='')
    # Admin refund tracking
    refunded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='refunds_issued'
    )
    refund_reason = models.TextField(blank=True, default='')
    refunded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-create_date']
        indexes = [
            models.Index(fields=['user', 'create_date']),
            models.Index(fields=['transaction_type', 'status']),
            models.Index(fields=['meter', 'create_date']),
            models.Index(fields=['is_flagged']),
        ]

    def __str__(self):
        return f"{self.transaction_type} — {self.user.email} — {self.amount_kwh} kWh ({self.status})"

