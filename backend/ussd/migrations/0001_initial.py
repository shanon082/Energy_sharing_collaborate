from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
from datetime import timedelta


def default_expiry():
    return django.utils.timezone.now() + timedelta(minutes=15)


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UssdSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("session_id", models.CharField(max_length=120, unique=True)),
                ("service_code", models.CharField(blank=True, max_length=40)),
                ("phone_number", models.CharField(db_index=True, max_length=20)),
                ("last_text", models.TextField(blank=True, default="")),
                ("current_menu", models.CharField(blank=True, default="root", max_length=80)),
                ("context", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("expires_at", models.DateTimeField(default=default_expiry)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ussd_sessions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-updated_at"],
            },
        ),
        migrations.AddIndex(
            model_name="ussdsession",
            index=models.Index(fields=["phone_number", "is_active"], name="ussd_ussdse_phone_n_2425f8_idx"),
        ),
        migrations.AddIndex(
            model_name="ussdsession",
            index=models.Index(fields=["expires_at"], name="ussd_ussdse_expires_0aa5ff_idx"),
        ),
    ]
