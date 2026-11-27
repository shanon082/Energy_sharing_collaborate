"""Domain-bound GPAWA_PZEM_V1/V2 adapter; no provider I/O or relay commands."""
import hmac
import re
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.debug import sensitive_variables

from accounts.models import User
from meter.diagnostics import mark_stage
from meter.bench_device import BenchError, payload_digest, rate_attempt
from meter.energy_tokens import authorized_source, cipher, digest_token
from meter.models import (EnergyAllocation, EnergyKeypadToken, Meter, MeterDelivery,
                          PrototypeBoot, PrototypeCommand, PrototypeDevice, PrototypeTelemetry,
                          PrototypeMeasurementTransition, PrototypeOutputAuthorization,
                          PrototypeOutputAuthorizationEvent)

PROTOCOL = 'GPAWA_PZEM_V1'
RECOVERY_PROTOCOL = 'GPAWA_RECOVERY_V1'
DOMAIN_PROTOCOLS = {'UGX_DEMO': PROTOCOL, 'SANDBOX': 'GPAWA_PZEM_V2'}
IDENTITY = {'protocol', 'device_id', 'meter_number', 'storage_id', 'binding_epoch', 'environment', 'hardware_class'}
MAX_COUNTER = 9_000_000_000_000_000
UINT32 = 2**32 - 1
OUTPUT_LEASE_SECONDS = 90
MAX_OUTPUT_AUTHORIZATION = timedelta(hours=24)
OUTPUT_EVIDENCE_FLAGS = {
    'contact_tested_ac_disconnected', 'startup_state_verified',
    'reset_state_verified', 'controller_power_loss_verified',
    'relay_supply_loss_verified', 'zero_credit_cutoff_verified',
    'meter_fault_cutoff_verified', 'electrical_installation_reviewed',
}


def mtn_tokens_required():
    return (getattr(settings, 'CONSUMER_SANDBOX_ENABLED', False) is True
            and getattr(settings, 'PROTOTYPE_PAYMENT_PROVIDER', '') == 'MTN_SANDBOX')


def require_mtn_purchase_tokens(terms=None, *, recovery=False):
    """All new MTN sandbox energy purchases require one usable source token."""
    if not recovery and not mtn_tokens_required():
        return
    from decimal import Decimal
    from transactions.payment_settlement import PaymentSettlementError
    try:
        if getattr(settings, 'ENERGY_TOKEN_ISSUANCE_ENABLED', False) is not True:
            raise ImproperlyConfigured('Token issuance disabled')
        cipher()
        digest_token('000000000000000')  # Configuration check only; never a token issued.
        if terms is not None:
            wh = Decimal(terms['energy_kwh']) * 1000
            if not wh.is_finite() or not 0 < wh <= 1_000_000 or wh != wh.to_integral_value() or wh % 10:
                raise ValueError
    except (ImproperlyConfigured, ValueError, KeyError, TypeError, ArithmeticError):
        raise PaymentSettlementError('Sandbox token service unavailable or quoted energy exceeds the AC lab command contract.') from None


def permitted_environment():
    return {'LOCAL_DEMO': 'UGX_DEMO', 'MTN_SANDBOX': 'SANDBOX'}.get(getattr(settings, 'PROTOTYPE_PAYMENT_PROVIDER', ''))


def enabled():
    return (getattr(settings, 'PROTOTYPE_AC_LAB_ENABLED', False) is True
            and getattr(settings, 'ALWAYSDATA_TESTING', False) is True
            and getattr(settings, 'CONSUMER_SANDBOX_ENABLED', False) is True
            and permitted_environment() in DOMAIN_PROTOCOLS)


def require_lab():
    if not enabled():
        raise BenchError('AC_LAB_DISABLED', 'Commissioned AC lab capability is unavailable.', 503)


def fail(code='RECONCILIATION_REQUIRED', message='Device state requires operator reconciliation.', status=409):
    raise BenchError(code, message, status)


def integer(body, key, maximum=UINT32, minimum=0):
    if type(body.get(key)) is not int or not minimum <= body[key] <= maximum:
        fail('REQUEST_INVALID', 'Invalid integer field: ' + key, 400)
    return body[key]


def canonical_uuid(value):
    try:
        parsed = uuid.UUID(value) if isinstance(value, str) else None
        if parsed is None or str(parsed) != value:
            raise ValueError
        return parsed
    except (ValueError, TypeError, AttributeError):
        fail('REQUEST_INVALID', 'Canonical UUID required.', 400)


def timestamp(value):
    try:
        at = parse_datetime(value) if isinstance(value, str) else None
        if at is None or timezone.is_naive(at) or at.utcoffset() != timedelta(0) or at > timezone.now() + timedelta(minutes=5):
            raise ValueError
        return at
    except (TypeError, ValueError):
        fail('REQUEST_INVALID', 'UTC timestamp required.', 400)


def identity(device):
    return dict(protocol=DOMAIN_PROTOCOLS[device.environment], device_id=str(device.pk), meter_number=device.meter.meter_no,
                storage_id=str(device.storage_id), binding_epoch=device.binding_epoch,
                environment=device.environment, hardware_class='AC_LAB')


def active_binding(device, meter=None):
    mark_stage('device_binding')
    if meter is None:
        meter = Meter.all_objects.get(pk=device.meter_id)
    if (not device.active or device.revoked_at or device.environment != permitted_environment()
            or device.hardware_class != 'AC_LAB' or meter.user_id != device.owner_id or meter.is_deleted
            or meter.status != 'ACTIVE' or not meter.sandbox_inventory or not re.fullmatch(r'[0-9]{11}', meter.meter_no)
            or meter.meter_no == '0' * 11
            or not device.owner.is_active or device.owner.user_role != User.CLIENT or device.owner.is_staff or device.owner.is_superuser
            or not getattr(getattr(device.owner, 'profile', None), 'email_verified', False)):
        fail('DEVICE_UNAUTHORIZED', 'Device authentication failed.', 401)
    device.meter = meter


def _expire_output_authorization(authorization, now):
    if authorization.state != PrototypeOutputAuthorization.ACTIVE or not authorization.is_expired(now):
        return False
    authorization.state = PrototypeOutputAuthorization.EXPIRED
    authorization.save(update_fields=['state'])
    PrototypeOutputAuthorizationEvent.objects.get_or_create(
        authorization=authorization, action=PrototypeOutputAuthorizationEvent.EXPIRED,
        defaults={
            'device': authorization.device,
            'reason': 'Authorization lease expired',
            'details': {'expires_at': authorization.expires_at.isoformat()},
        },
    )
    if authorization.device.output_enabled:
        PrototypeDevice.objects.filter(pk=authorization.device_id).update(output_enabled=False)
    return True


def output_binding(device):
    return {**identity(device), 'meter_id': device.meter_id, 'owner_id': device.owner_id}


def matches_telemetry_binding(sample, device):
    return all(sample.payload.get(key) == value for key, value in identity(device).items())


@transaction.atomic
def output_authorization(device, now=None, *, record_expiration=True):
    now = now or timezone.now()
    records = device.output_authorizations.filter(state=PrototypeOutputAuthorization.ACTIVE)
    if record_expiration:
        device = PrototypeDevice.objects.select_for_update().get(pk=device.pk)
        records = records.select_for_update()
    authorization = records.order_by('-granted_at', '-pk').first()
    grant_state = authorization.state if authorization else None
    if authorization and authorization.is_expired(now):
        if record_expiration:
            _expire_output_authorization(authorization, now)
        grant_state = PrototypeOutputAuthorization.EXPIRED
        authorization = None

    restart_policy = authorization.restart_policy if authorization else PrototypeOutputAuthorization.MANUAL
    result = {
        'output_authorized': False,
        'output_lease_seconds': 0,
        'output_restart_policy': restart_policy,
        'output_authorization_expires_at': authorization.expires_at.isoformat() if authorization and authorization.expires_at else None,
        'output_commissioning_mode': authorization.mode if authorization else None,
        'output_offline_allowed': False,
    }
    if getattr(settings, 'PROTOTYPE_RELAY_OUTPUT_ENABLED', False) is not True:
        return {**result, 'output_reason': 'OUTPUT_GLOBAL_DISABLE'}
    if not device.active or device.revoked_at:
        return {**result, 'output_reason': 'DEVICE_DISABLED'}
    if not authorization:
        if grant_state is None:
            grant_state = device.output_authorizations.order_by('-granted_at', '-pk').values_list('state', flat=True).first()
        reason = {'REVOKED': 'OUTPUT_GRANT_REVOKED', 'EXPIRED': 'OUTPUT_GRANT_EXPIRED'}.get(grant_state, 'OUTPUT_GRANT_MISSING')
        return {**result, 'output_reason': 'METER_RECOVERY_PENDING' if device.recovery_pending else reason}
    if not device.output_enabled:
        return {**result, 'output_reason': 'DEVICE_OUTPUT_DISABLED'}
    if authorization.mode == PrototypeOutputAuthorization.PERSISTENT:
        meters = Meter.all_objects.select_for_update() if record_expiration else Meter.all_objects
        device.meter = meters.get(pk=device.meter_id)
        if (authorization.binding_snapshot != output_binding(device)
                or device.meter.user_id != device.owner_id or device.meter.is_deleted):
            if record_expiration:
                _revoke_output_grant(authorization, None, 'Device binding replaced')
                device.output_enabled = False
                device.save(update_fields=['output_enabled'])
            return {**result, 'output_reason': 'OUTPUT_BINDING_CHANGED'}
        try:
            active_binding(device, device.meter)
        except BenchError:
            return {**result, 'output_reason': 'DEVICE_DISABLED'}
    if not PrototypeMeasurementTransition.objects.filter(device=device, state=PrototypeMeasurementTransition.COMMITTED).exists():
        return {**result, 'output_reason': 'MEASUREMENT_BASELINE_REQUIRED'}
    result['output_offline_allowed'] = authorization.offline_enabled
    if not device.recovery_enabled or device.recovery_pending:
        return {**result, 'output_reason': 'METER_RECOVERY_PENDING'}
    if device.commands.filter(receipt_id__isnull=True).exists():
        return {**result, 'output_reason': 'ACK_REQUIRED'}

    latest = device.telemetry.order_by('-received_at', '-pk').first()
    if not latest or latest.boot_id != device.boot_id or not matches_telemetry_binding(latest, device):
        return {**result, 'output_reason': 'CURRENT_BOOT_SAMPLE_REQUIRED'}
    received_age = (now - latest.received_at).total_seconds()
    measured_age = (now - latest.measured_at).total_seconds()
    if received_age > OUTPUT_LEASE_SECONDS or abs(measured_age) > OUTPUT_LEASE_SECONDS:
        return {**result, 'output_reason': 'OUTPUT_SAMPLE_STALE'}
    if latest.payload.get('sensor_status') != 'OK' or latest.payload.get('fault_status') != 'OK':
        return {**result, 'output_reason': 'METER_NOT_READY'}
    if device.uncertain_uwh or latest.payload.get('uncertain_uwh') != 0:
        return {**result, 'output_reason': 'CREDIT_UNCERTAIN'}
    if latest.payload.get('remaining_credit_uwh', 0) <= 0:
        return {**result, 'output_reason': 'CREDIT_UNAVAILABLE'}
    if latest.payload.get('relay_active_level') != authorization.evidence['relay_active_level']:
        return {**result, 'output_offline_allowed': False, 'output_reason': 'RELAY_POLARITY_MISMATCH'}

    credited = sum(
        command.delivery.command_payload['credit_wh'] * 1_000_000
        for command in device.commands.filter(receipt_id__isnull=False).select_related('delivery')
    )
    if credited <= device.consumed_uwh:
        return {**result, 'output_reason': 'CREDIT_UNAVAILABLE'}

    freshness_remaining = int(OUTPUT_LEASE_SECONDS - max(received_age, abs(measured_age), 0))
    lease = min(OUTPUT_LEASE_SECONDS, freshness_remaining)
    if authorization.expires_at:
        lease = min(lease, int((authorization.expires_at - now).total_seconds()))
    if lease <= 0:
        reason = 'OUTPUT_SAMPLE_STALE' if freshness_remaining <= 0 else 'OUTPUT_GRANT_EXPIRING'
        return {**result, 'output_reason': reason}
    result.update(output_authorized=True, output_lease_seconds=lease, output_reason='LEASE_GRANTED')
    return result


def _commissioning_request(body):
    required = {'expires_at', 'reason', 'restart_policy', 'evidence'}
    if not isinstance(body, dict) or set(body) != required:
        fail('REQUEST_INVALID', 'Commissioning fields do not match the required schema.', 400)
    try:
        expires_at = parse_datetime(body['expires_at']) if isinstance(body['expires_at'], str) else None
    except ValueError:
        expires_at = None
    now = timezone.now()
    if (expires_at is None or timezone.is_naive(expires_at) or expires_at.utcoffset() != timedelta(0)
            or not now < expires_at <= now + MAX_OUTPUT_AUTHORIZATION):
        fail('REQUEST_INVALID', 'Authorization expiry must be UTC and within 24 hours.', 400)
    reason = output_reason_text(body['reason'])
    restart_policy = body['restart_policy']
    if restart_policy not in (PrototypeOutputAuthorization.AUTO, PrototypeOutputAuthorization.MANUAL):
        fail('REQUEST_INVALID', 'Unsupported output restart policy.', 400)
    return expires_at, reason, restart_policy, validated_output_evidence(body['evidence'])


def output_reason_text(reason):
    if not isinstance(reason, str) or not 8 <= len(reason.strip()) <= 240:
        fail('REQUEST_INVALID', 'A reason of 8 to 240 characters is required.', 400)
    return reason.strip()


def validated_output_evidence(evidence):
    expected = OUTPUT_EVIDENCE_FLAGS | {'relay_active_level', 'evidence_reference'}
    if not isinstance(evidence, dict) or set(evidence) != expected:
        fail('COMMISSIONING_EVIDENCE_REQUIRED', 'The complete physical commissioning record is required.', 400)
    if (evidence['relay_active_level'] not in ('HIGH', 'LOW')
            or not isinstance(evidence['evidence_reference'], str)
            or not 1 <= len(evidence['evidence_reference'].strip()) <= 120
            or any(evidence[key] is not True for key in OUTPUT_EVIDENCE_FLAGS)):
        fail('COMMISSIONING_EVIDENCE_REQUIRED', 'All physical safety checks must be verified.', 400)
    return evidence


def lock_for_commissioning(device_id):
    require_lab()
    if getattr(settings, 'PROTOTYPE_RELAY_OUTPUT_ENABLED', False) is not True:
        fail('OUTPUT_GLOBAL_DISABLE', 'Physical output is disabled by the global safety switch.', 503)
    device = PrototypeDevice.objects.select_for_update(of=('self',)).select_related(
        'meter', 'owner__profile',
    ).filter(pk=device_id).first()
    if not device:
        fail('DEVICE_UNAVAILABLE', 'Device is unavailable.', 404)
    meter = Meter.all_objects.select_for_update().get(pk=device.meter_id)
    active_binding(device, meter)
    return device


def require_commissioning_sample(device, polarity, now):
    if not PrototypeMeasurementTransition.objects.filter(
        device=device, state=PrototypeMeasurementTransition.COMMITTED,
    ).exists():
        fail('MEASUREMENT_BASELINE_REQUIRED', 'A committed authenticated meter baseline is required.', 409)
    latest = device.telemetry.order_by('-received_at', '-pk').first()
    if (not device.recovery_enabled or device.recovery_pending or not latest or latest.boot_id != device.boot_id
            or not matches_telemetry_binding(latest, device)
            or device.commands.filter(receipt_id__isnull=True).exists()
            or (now - latest.received_at).total_seconds() > OUTPUT_LEASE_SECONDS
            or abs((now - latest.measured_at).total_seconds()) > OUTPUT_LEASE_SECONDS
            or latest.payload.get('sensor_status') != 'OK'
            or latest.payload.get('fault_status') != 'OK'
            or latest.payload.get('relay_active_level') != polarity
            or device.uncertain_uwh
            or latest.payload.get('uncertain_uwh') != 0):
        fail('METER_NOT_READY', 'A fresh valid meter sample from the matching commissioned relay profile is required.', 409)


@transaction.atomic
def commission_output(device_id, actor, body):
    device = lock_for_commissioning(device_id)
    expires_at, reason, restart_policy, evidence = _commissioning_request(body)
    now = timezone.now()
    require_commissioning_sample(device, evidence['relay_active_level'], now)
    credited = sum(
        command.delivery.command_payload['credit_wh'] * 1_000_000
        for command in device.commands.filter(receipt_id__isnull=False).select_related('delivery')
    )
    if credited <= device.consumed_uwh:
        fail('CREDIT_UNAVAILABLE', 'Positive acknowledged electricity credit is required.', 409)
    existing = device.output_authorizations.select_for_update().filter(
        state=PrototypeOutputAuthorization.ACTIVE,
    ).first()
    if existing:
        if _expire_output_authorization(existing, now):
            existing = None
        else:
            fail('OUTPUT_ALREADY_COMMISSIONED', 'Revoke the current authorization before replacing it.', 409)

    authorization = PrototypeOutputAuthorization.objects.create(
        device=device, restart_policy=restart_policy, expires_at=expires_at,
        granted_by=actor, reason=reason, evidence=evidence, binding_snapshot=output_binding(device),
    )
    device.output_enabled = True
    device.save(update_fields=['output_enabled'])
    PrototypeOutputAuthorizationEvent.objects.create(
        authorization=authorization, device=device, actor=actor,
        action=PrototypeOutputAuthorizationEvent.GRANTED, reason=reason,
        details={
            'expires_at': expires_at.isoformat(),
            'restart_policy': restart_policy,
            'relay_active_level': evidence['relay_active_level'],
            'evidence_reference': evidence['evidence_reference'],
        },
    )
    return output_grant_record(authorization)


def output_grant_record(authorization):
    return {
        'device_id': str(authorization.device_id), 'authorization_id': authorization.pk,
        'status': authorization.state, 'mode': authorization.mode,
        'expires_at': authorization.expires_at.isoformat() if authorization.expires_at else None,
        'restart_policy': authorization.restart_policy, 'output_enabled': True,
        'offline_enabled': authorization.offline_enabled,
    }


@transaction.atomic
def persist_output_commissioning(device_id, actor, body):
    if (not isinstance(body, dict) or 'reason' not in body or set(body) - {'reason', 'offline'}
            or type(body.get('offline', False)) is not bool):
        fail('REQUEST_INVALID', 'An administrative reason is required.', 400)
    reason = output_reason_text(body['reason'])
    device = lock_for_commissioning(device_id)
    source = device.output_authorizations.select_for_update().order_by('-granted_at', '-pk').first()
    snapshot = output_binding(device)
    offline = body.get('offline', source.offline_enabled if source and source.mode == PrototypeOutputAuthorization.PERSISTENT else False)
    if (source and source.mode == PrototypeOutputAuthorization.PERSISTENT
            and source.state == PrototypeOutputAuthorization.ACTIVE and source.binding_snapshot == snapshot
            and device.output_enabled and source.offline_enabled == offline):
        return output_grant_record(source), False
    if (not source or source.state == PrototypeOutputAuthorization.REVOKED or not source.events.filter(
            action=(PrototypeOutputAuthorizationEvent.GRANTED if source.mode == PrototypeOutputAuthorization.TEMPORARY
                    else PrototypeOutputAuthorizationEvent.PROMOTED)).exists()):
        fail('OUTPUT_COMMISSIONING_REVIEW_REQUIRED', 'A recorded, non-revoked commissioning grant is required.', 409)
    evidence = validated_output_evidence(source.evidence)
    if source.binding_snapshot is None:
        # Earlier grants checked this accepted sample at creation, before there
        # was a separate binding snapshot on the grant row.
        original_sample = device.telemetry.filter(received_at__lte=source.granted_at).order_by('-received_at', '-pk').first()
        if (not original_sample or not matches_telemetry_binding(original_sample, device)
                or original_sample.payload.get('relay_active_level') != evidence['relay_active_level']
                or original_sample.payload.get('sensor_status') != 'OK'):
            fail('OUTPUT_BINDING_CHANGED', 'The recorded commissioning binding could not be established.', 409)
    elif source.binding_snapshot != snapshot:
        fail('OUTPUT_BINDING_CHANGED', 'The recorded commissioning binding has changed.', 409)
    now = timezone.now()
    require_commissioning_sample(device, evidence['relay_active_level'], now)
    if source.state == PrototypeOutputAuthorization.ACTIVE and not _expire_output_authorization(source, now):
        _revoke_output_grant(source, actor, 'Replaced by reviewed persistent commissioning policy')

    grant = PrototypeOutputAuthorization.objects.create(
        device=device, mode=PrototypeOutputAuthorization.PERSISTENT, restart_policy=PrototypeOutputAuthorization.AUTO,
        binding_snapshot=snapshot, granted_by=actor, reason=reason, evidence=evidence, offline_enabled=offline,
    )
    device.output_enabled = True
    device.save(update_fields=['output_enabled'])
    PrototypeOutputAuthorizationEvent.objects.create(
        authorization=grant, device=device, actor=actor, action=PrototypeOutputAuthorizationEvent.PROMOTED,
        reason=reason, details={'source_authorization_id': source.pk, 'restart_policy': grant.restart_policy,
                                'offline_enabled': offline,
                                'relay_active_level': evidence['relay_active_level'],
                                'evidence_reference': evidence['evidence_reference']},
    )
    return output_grant_record(grant), True


@transaction.atomic
def revoke_output(device_id, actor, reason):
    reason = output_reason_text(reason)
    device = PrototypeDevice.objects.select_for_update().filter(pk=device_id).first()
    if not device:
        fail('DEVICE_UNAVAILABLE', 'Device is unavailable.', 404)
    authorization = device.output_authorizations.select_for_update().filter(
        state=PrototypeOutputAuthorization.ACTIVE,
    ).first()
    if authorization:
        _revoke_output_grant(authorization, actor, reason)
    device.output_enabled = False
    device.save(update_fields=['output_enabled'])
    return {'device_id': str(device.pk), 'status': 'REVOKED', 'output_enabled': False}


def _revoke_output_grant(authorization, actor, reason):
    authorization.state = PrototypeOutputAuthorization.REVOKED
    authorization.revoked_at = timezone.now()
    authorization.revoked_by = actor
    authorization.save(update_fields=['state', 'revoked_at', 'revoked_by'])
    PrototypeOutputAuthorizationEvent.objects.create(
        authorization=authorization, device_id=authorization.device_id, actor=actor,
        action=PrototypeOutputAuthorizationEvent.REVOKED, reason=reason,
    )


@sensitive_variables()
def authenticate(request):
    mark_stage('authentication')
    require_lab()
    rate_attempt('ac-ip:' + str(request.META.get('REMOTE_ADDR', 'unknown')), 120)
    try:
        pk = canonical_uuid(request.headers.get('X-Device-Id'))
    except BenchError:
        fail('DEVICE_UNAUTHORIZED', 'Device authentication failed.', 401)
    secret = request.headers.get('X-Device-Token', '')
    device = PrototypeDevice.objects.select_related('meter', 'owner__profile').filter(pk=pk).first()
    if not device or not secret or len(secret) > 256 or not check_password(secret, device.credential_hash):
        fail('DEVICE_UNAUTHORIZED', 'Device authentication failed.', 401)
    active_binding(device)
    rate_attempt('ac-device:' + str(pk), 90)
    return device


def validate(body, device, fields, optional_fields=()):
    mark_stage('request_validation')
    required = IDENTITY | set(fields)
    allowed = required | set(optional_fields)
    if not isinstance(body, dict) or not required.issubset(body) or set(body) - allowed:
        fail('REQUEST_INVALID', 'Payload fields do not match the firmware contract.', 400)
    integer(body, 'binding_epoch', minimum=1)
    mark_stage('device_binding')
    if any(body.get(key) != value for key, value in identity(device).items()):
        fail('DEVICE_BINDING_MISMATCH', 'Device binding does not match.', 403)
    mark_stage('request_validation')


def lab_source(allocation, environment=None):
    mark_stage('source_eligibility')
    environment = environment or permitted_environment()
    if environment not in DOMAIN_PROTOCOLS or allocation.accounting_environment != environment:
        return False
    if not authorized_source(allocation):
        return False
    if allocation.purchase_intent_id:
        intent = allocation.purchase_intent
        if (intent.sandbox_context or {}).get('authorization_policy'):
            from transactions.ugx_authorization import purchase_source_valid
            return environment == 'SANDBOX' and purchase_source_valid(intent, allocation)
        receipt = getattr(intent, 'sandbox_settlement', None)
        provider, currency, financial_environment = ('MTN_SANDBOX', 'EUR', 'MTN_SANDBOX') if environment == 'SANDBOX' else ('LOCAL_DEMO', 'UGX', 'UGX_DEMO')
        try:
            from decimal import Decimal
            terms = intent.sandbox_context['terms']
            source_energy = Decimal(terms['energy_kwh'])
            quote = intent.sandbox_quote
            return bool(intent.provider == provider and intent.currency == currency and receipt and receipt.environment == financial_environment
                        and receipt.currency == currency and receipt.received == intent.amount
                        and receipt.billed + receipt.residual == receipt.received
                        and quote and quote.owner_id == allocation.owner_id and quote.meter_id == allocation.meter_id
                        and quote.currency == currency and quote.environment == financial_environment and quote.terms == terms
                        and source_energy.is_finite() and source_energy == allocation.amount_kwh)
        except (KeyError, TypeError, ValueError, ArithmeticError):
            return False
    if allocation.sandbox_loan_id:
        from loan.prototype_lending import loan_energy_environment, is_lab_terms
        loan = allocation.sandbox_loan
        if is_lab_terms(loan.terms):
            try:
                from decimal import Decimal
                return (environment == 'SANDBOX' and loan_energy_environment(loan) == environment
                        and Decimal(loan.terms['energy_kwh']) == allocation.amount_kwh)
            except (KeyError, TypeError, ValueError, ArithmeticError):
                return False
        # Delivering an already-approved source never originates or approves a loan.
        expected = ('MTN_SANDBOX', 'EUR') if environment == 'SANDBOX' else ('UGX_DEMO', 'UGX')
        try:
            from decimal import Decimal
            return ((allocation.sandbox_loan.environment, allocation.sandbox_loan.currency) == expected
                    and Decimal(allocation.sandbox_loan.terms['energy_kwh']) == allocation.amount_kwh)
        except (KeyError, TypeError, ValueError, ArithmeticError):
            return False
    return False


def locked(device):
    require_lab()
    row = PrototypeDevice.objects.select_for_update(of=('self',)).select_related('meter', 'owner__profile').get(pk=device.pk)
    # Serialize against staff ownership changes, as well as other device calls.
    meter = Meter.all_objects.select_for_update().get(pk=row.meter_id)
    active_binding(row, meter)
    return row


def credit_state(device, body, session=False, allow_debit_lag=False):
    mark_stage('credit_reconciliation')
    """Device credit must equal ACKed commands, or precisely the one pending command."""
    counter = integer(body, 'application_counter')
    if counter < device.observed_application_counter:
        fail('DEVICE_COUNTER_REGRESSION')
    credited = integer(body, 'credited_uwh', MAX_COUNTER)
    consumed = integer(body, 'consumed_uwh', MAX_COUNTER)
    uncertain = integer(body, 'uncertain_uwh', MAX_COUNTER)
    commands = list(device.commands.select_related('delivery').order_by('sequence'))
    acked = [c for c in commands if c.receipt_id is not None]
    expected = sum(c.delivery.command_payload['credit_wh'] * 1_000_000 for c in acked)
    current = next((c for c in commands if c.sequence == counter), None)
    if counter == device.application_counter + 1:
        if not current or current.receipt_id is not None:
            fail()
        expected += current.delivery.command_payload['credit_wh'] * 1_000_000
        if session and body['ack_pending'] is not True:
            fail()
    elif counter != device.application_counter:
        fail()
    if (credited != expected or consumed + uncertain > credited
            or (not allow_debit_lag and (consumed < device.consumed_uwh or uncertain < device.uncertain_uwh))):
        fail()
    if session and counter:
        command = current.delivery.command_payload if current else {}
        if (body['last_command_id'] != command.get('command_id') or body['last_payload_digest'] != command.get('payload_digest')):
            fail()
        canonical_uuid(body['last_receipt_id'])
        if current.receipt_id and str(current.receipt_id) != body['last_receipt_id']:
            fail()
    device.observed_application_counter = counter
    return consumed, uncertain


def contact(device):
    device.last_contact_at = timezone.now()
    device.save(update_fields=['last_contact_at', 'consumed_uwh', 'uncertain_uwh', 'observed_application_counter'])


def recovery_protocol(device, body):
    value = body.get('accounting_protocol')
    if value != RECOVERY_PROTOCOL and ('accounting_protocol' in body or device.recovery_enabled):
        fail('ACCOUNTING_PROTOCOL_REQUIRED')
    return value == RECOVERY_PROTOCOL


def committed_baseline(device):
    return PrototypeMeasurementTransition.objects.filter(
        device=device, state=PrototypeMeasurementTransition.COMMITTED,
    ).first()


def adopt_legacy_baseline(device):
    """Anchor an existing metered journal to previously accepted server evidence."""
    if PrototypeMeasurementTransition.objects.filter(device=device).exists():
        return
    anchor = device.telemetry.filter(payload__sensor_status='OK').order_by('-received_at', '-pk').first()
    if not anchor:
        return
    data = anchor.payload
    if (data['consumed_uwh'] != device.consumed_uwh or data['uncertain_uwh'] != device.uncertain_uwh
            or data['application_counter'] != device.application_counter
            or device.commands.filter(receipt_id__isnull=True).exists()):
        fail('LEGACY_BASELINE_REVIEW')
    PrototypeMeasurementTransition.objects.create(
        device=device, transition_id=uuid.uuid4(), state=PrototypeMeasurementTransition.COMMITTED,
        had_baseline=True, old_baseline_wh=data['pzem_wh'], baseline_wh=data['pzem_wh'],
        application_counter=device.application_counter, credited_uwh=data['credited_uwh'],
        consumed_uwh=device.consumed_uwh, uncertain_uwh=device.uncertain_uwh,
        payload={'source_state': 'SERVER_LEGACY_ANCHOR', 'telemetry_id': anchor.pk},
        committed_at=timezone.now(),
    )


@transaction.atomic
def session(device, body):
    device = locked(device)
    fields = {'boot_id', 'boot_counter', 'application_counter', 'initialize', 'ack_pending', 'credited_uwh', 'consumed_uwh', 'uncertain_uwh'}
    optional_fields = {'relay_active_level', 'accounting_protocol', 'journal_mode', 'journal_counter_wh'}
    if isinstance(body, dict) and type(body.get('application_counter')) is int and body['application_counter'] > 0:
        fields |= {'last_command_id', 'last_payload_digest', 'last_receipt_id'}
    validate(body, device, fields, optional_fields)
    recovery = recovery_protocol(device, body)
    if recovery and body.get('journal_mode') not in ('FRESH', 'PAUSED', 'METERED'):
        fail('REQUEST_INVALID', 'Invalid measurement journal mode.', 400)
    journal_wh = 0
    if recovery:
        if body['journal_mode'] == 'METERED':
            journal_wh = integer(body, 'journal_counter_wh')
        elif body.get('journal_counter_wh') is not None:
            fail('REQUEST_INVALID', 'Journal counter requires metered mode.', 400)
    if ('relay_active_level' in body
            and body['relay_active_level'] not in (None, 'HIGH', 'LOW')):
        fail('REQUEST_INVALID', 'Invalid compiled relay polarity declaration.', 400)
    boot = canonical_uuid(body['boot_id'])
    count = integer(body, 'boot_counter', minimum=1)
    if (type(body['initialize']) is not bool or type(body['ack_pending']) is not bool
            or (body['application_counter'] == 0 and body['ack_pending'] is True)):
        fail('REQUEST_INVALID', 'Boolean session fields required.', 400)
    if body['initialize'] and (device.commands.exists() or body['application_counter'] != 0):
        fail('DEVICE_STORAGE_RESET')
    if not device.boot_id and not body['initialize']:
        fail('DEVICE_STORAGE_REQUIRED')
    if count < device.boot_counter or (count == device.boot_counter and boot != device.boot_id):
        fail('DEVICE_BOOT_REPLAY')
    if count > device.boot_counter:
        if PrototypeBoot.objects.filter(device=device, boot_id=boot).exists():
            fail('DEVICE_BOOT_REPLAY')
        PrototypeBoot.objects.create(device=device, boot_id=boot, boot_counter=count)
        device.boot_counter, device.boot_id, device.telemetry_sequence = count, boot, 0
        device.save(update_fields=['boot_counter', 'boot_id', 'telemetry_sequence'])
    reported_consumed, reported_uncertain = credit_state(device, body, session=True, allow_debit_lag=recovery)
    transition = getattr(device, 'measurement_transition', None)
    if recovery:
        if reported_uncertain != device.uncertain_uwh:
            fail('METER_ACCOUNTING_MISMATCH')
        if body['journal_mode'] == 'METERED' and not transition and not body['ack_pending']:
            adopt_legacy_baseline(device)
            transition = PrototypeMeasurementTransition.objects.filter(device=device).first()
        device.recovery_enabled = device.recovery_pending = True
        # A journal claim can hold output pending, but it never advances the
        # verified debit or counter without a subsequently validated sample.
        device.recovery_target_consumed_uwh = max(device.recovery_target_consumed_uwh, reported_consumed)
        device.recovery_target_wh = max(device.recovery_target_wh, journal_wh)
        device.save(update_fields=['recovery_enabled', 'recovery_pending',
                                   'recovery_target_consumed_uwh', 'recovery_target_wh'])
    elif transition and transition.state == PrototypeMeasurementTransition.COMMITTED and (
        reported_consumed != device.consumed_uwh
        or reported_uncertain != device.uncertain_uwh
    ):
        fail('METER_ACCOUNTING_MISMATCH')
    elif not recovery:
        device.consumed_uwh, device.uncertain_uwh = reported_consumed, reported_uncertain
    contact(device)
    result = {**identity(device), 'status': 'READY', **output_authorization(device)}
    if result['output_offline_allowed']:
        # A reconnect may check the cached policy while accounting catches up.
        # Bind that decision to the relay polarity in this authenticated boot.
        grant = device.output_authorizations.get(state=PrototypeOutputAuthorization.ACTIVE)
        result['output_offline_allowed'] = body.get('relay_active_level') == grant.evidence['relay_active_level']
    if recovery:
        result['measurement_baseline'] = transition.state if transition else 'REQUIRED'
        result['verified_consumed_uwh'] = device.consumed_uwh
        if transition and transition.state == PrototypeMeasurementTransition.COMMITTED:
            latest = device.telemetry.filter(payload__sensor_status='OK', received_at__gte=transition.committed_at).order_by('-received_at', '-pk').first()
            result['verified_counter_wh'] = latest.payload['pzem_wh'] if latest else transition.baseline_wh
        if not body['ack_pending']:
            pending = device.commands.filter(receipt_id__isnull=True).select_related('delivery').first()
            if pending:
                result['pending_credit_command'] = pending.delivery.command_payload
                result['credit_checkpoint_required'] = pending.checkpoint_required
    return result


@transaction.atomic
def prepare_measurement(device, body):
    device = locked(device)
    fields = {
        'transition_id', 'transition_protocol', 'source_state', 'had_baseline',
        'old_baseline_wh', 'baseline_wh', 'application_counter', 'ack_pending',
        'credited_uwh', 'consumed_uwh', 'uncertain_uwh',
    }
    if isinstance(body, dict) and type(body.get('application_counter')) is int and body['application_counter'] > 0:
        fields |= {'last_command_id', 'last_payload_digest', 'last_receipt_id'}
    validate(body, device, fields)
    transition_id = canonical_uuid(body['transition_id'])
    source = body['source_state']
    supported = ('AUTH_CREDIT_ONLY_V3', 'FRESH_METERED', 'LEGACY_METERED')
    if (body['transition_protocol'] != 'GPAWA_BASELINE_V1' or source not in supported
            or (source != 'AUTH_CREDIT_ONLY_V3' and not device.recovery_enabled)):
        fail('MEASUREMENT_TRANSITION_INVALID', 'Unsupported measurement transition.', 400)
    if type(body['had_baseline']) is not bool or type(body['ack_pending']) is not bool:
        fail('REQUEST_INVALID', 'Invalid migration journal flags.', 400)
    baseline = integer(body, 'baseline_wh')
    if body['had_baseline']:
        old_baseline = integer(body, 'old_baseline_wh')
    else:
        old_baseline = None
        if body['old_baseline_wh'] is not None:
            fail('REQUEST_INVALID', 'An absent prior baseline must be null.', 400)
    if body['ack_pending']:
        fail('ACK_REQUIRED', 'A pending credit acknowledgement must finish before baseline migration.')

    existing = PrototypeMeasurementTransition.objects.filter(device=device).first()
    if existing:
        if existing.transition_id != transition_id or existing.payload != body:
            fail('MEASUREMENT_TRANSITION_CONFLICT')
        contact(device)
        return transition_response(device, existing)
    if PrototypeMeasurementTransition.objects.filter(transition_id=transition_id).exists():
        fail('MEASUREMENT_TRANSITION_CONFLICT')
    if device.commands.filter(receipt_id__isnull=True).exists():
        fail('ACK_REQUIRED', 'A pending credit acknowledgement must finish before baseline migration.')

    consumed, uncertain = credit_state(device, body, session=True)
    if consumed != device.consumed_uwh or uncertain != device.uncertain_uwh:
        fail('METER_ACCOUNTING_MISMATCH')
    if source == 'FRESH_METERED' and (body['had_baseline'] or consumed or uncertain):
        fail('MEASUREMENT_TRANSITION_INVALID')
    if source == 'LEGACY_METERED' and (
        not body['had_baseline'] or baseline != old_baseline or consumed or uncertain
        or device.telemetry.filter(payload__sensor_status='OK').exists()
    ):
        fail('LEGACY_BASELINE_REVIEW')
    transition = PrototypeMeasurementTransition.objects.create(
        device=device,
        transition_id=transition_id,
        had_baseline=body['had_baseline'],
        old_baseline_wh=old_baseline,
        baseline_wh=baseline,
        application_counter=body['application_counter'],
        credited_uwh=body['credited_uwh'],
        consumed_uwh=body['consumed_uwh'],
        uncertain_uwh=body['uncertain_uwh'],
        payload=body,
    )
    contact(device)
    return transition_response(device, transition)


def transition_response(device, transition):
    return {
        **identity(device),
        'status': transition.state,
        'transition_id': str(transition.transition_id),
        'receipt_id': str(transition.receipt_id),
        'baseline_wh': transition.baseline_wh,
        'output_authorized': False,
        'output_lease_seconds': 0,
        'output_restart_policy': PrototypeOutputAuthorization.MANUAL,
        'output_authorization_expires_at': None,
    }


def transition_credit_matches_device(device, transition):
    credited = sum(
        command.delivery.command_payload['credit_wh'] * 1_000_000
        for command in device.commands.filter(receipt_id__isnull=False).select_related('delivery')
    )
    return (
        device.application_counter == transition.application_counter
        and credited == transition.credited_uwh
        and device.consumed_uwh == transition.consumed_uwh
        and device.uncertain_uwh == transition.uncertain_uwh
        and not device.commands.filter(receipt_id__isnull=True).exists()
    )


@transaction.atomic
def commit_measurement(device, body):
    device = locked(device)
    validate(body, device, {'transition_id', 'receipt_id'})
    transition_id = canonical_uuid(body['transition_id'])
    receipt_id = canonical_uuid(body['receipt_id'])
    transition = PrototypeMeasurementTransition.objects.select_for_update().filter(
        device=device, transition_id=transition_id,
    ).first()
    if not transition or transition.receipt_id != receipt_id:
        fail('MEASUREMENT_TRANSITION_CONFLICT')
    if transition.state == PrototypeMeasurementTransition.PREPARED:
        if not transition_credit_matches_device(device, transition):
            fail('MEASUREMENT_ALREADY_ACTIVE')
        transition.state = PrototypeMeasurementTransition.COMMITTED
        transition.committed_at = timezone.now()
        transition.save(update_fields=['state', 'committed_at'])
    contact(device)
    return transition_response(device, transition)


@sensitive_variables()
@transaction.atomic
def redeem(device, body):
    device = locked(device)
    if PrototypeMeasurementTransition.objects.filter(
        device=device, state=PrototypeMeasurementTransition.PREPARED,
    ).exists():
        fail('MEASUREMENT_TRANSITION_PENDING')
    validate(body, device, {'token', 'application_counter'}, {'accounting_protocol'})
    recovery = recovery_protocol(device, body)
    count = integer(body, 'application_counter')
    if count < device.observed_application_counter:
        fail('DEVICE_COUNTER_REGRESSION')
    if device.boot_id is None:
        fail('DEVICE_SESSION_REQUIRED')
    if not isinstance(body['token'], str) or not re.fullmatch(r'[0-9]{15}', body['token']):
        fail('REQUEST_INVALID', 'Use a 15-digit token.', 400)
    mark_stage('token_lookup')
    try:
        lookup = digest_token(body['token'])
    except ImproperlyConfigured:
        fail('TOKEN_SERVICE_UNAVAILABLE', 'Private token configuration requires operator review.', 503)
    mark_stage('token_lookup')
    row = EnergyKeypadToken.objects.filter(lookup_digest=lookup).first()
    if row is None:
        fail('TOKEN_LOOKUP_MISS', 'No matching token was found; retain the existing purchase for review.', 404)
    mark_stage('meter_environment_mismatch')
    allocation = EnergyAllocation.objects.select_for_update().get(pk=row.allocation_id)
    token = EnergyKeypadToken.objects.select_for_update().get(pk=row.pk)
    if (token.owner_id != device.owner_id or allocation.owner_id != device.owner_id or token.meter_id != device.meter_id
            or allocation.meter_id != device.meter_id or token.meter_number != device.meter.meter_no
            or token.environment != device.environment or allocation.accounting_environment != device.environment):
        fail('TOKEN_UNAVAILABLE', 'Token unavailable for this device.', 404)
    mark_stage('token_amount_validation')
    if allocation.amount_kwh * 1000 != token.amount_wh or not 0 < token.amount_wh <= 1_000_000 or token.amount_wh % 10:
        fail('TOKEN_AMOUNT_MISMATCH', 'Token amount requires reconciliation.', 409)
    if not lab_source(allocation, device.environment):
        fail('TOKEN_SOURCE_UNVERIFIED', 'Token source requires reconciliation; retain the existing purchase.', 409)
    mark_stage('token_integrity')
    # Check encrypted integrity as well as the lookup HMAC. Never return plaintext.
    try:
        plain = cipher().decrypt(token.ciphertext.encode()).decode('ascii')
        if not hmac.compare_digest(plain, body['token']):
            raise ValueError
    except Exception:
        fail('TOKEN_STORAGE_UNAVAILABLE', 'Token integrity requires operator review.', 409)
    mark_stage('already_used_token')
    if token.state == 'APPLIED':
        fail('TOKEN_ALREADY_USED')
    mark_stage('pending_delivery')
    pending = device.commands.filter(receipt_id__isnull=True).select_related('delivery').first()
    if pending:
        if token.delivery_id == pending.delivery_id and count in {device.application_counter, pending.sequence}:
            contact(device)
            return {**identity(device), 'command': pending.delivery.command_payload,
                    **({'credit_checkpoint_required': pending.checkpoint_required} if recovery else {})}
        fail('PENDING_COMMAND')
    if recovery and (not committed_baseline(device) or device.recovery_pending):
        fail('METER_RECOVERY_PENDING')
    mark_stage('conflicting_command')
    if count != device.application_counter:
        fail()
    if token.state != 'ISSUED' or token.delivery_id or allocation.deliveries.exists() or count == UINT32:
        fail('RESERVATION_CONFLICT')
    from meter.allocation_service import reserve_ac_lab_token
    mark_stage('delivery_reservation')
    delivery = reserve_ac_lab_token(token, device=device)
    if max(delivery.pk, allocation.pk) > 2**53 - 1:
        fail('IDENTITY_OUT_OF_RANGE')
    mark_stage('command_creation')
    command = {**identity(device), 'allocation_id': allocation.pk, 'delivery_id': delivery.pk,
        'command_id': str(token.command_id), 'command_sequence': count + 1, 'credit_wh': token.amount_wh, 'type': 'AC_LAB_CREDIT'}
    command['payload_digest'] = payload_digest(command)
    delivery.command_payload = command
    delivery.save(update_fields=['command_payload'])
    PrototypeCommand.objects.create(device=device, delivery=delivery, sequence=count + 1,
                                    checkpoint_required=recovery)
    contact(device)
    return {**identity(device), 'command': command,
            **({'credit_checkpoint_required': True} if recovery else {})}


@transaction.atomic
def acknowledge(device, body):
    device = locked(device)
    validate(body, device, {'type', 'command_id', 'command_sequence', 'payload_digest', 'credit_wh', 'receipt_id', 'applied_at', 'allocation_id', 'delivery_id'},
             {'credit_checkpoint'})
    for key in ('command_sequence', 'credit_wh', 'allocation_id', 'delivery_id'):
        integer(body, key, 2**53 - 1, 1)
    receipt = canonical_uuid(body['receipt_id'])
    at = timestamp(body['applied_at'])
    mark_stage('ack_command_lookup')
    command = device.commands.select_related('delivery__allocation').filter(delivery_id=body['delivery_id']).first()
    if command is None:
        fail('COMMAND_UNAVAILABLE', status=404)
    delivery = MeterDelivery.objects.select_for_update().get(pk=command.delivery_id)
    mark_stage('ack_validation')
    frozen = delivery.command_payload
    if delivery.transport != 'AC_LAB' or delivery.status not in {MeterDelivery.DISPATCHED, MeterDelivery.OUTCOME_UNKNOWN, MeterDelivery.APPLIED}:
        fail('RECONCILIATION_REQUIRED')
    if (body['type'] != 'AC_LAB_APPLIED' or any(body[k] != v for k, v in frozen.items() if k != 'type')
            or at < delivery.created_at - timedelta(minutes=5)):
        fail('RECEIPT_BINDING_MISMATCH')
    # Recheck current allocation/token provenance; never ACK another domain.
    allocation = EnergyAllocation.objects.select_for_update().get(pk=delivery.allocation_id)
    token = EnergyKeypadToken.objects.select_for_update().get(delivery=delivery)
    if (allocation.owner_id != device.owner_id or allocation.meter_id != device.meter_id
            or allocation.accounting_environment != device.environment or token.environment != device.environment
            or token.owner_id != device.owner_id or token.meter_id != device.meter_id
            or not lab_source(allocation, device.environment)):
        fail('RECEIPT_BINDING_MISMATCH')
    mark_stage('conflicting_command')
    checkpoint = body.get('credit_checkpoint')
    if command.receipt_id:
        if command.receipt_id != receipt or command.applied_at != at or checkpoint != command.credit_checkpoint:
            fail('RECEIPT_CONFLICT')
    else:
        if command.sequence != device.application_counter + 1 or PrototypeCommand.objects.filter(receipt_id=receipt).exists():
            fail('RECEIPT_CONFLICT')
        if command.checkpoint_required:
            if not isinstance(checkpoint, dict) or set(checkpoint) != {'boot_id', 'sequence'}:
                fail('CREDIT_CHECKPOINT_REQUIRED')
            boot = canonical_uuid(checkpoint['boot_id'])
            sequence = integer(checkpoint, 'sequence', minimum=1)
            latest = device.telemetry.order_by('-received_at', '-pk').first()
            # ACK recovery can cross a restart. The original stored checkpoint
            # must still be the last accepted sample from the old credit epoch.
            if (not latest or not latest.recovery_settled or latest.boot_id != boot or latest.sequence != sequence
                    or latest.payload.get('accounting_protocol') != RECOVERY_PROTOCOL
                    or latest.payload['application_counter'] != command.sequence - 1
                    or latest.payload['consumed_uwh'] != device.consumed_uwh
                    or latest.payload['uncertain_uwh'] != device.uncertain_uwh
                    or latest.payload['sensor_status'] != 'OK' or latest.payload.get('fault_status') != 'OK'
                    or latest.payload['output_requested']
                    or latest.received_at < delivery.created_at
                    or latest.measured_at < delivery.created_at - timedelta(minutes=5)
                    or latest.measured_at > at):
                fail('CREDIT_CHECKPOINT_REQUIRED')
        elif checkpoint is not None:
            fail('REQUEST_INVALID', 'Unexpected credit checkpoint.', 400)
        command.receipt_id, command.applied_at, command.received_at = receipt, at, timezone.now()
        command.credit_checkpoint = checkpoint
        try:
            with transaction.atomic():
                command.save(update_fields=['receipt_id', 'applied_at', 'received_at', 'credit_checkpoint'])
        except IntegrityError:
            fail('RECEIPT_CONFLICT')
        delivery.status, delivery.applied_at = MeterDelivery.APPLIED, at
        delivery.save(update_fields=['status', 'applied_at'])
        token.state = 'APPLIED'; token.save(update_fields=['state'])
        device.application_counter = command.sequence
        device.recovery_pending = device.recovery_enabled
        device.save(update_fields=['application_counter', 'recovery_pending'])
    contact(device)
    return {**identity(device), 'status': 'APPLIED', **{k: body[k] for k in ('command_id', 'command_sequence', 'payload_digest', 'receipt_id')}}


@transaction.atomic
def telemetry(device, body, *, replay=False):
    device = locked(device)
    fields = {'boot_id', 'boot_counter', 'sequence', 'measured_at', 'clock_status', 'application_counter', 'credited_uwh',
              'consumed_uwh', 'uncertain_uwh', 'remaining_credit_uwh', 'voltage_mv', 'current_ma', 'power_mw', 'pzem_wh',
              'output_requested', 'output_feedback', 'sensor_status'}
    optional_fields = {'frequency_cHz', 'power_factor_pct', 'fault_status', 'relay_active_level', 'accounting_protocol', 'offline_gap'}
    validate(body, device, fields, optional_fields)
    recovery = recovery_protocol(device, body)
    if recovery != device.recovery_enabled:
        fail('DEVICE_SESSION_REQUIRED')
    boot = canonical_uuid(body['boot_id'])
    integer(body, 'boot_counter', minimum=1)
    seq = integer(body, 'sequence', minimum=1)
    if device.boot_id != boot or device.boot_counter != body['boot_counter']:
        fail('DEVICE_SESSION_REQUIRED')
    prior = device.telemetry.filter(boot_id=boot, sequence=seq).first()
    if prior:
        if prior.payload != body:
            fail('EVENT_CONFLICT')
        if recovery and replay:
            device.recovery_pending = True
            device.save(update_fields=['recovery_pending'])
        return {
            **identity(device), 'status': 'ACCEPTED', 'boot_id': str(boot), 'sequence': seq,
            **output_authorization(device),
            **({'recovery_pending': True, 'output_authorized': False, 'output_lease_seconds': 0,
                'output_reason': 'METER_RECOVERY_PENDING'} if recovery else {}),
        }
    if seq <= device.telemetry_sequence:
        fail('STALE_TELEMETRY')
    clock_known = body['clock_status'] == 'NETWORK_TIME'
    if type(body.get('offline_gap', False)) is not bool:
        fail('REQUEST_INVALID', 'Invalid upload gap marker.', 400)
    if clock_known:
        at = timestamp(body['measured_at'])
    else:
        # This is an accounting checkpoint with an unknown capture time. The
        # database timestamp is its receipt-time upper bound, not a sample time.
        if (body['clock_status'] != 'OFFLINE_UNTIMED' or body['measured_at'] is not None
                or not recovery or body['sensor_status'] != 'OK' or body.get('fault_status') != 'SENSOR_UNAVAILABLE'
                or not device.output_authorizations.filter(offline_enabled=True, binding_snapshot=output_binding(device)).exists()):
            fail('REQUEST_INVALID', 'Invalid untimed offline observation.', 400)
        at = timezone.now().replace(microsecond=0)
    previous = device.telemetry.order_by('-received_at', '-pk').first()
    if previous and at < previous.measured_at:
        fail('STALE_TELEMETRY')
    if recovery and body['application_counter'] != device.application_counter:
        fail('ACK_REQUIRED')
    consumed, uncertain = credit_state(device, body)
    remaining = integer(body, 'remaining_credit_uwh', MAX_COUNTER)
    if body['credited_uwh'] != consumed + uncertain + remaining:
        fail('CREDIT_CONSERVATION')
    if body['sensor_status'] == 'OK':
        for key in ('voltage_mv', 'current_ma', 'power_mw', 'pzem_wh'):
            integer(body, key, UINT32)
        if 'frequency_cHz' in body:
            integer(body, 'frequency_cHz', 6500, 4500)
        if 'power_factor_pct' in body:
            integer(body, 'power_factor_pct', 100)
        if recovery:
            voltage, current, power = body['voltage_mv'], body['current_ma'], body['power_mw']
            if (not 80_000 <= voltage <= 260_000 or current > 100_000 or power > 26_000_000
                    or power > voltage * current // 1000 + 1000):
                fail('REQUEST_INVALID', 'Meter reading is out of range.', 400)
    elif body['sensor_status'] == 'FAULT':
        if any(body[key] is not None for key in ('voltage_mv', 'current_ma', 'power_mw', 'pzem_wh')
               + tuple(key for key in ('frequency_cHz', 'power_factor_pct') if key in body)):
            fail('REQUEST_INVALID', 'Unavailable sensor data must be null.', 400)
    else:
        fail('REQUEST_INVALID', 'Invalid sensor state.', 400)
    if (body['output_feedback'] != 'UNKNOWN'
            or type(body['output_requested']) is not bool):
        fail('REQUEST_INVALID', 'Invalid measurement state.', 400)
    if body.get('fault_status', 'OK' if body['sensor_status'] == 'OK' else 'SENSOR_UNAVAILABLE') not in {
        'OK', 'SENSOR_UNAVAILABLE', 'ACCOUNTING_HOLD', 'SAFETY_FAULT',
    }:
        fail('REQUEST_INVALID', 'Invalid device fault state.', 400)
    if ('relay_active_level' in body
            and body['relay_active_level'] not in (None, 'HIGH', 'LOW')):
        fail('REQUEST_INVALID', 'Invalid compiled relay polarity declaration.', 400)
    transition = committed_baseline(device)
    if recovery and not transition:
        fail('MEASUREMENT_BASELINE_REQUIRED')
    valid_telemetry = device.telemetry.filter(payload__sensor_status='OK')
    if transition:
        valid_telemetry = valid_telemetry.filter(received_at__gte=transition.committed_at)
    previous_valid = valid_telemetry.order_by('-received_at', '-pk').first()
    if body['sensor_status'] == 'OK' and previous_valid and body['pzem_wh'] < previous_valid.payload['pzem_wh']:
        fail('PZEM_COUNTER_RESET')
    if transition and body['sensor_status'] == 'FAULT' and (
        consumed != device.consumed_uwh or uncertain != device.uncertain_uwh
    ):
        fail('METER_ACCOUNTING_MISMATCH')
    if transition and body['sensor_status'] == 'OK':
        previous_wh = previous_valid.payload['pzem_wh'] if previous_valid else transition.baseline_wh
        previous_consumed = previous_valid.payload['consumed_uwh'] if previous_valid else transition.consumed_uwh
        previous_uncertain = previous_valid.payload['uncertain_uwh'] if previous_valid else transition.uncertain_uwh
        delta_wh = body['pzem_wh'] - previous_wh
        if delta_wh < 0:
            fail('PZEM_COUNTER_RESET')
        anchor = previous_valid
        if recovery and not anchor and transition.payload.get('source_state') == 'SERVER_LEGACY_ANCHOR':
            anchor = device.telemetry.filter(pk=transition.payload.get('telemetry_id')).first()
        if recovery and anchor:
            if anchor.payload.get('clock_status') == 'OFFLINE_UNTIMED':
                anchor = valid_telemetry.filter(payload__clock_status='NETWORK_TIME').order_by('-received_at', '-pk').first()
            lower_bound = anchor.measured_at if anchor else transition.committed_at
            elapsed = max(0, (at - lower_bound).total_seconds())
            # The PZEM reports integer Wh and firmware sends whole UTC seconds.
            if delta_wh > 26_000 * (elapsed + 1) / 3600 + 2:
                fail('PZEM_ENERGY_JUMP')
        expected_delta = min(delta_wh * 1_000_000, body['credited_uwh'] - previous_consumed - previous_uncertain)
        if (body['consumed_uwh'] != previous_consumed + expected_delta
                or body['uncertain_uwh'] != previous_uncertain):
            fail('METER_ACCOUNTING_MISMATCH')
    device.recovery_pending = recovery and (
        replay or not clock_known or body['sensor_status'] != 'OK' or body.get('fault_status') != 'OK'
        or consumed < device.recovery_target_consumed_uwh or body['pzem_wh'] < device.recovery_target_wh
    )
    PrototypeTelemetry.objects.create(device=device, boot_id=boot, sequence=seq, measured_at=at, payload=body,
                                      recovery_settled=recovery and not device.recovery_pending)
    device.telemetry_sequence, device.consumed_uwh, device.uncertain_uwh = seq, consumed, uncertain
    device.save(update_fields=['telemetry_sequence', 'consumed_uwh', 'uncertain_uwh', 'recovery_pending'])
    contact(device)
    return {
        **identity(device), 'status': 'ACCEPTED', 'boot_id': str(boot), 'sequence': seq,
        **output_authorization(device),
        **({'recovery_pending': device.recovery_pending} if recovery else {}),
    }
