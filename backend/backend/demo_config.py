"""Local prototype policy, not a tariff, currency conversion or production option."""
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from rest_framework.exceptions import PermissionDenied

LOCAL_DEMO = "LOCAL_DEMO"
DEMO_ENVIRONMENT = "UGX_DEMO"


def provider_mode():
    return getattr(settings, "PROTOTYPE_PAYMENT_PROVIDER", "MTN_SANDBOX")


def test_domain():
    return ("UGX", DEMO_ENVIRONMENT, LOCAL_DEMO) if provider_mode() == LOCAL_DEMO else ("EUR", "MTN_SANDBOX", "MTN_SANDBOX")


def require_demo():
    if getattr(settings, "CONSUMER_SANDBOX_ENABLED", False) is not True or provider_mode() != LOCAL_DEMO:
        raise PermissionDenied({"code": "DEMO_DISABLED", "message": "Local demo payments are unavailable in this deployment mode."})


def require_mtn_sandbox():
    if provider_mode() != "MTN_SANDBOX":
        raise PermissionDenied({"code": "MTN_PAUSED", "message": "MTN integration is paused. Existing EUR records remain available; demo payments cannot settle them."})


def demo_configuration(environ):
    mode = environ.get("PROTOTYPE_PAYMENT_PROVIDER", LOCAL_DEMO).strip()
    if mode not in {LOCAL_DEMO, "MTN_SANDBOX"}:
        raise ImproperlyConfigured("PROTOTYPE_PAYMENT_PROVIDER must be LOCAL_DEMO or MTN_SANDBOX in the prototype profile")
    cfg = {"id": environ.get("DEMO_POLICY_VERSION", "DEMO-UGX-v2"),
        "label": "DEMO TEST POLICY / NO REAL MONEY", "currency": "UGX", "environment": DEMO_ENVIRONMENT,
        "minimum": "1000", "starter_limit": "5000", "maximum": "50000", "rate_per_kwh": "1000",
        "interest_percent": "5", "fee": "0", "purchase_per_point": "10000",
        "purchase_score_cap": 10, "score_threshold": 80, "due_days": 7, "quote_minutes": 15,
        "penalty_percent": "0", "rounding": "Whole UGX requests; interest half-even once to whole UGX; energy floored to 10 Wh; exact remainder/excess retained"}
    for name in ("minimum", "starter_limit", "maximum", "rate_per_kwh", "fee", "purchase_per_point", "interest_percent"):
        try:
            value = Decimal(environ.get("DEMO_" + name.upper(), cfg[name]))
            if not value.is_finite() or value < 0 or value > (100 if name == "interest_percent" else 1000000):
                raise ValueError
            if name != "interest_percent" and value != value.to_integral_value():
                raise ValueError
            if name in {"minimum", "rate_per_kwh", "purchase_per_point"} and value <= 0:
                raise ValueError
            if value != value.quantize(Decimal("0.0001")):
                raise ValueError
            cfg[name] = str(value)
        except (InvalidOperation, ValueError, TypeError):
            raise ImproperlyConfigured(f"DEMO_{name.upper()} must use bounded exact prototype values (whole UGX except the percentage)") from None
    for name, low, high in (("purchase_score_cap", 0, 20), ("score_threshold", 80, 100), ("due_days", 1, 90), ("quote_minutes", 1, 60)):
        try:
            cfg[name] = int(environ.get("DEMO_" + name.upper(), cfg[name]))
            if not low <= cfg[name] <= high: raise ValueError
        except (ValueError, TypeError):
            raise ImproperlyConfigured(f"DEMO_{name.upper()} is outside prototype bounds") from None
    if not Decimal(cfg["minimum"]) <= Decimal(cfg["starter_limit"]) <= Decimal(cfg["maximum"]):
        raise ImproperlyConfigured("Demo minimum/starter/maximum must be ordered")
    if not cfg["id"].startswith("DEMO-UGX-") or len(cfg["id"]) > 80:
        raise ImproperlyConfigured("DEMO_POLICY_VERSION must start DEMO-UGX-")
    cfg["pricing_source"] = "CONFIGURED_DOMESTIC_TARIFF"
    cfg["rate_per_kwh"] = None  # Deprecated environment value cannot price new quotes.
    return mode, cfg
