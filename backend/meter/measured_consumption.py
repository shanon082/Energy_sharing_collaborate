"""Read accepted PZEM counter evidence without consulting credit or simulator ledgers."""
from collections import deque
from datetime import datetime, time, timedelta, timezone as utc
from decimal import Decimal

from django.utils import timezone

from meter.models import PrototypeDevice, PrototypeTelemetry
from meter.prototype_device import output_authorization


MAX_INTERVAL_SECONDS = 90
MAX_HISTORY = 120


def units(integer, scale):
    return None if integer is None else format(Decimal(integer) / scale, 'f')


def time_string(value):
    return value.isoformat() if value else None


def binding(row, devices):
    device = devices[row.device_id]
    t = getattr(device, 'measurement_transition', None)
    if t and t.committed_at and row.received_at >= t.committed_at:
        baseline = str(t.transition_id)
    elif t and row.received_at >= t.prepared_at:
        baseline = 'MIGRATING'
    else:
        baseline = 'LEGACY'
    payload = row.payload
    return {
        'device_id': str(row.device_id),
        'binding_epoch': payload.get('binding_epoch'),
        'baseline': baseline,
    }


def value(row, key):
    raw = row.payload.get(key)
    return raw if row.payload.get('sensor_status') == 'OK' and type(raw) is int and raw >= 0 else None


def interval(previous, current, devices):
    a, b = binding(previous, devices), binding(current, devices)
    start, end = previous.measured_at, current.measured_at
    before, after = value(previous, 'pzem_wh'), value(current, 'pzem_wh')
    seconds = (end - start).total_seconds()
    delta = None
    if previous.device_id != current.device_id:
        classification = 'DEVICE_CHANGED'
    elif (a['binding_epoch'] != b['binding_epoch'] or a['binding_epoch'] is None
          or not previous.payload.get('storage_id')
          or any(previous.payload.get(key) != current.payload.get(key)
                 for key in ('storage_id', 'meter_number', 'protocol'))):
        classification = 'BINDING_CHANGED'
    elif a['baseline'] != b['baseline'] or b['baseline'] == 'MIGRATING':
        classification = 'BASELINE_CHANGED'
    elif before is None or after is None:
        classification = 'SENSOR_UNAVAILABLE'
    elif after < before:
        classification = 'COUNTER_RESET'
    elif seconds <= 0:
        classification = 'TIME_UNRESOLVED'
    else:
        delta = after - before
        if previous.boot_id != current.boot_id:
            classification = 'RESTART'
        elif seconds > MAX_INTERVAL_SECONDS or current.sequence != previous.sequence + 1:
            classification = 'UPLOAD_GAP'
        elif start.astimezone(utc.utc).date() != end.astimezone(utc.utc).date():
            classification = 'DAY_BOUNDARY'
        else:
            classification = 'MEASURED'
    return classification, delta, {
        **b,
        'boot_id': str(current.boot_id),
        'sequence': str(current.sequence),
        'start_at': time_string(start),
        'measured_at': time_string(end),
        'received_at': time_string(current.received_at),
        'sensor_state': current.payload.get('sensor_status', 'UNAVAILABLE'),
    }


def latest_snapshot(device, reading, now):
    if not reading:
        return None
    age = (now - reading.received_at).total_seconds()
    freshness = 'RECENT' if (device.active and not device.revoked_at and age <= MAX_INTERVAL_SECONDS
                              and abs((now - reading.measured_at).total_seconds()) <= MAX_INTERVAL_SECONDS) else 'STALE'
    return {
        'measured_at': time_string(reading.measured_at),
        'received_at': time_string(reading.received_at),
        'freshness': freshness,
        'sensor_state': ('FAULT' if reading.payload.get('fault_status') == 'SENSOR_UNAVAILABLE'
                         else reading.payload.get('sensor_status', 'UNAVAILABLE')),
        'fault_status': reading.payload.get('fault_status'),
        'voltage_v': units(value(reading, 'voltage_mv'), 1000),
        'current_a': units(value(reading, 'current_ma'), 1000),
        'power_w': units(value(reading, 'power_mw'), 1000),
        'cumulative_kwh': units(value(reading, 'pzem_wh'), 1000),
        'remaining_credit_kwh': units(reading.payload.get('remaining_credit_uwh'), 1_000_000_000),
        'output_command': 'ON' if reading.payload.get('output_requested') else 'OFF',
    }


def measured_consumption(owner, meter, environment, days, now=None):
    now = (now or timezone.now()).astimezone(utc.utc)
    today = now.date()
    start = datetime.combine(today - timedelta(days=days - 1), time.min, utc.utc)
    devices = {d.pk: d for d in PrototypeDevice.objects.filter(
        owner=owner, meter=meter, meter__user=owner, meter__is_deleted=False,
        environment=environment, hardware_class='AC_LAB',
    ).select_related('measurement_transition').order_by('-active', '-created_at', '-pk')}
    device = next(iter(devices.values()), None)
    rows = PrototypeTelemetry.objects.filter(device_id__in=devices, measured_at__lte=now)
    order = ('measured_at', 'received_at', 'pk')
    preceding = rows.filter(measured_at__lt=start).order_by('-measured_at', '-received_at', '-pk').first()
    daily = {}
    for index in range(days):
        day = (start + timedelta(days=index)).date()
        day_start = datetime.combine(day, time.min, utc.utc)
        daily[day] = {'date': day.isoformat(), 'wh': 0, 'intervals': 0, 'covered_ms': 0,
                      'window_ms': int((min(day_start + timedelta(days=1), now) - day_start).total_seconds() * 1000)}
    history = deque(maxlen=MAX_HISTORY)
    unallocated_wh = unallocated_count = history_count = 0
    previous = preceding
    for row in rows.filter(measured_at__gte=start).order_by(*order).iterator(chunk_size=2000):
        if previous is None:
            history.append({**binding(row, devices), 'boot_id': str(row.boot_id), 'sequence': str(row.sequence),
                            'start_at': None, 'measured_at': time_string(row.measured_at),
                            'received_at': time_string(row.received_at), 'sensor_state': row.payload.get('sensor_status', 'UNAVAILABLE'),
                            'classification': 'NO_PRIOR_SAMPLE', 'consumption_kwh': None})
        else:
            category, delta, fields = interval(previous, row, devices)
            if previous.measured_at < start and delta is not None:
                category = 'PERIOD_BOUNDARY'
            elif category == 'MEASURED':
                bucket = daily[row.measured_at.astimezone(utc.utc).date()]
                bucket['wh'] += delta
                bucket['intervals'] += 1
                bucket['covered_ms'] += int((row.measured_at - previous.measured_at).total_seconds() * 1000)
            elif delta is not None:
                unallocated_wh += delta
                unallocated_count += 1
            history.append({**fields, 'classification': category, 'consumption_kwh': units(delta, 1000)})
        previous = row
        history_count += 1

    def totals(buckets):
        intervals = sum(bucket['intervals'] for bucket in buckets)
        covered = sum(bucket['covered_ms'] for bucket in buckets)
        window = sum(bucket['window_ms'] for bucket in buckets)
        return {
            'measured_kwh': units(sum(bucket['wh'] for bucket in buckets), 1000) if intervals else None,
            'interval_count': intervals,
            'covered_ms': covered,
            'window_ms': window,
            'coverage': ('COMPLETE' if covered >= window else 'PARTIAL') if intervals else 'UNAVAILABLE',
        }

    latest = latest_interval = None
    relay = {'authorized': False, 'state': 'NONE', 'expires_at': None, 'restart_policy': None, 'contact': 'UNKNOWN'}
    if device:
        current = rows.filter(device=device, payload__binding_epoch=device.binding_epoch,
                              payload__storage_id=str(device.storage_id), payload__meter_number=meter.meter_no)
        transition = getattr(device, 'measurement_transition', None)
        if transition:
            current = current.filter(received_at__gte=transition.committed_at) if transition.committed_at else current.none()
        latest_rows = list(current.order_by('-measured_at', '-received_at', '-pk')[:2])
        if latest_rows:
            reading = latest_rows[0]
            latest = {**binding(reading, devices), **latest_snapshot(device, reading, now)}
        if len(latest_rows) == 2:
            category, delta, fields = interval(latest_rows[1], latest_rows[0], devices)
            latest_interval = {**fields, 'classification': category, 'consumption_kwh': units(delta, 1000)}
        output = output_authorization(device, now, record_expiration=False)
        record = device.output_authorizations.order_by('-granted_at', '-pk').first()
        if record:
            state = 'EXPIRED' if record.state == 'ACTIVE' and record.expires_at <= now else record.state
            relay.update(authorized=output['output_authorized'], state=state,
                         expires_at=time_string(record.expires_at), restart_policy=record.restart_policy)

    return {
        'meter': {'id': meter.pk, 'meter_number': meter.meter_no},
        'environment': environment,
        'source': 'AC_LAB_PZEM',
        'device_bound': device is not None,
        'as_of': time_string(now),
        'stale_after_seconds': MAX_INTERVAL_SECONDS,
        'latest': latest,
        'latest_interval': latest_interval,
        'relay': relay,
        'period': {'days': days, 'timezone': 'UTC', 'start_at': time_string(start), 'end_at': time_string(now),
                   **totals(list(daily.values())),
                   'unallocated_kwh': units(unallocated_wh, 1000) if unallocated_count else None,
                   'unallocated_interval_count': unallocated_count},
        'daily': [{'date': bucket['date'], **totals([bucket])} for bucket in daily.values()],
        'history': list(reversed(history)),
        'history_truncated': history_count > MAX_HISTORY,
    }
