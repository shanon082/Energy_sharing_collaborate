"""Owner-only periodic lab evidence. Never infer readings from cloud allocations."""
from django.utils import timezone
from meter.models import PrototypeDevice, PrototypeTelemetry


def lab_device(owner, meter):
    return PrototypeDevice.objects.filter(owner=owner, meter=meter, meter__user=owner).order_by('-created_at').first()


def lab_dashboard(device):
    rows = list(device.telemetry.order_by('-received_at', '-pk')[:2])
    reading = rows[0] if rows else None
    previous = rows[1] if len(rows) > 1 else None
    now = timezone.now()
    fresh = bool(reading and (now - reading.received_at).total_seconds() <= 90
                 and abs((now - reading.measured_at).total_seconds()) <= 90)
    data = reading.payload if reading else None
    # Faulty PZEM data is not a measured zero. Remaining credit is device journal evidence.
    measured = bool(data and data['sensor_status'] == 'OK')
    return {
        'contact_source': 'AC_LAB', 'delivery_environment': 'AC_LAB',
        'contact_status': 'UNAVAILABLE' if not reading else 'RECENT' if fresh else 'STALE',
        'stale_after_seconds': 90,
        'last_meter_contact': device.last_contact_at.isoformat() if device.last_contact_at else None,
        'last_measurement_at': reading.measured_at.isoformat() if reading else None,
        'meter_reported_remaining_wh': None,  # Not independently verified physical/utility credit.
        'lab_remaining_credit_uwh': str(data['remaining_credit_uwh']) if data else None,
        'lab_consumed_uwh': str(data['consumed_uwh']) if measured else None,
        'lab_uncertain_uwh': str(data['uncertain_uwh']) if data else None,
        'lab_pzem_wh': str(data['pzem_wh']) if measured else None,
        'lab_interval_usage_wh': str(data['pzem_wh'] - previous.payload['pzem_wh'])
            if measured and previous and previous.payload['sensor_status'] == 'OK' else None,
        'lab_interval_start': previous.measured_at.isoformat() if previous else None,
        'lab_sensor_status': data['sensor_status'] if data else 'UNAVAILABLE',
        'lab_received_at': reading.received_at.isoformat() if reading else None,
        'reported_relay_state': 'UNKNOWN', 'relay_source': 'AC_LAB',
        'output_enabled': False, 'output_feedback': 'UNKNOWN',
        'consumption_reconciliation_required': bool(data and data['uncertain_uwh']),
        'simulator_remaining_wh': None,
    }


def lab_history(owner, meter):
    rows = PrototypeTelemetry.objects.filter(device__owner=owner, device__meter=meter, device__meter__user=owner).order_by('-received_at', '-pk')[:30]
    return [{
        'boot_id': str(row.boot_id), 'sequence': str(row.sequence),
        'measured_at': row.measured_at.isoformat(), 'received_at': row.received_at.isoformat(),
        'consumed_uwh': str(row.payload['consumed_uwh']) if row.payload['sensor_status'] == 'OK' else None,
        'remaining_credit_uwh': str(row.payload['remaining_credit_uwh']),
        'uncertain_uwh': str(row.payload['uncertain_uwh']), 'sensor_status': row.payload['sensor_status'],
        'pzem_wh': str(row.payload['pzem_wh']) if row.payload['sensor_status'] == 'OK' else None,
        'output_feedback': 'UNKNOWN', 'output_enabled': False,
    } for row in rows]
