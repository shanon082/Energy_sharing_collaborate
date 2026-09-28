# Generated manually for meter soft-delete and deletion audit records

from decimal import Decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        (
            "meter",
            "0018_rename_meter_meter_meter_i_8a1f2c_idx_meter_meter_meter_i_7236ad_idx_and_more",
        ),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="meter",
            name="is_deleted",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="meter",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="meter",
            name="deleted_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="meters_deleted_by_user",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="meter",
            name="deleted_reason",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AlterField(
            model_name="meter",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="devices",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.CreateModel(
            name="DeletedMeterRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("create_date", models.DateTimeField(auto_now_add=True)),
                ("modify_date", models.DateTimeField(auto_now=True)),
                ("original_meter_no", models.CharField(db_index=True, max_length=100)),
                ("former_user_id", models.IntegerField(blank=True, db_index=True, null=True)),
                ("former_user_email", models.EmailField(blank=True, default="", max_length=254)),
                ("former_user_phone", models.CharField(blank=True, default="", max_length=32)),
                ("architecture", models.CharField(max_length=3)),
                ("label", models.CharField(blank=True, default="", max_length=50)),
                ("static_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("units_at_deletion", models.DecimalField(decimal_places=2, max_digits=20)),
                (
                    "pending_units_at_deletion",
                    models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=20),
                ),
                ("had_iot_token", models.BooleanField(default=False)),
                ("status_at_deletion", models.CharField(blank=True, default="", max_length=12)),
                ("deleted_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                (
                    "deleted_by_role",
                    models.CharField(
                        choices=[("USER", "Customer"), ("ADMIN", "Admin")],
                        max_length=10,
                    ),
                ),
                ("reason", models.TextField(blank=True, default="")),
                ("metadata", models.JSONField(blank=True, default=dict)),
                (
                    "deleted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="meter_deletions_performed",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "meter",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="deletion_records",
                        to="meter.meter",
                    ),
                ),
            ],
            options={
                "ordering": ["-deleted_at"],
                "indexes": [
                    models.Index(fields=["original_meter_no", "-deleted_at"], name="meter_del_no_dt_idx"),
                    models.Index(fields=["former_user_id", "-deleted_at"], name="meter_del_user_dt_idx"),
                ],
            },
        ),
    ]
