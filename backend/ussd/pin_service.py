"""USSD 4-digit PIN: default for new users, per-user hash after change."""

from __future__ import annotations

from django.contrib.auth.hashers import check_password, make_password

DEFAULT_USSD_PIN = "1234"
PIN_LENGTH = 4


def is_valid_pin_format(pin: str) -> bool:
    value = str(pin or "").strip()
    return len(value) == PIN_LENGTH and value.isdigit()


def verify_ussd_pin(user, pin: str) -> bool:
    if not is_valid_pin_format(pin):
        return False
    stored = getattr(user, "ussd_pin_hash", None) or ""
    if stored:
        return check_password(pin, stored)
    return pin == DEFAULT_USSD_PIN


def set_ussd_pin(user, new_pin: str) -> tuple[bool, str]:
    if not is_valid_pin_format(new_pin):
        return False, "PIN must be exactly 4 digits."
    user.ussd_pin_hash = make_password(new_pin)
    user.save(update_fields=["ussd_pin_hash", "updated_at"])
    return True, "PIN changed successfully."
