from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("meter", "0026_meterenrollmentrequest"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(
        name="MeterEnrollmentReview",
        fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("decision", models.CharField(choices=[("APPROVED", "Approved"), ("REJECTED", "Rejected")], max_length=8)),
                ("reviewed_at", models.DateTimeField(auto_now_add=True)),
                ("evidence_type", models.CharField(blank=True, max_length=32)),
                ("evidence_reference", models.CharField(blank=True, max_length=160)),
                ("consumer_reason", models.CharField(blank=True, max_length=240)),
                ("request", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="review", to="meter.meterenrollmentrequest")),
                ("meter", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="meter.meter")),
                ("reviewed_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL))],
    )]
