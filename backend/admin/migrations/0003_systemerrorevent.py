# Generated manually for SystemErrorEvent model

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("portal_admin", "0002_alter_auditlog_action_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="SystemErrorEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("component", models.CharField(db_index=True, max_length=80)),
                ("message", models.TextField()),
                ("reference_id", models.CharField(blank=True, default="", max_length=100)),
                ("details", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="system_error_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="systemerrorevent",
            index=models.Index(fields=["component", "created_at"], name="portal_admi_compone_idx"),
        ),
    ]
