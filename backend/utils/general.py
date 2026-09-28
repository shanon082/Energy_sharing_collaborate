import logging
import random
from base64 import b64encode
from typing import Callable
from django.conf import settings
from django.utils import timezone
from decimal import Decimal

_task_logger = logging.getLogger(__name__)


def dispatch_task(task, *args, **kwargs):
    """
    Call a Celery task directly in DEBUG mode (no Redis/broker needed),
    or dispatch via .delay() in production.
    """
    if settings.DEBUG:
        try:
            task(*args, **kwargs)
        except Exception as exc:
            _task_logger.warning("Background task %s failed: %s", task.__name__, exc)
    else:
        try:
            task.delay(*args, **kwargs)
        except Exception as exc:
            # Production resilience: if broker/worker is unavailable, execute now
            # so critical notifications (verification/reset/share alerts) are not lost.
            _task_logger.exception(
                "Celery dispatch failed for %s; falling back to sync execution: %s",
                getattr(task, "__name__", str(task)),
                exc,
            )
            try:
                task(*args, **kwargs)
            except Exception as sync_exc:
                _task_logger.warning(
                    "Synchronous fallback also failed for %s: %s",
                    getattr(task, "__name__", str(task)),
                    sync_exc,
                )

def format_currency(value: Decimal, currency_symbol="") -> str:
    """Format decimal value as currency string (e.g., '100.00 units')."""
    return f"{currency_symbol}{float(value):.2f}".replace("-", "-")


def get_base_url():
    return f"{settings.DEFAULT_HTTP_PROTOCOL}://{settings.DOMAIN_NAME}"


def get_b64_encoded_token(key, pwd, encoding="utf-8"):
    return b64encode(f"{key}:{pwd}".encode(encoding)).decode(encoding)


def get_app_base_url():
    base_url = get_base_url()
    if settings.ENV_PREFIX == "local":
        base_url = settings.LOCAL_CALLBACK_URL
    return base_url


def generate_numeric_id(upper=10):
    """Utility to generate a random combination of numeric characters"""
    now = timezone.now()
    month = f"{now.month:02}"
    day = f"{now.day:02}"
    rand = f"{random.randint(0,999999):06}"
    unique_str = f"{month}{day}{rand}"
    return unique_str


def get_human_date(date):
    day = date.day
    month = date.strftime("%B")
    year = date.year
    hour = date.hour
    minute = date.minute
    return f"{month} {day}, {year} {hour}:{minute}"


def bytes2str(
    func: Callable[[bytes], bytes], text: str, encoding="utf8"
) -> str:
    if isinstance(text, str):
        # convert/encode to bytes
        text = text.encode(encoding)
    return func(text).decode(encoding)
