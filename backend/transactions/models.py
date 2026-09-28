from django.db import models
from accounts.models import TimestampMixin, User
from meter.models import Meter
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField
from accounts.models import Wallet

# Create your models here.

IN = "IN"
OUT = "OUT"

DIRECTION_CHOICES = [
    (IN, _("In")),
    (OUT, _("Out"))
]

PENDING = "PENDING"
COMPLETED = "COMPLETED"
FAILED = "FAILED"

STATUS_CHOICES = [
    (PENDING, _("Pending")),
    (COMPLETED, _("Completed")),
    (FAILED, _("Failed"))
]

class UnitTransaction(TimestampMixin):
    """
    Model for tracking unit transactions (sharing or transferring units between users/devices)
    """
    transaction_id = models.CharField(max_length=16, unique=True, null=True, blank=True)
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_transactions')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_transactions')
    units = models.FloatField()  # Amount of units transferred
    meter = models.ForeignKey(Meter, on_delete=models.SET_NULL, null=True, blank=True)
    direction = models.CharField(
        choices=DIRECTION_CHOICES, default=IN, max_length=3
    )
    status = models.CharField(
        choices=STATUS_CHOICES, default=PENDING, max_length=20
    )
    message = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Transaction {self.transaction_id} from {self.sender.username}"
    

class Transaction(TimestampMixin):
    transaction_id = models.CharField(max_length=16, unique=True, null=True, blank=True)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE)
    amount = models.DecimalField(
        default=0.00, max_digits=20, decimal_places=2, null=True
    )
    status = models.CharField(
        choices=STATUS_CHOICES, default=PENDING, max_length=20
    )
    phone_number = PhoneNumberField(blank=False, null=False)
    message = models.TextField(null=True, blank=True)
    transaction_reference = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.transaction_id} - {self.wallet}"

class TransactionType(models.TextChoices):
    WALLET_DEPOSIT = 'WALLET_DEPOSIT', _('Wallet Deposit')
    WALLET_WITHDRAWAL = 'WALLET_WITHDRAWAL', _('Wallet Withdrawal')
    LOAN_APPLICATION = 'LOAN_APPLICATION', _('Loan Application')
    LOAN_APPROVAL = 'LOAN_APPROVAL', _('Loan Approval')
    LOAN_DISBURSEMENT = 'LOAN_DISBURSEMENT', _('Loan Disbursement')
    LOAN_REPAYMENT = 'LOAN_REPAYMENT', _('Loan Repayment')
    LOAN_COMPLETION = 'LOAN_COMPLETION', _('Loan Completion') 
    UNIT_PURCHASE = 'UNIT_PURCHASE', _('Unit Purchase')
    UNIT_SHARE = 'UNIT_SHARE', _('Unit Share')
    UNIT_TRANSFER = 'UNIT_TRANSFER', _('Unit Transfer')
    TOKEN_GENERATE = 'TOKEN_GENERATE', _('STS Token Generated')
    WALLET_LOAD_AMI = 'WALLET_LOAD_AMI', _('Wallet Load (AMI)')

class TransactionLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transaction_logs')
    transaction_type = models.CharField(max_length=50, choices=TransactionType.choices)
    amount = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)  
    units = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True) 
    status = models.CharField(max_length=20, default='PENDING')
    reference_id = models.CharField(max_length=100, null=True, blank=True)  
    details = models.JSONField(null=True, blank=True) 
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_type} - {self.user.username} - {self.created_at}"
