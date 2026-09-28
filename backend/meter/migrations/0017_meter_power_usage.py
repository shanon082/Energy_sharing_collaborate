# Generated migration for AMI Energy Usage models

import django.core.validators
from decimal import Decimal
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("meter", "0016_meternotification"),
    ]

    operations = [
        migrations.CreateModel(
            name="MeterBalanceSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("create_date", models.DateTimeField(auto_now_add=True)),
                ("modify_date", models.DateTimeField(auto_now=True)),
                ("remaining_kwh", models.DecimalField(decimal_places=4, max_digits=14)),
                ("recorded_at", models.DateTimeField(db_index=True)),
                ("source", models.CharField(default="thingsboard", max_length=32)),
                (
                    "meter",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="balance_snapshots",
                        to="meter.meter",
                    ),
                ),
            ],
            options={
                "ordering": ["-recorded_at"],
            },
        ),
        migrations.CreateModel(
            name="MeterUsageDaily",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("create_date", models.DateTimeField(auto_now_add=True)),
                ("modify_date", models.DateTimeField(auto_now=True)),
                ("usage_date", models.DateField(db_index=True)),
                (
                    "kwh_used",
                    models.DecimalField(
                        decimal_places=4,
                        max_digits=12,
                        validators=[django.core.validators.MinValueValidator(Decimal("0.00"))],
                    ),
                ),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("SNAPSHOT", "Balance snapshots"),
                            ("THINGSBOARD", "ThingsBoard telemetry"),
                            ("WEBHOOK", "ThingsBoard webhook"),
                            ("STUB", "Development stub"),
                        ],
                        default="SNAPSHOT",
                        max_length=16,
                    ),
                ),
                (
                    "meter",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="daily_usage",
                        to="meter.meter",
                    ),
                ),
            ],
            options={
                "ordering": ["-usage_date"],
            },
        ),
        migrations.AddIndex(
            model_name="meterbalancesnapshot",
            index=models.Index(fields=["meter", "-recorded_at"], name="meter_meter_meter_i_8a1f2c_idx"),
        ),
        migrations.AddIndex(
            model_name="meterusagedaily",
            index=models.Index(fields=["meter", "-usage_date"], name="meter_meter_meter_i_9b2e3d_idx"),
        ),
        migrations.AddConstraint(
            model_name="meterusagedaily",
            constraint=models.UniqueConstraint(
                fields=("meter", "usage_date"),
                name="unique_meter_usage_date",
            ),
        ),
    ]
