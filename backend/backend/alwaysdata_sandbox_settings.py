"""Opt-in consumer prototype; LOCAL_DEMO by default, ordinary hosting stays read-only."""
import os
from backend.alwaysdata_settings import *  # noqa: F403
from backend.sandbox_config import sandbox_configuration
from backend.demo_config import demo_configuration

CONSUMER_SANDBOX_ENABLED = True
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
