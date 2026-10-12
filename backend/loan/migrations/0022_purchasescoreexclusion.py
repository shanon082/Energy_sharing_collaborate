from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("loan", "0021_loanrepayment_applied_excess"), ("transactions", "0010_paymentintent_client_request_id"),
                    migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(
        name="PurchaseScoreExclusion",
        fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reason", models.CharField(choices=[("REVERSED", "Reversed"), ("UNCERTAIN", "Uncertain")], max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("intent", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="score_exclusion", to="transactions.paymentintent")),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL))],
    )]
