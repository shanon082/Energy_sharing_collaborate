"""Explicit loopback-only software-device bench; never use on alwaysdata."""
import os
from django.core.exceptions import ImproperlyConfigured
from backend.feature_config import parse_feature_bool

if os.environ.get("BENCH_ENV_FILE"):
    from backend.hosting_environment import load_private_environment
    private = dict(os.environ)
    private["ALWAYSDATA_ENV_FILE"] = os.environ["BENCH_ENV_FILE"]
    load_private_environment(private)
    for name, value in private.items():
        if name != "ALWAYSDATA_ENV_FILE":
            os.environ.setdefault(name, value)
if len(os.environ.get("SECRET_KEY", "")) < 50:
    raise ImproperlyConfigured("Use a fresh private SECRET_KEY for the isolated bench")

os.environ["DJANGO_LOAD_LOCAL_ENV"] = "false"
if not parse_feature_bool(os.environ.get("BENCH_DEVICE_ENABLED", "false"), name="BENCH_DEVICE_ENABLED"):
    raise ImproperlyConfigured("Explicit BENCH_DEVICE_ENABLED=true is required for the isolated bench")
_name = os.environ.get("BENCH_DATABASE_NAME", "")
if not _name.startswith("gpawa_bench_") or os.environ.get("DB_HOST", "") not in {"127.0.0.1", "localhost", "::1"}:
    raise ImproperlyConfigured("Bench requires a separate gpawa_bench_* PostgreSQL database on loopback")
from backend.settings import *  # noqa: F403
from backend.demo_config import demo_configuration
from backend.sandbox_config import sandbox_configuration

DATABASES = {"default": {**DATABASES["default"], "NAME": _name}}
DEBUG = False
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]
BENCH_DEVICE_ENABLED = True
DEVICE_BENCH_ISOLATED = True
CONSUMER_SANDBOX_ENABLED = True
PROTOTYPE_PAYMENT_PROVIDER, DEMO_POLICY = demo_configuration({"PROTOTYPE_PAYMENT_PROVIDER": "LOCAL_DEMO"})
SANDBOX_POLICY, MTN_SANDBOX_CONFIG = sandbox_configuration({}, validate_credentials=False)
if not ENERGY_TOKEN_ISSUANCE_ENABLED:
    raise ImproperlyConfigured("Bench requires configured ENERGY_TOKEN_ISSUANCE_ENABLED=true")
SIMULATED_METER_ENABLED = False
MOBILE_PAYMENT_ACTIONS_ENABLED = False
MTN_USE_SIMULATED_PAYMENTS = False
MTN_MOMO_CONFIG = {"ENVIRONMENT": "disabled", "BASE_URL": "https://payments.disabled.invalid"}
THINGSBOARD_BASE_URL = "https://devices.disabled.invalid"
THINGSBOARD_INTERNAL_BASE_URL = ""
BACKGROUND_TASKS_AVAILABLE = False
CELERY_TASK_ALWAYS_EAGER = False
CELERY_BEAT_SCHEDULE = {}
CELERY_BROKER_URL = None
CELERY_RESULT_BACKEND = None
ACCOUNT_EMAIL_OUTBOX_ENABLED = True
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
FEATURE_FLAGS = {key: False for key in FEATURE_FLAGS}
