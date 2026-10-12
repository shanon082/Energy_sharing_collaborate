"""Isolated EUR test obligations: never reuse historical UGX repayment columns."""
import uuid
from django.db import models
from django.conf import settings


class SandboxQuote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    meter = models.ForeignKey("meter.Meter", on_delete=models.PROTECT)
    purpose = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    terms = models.JSONField()
    terms_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()


class SandboxLoan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client_request_id = models.UUIDField(unique=True)
    quote = models.OneToOneField(SandboxQuote, on_delete=models.PROTECT)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    meter = models.ForeignKey("meter.Meter", on_delete=models.PROTECT)
    currency = models.CharField(max_length=3, default="EUR")
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
        constraints = [models.CheckConstraint(condition=models.Q(currency="EUR"), name="sandbox_loan_eur_only"), models.UniqueConstraint(fields=["owner"], condition=models.Q(status="DISBURSED"),
                                               name="one_active_sandbox_loan")]

    @property
    def outstanding(self):
        from decimal import Decimal
        from transactions.sandbox_models import SandboxSettlement
        applied = SandboxSettlement.objects.filter(intent__sandbox_loan=self).aggregate(
            total=models.Sum("applied"))["total"] or Decimal("0.00")
        return max(Decimal("0.00"), self.total_due - applied) if self.status != "REJECTED" else Decimal("0.00")
