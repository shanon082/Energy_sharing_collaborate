"""Device diagnostics contain IDs, fixed codes and stack locations, never data."""
from contextlib import contextmanager
from contextvars import ContextVar
import logging
from pathlib import Path
import re
import traceback
import uuid

CODES = frozenset('COMMAND_UNAVAILABLE CREDIT_CONSERVATION DEVICE_BOOT_REPLAY DEVICE_STORAGE_REQUIRED EVENT_CONFLICT IDENTITY_OUT_OF_RANGE PZEM_COUNTER_RESET STALE_TELEMETRY REQUEST_INVALID REQUEST_TOO_LARGE TOKEN_LOOKUP_MISS TOKEN_UNAVAILABLE TOKEN_AMOUNT_MISMATCH TOKEN_SOURCE_UNVERIFIED TOKEN_ALREADY_USED PENDING_COMMAND RESERVATION_CONFLICT DEVICE_UNAUTHORIZED DEVICE_BINDING_MISMATCH DEVICE_SESSION_REQUIRED DEVICE_STORAGE_RESET DEVICE_COUNTER_REGRESSION RECONCILIATION_REQUIRED TOKEN_SERVICE_UNAVAILABLE TOKEN_STORAGE_UNAVAILABLE AC_LAB_DISABLED DEVICE_RATE_LIMITED RECEIPT_BINDING_MISMATCH RECEIPT_CONFLICT OUTPUT_DISABLED OUTPUT_GLOBAL_DISABLE OUTPUT_ALREADY_COMMISSIONED COMMISSIONING_EVIDENCE_REQUIRED MEASUREMENT_BASELINE_REQUIRED METER_NOT_READY CREDIT_UNAVAILABLE DEVICE_UNAVAILABLE TESTING_OPERATION_UNAVAILABLE INTERNAL_ERROR'.split())
STAGES = frozenset('authentication device_binding request_validation token_lookup meter_environment_mismatch token_amount_validation source_eligibility token_integrity already_used_token pending_delivery conflicting_command delivery_reservation command_creation ack_command_lookup ack_validation credit_reconciliation hosting_policy request_routing response_serialization handler complete'.split())
CODES |= frozenset((
    'ACCOUNTING_PROTOCOL_REQUIRED', 'ACK_REQUIRED', 'CREDIT_CHECKPOINT_REQUIRED',
    'LEGACY_BASELINE_REVIEW', 'MEASUREMENT_ALREADY_ACTIVE', 'MEASUREMENT_TRANSITION_CONFLICT',
    'MEASUREMENT_TRANSITION_INVALID', 'MEASUREMENT_TRANSITION_PENDING',
    'METER_ACCOUNTING_MISMATCH', 'METER_RECOVERY_PENDING', 'PZEM_ENERGY_JUMP',
))
_current = ContextVar('device_diagnostic', default=None)
logger = logging.getLogger('meter.device')
# The isolated protocol logger must retain 2xx replies too: a device may reject
# their JSON/command locally. Do not enable global DEBUG or attach request data.
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def request_id(request):
    value = request.headers.get('X-Request-ID', '')
    if not isinstance(value, str) or len(value) != 36:
        return str(uuid.uuid4())
    try:
        parsed = uuid.UUID(value)
        if parsed.version == 4 and str(parsed) == value:
            return value
    except (ValueError, TypeError, AttributeError):
        pass
    return str(uuid.uuid4())  # Never echo/log an arbitrary incoming header.


@contextmanager
def trace_request(request, operation):
    state = {'request_id': request_id(request), 'operation': operation, 'stage': 'handler'}
    token = _current.set(state)
    try:
        yield state
    finally:
        _current.reset(token)


def mark_stage(stage):
    state = _current.get()
    if state is not None:
        state['stage'] = stage if stage in STAGES else 'handler'


def safe_code(data, status):
    value = data.get('code') if isinstance(data, dict) else None
    return str(value) if isinstance(value, str) and value in CODES else f'HTTP_{status}'


def error_stage(code, current):
    fixed = {'REQUEST_INVALID': 'request_validation', 'REQUEST_TOO_LARGE': 'request_validation',
             'DEVICE_BINDING_MISMATCH': 'device_binding', 'DEVICE_SESSION_REQUIRED': 'device_binding',
             'DEVICE_COUNTER_REGRESSION': 'credit_reconciliation', 'DEVICE_BOOT_REPLAY': 'credit_reconciliation',
             'DEVICE_STORAGE_REQUIRED': 'credit_reconciliation', 'DEVICE_STORAGE_RESET': 'credit_reconciliation', 'TOKEN_LOOKUP_MISS': 'token_lookup',
             'TOKEN_AMOUNT_MISMATCH': 'token_amount_validation', 'TOKEN_SOURCE_UNVERIFIED': 'source_eligibility',
             'TOKEN_STORAGE_UNAVAILABLE': 'token_integrity', 'TOKEN_ALREADY_USED': 'already_used_token',
             'PENDING_COMMAND': 'pending_delivery', 'RESERVATION_CONFLICT': 'conflicting_command',
             'RECEIPT_CONFLICT': 'conflicting_command', 'RECEIPT_BINDING_MISMATCH': 'ack_validation',
             'COMMAND_UNAVAILABLE': 'ack_command_lookup', 'AC_LAB_DISABLED': 'hosting_policy',
             'TESTING_OPERATION_UNAVAILABLE': 'hosting_policy'}
    return fixed.get(code, current if current in STAGES else 'handler')


def safe_trace(exc):
    """No exception messages, source text, request object or frame locals."""
    locations = []
    for frame, line in traceback.walk_tb(exc.__traceback__):
        filename = Path(frame.f_code.co_filename).name
        function = frame.f_code.co_name
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]{0,95}\.py', filename):
            filename = 'external'
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,95}', function):
            function = 'external'
        locations.append(f'{filename}:{line}:{function}')
    name = type(exc).__name__
    if name not in {'ValueError', 'KeyError', 'TypeError', 'AttributeError', 'RuntimeError', 'OperationalError', 'ProgrammingError', 'IntegrityError', 'DatabaseError', 'AssertionError'}:
        name = 'Exception'
    return name + ':' + (' > '.join(locations[-16:]) or 'unavailable')


def log_result(state, status, code):
    stage = error_stage(code, state['stage']) if status >= 400 else 'complete'
    if code == 'TOKEN_UNAVAILABLE' and stage == 'token_lookup':
        code = 'TOKEN_LOOKUP_MISS'  # Operator only; public reply stays generic.
    logger.log(logging.ERROR if status >= 500 else logging.WARNING if status >= 400 else logging.INFO,
               'DEVICE request_id=%s operation=%s http=%d stage=%s code=%s%s',
               state['request_id'], state['operation'], status, stage, code,
               ' traceback=' + state['traceback'] if 'traceback' in state else '')


def hosting_rejection(request):
    from django.http import JsonResponse
    operation = request.path.rstrip('/').rsplit('/', 1)[-1]
    if operation not in {'session', 'redeem', 'ack', 'telemetry'}:
        operation = 'handler'
    with trace_request(request, operation) as state:
        mark_stage('hosting_policy')
        response = JsonResponse({'code': 'TESTING_OPERATION_UNAVAILABLE',
                                 'message': 'Device operation unavailable in this hosting profile.',
                                 'request_id': state['request_id']}, status=503)
        response['X-Request-ID'] = state['request_id']
        response['Cache-Control'] = 'private, no-store'
        log_result(state, 503, 'TESTING_OPERATION_UNAVAILABLE')
        return response


def unhandled_response(request, response):
    """Correlate a missing route/proxy-to-Django failure without enabling it."""
    if response.has_header('X-Request-ID'):
        return response
    operation = request.path.rstrip('/').rsplit('/', 1)[-1]
    if operation not in {'session', 'redeem', 'ack', 'telemetry'}:
        operation = 'handler'
    with trace_request(request, operation) as state:
        mark_stage('request_routing' if response.status_code == 404 else 'handler')
        response['X-Request-ID'] = state['request_id']
        response['Cache-Control'] = 'private, no-store'
        log_result(state, response.status_code, f'HTTP_{response.status_code}')
    return response
