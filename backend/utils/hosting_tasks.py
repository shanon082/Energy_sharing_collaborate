"""Fail explicitly instead of accepting tasks into a nonexistent Free-plan queue."""

from celery import Celery, Task
from django.conf import settings
from rest_framework.exceptions import APIException


class BackgroundTaskUnavailable(APIException):
    status_code = 503
    default_code = "BACKGROUND_TASK_UNAVAILABLE"

    def __init__(self):
        super().__init__({"code": self.default_code,
                          "message": "This operation needs a background worker unavailable on this testing host."})


def require_background_tasks():
    if getattr(settings, "BACKGROUND_TASKS_AVAILABLE", True) is False:
        raise BackgroundTaskUnavailable()


class HostingTask(Task):
    def apply_async(self, *args, **kwargs):
        require_background_tasks()
        return super().apply_async(*args, **kwargs)


class HostingCelery(Celery):
    def send_task(self, *args, **kwargs):
        require_background_tasks()
        return super().send_task(*args, **kwargs)
