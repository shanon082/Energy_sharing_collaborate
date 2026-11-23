import os

from backend.settings import *  # noqa: F403

# Dedicated PostgreSQL test database; never points at the application database.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_TEST_NAME", "energy_test_db"),
        "USER": os.environ.get("DB_TEST_USER", "energy_test"),
        "PASSWORD": os.environ.get("DB_TEST_PASSWORD", ""),
        "HOST": os.environ.get("DB_TEST_HOST", "127.0.0.1"),
        "PORT": int(os.environ.get("DB_TEST_PORT", "5432")),
        "ATOMIC_REQUESTS": True,
        "CONN_MAX_AGE": 0,
        "TEST": {"NAME": os.environ.get("DB_TEST_DATABASE", "test_energy_test_db")},
        "OPTIONS": {"connect_timeout": 10},
    }
}
CELERY_TASK_ALWAYS_EAGER = True
CELERY_EAGER_PROPAGATES = True
