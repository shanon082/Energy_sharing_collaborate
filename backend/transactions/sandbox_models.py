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
