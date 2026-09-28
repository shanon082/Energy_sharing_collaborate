"""Shared transaction PIN verification.

A confirmation PIN required as the final authentication step for value-moving
actions (buy units, share units, loan request) across USSD, web, and mobile —
even after the user has already logged in with their password.

NOTE: Currently a single shared default PIN for every user. Replace with a
per-user hashed PIN later (the User model previously carried a ``ussd_pin_hash``
field; see accounts migrations 0016/0017). Call sites already pass ``user`` so
that switch needs no changes here.
"""
from django.conf import settings

# Shared confirmation PIN for all users (temporary; per-user PIN TBD).
DEFAULT_TRANSACTION_PIN = str(getattr(settings, "TRANSACTION_PIN_DEFAULT", "1234"))

# Standard message returned to clients on a wrong/missing PIN.
PIN_ERROR_MESSAGE = "Incorrect PIN."


def normalize_pin(pin) -> str:
    return str(pin or "").strip()


def verify_transaction_pin(user, pin) -> bool:
    """Return True when the supplied PIN matches the user's transaction PIN.

    ``user`` is accepted (and currently unused) so call sites are ready for a
    per-user PIN without further changes.
    """
    return normalize_pin(pin) == DEFAULT_TRANSACTION_PIN
