"""Explicitly versioned test defaults, no UGX/EUR conversion and no real credentials."""
from decimal import Decimal, InvalidOperation
import uuid
from django.core.exceptions import ImproperlyConfigured

BASE_URL = "https://sandbox.momodeveloper.mtn.com"


def sandbox_configuration(environ, *, validate_credentials=True):
    if any(environ.get(name) for name in ("MTN_API_KEY", "MTN_API_SECRET", "MTN_SUBSCRIPTION_KEY", "MTN_API_USER_ID", "MTN_PRIMARY_KEY", "MTN_COLLECTION_PRIMARY_KEY")):
        raise ImproperlyConfigured("Legacy/production MTN credential variables are forbidden; provision dedicated MTN_SANDBOX credentials")
    if environ.get("MTN_ENVIRONMENT", "sandbox") != "sandbox" or environ.get("MTN_BASE_URL", BASE_URL).rstrip("/") != BASE_URL:
        raise ImproperlyConfigured("Production MTN environment/endpoints are forbidden in sandbox mode")
    if environ.get("MTN_SANDBOX_BASE_URL", BASE_URL).rstrip("/") != BASE_URL or environ.get("MTN_SANDBOX_CURRENCY", "EUR") != "EUR":
        raise ImproperlyConfigured("MTN sandbox requires the exact HTTPS sandbox endpoint and EUR test currency")
    config = {"BASE_URL": BASE_URL, "ENVIRONMENT": "sandbox", "CURRENCY": "EUR",
              **{key: environ.get("MTN_SANDBOX_" + key, "") for key in ("SUBSCRIPTION_KEY", "API_USER_ID", "API_KEY")}}
    if validate_credentials and config["API_USER_ID"]:
        try:
            uuid.UUID(config["API_USER_ID"])
        except ValueError:
            raise ImproperlyConfigured("MTN_SANDBOX_API_USER_ID must be a sandbox API-user UUID") from None
    policy = {"id": environ.get("SANDBOX_POLICY_VERSION", "SANDBOX-TEST-v1"),
        "label": "SANDBOX TEST POLICY / NO REAL MONEY", "currency": "EUR",
        "minimum": "1.00", "starter_limit": "2.00", "maximum": "20.00",
        "interest_percent": "5.00", "fee": "0.00", "rate_per_kwh": "1.00",
        "purchase_per_point": "10.00", "purchase_score_cap": 10, "score_threshold": 75,
        "due_days": 7, "quote_minutes": 15, "penalty_percent": "0.00",
        "rounding": "EUR cents half-even; energy floored to 10 Wh; residual/excess retained for reconciliation"}
    for name in ("minimum", "starter_limit", "maximum", "interest_percent", "fee", "rate_per_kwh", "purchase_per_point"):
        raw = environ.get("SANDBOX_" + name.upper(), policy[name])
        try:
            value = Decimal(raw)
            if not value.is_finite() or value < 0 or (name in {"minimum", "rate_per_kwh", "purchase_per_point"} and value <= 0) or value > 10000:
                raise ValueError
        except (InvalidOperation, ValueError):
            raise ImproperlyConfigured(f"SANDBOX_{name.upper()} must be a bounded exact decimal") from None
        if name in {"minimum", "starter_limit", "maximum", "fee"} and value != value.quantize(Decimal("0.01")):
            raise ImproperlyConfigured(f"SANDBOX_{name.upper()} must use EUR cents")
        if name in {"rate_per_kwh", "purchase_per_point", "interest_percent"} and value != value.quantize(Decimal("0.0001")):
            raise ImproperlyConfigured(f"SANDBOX_{name.upper()} supports at most four decimal places")
        policy[name] = str(value)
    for name, low, high in (("purchase_score_cap", 0, 20), ("score_threshold", 1, 100), ("due_days", 1, 90), ("quote_minutes", 1, 60)):
        try:
            policy[name] = int(environ.get("SANDBOX_" + name.upper(), policy[name]))
            if not low <= policy[name] <= high:
                raise ValueError
        except (TypeError, ValueError):
            raise ImproperlyConfigured(f"SANDBOX_{name.upper()} is outside its test bounds") from None
    if not Decimal(policy["minimum"]) <= Decimal(policy["starter_limit"]) <= Decimal(policy["maximum"]):
        raise ImproperlyConfigured("Sandbox minimum/starter/maximum must be ordered")
    if not policy["id"].startswith("SANDBOX-") or len(policy["id"]) > 80:
        raise ImproperlyConfigured("SANDBOX_POLICY_VERSION must be explicitly labelled SANDBOX-")
    return policy, config
