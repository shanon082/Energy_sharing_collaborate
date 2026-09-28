import decimal
import logging
import random
import string
import uuid

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
# from django.utils.translation import ugettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField
from rest_framework_simplejwt.tokens import RefreshToken
from accounts.managers import CustomUserManager
from django.db.models import Sum
from django.conf import settings
import random

logger = logging.getLogger(__name__)


def generate_secure_random_int(upper=10):
    """
    Returns a random integer between 0 (inclusive) and upper (exclusive)
    generated using the OS' random number sources.
    """
    return random.SystemRandom().randrange(upper)


# def generate_verification_code():
#     return "".join(
#         [
#             "{}".format(generate_secure_random_int(10))
#             for num in range(PhoneVerificationCode.CODE_LENGTH)
#         ]
#     )


def generate_random_string(length):
    # Define the character set excluding 'i' and '0'
    characters = string.ascii_uppercase.replace('i', '').replace('O', '') + '123456789'

    # Generate the random string
    random_string = ''.join(random.choice(characters) for _ in range(length))
    return random_string


class TimestampMixin(models.Model):
    """
    Model mixin that provides timestamping fields.
    """

    create_date = models.DateTimeField("date created", auto_now_add=True)
    modify_date = models.DateTimeField("date modified", auto_now=True)

    class Meta:
        abstract = True


class User(TimestampMixin, AbstractUser):
    """
    Model class that extends the default User model
    """


    # Roles
    ADMIN = "ADMIN"
    CLIENT = "CLIENT"
    CUSTOMER_SERVICE = "CUSTOMER_SERVICE"
    OPERATOR = "OPERATOR"

    USER_ROLES = [
        (ADMIN, _("admin")),
        (CLIENT, _("client")),
        (CUSTOMER_SERVICE, _("customer_service")),
        (OPERATOR, _("operator")),
    ]

    MALE = "MALE"
    FEMALE = "FEMALE"

    USER_GENDER = [
        (MALE, _("male")),
        (FEMALE, _("female"))
    ]

    

    username = None
    email = models.EmailField(_("email_address"), unique=True)
    phone_number = PhoneNumberField(_("phone_number"), unique=True, blank=True, null=True)
    # country = models.ForeignKey(
    #     Country, on_delete=models.CASCADE, null=True, blank=True
    # )
    account_is_active = models.BooleanField(default=False)
    user_role = models.CharField(default=CLIENT, choices=USER_ROLES, max_length=20)
    gender = models.CharField(max_length=6, choices=USER_GENDER, default=MALE)
    monthly_unit_balance = models.FloatField(default=0)  # Units bought in the current month
    last_purchase_date = models.DateField(null=True, blank=True)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = CustomUserManager()    
    # Loan assessment fields (from profile popup)
    monthly_expenditure = models.CharField(
        max_length=50, 
        choices=[
            ("<50,000 UGX", "<50,000 UGX"),
            ("50,000–100,000 UGX", "50,000–100,000 UGX"),
            ("100,001–200,000 UGX", "100,001–200,000 UGX"),
            ("200,001–300,000 UGX", "200,001–300,000 UGX"),
            (">300,000 UGX", ">300,000 UGX")
        ], 
        null=True, 
        blank=True
    )
    
    purchase_frequency = models.CharField(
        max_length=20, 
        choices=[
            ("Daily", "Daily"),
            ("Weekly", "Weekly"),
            ("Bi-weekly", "Bi-weekly"),
            ("Monthly", "Monthly"),
            ("Rarely", "Rarely")
        ], 
        null=True, 
        blank=True
    )
    
    payment_consistency = models.CharField(
        max_length=20, 
        choices=[
            ("Always on time", "Always on time"),
            ("Often on time", "Often on time"),
            ("Sometimes late", "Sometimes late"),
            ("Mostly late", "Mostly late"),
            ("Never paid", "Never paid")
        ], 
        null=True, 
        blank=True
    )
    
    disconnection_history = models.CharField(
        max_length=30, 
        choices=[
            ("No disconnections", "No disconnections"),
            ("1–2 disconnections", "1–2 disconnections"),
            ("3–4 disconnections", "3–4 disconnections"),
            (">4 disconnections", ">4 disconnections"),
            ("Frequently disconnected", "Frequently disconnected")
        ], 
        null=True, 
        blank=True
    )
    
    meter_sharing = models.CharField(
        max_length=30, 
        choices=[
            ("No sharing", "No sharing"),
            ("Shared with 1 household", "Shared with 1 household"),
            ("Shared with 2+ households", "Shared with 2+ households"),
            ("Commercial sharing", "Commercial sharing")
        ], 
        null=True, 
        blank=True
    )
    
    monthly_income = models.CharField(
        max_length=30, 
        choices=[
            ("<100,000 UGX", "<100,000 UGX"),
            ("100,000–199,999 UGX", "100,000–199,999 UGX"),
            ("200,000–499,999 UGX", "200,000–499,999 UGX"),
            ("500,000–999,999 UGX", "500,000–999,999 UGX"),
            (">1,000,000 UGX", ">1,000,000 UGX")
        ], 
        null=True, 
        blank=True
    )
    
    income_stability = models.CharField(
        max_length=30, 
        choices=[
            ("Fixed and stable", "Fixed and stable"),
            ("Regular but variable", "Regular but variable"),
            ("Seasonal income", "Seasonal income"),
            ("Irregular but frequent", "Irregular but frequent"),
            ("Unstable income", "Unstable income")
        ], 
        null=True, 
        blank=True
    )
    
    consumption_level = models.CharField(
        max_length=30,
        choices=[
            ("Very low (<50 kWh)", "Very low (<50 kWh)"),
            ("Low (50–99 kWh)", "Low (50–99 kWh)"),
            ("Moderate (100–200 kWh)", "Moderate (100–200 kWh)"),
            ("High (>200 kWh)", "High (>200 kWh)"),
            ("Extremely high (>300 kWh)", "Extremely high (>300 kWh)")
        ],
        null=True,
        blank=True
    )

    # KYC status — per Section 3.7
    KYC_UNVERIFIED = "UNVERIFIED"
    KYC_VERIFIED = "VERIFIED"
    KYC_FLAGGED = "FLAGGED"
    KYC_STATUS_CHOICES = [
        (KYC_UNVERIFIED, "Unverified"),
        (KYC_VERIFIED, "Verified"),
        (KYC_FLAGGED, "Flagged"),
    ]
    kyc_status = models.CharField(max_length=12, choices=KYC_STATUS_CHOICES, default=KYC_UNVERIFIED)

    # Account suspension tracking
    is_suspended = models.BooleanField(default=False)
    suspension_reason = models.CharField(max_length=50, null=True, blank=True)
    suspension_note = models.TextField(null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    national_id = models.CharField(max_length=30, null=True, blank=True)

    # Credit limit override (Admin only, hard cap 20 kWh per spec Section 5.4)
    credit_limit_override_kwh = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    credit_limit_override_reason = models.TextField(null=True, blank=True)

    # 2FA (TOTP / Google Authenticator) — mandatory for staff per spec Section 1.3
    totp_secret = models.CharField(max_length=64, null=True, blank=True)
    totp_enabled = models.BooleanField(default=False)

    # Admin-provisioned accounts must set a new password on first login
    must_change_password = models.BooleanField(default=False)

    def __str__(self):
        """
        Returns a string representation of the User.
        """
        return f"{self.first_name} {self.last_name} {self.email}, {self.phone_number}"

    @property
    def tokens(self):
        refresh = RefreshToken.for_user(self)
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }
    
    @property
    def has_complete_profile(self):
        """Check if user has completed all profile fields"""
        
        required_fields = [
            'monthly_expenditure', 'purchase_frequency', 'payment_consistency',
            'disconnection_history', 'meter_sharing', 'monthly_income',
            'income_stability', 'consumption_level'
        ]
        return all(getattr(self, field, None) for field in required_fields)


    @property
    def is_verified(self):
        return self.profile.email_verified

    @property
    def is_admin(self):
        return self.user_role == self.ADMIN

    @property
    def is_client(self):
        return self.user_role == self.CLIENT

    @property
    def is_customer_service(self):
        return self.user_role == self.CUSTOMER_SERVICE

    @property
    def is_operator(self):
        return self.user_role == self.OPERATOR

    @property
    def is_staff_member(self):
        """True for any admin panel staff role."""
        return self.user_role in (self.ADMIN, self.CUSTOMER_SERVICE, self.OPERATOR)


class UserAccountDetails(TimestampMixin, models.Model):
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='account_details'
    )
    account_number = models.CharField(
        max_length=20, 
        unique=True, 
        blank=True, 
        null=True
    )
    address = models.TextField(blank=True, null=True)
    energy_preference = models.CharField(
        max_length=50, 
        blank=True, 
        null=True,
        choices=[
            ('SOLAR', 'Solar'),
            ('HYDRO', 'Hydro'),
            ('THERMAL', 'Thermal'),
            ('OTHER', 'Other'),
        ]
    )
    payment_method = models.CharField(
        max_length=50, 
        blank=True, 
        null=True,
        choices=[
            ('CREDIT_CARD', 'Credit Card'),
            ('MOBILE_MONEY', 'Mobile Money'),
            ('BANK_TRANSFER', 'Bank Transfer'),
        ]
    )

    def __str__(self):
        return f"Account details for {self.user.email}"

    def save(self, *args, **kwargs):
        if not self.account_number:        
            while True:
                new_account_number = f"EN-{random.randint(10000000, 99999999)}"
                if not UserAccountDetails.objects.filter(account_number=new_account_number).exists():
                    self.account_number = new_account_number
                    break
        super().save(*args, **kwargs)


class SettingsConfirmationEmailCode(TimestampMixin):

    USED = "USED"
    ACTIVE = "ACTIVE"

    STATUS_CHOICES = [
        (USED, _("used")),
        (ACTIVE, _("active"))
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    email = models.EmailField(_("email_address"))
    code = models.TextField(_("code"))

    status = models.CharField(
        choices=STATUS_CHOICES, default=ACTIVE, max_length=10
    )


class Profile(TimestampMixin, models.Model):
    """Model class to handle user profiles"""

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    email_verified = models.BooleanField(default=False)
    id_image = models.URLField(null=True, blank=True)
    # Lifeline eligibility: ERA requires ≤100 kWh average over the previous 6 months.
    # For the pilot, all domestic accounts default to eligible; the real six-month
    # check will be activated once sufficient purchase history exists.
    lifeline_eligible = models.BooleanField(default=True)

    def __str__(self):
        """
        Returns a string representation of the profile.
        """
        return f"{self.user.email}"


class Wallet(TimestampMixin):
    wallet_id = models.CharField(
        null=False, blank=False, max_length=10, unique=True, editable=False
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=False)
    currency = models.CharField(default="USD", max_length=10)
    balance = models.DecimalField(default=0.00, max_digits=20, decimal_places=2)

    def save(self, *args, **kwargs):
        if not self.wallet_id:
            # Generate a unique wallet ID
            while True:
                new_id = generate_random_string(10)
                if not Wallet.objects.filter(wallet_id=new_id).exists():
                    self.wallet_id = new_id
                    break
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.wallet_id} - {self.currency}"


    def add_funds(self, transaction):
        logger.info(
            f"Adding funds. Details: {transaction.get_logging_context()}"
        )

        blc = decimal.Decimal(self.balance)
        self.balance = blc + decimal.Decimal(transaction.amount)
        self.save()
        WalletLog.objects.create(
            wallet=self,
            current_amount=blc,
            incoming_amount=transaction.amount,
        )

    def deduct_funds(self, amount):
        # log this operation
        blc = decimal.Decimal(self.balance)
        if blc < amount:
            raise ValidationError("Insufficient account balance")

        self.balance = blc - amount
        self.save()
        # TODO notify_user

    def get_logging_context(self):
        return {
            "wallet_id": self.wallet_id,
            "currency": self.currency,
            "balance": self.balance,
        }

    @property
    def total_earnings(self):
        from meter.models import Transaction, COMMISSION
        total = Transaction.objects.filter(wallet=self, flow_type=COMMISSION).aggregate(Sum('amount', default=0))
        logger.info(f"[ACCOUNT_MODELS] total_earnings: {total.get('amount__sum')}")
        return total.get('amount__sum')


class WalletLog(TimestampMixin):
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE)
    current_amount = models.DecimalField(
        default=0.00, max_digits=20, decimal_places=2, null=True
    )
    incoming_amount = models.DecimalField(
        default=0.00, max_digits=20, decimal_places=2, null=True, blank=True
    )
    outgoing_amount = models.DecimalField(
        default=0.00, max_digits=20, decimal_places=2, null=True, blank=True
    )


class CreditScoreResponse(models.Model):
    QUESTION_CHOICES = [
        ('Q1', 'Average Monthly Expenditure on Electricity'),
        ('Q2', 'Purchase Frequency'),
        ('Q3', 'Payment Consistency'),
        ('Q4', 'Disconnection History'),
        ('Q5', 'Meter Sharing'),
        ('Q6', 'Monthly Income Range'),
        ('Q7', 'Income Stability'),
        ('Q8', 'Typical Consumption Level'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    question = models.CharField(max_length=2, choices=QUESTION_CHOICES)
    response = models.CharField(max_length=100)
    score = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

class EnergyLoan(models.Model):
    LOAN_STATUS = (
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
        ('DEFAULTED', 'Defaulted'),
        ('REJECTED', 'Rejected'),
    )
    
    LOAN_TIERS = (
        (1, 'Tier 1 (60-69%)'),
        (2, 'Tier 2 (70-79%)'),
        (3, 'Tier 3 (80-89%)'),
        (4, 'Tier 4 (90-100%)'),
    )
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    amount_requested = models.DecimalField(max_digits=12, decimal_places=2)
    amount_approved = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    credit_score = models.IntegerField()
    loan_tier = models.IntegerField(choices=LOAN_TIERS)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.0)  # 10% default
    term_months = models.IntegerField(default=6)  # 6 months default term
    status = models.CharField(max_length=20, choices=LOAN_STATUS, default='PENDING')
    purpose = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

class LoanRepayment(models.Model):
    loan = models.ForeignKey(EnergyLoan, on_delete=models.CASCADE, related_name='repayments')
    amount_due = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    due_date = models.DateField()
    paid_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[('PENDING', 'Pending'), ('PARTIAL', 'Partial'), ('PAID', 'Paid'), ('OVERDUE', 'Overdue')], default='PENDING')
    is_penalty = models.BooleanField(default=False)

    