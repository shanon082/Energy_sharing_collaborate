"""Opt-in Free testing deployment: auth/read-only APIs and durable account mail."""

import os
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

from backend.feature_config import parse_feature_bool
from backend.hosting_environment import load_private_environment, positive_integer
from backend.render_config import hostname, https_url, origin, required, validate_testing_environment

load_private_environment(os.environ)
validate_testing_environment(os.environ, profile="alwaysdata")
os.environ["DJANGO_LOAD_LOCAL_ENV"] = "false"
os.environ["DEBUG"] = "False"
os.environ.setdefault("MTN_USE_SIMULATED_PAYMENTS", "false")

from backend.settings import *  # noqa: F403 -- opt-in Django settings inheritance

ALWAYSDATA_TESTING = True
ACCOUNT_EMAIL_OUTBOX_ENABLED = True
BACKGROUND_TASKS_AVAILABLE = False
SECRET_KEY = required(os.environ, "SECRET_KEY")
if len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5 or SECRET_KEY.startswith("django-insecure-"):
    raise ImproperlyConfigured("SECRET_KEY must be a fresh, strong deployment-specific secret")
_host = hostname(required(os.environ, "ALWAYSDATA_HOSTNAME"), "ALWAYSDATA_HOSTNAME")
ALLOWED_HOSTS = [_host] + [hostname(item, "EXTRA_ALLOWED_HOSTS") for item in
                         os.environ.get("EXTRA_ALLOWED_HOSTS", "").split(",") if item.strip()]
BASE_URL = https_url(os.environ.get("BASE_URL", f"https://{_host}/api/v1"), "BASE_URL")
DJANGO_HOSTED_ACCOUNT_PAGES = True
ACCOUNT_PAGES_ORIGIN = origin(f"https://{_host}", "ALWAYSDATA_HOSTNAME")
# Optional future Next.js address; account emails always use the backend origin.
FRONTEND_URL = https_url(os.environ.get("FRONTEND_URL") or ACCOUNT_PAGES_ORIGIN, "FRONTEND_URL")
_frontend = urlsplit(FRONTEND_URL)
PRODUCTION_ORIGIN = origin(os.environ.get("PRODUCTION_ORIGIN", f"https://{_frontend.netloc}"), "PRODUCTION_ORIGIN")
MOBILE_APP_ORIGIN = "http://localhost"  # installed debug APK; never remove implicitly
MOBILE_RELEASE_ORIGIN = "https://localhost"  # capacitor.config.ts default androidScheme
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = list(dict.fromkeys([PRODUCTION_ORIGIN, MOBILE_APP_ORIGIN, MOBILE_RELEASE_ORIGIN]))
CORS_ALLOW_METHODS = ["GET", "POST", "PATCH", "OPTIONS"]
CORS_ALLOW_HEADERS = ["authorization", "content-type"]
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys([ACCOUNT_PAGES_ORIGIN, PRODUCTION_ORIGIN]))
DEFAULT_HTTP_PROTOCOL = "https"
DOMAIN_NAME = _frontend.netloc

DATABASES = {"default": {
    **DATABASES["default"],
    "NAME": required(os.environ, "DB_NAME"), "USER": required(os.environ, "DB_USER"),
    "PASSWORD": required(os.environ, "DB_PASSWORD"), "HOST": required(os.environ, "DB_HOST"),
    "PORT": positive_integer(os.environ, "DB_PORT", 5432, maximum=65535),
    "CONN_MAX_AGE": 0,  # limited Free-plan database/process budget
    "OPTIONS": {**DATABASES["default"]["OPTIONS"], "sslmode": required(os.environ, "DB_SSLMODE")},
}}
if DATABASES["default"]["OPTIONS"]["sslmode"] not in {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}:
    raise ImproperlyConfigured("DB_SSLMODE must be a supported PostgreSQL SSL mode")
if os.environ.get("DB_SSLROOTCERT"):
    DATABASES["default"]["OPTIONS"]["sslrootcert"] = os.environ["DB_SSLROOTCERT"]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SIMPLE_JWT = {**SIMPLE_JWT, "AUTH_COOKIE_SECURE": True}
SECURE_HSTS_SECONDS = 0  # no persistent HSTS policy for a testing deployment
WSGI_APPLICATION = "backend.alwaysdata_wsgi.application"
ROOT_URLCONF = "backend.alwaysdata_urls"
MIDDLEWARE = [item for item in MIDDLEWARE if item != "corsheaders.middleware.CorsMiddleware"]
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
MIDDLEWARE.insert(2, "corsheaders.middleware.CorsMiddleware")
MIDDLEWARE.insert(3, "backend.hosting_middleware.FreeTestingMiddleware")
MIDDLEWARE.insert(0, "backend.hosting_middleware.AccountPageSecurityMiddleware")
STATIC_URL = "/static/"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
WHITENOISE_ALLOW_ALL_ORIGINS = False

EMAIL_HOST = required(os.environ, "EMAIL_HOST")
EMAIL_PORT = positive_integer(os.environ, "EMAIL_PORT", 587, maximum=65535)
EMAIL_HOST_USER = required(os.environ, "EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = required(os.environ, "EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = required(os.environ, "DEFAULT_EMAIL_SENDER")
DEFAULT_EMAIL_SENDER = DEFAULT_FROM_EMAIL
EMAIL_USE_TLS = parse_feature_bool(os.environ.get("EMAIL_USE_TLS", "true"), name="EMAIL_USE_TLS")
EMAIL_USE_SSL = parse_feature_bool(os.environ.get("EMAIL_USE_SSL", "false"), name="EMAIL_USE_SSL")
if EMAIL_USE_TLS == EMAIL_USE_SSL:
    raise ImproperlyConfigured("Enable exactly one of EMAIL_USE_TLS and EMAIL_USE_SSL")
EMAIL_TIMEOUT = positive_integer(os.environ, "EMAIL_TIMEOUT", 10, maximum=30)

# LocMem is deliberately not a shared throttle, ledger, session or task store.
# Django's existing database-backed sessions and JWT blacklist are unchanged.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                       "LOCATION": "alwaysdata-test-process"}}
CELERY_TASK_ALWAYS_EAGER = False
CELERY_BEAT_SCHEDULE = {}
CELERY_BROKER_URL = None
CELERY_RESULT_BACKEND = None
REDIS_URL = ""
THINGSBOARD_BASE_URL = "https://devices.disabled.invalid"
THINGSBOARD_INTERNAL_BASE_URL = ""
