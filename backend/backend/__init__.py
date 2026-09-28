import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

try:
    from celery import Celery

    celery_app = Celery("backend")
    celery_app.config_from_object("django.conf:settings", namespace="CELERY")
    celery_app.autodiscover_tasks()
    celery_app.conf.worker_hijack_root_logger = False
except ModuleNotFoundError:
    # Keep Django management commands usable when Celery isn't installed locally.
    celery_app = None