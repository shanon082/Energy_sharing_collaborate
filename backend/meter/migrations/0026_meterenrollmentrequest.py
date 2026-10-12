import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("meter", "0025_meterdelivery_request_id"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(
        name="MeterEnrollmentRequest",
        fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("request_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("meter_no", models.CharField(max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL))],
        options={"constraints": [models.UniqueConstraint(fields=("owner", "meter_no"), name="meter_enrollment_owner_number")]},
    )]
