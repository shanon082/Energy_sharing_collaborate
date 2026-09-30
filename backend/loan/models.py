from decimal import Decimal
from django.db import models
from django.conf import settings
from accounts.models import User
import random
import string
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError
from loan.tenure import loan_due_date
import logging
logger = logging.getLogger(__name__)

LOAN_TIERS = [
    {
        'name': 'Bronze',
        'min_score': 75,
        'max_score': 79,
        'max_amount': 50000,
        'interest_rate': 12.0
    },
    {
        'name': 'Silver',
        'min_score': 80,
        'max_score': 84,
        'max_amount': 100000,
        'interest_rate': 11.0
    },
    {
        'name': 'Gold',
        'min_score': 85,
        'max_score': 89,
        'max_amount': 150000,
        'interest_rate': 10.0
    },
    {
        'name': 'Platinum',
        'min_score': 90,
        'max_score': 100,
        'max_amount': 200000,
        'interest_rate': 9.0
    }
]

# def get_tier_by_score(score):
#     """Get loan tier based on credit score"""
#     for tier in LOAN_TIERS:
#         if tier['min_score'] <= score <= tier['max_score']:
#             return tier
#     return None    

def generate_loan_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))


def generate_token():
    return ''.join(random.choices(string.digits, k=10))  

class ElectricityTariff(models.Model):
    """
    ERA/UEDCL tariff schedule. Rates are versioned by effective date range so
    a quarterly revision is a data change, not a code change.
    Only DOMESTIC (Code 10.1) tariffs are used in the pilot.
    """
    TARIFF_TYPES = (
        ('DOMESTIC', 'Domestic'),
        ('COMMERCIAL', 'Commercial'),
        ('INDUSTRIAL', 'Industrial'),
    )

    tariff_code = models.CharField(max_length=20, unique=True)
    tariff_name = models.CharField(max_length=100)
    tariff_type = models.CharField(max_length=20, choices=TARIFF_TYPES, default='DOMESTIC')
    voltage_level = models.CharField(max_length=50)
    voltage_value = models.CharField(max_length=20, blank=True)
    service_charge = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    # Legacy field kept for backwards compat; prefer effective_from/effective_to
    effective_date = models.DateTimeField(default=timezone.now)
    effective_from = models.DateField(null=True, blank=True, help_text="Date from which this tariff applies")
    effective_to = models.DateField(null=True, blank=True, help_text="Last date this tariff applies (null = open-ended)")

    def __str__(self):
        return f"{self.tariff_code} - {self.tariff_name}"


class TariffBlock(models.Model):
    """
    A single rate block within a tariff schedule.
    Blocks are monthly-cumulative: a purchase's cost depends on how many
    units the customer has already bought in the current calendar month.
    """
    tariff = models.ForeignKey(ElectricityTariff, on_delete=models.CASCADE, related_name='blocks')
    block_name = models.CharField(max_length=100)
    min_units = models.IntegerField(default=0)
    max_units = models.IntegerField(null=True, blank=True)
    rate_per_unit = models.DecimalField(max_digits=8, decimal_places=2)
    block_order = models.IntegerField(default=0)
    # Lifeline block: applies only to users whose 6-month rolling average ≤ 100 kWh/month.
    # For the pilot, all domestic users are treated as lifeline-eligible.
    is_lifeline_block = models.BooleanField(
        default=False,
        help_text="If true, this block only applies to lifeline-eligible customers"
    )
    # Non-lifeline fallback rate for this block (used when is_lifeline_block=True but user is ineligible)
    non_lifeline_rate = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text="Rate charged for ineligible customers in a lifeline block"
    )

    class Meta:
        ordering = ['block_order']

    def __str__(self):
        if self.max_units:
            return f"{self.block_name} ({self.min_units}-{self.max_units} kWh): {self.rate_per_unit} UGX"
        return f"{self.block_name} (Above {self.min_units} kWh): {self.rate_per_unit} UGX"

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UserCreditSignal(TimeStampedModel):
    """Third-party credit indicators used for loan eligibility scoring."""
    PAYMENT_HISTORY_CHOICES = (
        ('GOOD', 'Good'),
        ('FAIR', 'Fair'),
        ('POOR', 'Poor'),
    )
    ENERGY_CONSUMPTION_CHOICES = (
        ('STABLE', 'Stable'),
        ('MODERATE', 'Moderate'),
        ('ERRATIC', 'Erratic'),
    )
    FINANCIAL_CAPACITY_CHOICES = (
        ('STRONG', 'Strong'),
        ('AVERAGE', 'Average'),
        ('WEAK', 'Weak'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='credit_signal')
    payment_history = models.CharField(max_length=10, choices=PAYMENT_HISTORY_CHOICES)
    energy_consumption = models.CharField(max_length=10, choices=ENERGY_CONSUMPTION_CHOICES)
    financial_capacity = models.CharField(max_length=10, choices=FINANCIAL_CAPACITY_CHOICES)
    source = models.CharField(max_length=100, default='DUMMY_THIRD_PARTY')

    def __str__(self):
        return f"CreditSignal<{self.user.email}>"


class LoanApplication(TimeStampedModel):
    LOAN_STATUS = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('DISBURSED', 'Disbursed'),
        ('COMPLETED', 'Completed'),
        ('DEFAULTED', 'Defaulted'),
    )
    LOAN_TIER_CHOICES = (
        ('BRONZE', 'Bronze'),
        ('SILVER', 'Silver'),
        ('GOLD', 'Gold'),
        ('PLATINUM', 'Platinum'),
    )    
    loan_id = models.CharField(max_length=10, unique=True, default=generate_loan_id)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='loan_applications')
    intended_meter = models.ForeignKey(
        'meter.Meter', on_delete=models.PROTECT, null=True, blank=True,
        related_name='intended_loans',
    )
    purpose = models.TextField()
    amount_requested = models.DecimalField(max_digits=10, decimal_places=2)
    amount_approved = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tenure_months = models.IntegerField(default=6)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.0)
    status = models.CharField(max_length=20, choices=LOAN_STATUS, default='PENDING')
    credit_score = models.IntegerField(null=True, blank=True)
    loan_tier = models.CharField(max_length=20, choices=LOAN_TIER_CHOICES, null=True, blank=True)
    tariff = models.ForeignKey(ElectricityTariff, on_delete=models.SET_NULL, null=True, blank=True)
    rejection_reason = models.TextField(null=True, blank=True)
    user_notified = models.BooleanField(default=False)
    
    def check_eligibility(self):
        return self.credit_score >= 75 if self.credit_score else False
    

    def save(self, *args, **kwargs):
        # Disbursed debt must retain its stored rate when status or notification
        # fields are saved; changing the score tier later must not reprice it.
        if self.credit_score and (self._state.adding or self.status in {"PENDING", "APPROVED", "REJECTED"}):
            tier_info = get_tier_by_score(self.credit_score)
            if tier_info:
                self.loan_tier = tier_info['name']
                self.interest_rate = tier_info['interest_rate']
    
        if not self.pk and not self.status:  # Only for new instances
            if self.check_eligibility():
                self.status = 'APPROVED'
            else:
                self.status = 'REJECTED'
                self.rejection_reason = "Credit score below 75% threshold"
    
        super().save(*args, **kwargs)

    def get_max_eligible_amount(self):
        """Get maximum loan amount user is eligible for based on tier (from database)"""
        if self.credit_score and self.loan_tier:
            tier_info = get_tier_by_score(self.credit_score)
            if tier_info:
                return tier_info['max_amount']
        return 0
    
    def calculate_units_from_amount(self, amount=None):
        """Mirror the loan disbursement's existing tariff/legacy branch exactly."""
        from meter.allocation_service import quantize_source_kwh
        from utils.billing import calculate_units_from_payment

        loan_amount = Decimal(str(self.amount_approved if amount is None else amount))
        if self.tariff_id is None:
            return quantize_source_kwh(loan_amount / Decimal("500"))
        units, _ = calculate_units_from_payment(
            loan_amount,
            self.user,
            tariff=self.tariff,
            apply_deductions=False,
        )
        return units

    def calculate_cost_for_units(self, units):
        """Total UGX payable (energy + service + VAT) for a given kWh amount."""
        from utils.billing import calculate_cost_from_units

        if self.tariff_id is None:
            return Decimal(str(units)) * Decimal("500")
        cost, _ = calculate_cost_from_units(Decimal(str(units)), self.user, tariff=self.tariff)
        return cost

    def __str__(self):
        tier_display = f" ({self.loan_tier})" if self.loan_tier else ""
        return f"Loan #{self.loan_id}{tier_display} - {self.user.email} - {self.status}"
    
    @property
    def due_date(self):
        if hasattr(self, 'disbursement') and self.disbursement:
            return loan_due_date(self.disbursement.disbursement_date, self.tenure_months)
        return None
    
    @property
    def total_amount_due(self):
        from loan.financial import interest_charge, money
        if not self.amount_approved:
            return Decimal("0.00")
        return Decimal(self.amount_approved) + money(interest_charge(self))
    
    @property
    def amount_paid(self):
        from loan.financial import applied_repayments
        return applied_repayments(self)


    @property
    def outstanding_balance(self):
        """Principal plus capped charges, less only applied successful repayments."""
        from loan.financial import outstanding_debt
        return outstanding_debt(self)
    
    class Meta:
        ordering = ['-created_at']


class LoanDisbursement(TimeStampedModel):
    loan_application = models.OneToOneField(LoanApplication, on_delete=models.CASCADE, related_name='disbursement')
    disbursement_date = models.DateTimeField(auto_now_add=True)
    disbursed_amount = models.DecimalField(max_digits=10, decimal_places=2)
    units_disbursed = models.FloatField()
    token = models.CharField(max_length=10, unique=True, default=generate_token)
    token_expiry = models.DateTimeField()
    meter = models.ForeignKey('meter.Meter', on_delete=models.CASCADE, related_name='loan_disbursements')
    
    def __str__(self):
        return f"Disbursement for Loan #{self.loan_application.loan_id}"
    
    def save(self, *args, **kwargs):
        if not self.token_expiry:
            self.token_expiry = timezone.now() + timedelta(days=30)
        super().save(*args, **kwargs)


class LoanRepayment(TimeStampedModel):
    loan = models.ForeignKey(LoanApplication, on_delete=models.CASCADE, related_name='repayments')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    # For new verified payments amount_paid is the full amount received. NULL
    # on historical rows preserves their existing debt-reduction interpretation.
    amount_applied_ugx = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    excess_ugx = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_date = models.DateTimeField(auto_now_add=True)
    units_paid = models.FloatField()
    is_on_time = models.BooleanField(default=True)
    payment_reference = models.CharField(max_length=50, unique=True)
    paid_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='third_party_payments',
        help_text="User who paid on behalf of the loan owner (null = self-payment)",
    )
    is_anonymous = models.BooleanField(
        default=False,
        help_text="Whether the payer chose to stay anonymous to the loan owner",
    )

    payment_method = models.CharField(
        max_length=20, 
        choices=[
            ('CASH', 'Cash'),
            ('MOBILE_MONEY', 'Mobile Money'),
            ('BANK_TRANSFER', 'Bank Transfer')
        ],
        default='CASH'
    )
    momo_transaction_id = models.CharField(max_length=100, blank=True, null=True)
    momo_external_id = models.CharField(max_length=100, blank=True, null=True)
    momo_phone_number = models.CharField(max_length=15, blank=True, null=True)
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('SUCCESS', 'Success'),
            ('FAILED', 'Failed'),
            ('CANCELLED', 'Cancelled')
        ],
        default='PENDING'
    )
    
    def __str__(self):
        return f"Repayment #{self.id} for Loan #{self.loan.loan_id}"
    
    class Meta:
        ordering = ['-created_at']


class LoanTier(models.Model):
    """Dynamic loan tier configuration"""
    name = models.CharField(max_length=20, unique=True)  # Bronze, Silver, Gold, Platinum
    display_name = models.CharField(max_length=50)
    min_score = models.IntegerField()
    max_score = models.IntegerField()
    max_amount = models.DecimalField(max_digits=10, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['min_score']
    
    def __str__(self):
        return f"{self.name} ({self.min_score}-{self.max_score})"
    
    def clean(self):
        """Validate score ranges and statutory interest cap."""
        overlapping = LoanTier.objects.filter(
            is_active=True
        ).exclude(id=self.id).filter(
            models.Q(min_score__lte=self.max_score, max_score__gte=self.min_score)
        )
        if overlapping.exists():
            raise ValidationError("Tier score ranges cannot overlap")

        # Uganda Tier 4 MFI / Money Lenders Act: max 2.8% per month = 33.6% per annum.
        # interest_rate is stored as annual %. Monthly equivalent = interest_rate / 12.
        max_annual = getattr(settings, 'MAX_ANNUAL_INTEREST_RATE_PCT', Decimal('33.6'))
        if Decimal(str(self.interest_rate)) > max_annual:
            raise ValidationError(
                f"Interest rate {self.interest_rate}% per annum exceeds the statutory "
                f"cap of {max_annual}% per annum (2.8%/month). "
                "Reduce the rate or obtain a regulatory exemption."
            )
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


LOAN_TIERS_DEPRECATED = LOAN_TIERS 

def get_tier_by_score(score):
    """Get loan tier based on credit score from database (admin-configured)"""
    try:
        # ALWAYS try to get from database first (admin configured)
        tier = LoanTier.objects.filter(
            is_active=True,
            min_score__lte=score,
            max_score__gte=score
        ).first()
        
        if tier:
            return {
                'name': tier.name,
                'display_name': tier.display_name,
                'min_score': tier.min_score,
                'max_score': tier.max_score,
                'max_amount': float(tier.max_amount),  # Convert to float for calculations
                'interest_rate': float(tier.interest_rate),  # Convert to float for calculations
                'is_active': tier.is_active,
                'id': tier.id  
            }
        
        # If no tier found in database for this score, log it
        logger.warning(f"No active loan tier found for credit score: {score}")
        return None
        
    except Exception as e:
        logger.error(f"Error fetching loan tier from database: {str(e)}")
        
        logger.warning("Falling back to hardcoded loan tiers")
        for tier in LOAN_TIERS:  # Your hardcoded fallback
            if tier['min_score'] <= score <= tier['max_score']:
                return tier
        return None


class CreditScoreHistory(models.Model):
    """
    Track credit score changes over time
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='credit_score_history')
    previous_score = models.IntegerField()
    new_score = models.IntegerField()
    change_amount = models.IntegerField()
    reason = models.CharField(max_length=200)
    event_type = models.CharField(max_length=50, choices=[
        ('LOAN_APPLICATION', 'Loan Application'),
        ('LOAN_REPAYMENT', 'Loan Repayment'),
        ('UNIT_PURCHASE', 'Unit Purchase'),
        ('WALLET_USAGE', 'Wallet Usage'),
        ('LATE_PAYMENT', 'Late Payment'),
        ('ON_TIME_PAYMENT', 'On-Time Payment'),
        ('SHARE_UNITS', 'Share Units'),
        ('METER_REGISTRATION', 'Meter Registration'),
    ])
    reference_id = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email}: {self.previous_score} → {self.new_score} ({self.change_amount})"


class CreditScoreFactors(models.Model):
    """
    Store detailed credit scoring factors for each user
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='credit_factors')
    
    # Payment behavior factors
    on_time_payments = models.IntegerField(default=0)
    late_payments = models.IntegerField(default=0)
    total_repayments = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    repayment_consistency_score = models.FloatField(default=0)
    
    # Purchase behavior factors
    total_units_purchased = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    purchase_frequency = models.IntegerField(default=0)  # Number of purchases
    wallet_usage_count = models.IntegerField(default=0)  # Times used wallet for transactions
    wallet_transaction_volume = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Sharing behavior factors
    units_shared = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    units_received = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    sharing_count = models.IntegerField(default=0)
    
    # Loan behavior factors
    loans_taken = models.IntegerField(default=0)
    loans_completed = models.IntegerField(default=0)
    loans_defaulted = models.IntegerField(default=0)
    total_loan_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Account age
    account_age_days = models.IntegerField(default=0)
    last_activity_date = models.DateTimeField(auto_now=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Factors for {self.user.email}"
