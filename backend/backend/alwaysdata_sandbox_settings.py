"""Opt-in EUR MTN sandbox; ordinary hosting and physical writes stay restricted."""
import os
from backend.alwaysdata_settings import *  # noqa: F403
from backend.sandbox_config import sandbox_configuration
from backend.demo_config import demo_configuration

CONSUMER_SANDBOX_ENABLED = True
# Meter-bound automatic assessment currently exists only in UGX_DEMO. Historical
# EUR debt is repayable, but its old questionnaire source cannot authorize NEW loans.
SANDBOX_EUR_LOANS_ENABLED = False  # Requires a separately reviewed EUR assessment policy.
PROTOTYPE_PAYMENT_PROVIDER, DEMO_POLICY = demo_configuration(os.environ)
SANDBOX_POLICY, MTN_SANDBOX_CONFIG = sandbox_configuration(os.environ, validate_credentials=PROTOTYPE_PAYMENT_PROVIDER == "MTN_SANDBOX")
# Never reuse the legacy adapter's credentials or automatic simulation fallback.
MTN_MOMO_CONFIG = {"BASE_URL": "https://sandbox.momodeveloper.mtn.com", "ENVIRONMENT": "sandbox"}
ROOT_URLCONF = "backend.alwaysdata_urls"
WSGI_APPLICATION = "backend.alwaysdata_sandbox_wsgi.application"
DATABASES = {"default": {**DATABASES["default"], "OPTIONS": {
    **DATABASES["default"]["OPTIONS"], "connect_timeout": 5,
    "options": DATABASES["default"]["OPTIONS"].get("options", "") + " -c statement_timeout=10000 -c lock_timeout=5000",
}}}

from loan.account_data import SCENARIOS
DEMO_ACCOUNT_PROFILE = os.environ.get("DEMO_ACCOUNT_PROFILE", "APPROVAL_V1")
if DEMO_ACCOUNT_PROFILE not in SCENARIOS:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("DEMO_ACCOUNT_PROFILE must name a supported synthetic fixture")

# Separate commissioned AC lab capability; all household/relay routes stay blocked.
from backend.feature_config import parse_feature_bool
PROTOTYPE_AC_LAB_ENABLED = parse_feature_bool(os.environ.get("PROTOTYPE_AC_LAB_ENABLED", "false"), name="PROTOTYPE_AC_LAB_ENABLED")
PROTOTYPE_RELAY_OUTPUT_ENABLED = False  # Not environment-configurable in this milestone.
