"""Currency/environment-isolated test obligations; no historical conversions."""
import uuid
from django.db import models
from django.conf import settings


class SandboxQuote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    meter = models.ForeignKey("meter.Meter", on_delete=models.PROTECT)
    purpose = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="EUR")
    environment = models.CharField(max_length=20, default="MTN_SANDBOX")
    terms = models.JSONField()
    terms_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        constraints = [models.CheckConstraint(condition=(models.Q(currency="EUR", environment="MTN_SANDBOX")
            | models.Q(currency="UGX", environment="UGX_DEMO")), name="sandbox_quote_test_domain")]


class SandboxLoan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client_request_id = models.UUIDField(unique=True)
    quote = models.OneToOneField(SandboxQuote, on_delete=models.PROTECT)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    meter = models.ForeignKey("meter.Meter", on_delete=models.PROTECT)
    currency = models.CharField(max_length=3, default="EUR")
    environment = models.CharField(max_length=20, default="MTN_SANDBOX")
    principal = models.DecimalField(max_digits=12, decimal_places=2)
    total_due = models.DecimalField(max_digits=12, decimal_places=2)
    terms = models.JSONField()
    assessment = models.JSONField()
    status = models.CharField(max_length=12)
    decision_reason = models.CharField(max_length=240)
    created_at = models.DateTimeField(auto_now_add=True)
    due_at = models.DateTimeField()
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=(models.Q(currency="EUR", environment="MTN_SANDBOX")
            | models.Q(currency="UGX", environment="UGX_DEMO")), name="sandbox_loan_test_domain"), models.UniqueConstraint(fields=["owner", "environment"], condition=models.Q(status="DISBURSED"),
                                               name="one_active_sandbox_loan")]

    @property
    def outstanding(self):
        from decimal import Decimal
        from transactions.sandbox_models import SandboxSettlement
        applied = SandboxSettlement.objects.filter(intent__sandbox_loan=self).aggregate(
            total=models.Sum("applied"))["total"] or Decimal("0.00")
        return max(Decimal("0.00"), self.total_due - applied) if self.status != "REJECTED" else Decimal("0.00")


class DemoCreditAssessment(models.Model):
    """Prototype-only account evidence; never replaces UserCreditSignal/history."""
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="demo_assessments")
    environment = models.CharField(max_length=20, default="UGX_DEMO")
    meter = models.ForeignKey("meter.Meter", null=True, blank=True, on_delete=models.PROTECT)
    status = models.CharField(max_length=12, default="PENDING", choices=[("PENDING", "Pending"), ("READY", "Ready"), ("UNAVAILABLE", "Unavailable")])
    provider = models.CharField(max_length=60, default="SIMULATED_ACCOUNT_V1")
    scenario = models.CharField(max_length=40)
    scoring_policy_version = models.CharField(max_length=60, default="DEMO-SCORE-v1")
    inputs = models.JSONField(default=dict)
    formula = models.JSONField(default=dict)
    factors = models.JSONField(default=dict)
    base_score = models.PositiveSmallIntegerField(null=True, blank=True)
    score = models.PositiveSmallIntegerField(null=True, blank=True)
    bonus_policy = models.JSONField(default=dict)
    purchase_points = models.PositiveSmallIntegerField(default=0)
    qualifying_billed_ugx = models.DecimalField(max_digits=20, decimal_places=6, default=0)
    purchase_source_count = models.PositiveIntegerField(default=0)
    error_code = models.CharField(max_length=48, blank=True, default="WAITING_FOR_METER")
    created_at = models.DateTimeField(auto_now_add=True)
    assessed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["owner", "environment"], name="one_demo_assessment_per_owner"),
            models.CheckConstraint(condition=models.Q(environment="UGX_DEMO", provider="SIMULATED_ACCOUNT_V1"), name="demo_assessment_isolated"),
            models.CheckConstraint(condition=(models.Q(status="READY", base_score__isnull=False, score__isnull=False, assessed_at__isnull=False)
                | models.Q(status__in=["PENDING", "UNAVAILABLE"], base_score__isnull=True, score__isnull=True)), name="demo_assessment_state"),
            models.CheckConstraint(condition=(models.Q(base_score__lte=100) | models.Q(base_score__isnull=True))
                & (models.Q(score__lte=100) | models.Q(score__isnull=True)), name="demo_assessment_score_range")]
