"""Owner-only periodic lab evidence. Never infer readings from cloud allocations."""
from django.utils import timezone
from meter.models import PrototypeDevice, PrototypeTelemetry


def lab_device(owner, meter, environment):
    return PrototypeDevice.objects.filter(owner=owner, meter=meter, meter__user=owner, environment=environment).order_by('-created_at').first()


def lab_dashboard(device):
    transition = getattr(device, 'measurement_transition', None)
    telemetry = device.telemetry.all()
    if transition and transition.state == 'COMMITTED':
        telemetry = telemetry.filter(received_at__gte=transition.committed_at)
    rows = list(telemetry.order_by('-received_at', '-pk')[:2])
    reading = rows[0] if rows else None
    previous_valid = telemetry.filter(payload__sensor_status='OK').order_by('-received_at', '-pk')[:2]
    previous = previous_valid[1] if len(previous_valid) > 1 else None
    now = timezone.now()
    fresh = bool(device.active and not device.revoked_at and reading and reading.observed_at and (now - reading.received_at).total_seconds() <= 90
                 and abs((now - reading.measured_at).total_seconds()) <= 90)
    data = reading.payload if reading else None
    if transition is None:
        measurement_state = 'SUSPENDED' if not device.telemetry.exists() else 'LEGACY_METERED'
    else:
        measurement_state = 'BASELINED' if transition.state == 'COMMITTED' else 'MIGRATING'
    # Faulty PZEM data is not a measured zero. Remaining credit is device journal evidence.
    measured = bool(data and reading.observed_at and data['sensor_status'] == 'OK')
    from meter.prototype_device import output_authorization
    output = output_authorization(device, now)
    authorization = device.output_authorizations.order_by('-granted_at', '-pk').first()
    return {
        'contact_source': 'AC_LAB', 'delivery_environment': 'AC_LAB',
        'lab_environment': device.environment,
        'lab_protocol': 'GPAWA_PZEM_V2' if device.environment == 'SANDBOX' else 'GPAWA_PZEM_V1',
        'contact_status': 'UNAVAILABLE' if not reading else 'RECENT' if fresh else 'STALE',
        'stale_after_seconds': 90,
        'last_meter_contact': device.last_contact_at.isoformat() if device.last_contact_at else None,
        'last_measurement_at': reading.observed_at.isoformat() if reading and reading.observed_at else None,
        'meter_reported_remaining_wh': None,  # Not independently verified physical/utility credit.
        'lab_remaining_credit_uwh': str(data['remaining_credit_uwh']) if data else None,
        'lab_consumed_uwh': str(data['consumed_uwh']) if data else None,
        'lab_uncertain_uwh': str(data['uncertain_uwh']) if data else None,
        'lab_pzem_wh': str(data['pzem_wh']) if measured else None,
        'lab_interval_usage_wh': str(data['pzem_wh'] - previous.payload['pzem_wh'])
            if measured and previous and previous.payload['sensor_status'] == 'OK' else None,
        'lab_interval_start': previous.observed_at.isoformat() if previous and previous.observed_at else None,
        'lab_sensor_status': ('FAULT' if data.get('fault_status') == 'SENSOR_UNAVAILABLE' else data['sensor_status']) if data else 'UNAVAILABLE',
        'lab_received_at': reading.received_at.isoformat() if reading else None,
        'lab_measurement_state': measurement_state,
        'lab_voltage_mv': data.get('voltage_mv') if measured else None,
        'lab_current_ma': data.get('current_ma') if measured else None,
        'lab_power_mw': data.get('power_mw') if measured else None,
        'lab_frequency_cHz': data.get('frequency_cHz') if measured else None,
        'lab_power_factor_pct': data.get('power_factor_pct') if measured else None,
        'lab_output_command': ('ON' if data['output_requested'] else 'OFF') if data else 'UNKNOWN',
        'lab_fault_status': data.get('fault_status', 'OK' if measured else 'SENSOR_UNAVAILABLE') if data else 'SENSOR_UNAVAILABLE',
        'output_authorized': output['output_authorized'],
        'output_authorization_state': authorization.state if authorization else 'NONE',
        'output_authorization_expires_at': authorization.expires_at.isoformat() if authorization and authorization.expires_at else None,
        'output_commissioning_mode': authorization.mode if authorization else None,
        'output_offline_allowed': output['output_offline_allowed'],
        'output_restart_policy': output['output_restart_policy'],
        'reported_relay_state': 'UNKNOWN', 'relay_source': 'AC_LAB',
        'output_enabled': output['output_authorized'], 'output_feedback': 'UNKNOWN',
        'consumption_reconciliation_required': bool(data and data['uncertain_uwh']),
        'simulator_remaining_wh': None,
    }


def lab_history(owner, meter, environment):
    rows = PrototypeTelemetry.objects.filter(device__owner=owner, device__meter=meter, device__meter__user=owner, device__environment=environment).select_related('device').order_by('-received_at', '-pk')[:30]
    return [{
        'boot_id': str(row.boot_id), 'sequence': str(row.sequence),
        'environment': row.device.environment,
        'measured_at': row.observed_at.isoformat() if row.observed_at else None, 'received_at': row.received_at.isoformat(),
        'consumed_uwh': str(row.payload['consumed_uwh']) if row.payload['sensor_status'] == 'OK' else None,
        'remaining_credit_uwh': str(row.payload['remaining_credit_uwh']),
        'uncertain_uwh': str(row.payload['uncertain_uwh']), 'sensor_status': row.payload['sensor_status'],
        'pzem_wh': str(row.payload['pzem_wh']) if row.payload['sensor_status'] == 'OK' else None,
        'output_feedback': 'UNKNOWN', 'output_enabled': False,
        'output_command': 'ON' if row.payload.get('output_requested') else 'OFF',
        'fault_status': row.payload.get('fault_status', 'OK' if row.payload['sensor_status'] == 'OK' else 'SENSOR_UNAVAILABLE'),
        'voltage_mv': str(row.payload['voltage_mv']) if row.payload['sensor_status'] == 'OK' else None,
        'current_ma': str(row.payload['current_ma']) if row.payload['sensor_status'] == 'OK' else None,
        'power_mw': str(row.payload['power_mw']) if row.payload['sensor_status'] == 'OK' else None,
        'frequency_cHz': str(row.payload['frequency_cHz']) if row.payload.get('frequency_cHz') is not None else None,
        'power_factor_pct': str(row.payload['power_factor_pct']) if row.payload.get('power_factor_pct') is not None else None,
    } for row in rows]
