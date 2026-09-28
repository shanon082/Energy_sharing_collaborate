import logging
from datetime import datetime
from decimal import Decimal

import requests
from django.conf import settings
from django.utils import timezone


logger = logging.getLogger(__name__)


def _thingsboard_base_url():
    """URL used for outbound server→ThingsBoard HTTP calls."""
    internal = (getattr(settings, "THINGSBOARD_INTERNAL_BASE_URL", "") or "").strip().rstrip("/")
    if internal:
        return internal
    return (getattr(settings, "THINGSBOARD_BASE_URL", "") or "").rstrip("/")


def _thingsboard_public_base_url():
    return (getattr(settings, "THINGSBOARD_BASE_URL", "") or "").rstrip("/")


def _thingsboard_request_kwargs():
    return {
        "timeout": int(getattr(settings, "THINGSBOARD_TIMEOUT_SECONDS", 15)),
        "verify": getattr(settings, "THINGSBOARD_VERIFY_SSL", True),
    }


def _thingsboard_connection_error_message(exc, *, action="reach ThingsBoard") -> str:
    host = _thingsboard_base_url() or "(not configured)"
    public = _thingsboard_public_base_url()
    detail = str(exc).strip()
    name = exc.__class__.__name__
    parts = [f"ThingsBoard request failed: could not {action} at {host} ({name}"]
    if detail and detail != name:
        parts.append(f": {detail}")
    parts.append(").")
    msg = "".join(parts)

    hints = []
    if name in ("ConnectionError", "ConnectTimeout", "ReadTimeout", "ConnectionRefusedError"):
        hints.append(
            "Confirm ThingsBoard is running and the backend server can reach it "
            "(firewall, DNS, nginx)."
        )
        if public and host != public:
            hints.append(f"Public URL is {public}; backend is using internal URL {host}.")
        elif public:
            hints.append(
                "If ThingsBoard is on this same machine, set THINGSBOARD_INTERNAL_BASE_URL "
                "in backend .env (e.g. http://127.0.0.1:8080)."
            )
    elif name == "SSLError":
        hints.append(
            "TLS verification failed. Use a valid certificate or set THINGSBOARD_VERIFY_SSL=false "
            "for pilot/self-signed setups."
        )
    if hints:
        msg += " " + " ".join(hints)
    return msg


def _meter_device_token(meter):
    return (meter.iot_device_token or "").strip()


def push_units_to_thingsboard(meter, units, reference_id=""):
    """
    Push unit credit telemetry to ThingsBoard for a specific meter device.
    Returns (ok: bool, message: str).
    """
    token = _meter_device_token(meter)
    if not token:
        return False, "Meter has no ThingsBoard device token configured."

    if token.startswith("dev-"):
        logger.info(
            "[ThingsBoard] Stub push for meter=%s amount=%s ref=%s",
            meter.meter_no,
            units,
            reference_id,
        )
        return True, "ThingsBoard push stubbed (dev token)."

    base_url = _thingsboard_base_url()
    if not base_url:
        return False, "THINGSBOARD_BASE_URL is not configured."

    payload = {
        "payment": True,
        "amount": float(Decimal(str(units))),
    }
    if reference_id:
        payload["tx_ref"] = reference_id

    url = f"{base_url}/api/v1/{token}/telemetry"
    req_kwargs = _thingsboard_request_kwargs()

    try:
        response = requests.post(url, json=payload, **req_kwargs)
        if 200 <= response.status_code < 300:
            return True, "ThingsBoard push successful."
        logger.warning(
            "ThingsBoard push failed for meter=%s status=%s body=%s",
            meter.meter_no,
            response.status_code,
            response.text[:300],
        )
        return False, f"ThingsBoard rejected telemetry (HTTP {response.status_code})."
    except requests.RequestException as exc:
        logger.exception("ThingsBoard request failed for meter=%s", meter.meter_no)
        return False, _thingsboard_connection_error_message(exc, action="push telemetry to")


def _parse_remaining_units_value(raw):
    """Normalize ThingsBoard remaining_units from attribute or telemetry payloads."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float, Decimal)):
        return float(raw)
    if isinstance(raw, str):
        try:
            return float(Decimal(raw.strip()))
        except Exception:
            return None
    if isinstance(raw, dict):
        if "value" in raw:
            return _parse_remaining_units_value(raw.get("value"))
        if "remaining_units" in raw:
            return _parse_remaining_units_value(raw.get("remaining_units"))
        return None
    if isinstance(raw, list) and raw:
        last = raw[-1]
        if isinstance(last, dict):
            return _parse_remaining_units_value(last.get("value", last))
        return _parse_remaining_units_value(last)
    return None


def _read_remaining_from_thingsboard_scope(token, base_url, timeout, scope_key):
    """Read remaining_units from shared or server device attributes."""
    url = f"{base_url}/api/v1/{token}/attributes"
    params = {scope_key: "remaining_units"}
    req_kwargs = {**_thingsboard_request_kwargs(), "timeout": timeout}
    response = requests.get(url, params=params, **req_kwargs)
    if not (200 <= response.status_code < 300):
        return None, response

    payload = response.json()
    bucket = payload.get(scope_key.replace("Keys", "")) or {}
    if not isinstance(bucket, dict):
        bucket = {}
    remaining = _parse_remaining_units_value(bucket.get("remaining_units"))
    return remaining, response


def _read_remaining_from_thingsboard_telemetry(token, base_url, timeout):
    """Fallback: latest remaining_units telemetry point."""
    url = f"{base_url}/api/v1/{token}/telemetry"
    params = {"keys": "remaining_units", "limit": 1}
    req_kwargs = {**_thingsboard_request_kwargs(), "timeout": timeout}
    response = requests.get(url, params=params, **req_kwargs)
    if not (200 <= response.status_code < 300):
        return None, response

    payload = response.json()
    series = payload.get("remaining_units")
    remaining = _parse_remaining_units_value(series)
    return remaining, response


def query_latest_units_from_thingsboard(meter):
    """
    Read live remaining kWh from ThingsBoard (`remaining_units` shared/server/client
    attribute, with telemetry fallback).
    Returns (ok: bool, message: str, data: dict | None).
    """
    token = _meter_device_token(meter)
    if not token:
        return False, "Meter has no ThingsBoard device token configured.", None

    queried_at = timezone.now().isoformat()

    if token.startswith("dev-"):
        return True, "OK", {
            "units_kwh": float(meter.units),
            "queried_at": queried_at,
            "source": "dev-stub",
        }

    base_url = _thingsboard_base_url()
    if not base_url:
        return False, "THINGSBOARD_BASE_URL is not configured.", None

    timeout = int(getattr(settings, "THINGSBOARD_TIMEOUT_SECONDS", 8))

    try:
        remaining = None
        for scope_key in ("sharedKeys", "serverKeys", "clientKeys"):
            remaining, response = _read_remaining_from_thingsboard_scope(
                token, base_url, timeout, scope_key
            )
            if remaining is not None:
                break
            if response is not None and not (200 <= response.status_code < 300):
                logger.warning(
                    "ThingsBoard attribute read failed for meter=%s scope=%s status=%s body=%s",
                    meter.meter_no,
                    scope_key,
                    response.status_code,
                    response.text[:300],
                )

        if remaining is None:
            remaining, telemetry_response = _read_remaining_from_thingsboard_telemetry(
                token, base_url, timeout
            )
            if remaining is None and telemetry_response is not None and not (
                200 <= telemetry_response.status_code < 300
            ):
                logger.warning(
                    "ThingsBoard telemetry read failed for meter=%s status=%s body=%s",
                    meter.meter_no,
                    telemetry_response.status_code,
                    telemetry_response.text[:300],
                )

        if remaining is None:
            return False, "ThingsBoard device has no remaining_units attribute.", None

        return True, "OK", {
            "units_kwh": remaining,
            "queried_at": queried_at,
            "source": "thingsboard",
        }
    except requests.RequestException as exc:
        logger.exception("ThingsBoard attribute read failed for meter=%s", meter.meter_no)
        return False, _thingsboard_connection_error_message(exc, action="read attributes from"), None


def record_balance_snapshot(meter, remaining_kwh, source="thingsboard"):
    """Persist a point-in-time remaining kWh reading for usage analytics."""
    from meter.models import MeterBalanceSnapshot

    MeterBalanceSnapshot.objects.create(
        meter=meter,
        remaining_kwh=Decimal(str(remaining_kwh)),
        recorded_at=timezone.now(),
        source=source or "thingsboard",
    )


def _thingsboard_tenant_token():
    """Obtain a short-lived ThingsBoard tenant JWT (cached per process)."""
    username = getattr(settings, "THINGSBOARD_TENANT_USERNAME", "") or ""
    password = getattr(settings, "THINGSBOARD_TENANT_PASSWORD", "") or ""
    base_url = _thingsboard_base_url()
    if not username or not password or not base_url:
        return None, "ThingsBoard tenant credentials not configured."

    url = f"{base_url}/api/auth/login"
    req_kwargs = _thingsboard_request_kwargs()
    try:
        response = requests.post(
            url,
            json={"username": username, "password": password},
            **req_kwargs,
        )
        if not (200 <= response.status_code < 300):
            return None, f"Tenant login failed (HTTP {response.status_code})."
        token = response.json().get("token")
        if not token:
            return None, "Tenant login returned no token."
        return token, "OK"
    except requests.RequestException as exc:
        return None, _thingsboard_connection_error_message(exc, action="log in to")


def _find_thingsboard_device_id(meter, tenant_token):
    """Resolve ThingsBoard device UUID from the meter access token."""
    base_url = _thingsboard_base_url()
    req_kwargs = _thingsboard_request_kwargs()
    device_token = _meter_device_token(meter)
    headers = {"X-Authorization": f"Bearer {tenant_token}"}

    # Prefer lookup by access token text search
    url = f"{base_url}/api/tenant/devices"
    params = {"pageSize": 50, "page": 0, "textSearch": device_token}
    try:
        response = requests.get(url, headers=headers, params=params, **req_kwargs)
        if 200 <= response.status_code < 300:
            for item in response.json().get("data", []):
                dev_id = item.get("id", {}).get("id")
                if dev_id:
                    return dev_id, "OK"
    except requests.RequestException:
        pass

    # Fallback: search by meter number
    params = {"pageSize": 50, "page": 0, "textSearch": meter.meter_no}
    try:
        response = requests.get(url, headers=headers, params=params, **req_kwargs)
        if 200 <= response.status_code < 300:
            for item in response.json().get("data", []):
                dev_id = item.get("id", {}).get("id")
                if dev_id:
                    return dev_id, "OK"
    except requests.RequestException as exc:
        return None, _thingsboard_connection_error_message(exc, action="look up device on")

    return None, "ThingsBoard device not found for meter."


def set_shared_remaining_units(meter, value):
    """
    Write remaining_units on the device shared scope (tenant REST API).
    Returns (ok: bool, message: str).
    """
    token = _meter_device_token(meter)
    if token.startswith("dev-"):
        return True, "Dev stub — attribute sync skipped."

    tenant_token, msg = _thingsboard_tenant_token()
    if not tenant_token:
        return False, msg

    device_id, msg = _find_thingsboard_device_id(meter, tenant_token)
    if not device_id:
        return False, msg

    base_url = _thingsboard_base_url()
    url = f"{base_url}/api/plugins/telemetry/DEVICE/{device_id}/SHARED_SCOPE"
    headers = {
        "X-Authorization": f"Bearer {tenant_token}",
        "Content-Type": "application/json",
    }
    req_kwargs = _thingsboard_request_kwargs()
    try:
        response = requests.post(
            url,
            json={"remaining_units": float(Decimal(str(value)))},
            headers=headers,
            **req_kwargs,
        )
        if 200 <= response.status_code < 300:
            return True, "remaining_units attribute updated."
        return False, f"Attribute write failed (HTTP {response.status_code})."
    except requests.RequestException as exc:
        return False, _thingsboard_connection_error_message(exc, action="write attributes to")


def increment_shared_remaining_units(meter, delta):
    """
    Add delta kWh to the ThingsBoard remaining_units shared attribute.
    Reads current value first (0 if missing).
    """
    delta = Decimal(str(delta))
    if delta <= 0:
        return False, "Delta must be positive."

    token = _meter_device_token(meter)
    if token.startswith("dev-"):
        return True, "Dev stub — attribute sync skipped."

    ok, _msg, data = query_latest_units_from_thingsboard(meter)
    current = Decimal(str(data["units_kwh"])) if ok and data else Decimal("0")
    new_value = current + delta
    return set_shared_remaining_units(meter, new_value)


def query_usage_timeseries_from_thingsboard(meter, start_date, end_date):
    """
    Read daily kWh usage from ThingsBoard telemetry timeseries.
    Returns (ok, message, rows) where rows = [{date, kwh_used}, ...].
    """
    token = _meter_device_token(meter)
    if token.startswith("dev-"):
        return False, "Dev token — use stub data.", None

    telemetry_key = getattr(settings, "THINGSBOARD_USAGE_TELEMETRY_KEY", "daily_kwh") or "daily_kwh"
    tenant_token, msg = _thingsboard_tenant_token()
    if not tenant_token:
        return False, msg, None

    device_id, msg = _find_thingsboard_device_id(meter, tenant_token)
    if not device_id:
        return False, msg, None

    base_url = _thingsboard_base_url()
    start_ts = int(
        timezone.make_aware(datetime.combine(start_date, datetime.min.time())).timestamp() * 1000
    )
    end_ts = int(
        timezone.make_aware(
            datetime.combine(end_date, datetime.max.time().replace(microsecond=0))
        ).timestamp()
        * 1000
    )

    url = f"{base_url}/api/plugins/telemetry/DEVICE/{device_id}/values/timeseries"
    params = {
        "keys": telemetry_key,
        "startTs": start_ts,
        "endTs": end_ts,
        "interval": 86400000,
        "agg": "SUM",
        "limit": 5000,
        "orderBy": "ASC",
    }
    headers = {"X-Authorization": f"Bearer {tenant_token}"}
    req_kwargs = _thingsboard_request_kwargs()

    try:
        response = requests.get(url, headers=headers, params=params, **req_kwargs)
        if not (200 <= response.status_code < 300):
            return (
                False,
                f"Timeseries read failed (HTTP {response.status_code}).",
                None,
            )

        series = response.json().get(telemetry_key) or []
        rows = []
        for point in series:
            ts = point.get("ts")
            value = point.get("value")
            if ts is None or value is None:
                continue
            dt = timezone.localtime(
                datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
            )
            rows.append({"date": dt.date(), "kwh_used": float(Decimal(str(value)))})
        return True, "OK", rows
    except requests.RequestException as exc:
        return False, _thingsboard_connection_error_message(exc, action="read timeseries from"), None
