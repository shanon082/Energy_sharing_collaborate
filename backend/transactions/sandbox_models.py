import uuid
from django.db import models


class SandboxSettlement(models.Model):
    """Exact isolated test receipts; no core wallet or LoanRepayment write."""
    intent = models.OneToOneField("transactions.PaymentIntent", on_delete=models.PROTECT, related_name="sandbox_settlement")
    currency = models.CharField(max_length=3, default="EUR")
    environment = models.CharField(max_length=20, default="MTN_SANDBOX")
    received = models.DecimalField(max_digits=20, decimal_places=6)
    applied = models.DecimalField(max_digits=20, decimal_places=6, default=0)
    excess = models.DecimalField(max_digits=20, decimal_places=6, default=0)
    billed = models.DecimalField(max_digits=20, decimal_places=6, default=0)
    residual = models.DecimalField(max_digits=20, decimal_places=6, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=(models.Q(currency="EUR", environment="MTN_SANDBOX")
            | models.Q(currency="UGX", environment="UGX_DEMO")), name="sandbox_receipt_test_domain"),
            models.CheckConstraint(condition=models.Q(received=models.F("applied")+models.F("excess")+models.F("billed")+models.F("residual"))
            & models.Q(applied__gte=0, excess__gte=0, billed__gte=0, residual__gte=0), name="sandbox_receipt_conservation")]


class SandboxUGXInstruction(models.Model):
    """Immutable UGX business instruction; its intent remains actual EUR1 evidence."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    intent = models.OneToOneField('transactions.PaymentIntent', on_delete=models.PROTECT, related_name='ugx_instruction')
    owner = models.ForeignKey('accounts.User', on_delete=models.PROTECT)
    meter = models.ForeignKey('meter.Meter', on_delete=models.PROTECT)
    loan = models.ForeignKey('loan.SandboxLoan', on_delete=models.PROTECT, null=True, blank=True)
    quote = models.OneToOneField('loan.SandboxQuote', on_delete=models.PROTECT)
    purpose = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=12, decimal_places=0)
    currency = models.CharField(max_length=3, default='UGX')
    environment = models.CharField(max_length=20, default='UGX_DEMO')
    policy_version = models.CharField(max_length=40, default='UGX-MTN-TEST-AUTH-v1')
    snapshot = models.JSONField()
    snapshot_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            from django.core.exceptions import ValidationError
            raise ValidationError('A sandbox UGX instruction is immutable.')
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(currency='UGX', environment='UGX_DEMO',
            policy_version='UGX-MTN-TEST-AUTH-v1', amount__gt=0, amount__lte=1000000), name='ugx_instruction_domain'),
            models.CheckConstraint(condition=(models.Q(purpose='PURCHASE', loan__isnull=True)
                | models.Q(purpose='LOAN_REPAYMENT', loan__isnull=False)), name='ugx_instruction_purpose')]


class SandboxUGXSettlement(models.Model):
    """Noncash test effect, separate from the conserved EUR provider receipt."""
    instruction = models.OneToOneField(SandboxUGXInstruction, on_delete=models.PROTECT, related_name='business_settlement')
    authorized = models.DecimalField(max_digits=20, decimal_places=6)
    applied = models.DecimalField(max_digits=20, decimal_places=6, default=0)
    excess = models.DecimalField(max_digits=20, decimal_places=6, default=0)
    billed = models.DecimalField(max_digits=20, decimal_places=6, default=0)
    residual = models.DecimalField(max_digits=20, decimal_places=6, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(authorized=models.F('applied')+models.F('excess')+models.F('billed')+models.F('residual'))
            & models.Q(authorized__gt=0, applied__gte=0, excess__gte=0, billed__gte=0, residual__gte=0), name='ugx_test_effect_conservation')]


class SandboxCheckout(models.Model):
    """Local checkout lifecycle, deliberately independent of provider outcome.

    Replacement attempts point to one root. Only the root records its winning
    authorization. Immutable instructions and actual provider receipts stay intact.
    """
    intent = models.OneToOneField('transactions.PaymentIntent', on_delete=models.PROTECT, related_name='checkout')
    root = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='attempts')
    replaces = models.OneToOneField('self', null=True, blank=True, on_delete=models.PROTECT, related_name='replacement')
    expired_at = models.DateTimeField(null=True, blank=True)
    initiation_cancelled_at = models.DateTimeField(null=True, blank=True)
    closure_reason = models.CharField(max_length=40, blank=True, default='')
    fulfilled_by = models.OneToOneField('transactions.PaymentIntent', null=True, blank=True, on_delete=models.PROTECT, related_name='fulfilled_checkout')

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(initiation_cancelled_at__isnull=True) | models.Q(expired_at__isnull=False) | models.Q(closure_reason='OPERATION_ALREADY_FULFILLED'),
            name='checkout_local_cancel_requires_expiry'),
            models.CheckConstraint(condition=models.Q(root__isnull=True) | models.Q(fulfilled_by__isnull=True), name='checkout_only_root_fulfills')]
