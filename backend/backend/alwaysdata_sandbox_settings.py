"""Opt-in MTN SANDBOX / NO REAL MONEY profile; the default profile stays read-only."""
import os
from backend.alwaysdata_settings import *  # noqa: F403
from backend.sandbox_config import sandbox_configuration

CONSUMER_SANDBOX_ENABLED = True
SANDBOX_POLICY, MTN_SANDBOX_CONFIG = sandbox_configuration(os.environ)
# Never reuse the legacy adapter's credentials or automatic simulation fallback.
MTN_MOMO_CONFIG = {"BASE_URL": "https://sandbox.momodeveloper.mtn.com", "ENVIRONMENT": "sandbox"}
ROOT_URLCONF = "backend.alwaysdata_urls"
WSGI_APPLICATION = "backend.alwaysdata_sandbox_wsgi.application"
DATABASES = {"default": {**DATABASES["default"], "OPTIONS": {
    **DATABASES["default"]["OPTIONS"], "connect_timeout": 5,
    "options": DATABASES["default"]["OPTIONS"].get("options", "") + " -c statement_timeout=10000 -c lock_timeout=5000",
}}}
