"""Opt-in, isolated Render testing settings. Never use for funded live accounts."""

import os
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

from backend.feature_config import parse_feature_bool
from backend.render_config import (
    hostname, https_url, origin, redis_url, required, validate_testing_environment,
)

validate_testing_environment(os.environ)
# Must happen before importing settings: never read the developer's .env here.
os.environ["DJANGO_LOAD_LOCAL_ENV"] = "false"
os.environ["DEBUG"] = "False"
os.environ.setdefault("MTN_USE_SIMULATED_PAYMENTS", "false")

from backend.settings import *  # noqa: F403 -- Django settings profile inheritance

SECRET_KEY = required(os.environ, "SECRET_KEY")
_render_host = hostname(required(os.environ, "RENDER_EXTERNAL_HOSTNAME"), "RENDER_EXTERNAL_HOSTNAME")
ALLOWED_HOSTS = [_render_host] + [
    hostname(host, "EXTRA_ALLOWED_HOSTS")
    for host in os.environ.get("EXTRA_ALLOWED_HOSTS", "").split(",") if host.strip()
]
BASE_URL = https_url(os.environ.get("BASE_URL", f"https://{_render_host}/api/v1"), "BASE_URL")
FRONTEND_URL = https_url(required(os.environ, "FRONTEND_URL"), "FRONTEND_URL")
_frontend = urlsplit(FRONTEND_URL)
PRODUCTION_ORIGIN = origin(
    os.environ.get("PRODUCTION_ORIGIN", f"{_frontend.scheme}://{_frontend.netloc}"), "PRODUCTION_ORIGIN",
)
MOBILE_APP_ORIGIN = origin(
    os.environ.get("MOBILE_APP_ORIGIN", "http://localhost"), "MOBILE_APP_ORIGIN", mobile=True,
)
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = list(dict.fromkeys([PRODUCTION_ORIGIN, MOBILE_APP_ORIGIN]))
# Cookie-based web/admin CSRF protection is retained. Native bearer requests do
# not need their WebView origin trusted for cookie-based CSRF.
CSRF_TRUSTED_ORIGINS = [PRODUCTION_ORIGIN]
DEFAULT_HTTP_PROTOCOL = "https"
DOMAIN_NAME = _frontend.netloc

DATABASES = {"default": {
    **DATABASES["default"],
    "NAME": required(os.environ, "DB_NAME"),
    "USER": required(os.environ, "DB_USER"),
    "PASSWORD": required(os.environ, "DB_PASSWORD"),
    "HOST": required(os.environ, "DB_HOST"),
    "PORT": int(os.environ.get("DB_PORT", "5432")),
    "OPTIONS": {**DATABASES["default"]["OPTIONS"], "sslmode": required(os.environ, "DB_SSLMODE")},
}}
if DATABASES["default"]["OPTIONS"]["sslmode"] not in {
    "disable", "allow", "prefer", "require", "verify-ca", "verify-full",
}:
    raise ImproperlyConfigured("DB_SSLMODE must be a supported PostgreSQL SSL mode")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SIMPLE_JWT = {**SIMPLE_JWT, "AUTH_COOKIE_SECURE": True}
# No HSTS preload/long-lived policy for disposable testing domains.
SECURE_HSTS_SECONDS = 0

MIDDLEWARE = [item for item in MIDDLEWARE if item != "corsheaders.middleware.CorsMiddleware"]
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
MIDDLEWARE.insert(2, "corsheaders.middleware.CorsMiddleware")
STATIC_URL = "/static/"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
WHITENOISE_ALLOW_ALL_ORIGINS = False

EMAIL_HOST = required(os.environ, "EMAIL_HOST")
EMAIL_HOST_USER = required(os.environ, "EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = required(os.environ, "EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = required(os.environ, "DEFAULT_EMAIL_SENDER")
DEFAULT_EMAIL_SENDER = DEFAULT_FROM_EMAIL
EMAIL_USE_TLS = parse_feature_bool(os.environ.get("EMAIL_USE_TLS", "true"), name="EMAIL_USE_TLS")
EMAIL_USE_SSL = parse_feature_bool(os.environ.get("EMAIL_USE_SSL", "false"), name="EMAIL_USE_SSL")
if EMAIL_USE_TLS == EMAIL_USE_SSL:
    raise ImproperlyConfigured("Enable exactly one of EMAIL_USE_TLS and EMAIL_USE_SSL")
EMAIL_TIMEOUT = 15

CELERY_BROKER_URL = redis_url(required(os.environ, "CELERY_BROKER_URL"), "CELERY_BROKER_URL")
REDIS_URL = redis_url(os.environ.get("REDIS_URL", CELERY_BROKER_URL), "REDIS_URL")
CELERY_RESULT_BACKEND = redis_url(
    os.environ.get("CELERY_RESULT_BACKEND", CELERY_BROKER_URL), "CELERY_RESULT_BACKEND",
)
CELERY_TASK_ALWAYS_EAGER = False
# Only email/background tasks explicitly dispatched by isolated test activity.
# Beat's base schedule includes provider polling and physical AMI integration.
# A live deployment needs an independently reviewed reconciliation schedule.
CELERY_BEAT_SCHEDULE = {}
CELERY_BEAT_SCHEDULER = "celery.beat:PersistentScheduler"
THINGSBOARD_BASE_URL = "https://devices.disabled.invalid"
THINGSBOARD_INTERNAL_BASE_URL = ""
