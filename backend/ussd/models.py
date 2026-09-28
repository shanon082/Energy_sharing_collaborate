from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


def ussd_session_timeout_seconds() -> int:
    """Inactivity limit between USSD inputs (default 90s — common USSD standard)."""
    return int(getattr(settings, "USSD_SESSION_TIMEOUT_SECONDS", 90))


class UssdSession(models.Model):
    session_id = models.CharField(max_length=120, unique=True)
    service_code = models.CharField(max_length=40, blank=True)
    phone_number = models.CharField(max_length=20, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ussd_sessions",
    )
    last_text = models.TextField(blank=True, default="")
    current_menu = models.CharField(max_length=80, blank=True, default="root")
    context = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["phone_number", "is_active"]),
            models.Index(fields=["expires_at"]),
        ]
        ordering = ["-updated_at"]

    def __str__(self):
        return f"USSD {self.session_id} ({self.phone_number})"

    @staticmethod
    def timeout_delta() -> timedelta:
        return timedelta(seconds=ussd_session_timeout_seconds())

    @classmethod
    def default_expiry(cls):
        return timezone.now() + cls.timeout_delta()

    def touch(self):
        """Extend session expiry after each interactive response (inactivity clock resets)."""
        self.expires_at = self.default_expiry()
        self.is_active = True
        self.save(update_fields=["expires_at", "is_active", "updated_at"])

    def reset(self):
        self.current_menu = "root"
        self.last_text = ""
        self.context = {}
        self.is_active = True
        self.expires_at = self.default_expiry()
        self.save(
            update_fields=[
                "current_menu",
                "last_text",
                "context",
                "is_active",
                "expires_at",
                "updated_at",
            ]
        )

    @property
    def expired(self):
        return timezone.now() > self.expires_at
