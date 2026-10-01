import django.db.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("meter", "0024_simulatedmeter_last_measured_at")]

    operations = [
        migrations.AddField(
            model_name="meterdelivery", name="request_id",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="meterdelivery",
            constraint=models.UniqueConstraint(
                fields=("allocation", "request_id"),
                condition=django.db.models.Q(("request_id__isnull", False)),
                name="delivery_request_allocation_unique",
            ),
        ),
    ]
