from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("loan", "0020_loanapplication_intended_meter")]

    operations = [
        migrations.AddField(
            model_name="loanrepayment", name="amount_applied_ugx",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="loanrepayment", name="excess_ugx",
            field=models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=10),
        ),
    ]
