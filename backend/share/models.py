from django.db import models
from accounts.models import TimestampMixin, User
from meter.models import Meter
from django.utils.translation import gettext_lazy as _
from accounts.models import Wallet
from django.core.validators import MinValueValidator

IN = "IN"
OUT = "OUT"

DIRECTION_CHOICES = [
    (IN, _("In")),
    (OUT, _("Out"))
]

PENDING = "PENDING"
COMPLETED = "COMPLETED"
FAILED = "FAILED"
CANCELLED = "CANCELLED"

STATUS_CHOICES = [
    (PENDING, _("Pending")),
    (COMPLETED, _("Completed")),
    (FAILED, _("Failed")),
    (CANCELLED, _("Cancelled"))
]

class ShareTransaction(TimestampMixin):
    share_transaction_id = models.CharField(max_length=20, unique=True, null=False, blank=False)
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='share_sent_transactions')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='share_received_transactions')
    units = models.DecimalField(
        max_digits=20, 
        decimal_places=2,
        validators=[MinValueValidator(2.00)]
    )
    meter_send = models.ForeignKey(Meter, on_delete=models.CASCADE, related_name='outgoing_transactions')
    meter_receive = models.ForeignKey(Meter, on_delete=models.CASCADE, related_name='incoming_transactions')
    direction = models.CharField(
        choices=DIRECTION_CHOICES, default=IN, max_length=3
    )
    status = models.CharField(
        choices=STATUS_CHOICES, default=PENDING, max_length=20
    )
    message = models.TextField(null=True, blank=True)
    
    # Security fields
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['share_transaction_id']),
            models.Index(fields=['sender', 'receiver']),
            models.Index(fields=['status', 'create_date']),
        ]
        ordering = ['-create_date']

    def __str__(self):
        return f"Transaction {self.share_transaction_id}: {self.units} units"

class Share(TimestampMixin):
    share_transaction_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='share_transactions')
    units = models.DecimalField(
        default=0.00, max_digits=20, decimal_places=2,
        validators=[MinValueValidator(0.00)]
    )
    status = models.CharField(
        choices=STATUS_CHOICES, default=PENDING, max_length=20
    )
    meter_number = models.ForeignKey(Meter, on_delete=models.CASCADE, related_name='share_records')
    message = models.TextField(null=True, blank=True)
    share_transaction_reference = models.TextField(null=True, blank=True)
    
    # Security fields
    is_verified = models.BooleanField(default=False)
    verification_code = models.CharField(max_length=6, null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['share_transaction_id']),
            models.Index(fields=['wallet', 'status']),
        ]
        ordering = ['-create_date']

    def __str__(self):
        return f"{self.share_transaction_id} - {self.wallet.user.username}"

class TransferRequest(TimestampMixin):
    """
    Separate model for transfer requests that require admin approval
    """
    request_id = models.CharField(max_length=20, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transfer_requests')
    old_meter = models.ForeignKey(Meter, on_delete=models.CASCADE, related_name='old_transfers')
    new_meter = models.ForeignKey(Meter, on_delete=models.CASCADE, related_name='new_transfers')
    units_to_transfer = models.DecimalField(max_digits=20, decimal_places=2)
    status = models.CharField(
        choices=[
            ('PENDING', 'Pending Approval'),
            ('APPROVED', 'Approved'),
            ('REJECTED', 'Rejected'),
            ('COMPLETED', 'Completed')
        ],
        default='PENDING',
        max_length=20
    )
    admin_notes = models.TextField(null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_transfers')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Transfer {self.request_id}: {self.old_meter.meter_number} -> {self.new_meter.meter_number}"