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
    from backend.ugx_authorization import business_domain
    if business_domain():
        return ('UGX', DEMO_ENVIRONMENT, 'MTN_SANDBOX')
    return ("UGX", DEMO_ENVIRONMENT, LOCAL_DEMO) if provider_mode() == LOCAL_DEMO else ("EUR", "MTN_SANDBOX", "MTN_SANDBOX")


def require_demo(*, recovery=False):
    if getattr(settings, "CONSUMER_SANDBOX_ENABLED", False) is not True or (not recovery and provider_mode() != LOCAL_DEMO):
        raise PermissionDenied({"code": "DEMO_DISABLED", "message": "Local demo payments are unavailable in this deployment mode."})


def new_mtn_payments_paused():
    return getattr(settings, "SANDBOX_NEW_PAYMENTS_ENABLED", True) is not True


def require_new_mtn_payments():
    from backend.ugx_authorization import missing_required_authorization
    if missing_required_authorization():
        raise PermissionDenied({'code': 'UGX_AUTHORIZATION_DISABLED', 'message': 'Sandbox payments unavailable: enable SANDBOX_UGX_AUTHORIZATION_ENABLED for the approved UGX test policy. Legacy EUR charging is not a fallback.'})
    if new_mtn_payments_paused():
        from backend.ugx_authorization import enabled
        if enabled():
            raise PermissionDenied({'code': 'NEW_PAYMENTS_PAUSED', 'message': 'New UGX test payment instructions are paused by server configuration. Existing submitted references remain recoverable.'})
        raise PermissionDenied({"code": "NEW_PAYMENTS_PAUSED", "message": "New payments are paused. MTN Sandbox accepts EUR only; UGX payment support requires a separately approved provider. Existing receipts and pending-payment recovery remain available."})


def require_mtn_sandbox(*, recovery=False):
    if not recovery:
        require_new_mtn_payments()
    if getattr(settings, "CONSUMER_SANDBOX_ENABLED", False) is not True or (not recovery and provider_mode() != "MTN_SANDBOX"):
        raise PermissionDenied({"code": "MTN_PAUSED", "message": "New MTN collections are unavailable in this mode. Existing references retain their original provider for reconciliation."})


def demo_configuration(environ):
    mode = environ.get("PROTOTYPE_PAYMENT_PROVIDER", "MTN_SANDBOX").strip()
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
