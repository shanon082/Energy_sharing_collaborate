from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("transactions", "0008_paymentintent_payment_provider_transaction_unique"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentintent", name="purchase_billed_ugx",
            field=models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="paymentintent", name="purchase_residual_ugx",
            field=models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="paymentintent", name="purchase_calculation",
            field=models.JSONField(null=True, blank=True),
        ),
    ]
