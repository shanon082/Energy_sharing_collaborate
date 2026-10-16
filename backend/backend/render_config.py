"""Validation for the opt-in Render testing profile; errors never include values."""

import re
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

from backend.feature_config import FEATURE_ENV_VARS, parse_feature_bool


def required(environ, name):
    value = environ.get(name, "")
    if not value.strip() or re.fullmatch(r"<[^<>]+>", value.strip()):
        raise ImproperlyConfigured(f"Set {name} in the hosting environment; placeholders are not values")
    return value


def hostname(value, name):
    value = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", value):
        raise ImproperlyConfigured(f"{name} must contain hostnames without schemes, ports or wildcards")
    return value


def https_url(value, name):
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise ImproperlyConfigured(f"{name} must be an HTTPS URL") from None
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment or port == 0):
        raise ImproperlyConfigured(f"{name} must be an HTTPS URL without credentials, query or fragment")
    hostname(parsed.hostname, name)
    return value.rstrip("/")


def origin(value, name, *, mobile=False):
    # This is the WebView's origin, not its remote API hostname. Only the debug
    # localhost origin is allowed to use HTTP; the API itself remains HTTPS.
    if mobile and value == "http://localhost":
        return value
    https_url(value, name)
    parsed = urlsplit(value)
    if parsed.path:
        raise ImproperlyConfigured(f"{name} must be one origin without a path or trailing slash")
    return value


def redis_url(value, name):
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise ImproperlyConfigured(f"{name} must be a Redis URL") from None
    if parsed.scheme not in {"redis", "rediss"} or not parsed.hostname or port == 0:
        raise ImproperlyConfigured(f"{name} must be a redis:// or rediss:// URL")
    hostname(parsed.hostname, name)
    return value


def validate_testing_environment(environ, *, profile="Render"):
    for name in ("BENCH_DEVICE_ENABLED", "DEBUG", "SIMULATED_METER_ENABLED", "MOBILE_PAYMENT_ACTIONS_ENABLED",
                 "CELERY_TASK_ALWAYS_EAGER", "PURCHASE_HISTORY_SCORING_ENABLED", *FEATURE_ENV_VARS.values()):
        if parse_feature_bool(environ.get(name, "false"), name=name):
            raise ImproperlyConfigured(f"{name} must remain disabled in the {profile} testing profile")
    # The provider's legacy parser accepts false/0/no (not the feature parser's
    # off). Require an explicit value so missing keys cannot enable simulation.
    if environ.get("MTN_USE_SIMULATED_PAYMENTS", "false").lower() not in {"false", "0", "no"}:
        raise ImproperlyConfigured("MTN_USE_SIMULATED_PAYMENTS must be false, 0 or no")
    for name in ("THINGSBOARD_TENANT_PASSWORD", "THINGSBOARD_WEBHOOK_SECRET",
                 "MTN_SUBSCRIPTION_KEY", "PRIMARY_KEY", "SECONDARY_KEY", "MTN_API_KEY",
                 "MTN_API_USER_ID"):
        if environ.get(name):
            raise ImproperlyConfigured(f"Do not provision {name} in the isolated {profile} testing profile")
    if environ.get("AMI_GATEWAY", "utils.ami_gateway.MockAMIGateway") != "utils.ami_gateway.MockAMIGateway":
        raise ImproperlyConfigured(f"AMI_GATEWAY must remain the mock gateway for {profile} testing")
    if environ.get("CRB_PROVIDER", "loan.crb.NoOpCreditBureauProvider") != "loan.crb.NoOpCreditBureauProvider":
        raise ImproperlyConfigured(f"CRB_PROVIDER must remain the no-op provider for {profile} testing")
