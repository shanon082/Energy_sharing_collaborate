import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("meter", "0028_remove_energyallocation_allocation_one_source_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [migrations.CreateModel(
        name="SandboxMeterEnrollment",
        fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("provenance", models.CharField(default="SELF_DECLARED", editable=False, max_length=20)),
            ("enrolled_at", models.DateTimeField(auto_now_add=True)),
            ("meter", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="sandbox_enrollment", to="meter.meter")),
            ("owner", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sandbox_meter_enrollments", to=settings.AUTH_USER_MODEL)),
            ("prior_request", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="sandbox_transition", to="meter.meterenrollmentrequest")),
        ],
        options={"constraints": [models.CheckConstraint(condition=models.Q(provenance="SELF_DECLARED"), name="sandbox_meter_self_declared")]},
    )]
