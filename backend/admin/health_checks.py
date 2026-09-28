"""
Live probes for the admin System Health dashboard.
Each checker returns: status (GREEN|AMBER|RED), description, optional error, optional latency_ms.
"""
from __future__ import annotations

import os
import time

import requests
from django.conf import settings
from django.db import connection


def _latency_ms(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)


def _component(
    description: str,
    status: str,
    *,
    error: str = "",
    latency_ms: int | None = None,
    extras: dict | None = None,
) -> dict:
    payload = {"description": description, "status": status}
    if error:
        payload["error"] = error
    if latency_ms is not None:
        payload["latency_ms"] = latency_ms
    if extras:
        payload.update(extras)
    return payload


def check_postgresql() -> dict:
    start = time.perf_counter()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return _component("PostgreSQL Database", "GREEN", latency_ms=_latency_ms(start))
    except Exception as exc:
        return _component("PostgreSQL Database", "RED", error=str(exc), latency_ms=_latency_ms(start))


def check_redis() -> dict:
    start = time.perf_counter()
    broker_url = getattr(settings, "CELERY_BROKER_URL", "") or getattr(settings, "REDIS_URL", "")
    if not broker_url:
        return _component("Redis Cache", "AMBER", error="Redis URL not configured", latency_ms=_latency_ms(start))
    try:
        import redis

        client = redis.from_url(broker_url, socket_connect_timeout=3, socket_timeout=3)
        client.ping()
        return _component("Redis Cache", "GREEN", latency_ms=_latency_ms(start))
    except Exception as exc:
        eager = getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False)
        if eager:
            return _component(
                "Redis Cache",
                "AMBER",
                error=f"Unreachable ({exc}); tasks run inline (CELERY_TASK_ALWAYS_EAGER)",
                latency_ms=_latency_ms(start),
            )
        return _component("Redis Cache", "RED", error=str(exc), latency_ms=_latency_ms(start))


def check_api_gateway() -> dict:
    """API is up if this health check runs successfully."""
    start = time.perf_counter()
    return _component("API Gateway", "GREEN", latency_ms=_latency_ms(start))


def check_celery_dispatch() -> dict:
    """Verify background tasks can be dispatched to the Celery broker."""
    start = time.perf_counter()
    eager = getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False)
    if eager:
        return _component(
            "Celery Dispatch",
            "AMBER",
            error="Tasks run inline (CELERY_TASK_ALWAYS_EAGER); no broker dispatch",
            latency_ms=_latency_ms(start),
            extras={"celery_dispatch_ok": True, "celery_mode": "inline"},
        )
    try:
        from celery import current_app

        conn = current_app.connection()
        conn.ensure_connection(max_retries=1, timeout=3)
        with current_app.producer_or_acquire() as _producer:
            pass
        conn.release()
        return _component(
            "Celery Dispatch",
            "GREEN",
            latency_ms=_latency_ms(start),
            extras={"celery_dispatch_ok": True, "celery_mode": "broker"},
        )
    except ImportError:
        return _component(
            "Celery Dispatch",
            "AMBER",
            error="Celery not installed; background worker status unknown",
            latency_ms=_latency_ms(start),
            extras={"celery_dispatch_ok": False, "celery_mode": "unknown"},
        )
    except Exception as exc:
        return _component(
            "Celery Dispatch",
            "RED",
            error=f"Broker unreachable: {exc}",
            latency_ms=_latency_ms(start),
            extras={"celery_dispatch_ok": False, "celery_mode": "broker"},
        )


def _thingsboard_probe() -> tuple[bool, str]:
    from meter.services import (
        _thingsboard_base_url,
        _thingsboard_request_kwargs,
    )

    base = _thingsboard_base_url()
    if not base:
        return False, "THINGSBOARD_BASE_URL is not configured"
    try:
        response = requests.get(f"{base}/", **_thingsboard_request_kwargs())
        if response.status_code < 500:
            return True, ""
        return False, f"HTTP {response.status_code}"
    except requests.RequestException as exc:
        return False, f"{exc.__class__.__name__}: {exc}"


def check_cvs_sts_api() -> dict:
    """
    STS tokens are generated locally; AMI delivery uses ThingsBoard when configured.
  """
    start = time.perf_counter()
    gateway = getattr(settings, "AMI_GATEWAY", "") or ""
    external_cvs = (os.getenv("CVS_STS_API_URL") or os.getenv("STS_API_URL") or "").strip()

    if external_cvs:
        try:
            response = requests.get(external_cvs, timeout=8)
            if response.status_code < 500:
                return _component("CVS/STS Token API", "GREEN", latency_ms=_latency_ms(start))
            return _component(
                "CVS/STS Token API",
                "RED",
                error=f"External CVS API returned HTTP {response.status_code}",
                latency_ms=_latency_ms(start),
            )
        except requests.RequestException as exc:
            return _component("CVS/STS Token API", "RED", error=str(exc), latency_ms=_latency_ms(start))

    if "MockAMIGateway" in gateway:
        tb_ok, tb_err = _thingsboard_probe()
        if tb_ok:
            return _component(
                "CVS/STS Token API",
                "AMBER",
                error="Pilot mode: local STS tokens; ThingsBoard reachable for AMI",
                latency_ms=_latency_ms(start),
            )
        if (getattr(settings, "THINGSBOARD_INTERNAL_BASE_URL", "") or getattr(settings, "THINGSBOARD_BASE_URL", "")):
            return _component(
                "CVS/STS Token API",
                "RED",
                error=f"Pilot STS mode; ThingsBoard unreachable: {tb_err}",
                latency_ms=_latency_ms(start),
            )
        return _component(
            "CVS/STS Token API",
            "AMBER",
            error="Pilot mode: local STS tokens; mock AMI gateway (no ThingsBoard)",
            latency_ms=_latency_ms(start),
        )

    tb_ok, tb_err = _thingsboard_probe()
    if not tb_ok:
        return _component(
            "CVS/STS Token API",
            "RED",
            error=f"AMI gateway active but ThingsBoard unreachable: {tb_err}",
            latency_ms=_latency_ms(start),
        )
    return _component("CVS/STS Token API", "GREEN", latency_ms=_latency_ms(start))


def check_africas_talking() -> dict:
    start = time.perf_counter()
    api_key = (
        os.getenv("AT_API_KEY")
        or os.getenv("AFRICASTALKING_API_KEY")
        or os.getenv("AFRICAS_TALKING_API_KEY")
        or ""
    ).strip()
    username = (
        os.getenv("AT_USERNAME")
        or os.getenv("AFRICASTALKING_USERNAME")
        or os.getenv("AFRICAS_TALKING_USERNAME")
        or ""
    ).strip()
    if not api_key or not username:
        return _component(
            "Africa's Talking (USSD/SMS)",
            "AMBER",
            error="Not configured — USSD uses local simulator / direct HTTP",
            latency_ms=_latency_ms(start),
        )
    try:
        response = requests.get(
            "https://api.africastalking.com/version1/user",
            headers={"apiKey": api_key, "Accept": "application/json"},
            params={"username": username},
            timeout=10,
        )
        if response.status_code == 200:
            return _component("Africa's Talking (USSD/SMS)", "GREEN", latency_ms=_latency_ms(start))
        return _component(
            "Africa's Talking (USSD/SMS)",
            "RED",
            error=f"API returned HTTP {response.status_code}",
            latency_ms=_latency_ms(start),
        )
    except requests.RequestException as exc:
        return _component("Africa's Talking (USSD/SMS)", "RED", error=str(exc), latency_ms=_latency_ms(start))


def check_mtn_momo() -> dict:
    start = time.perf_counter()
    from mtn_momo.config import is_momo_configured, should_simulate_payments
    from mtn_momo.services import MTNMoMoService

    if should_simulate_payments():
        reason = "MTN_USE_SIMULATED_PAYMENTS enabled" if os.getenv("MTN_USE_SIMULATED_PAYMENTS") else "credentials missing"
        return _component(
            "MTN MoMo API",
            "AMBER",
            error=f"Simulated payments ({reason})",
            latency_ms=_latency_ms(start),
        )
    if not is_momo_configured():
        return _component(
            "MTN MoMo API",
            "AMBER",
            error="Not fully configured",
            latency_ms=_latency_ms(start),
        )
    token = MTNMoMoService().get_api_token()
    if token:
        return _component("MTN MoMo API", "GREEN", latency_ms=_latency_ms(start))
    return _component("MTN MoMo API", "RED", error="Could not obtain API token", latency_ms=_latency_ms(start))


def check_airtel_money() -> dict:
    start = time.perf_counter()
    client_id = (os.getenv("AIRTEL_MONEY_CLIENT_ID") or os.getenv("AIRTEL_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("AIRTEL_MONEY_CLIENT_SECRET") or os.getenv("AIRTEL_CLIENT_SECRET") or "").strip()
    if not client_id or not client_secret:
        return _component(
            "Airtel Money API",
            "AMBER",
            error="Not integrated / credentials not set",
            latency_ms=_latency_ms(start),
        )
    base = (os.getenv("AIRTEL_MONEY_BASE_URL") or "https://openapi.airtel.africa").rstrip("/")
    try:
        response = requests.get(f"{base}/", timeout=8)
        if response.status_code < 500:
            return _component("Airtel Money API", "GREEN", latency_ms=_latency_ms(start))
        return _component(
            "Airtel Money API",
            "RED",
            error=f"HTTP {response.status_code}",
            latency_ms=_latency_ms(start),
        )
    except requests.RequestException as exc:
        return _component("Airtel Money API", "RED", error=str(exc), latency_ms=_latency_ms(start))


def check_firebase() -> dict:
    start = time.perf_counter()
    creds = (
        os.getenv("FIREBASE_CREDENTIALS_JSON")
        or os.getenv("FIREBASE_CREDENTIALS_PATH")
        or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        or ""
    ).strip()
    project_id = (os.getenv("FIREBASE_PROJECT_ID") or "").strip()
    if not creds and not project_id:
        return _component(
            "Firebase (Push Notifications)",
            "AMBER",
            error="Not configured",
            latency_ms=_latency_ms(start),
        )
    if creds and not os.path.isfile(creds) and not creds.strip().startswith("{"):
        return _component(
            "Firebase (Push Notifications)",
            "AMBER",
            error="Credentials path set but file not found",
            latency_ms=_latency_ms(start),
        )
    return _component("Firebase (Push Notifications)", "GREEN", latency_ms=_latency_ms(start))


def run_all_health_checks() -> dict:
    components = {
        "api_gateway": check_api_gateway(),
        "celery_dispatch": check_celery_dispatch(),
        "postgresql": check_postgresql(),
        "redis": check_redis(),
        "cvs_sts_api": check_cvs_sts_api(),
        "africas_talking": check_africas_talking(),
        "mtn_momo": check_mtn_momo(),
        "airtel_money": check_airtel_money(),
        "firebase": check_firebase(),
    }
    statuses = [c["status"] for c in components.values()]
    if "RED" in statuses:
        overall = "RED"
    elif "AMBER" in statuses:
        overall = "AMBER"
    else:
        overall = "GREEN"
    return {"overall_status": overall, "components": components}
