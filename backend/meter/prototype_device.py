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
                          PrototypeBoot, PrototypeCommand, PrototypeDevice, PrototypeTelemetry)

PROTOCOL = 'GPAWA_PZEM_V1'
DOMAIN_PROTOCOLS = {'UGX_DEMO': PROTOCOL, 'SANDBOX': 'GPAWA_PZEM_V2'}
IDENTITY = {'protocol', 'device_id', 'meter_number', 'storage_id', 'binding_epoch', 'environment', 'hardware_class'}
MAX_COUNTER = 9_000_000_000_000_000
UINT32 = 2**32 - 1


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
            and permitted_environment() in DOMAIN_PROTOCOLS
            and getattr(settings, 'PROTOTYPE_RELAY_OUTPUT_ENABLED', True) is False)


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


def active_binding(device):
    mark_stage('device_binding')
    meter = Meter.all_objects.get(pk=device.meter_id)
    if (not device.active or device.revoked_at or device.output_enabled or device.environment != permitted_environment()
            or device.hardware_class != 'AC_LAB' or meter.user_id != device.owner_id or meter.is_deleted
            or meter.status != 'ACTIVE' or not meter.sandbox_inventory or not re.fullmatch(r'[0-9]{11}', meter.meter_no)
            or meter.meter_no == '0' * 11
            or not device.owner.is_active or device.owner.user_role != User.CLIENT or device.owner.is_staff or device.owner.is_superuser
            or not getattr(getattr(device.owner, 'profile', None), 'email_verified', False)):
        fail('DEVICE_UNAUTHORIZED', 'Device authentication failed.', 401)
    device.meter = meter


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


def validate(body, device, fields):
    mark_stage('request_validation')
    if not isinstance(body, dict) or set(body) != IDENTITY | set(fields):
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
    Meter.all_objects.select_for_update().get(pk=row.meter_id)
    active_binding(row)
    return row


def credit_state(device, body, session=False):
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
    if credited != expected or consumed < device.consumed_uwh or uncertain < device.uncertain_uwh or consumed + uncertain > credited:
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


@transaction.atomic
def session(device, body):
    device = locked(device)
    fields = {'boot_id', 'boot_counter', 'application_counter', 'initialize', 'ack_pending', 'credited_uwh', 'consumed_uwh', 'uncertain_uwh'}
    if isinstance(body, dict) and type(body.get('application_counter')) is int and body['application_counter'] > 0:
        fields |= {'last_command_id', 'last_payload_digest', 'last_receipt_id'}
    validate(body, device, fields)
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
    device.consumed_uwh, device.uncertain_uwh = credit_state(device, body, session=True)
    contact(device)
    return {**identity(device), 'status': 'READY'}


@sensitive_variables()
@transaction.atomic
def redeem(device, body):
    device = locked(device)
    validate(body, device, {'token', 'application_counter'})
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
            return {**identity(device), 'command': pending.delivery.command_payload}
        fail('PENDING_COMMAND')
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
    PrototypeCommand.objects.create(device=device, delivery=delivery, sequence=count + 1)
    contact(device)
    return {**identity(device), 'command': command}


@transaction.atomic
def acknowledge(device, body):
    device = locked(device)
    validate(body, device, {'type', 'command_id', 'command_sequence', 'payload_digest', 'credit_wh', 'receipt_id', 'applied_at', 'allocation_id', 'delivery_id'})
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
    if command.receipt_id:
        if command.receipt_id != receipt or command.applied_at != at:
            fail('RECEIPT_CONFLICT')
    else:
        if command.sequence != device.application_counter + 1 or PrototypeCommand.objects.filter(receipt_id=receipt).exists():
            fail('RECEIPT_CONFLICT')
        command.receipt_id, command.applied_at, command.received_at = receipt, at, timezone.now()
        try:
            with transaction.atomic():
                command.save(update_fields=['receipt_id', 'applied_at', 'received_at'])
        except IntegrityError:
            fail('RECEIPT_CONFLICT')
        delivery.status, delivery.applied_at = MeterDelivery.APPLIED, at
        delivery.save(update_fields=['status', 'applied_at'])
        token.state = 'APPLIED'; token.save(update_fields=['state'])
        device.application_counter = command.sequence
        device.save(update_fields=['application_counter'])
    contact(device)
    return {**identity(device), 'status': 'APPLIED', **{k: body[k] for k in ('command_id', 'command_sequence', 'payload_digest', 'receipt_id')}}


@transaction.atomic
def telemetry(device, body):
    device = locked(device)
    fields = {'boot_id', 'boot_counter', 'sequence', 'measured_at', 'clock_status', 'application_counter', 'credited_uwh',
              'consumed_uwh', 'uncertain_uwh', 'remaining_credit_uwh', 'voltage_mv', 'current_ma', 'power_mw', 'pzem_wh',
              'output_requested', 'output_feedback', 'sensor_status'}
    validate(body, device, fields)
    boot = canonical_uuid(body['boot_id'])
    integer(body, 'boot_counter', minimum=1)
    seq = integer(body, 'sequence', minimum=1)
    at = timestamp(body['measured_at'])
    if device.boot_id != boot or device.boot_counter != body['boot_counter']:
        fail('DEVICE_SESSION_REQUIRED')
    prior = device.telemetry.filter(boot_id=boot, sequence=seq).first()
    if prior:
        if prior.payload != body:
            fail('EVENT_CONFLICT')
        return {**identity(device), 'status': 'ACCEPTED', 'boot_id': str(boot), 'sequence': seq}
    if seq <= device.telemetry_sequence:
        fail('STALE_TELEMETRY')
    previous = device.telemetry.order_by('-received_at', '-pk').first()
    if previous and at < previous.measured_at:
        fail('STALE_TELEMETRY')
    consumed, uncertain = credit_state(device, body)
    remaining = integer(body, 'remaining_credit_uwh', MAX_COUNTER)
    if body['credited_uwh'] != consumed + uncertain + remaining:
        fail('CREDIT_CONSERVATION')
    for key in ('voltage_mv', 'current_ma', 'power_mw', 'pzem_wh'):
        integer(body, key, UINT32)
    if (body['clock_status'] != 'NETWORK_TIME' or body['output_feedback'] != 'UNKNOWN'
            or body['sensor_status'] not in ('OK', 'FAULT') or type(body['output_requested']) is not bool):
        fail('REQUEST_INVALID', 'Invalid measurement state.', 400)
    if body['output_requested'] is not False:
        fail('OUTPUT_DISABLED', 'This milestone requires physical output disabled.', 403)
    if previous and body['pzem_wh'] < previous.payload['pzem_wh']:
        fail('PZEM_COUNTER_RESET')
    PrototypeTelemetry.objects.create(device=device, boot_id=boot, sequence=seq, measured_at=at, payload=body)
    device.telemetry_sequence, device.consumed_uwh, device.uncertain_uwh = seq, consumed, uncertain
    device.save(update_fields=['telemetry_sequence'])
    contact(device)
    return {**identity(device), 'status': 'ACCEPTED', 'boot_id': str(boot), 'sequence': seq}
