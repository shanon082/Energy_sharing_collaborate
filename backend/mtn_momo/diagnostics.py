"""Strictly allowlisted diagnostics: never pass provider text or exception reprs."""
import logging

logger = logging.getLogger(__name__)
PROVIDER_CODES = frozenset({
    'PAYER_NOT_FOUND', 'PAYEE_NOT_FOUND', 'NOT_ALLOWED', 'NOT_ALLOWED_TARGET_ENVIRONMENT',
    'INVALID_CURRENCY', 'RESOURCE_NOT_FOUND', 'RESOURCE_ALREADY_EXIST',
    'INTERNAL_PROCESSING_ERROR', 'SERVICE_UNAVAILABLE', 'COULD_NOT_PERFORM_TRANSACTION',
    'TRANSACTION_CANCELED', 'TRANSACTION_CANCELLED', 'TRANSACTION_EXPIRED',
    'TRANSACTION_REJECTED', 'PAYER_LIMIT_REACHED', 'PAYEE_LIMIT_REACHED',
    'NOT_ENOUGH_FUNDS', 'INVALID_CALLBACK_URL_HOST', 'APPROVAL_REJECTED',
})


def provider_code(data):
    if not isinstance(data, dict):
        return 'UNRECOGNIZED'
    reason = data.get('reason', data)
    value = reason.get('code') if isinstance(reason, dict) else reason
    return value if isinstance(value, str) and value in PROVIDER_CODES else 'UNRECOGNIZED'


def diagnostic(stage, *, http_status=None, status='UNKNOWN', code='NONE'):
    # All callers supply local literal stage/code strings, never provider messages.
    return {'stage': stage, 'http_status': http_status, 'provider_status': status, 'code': code}


def record(intent, item):
    logger.warning('mtn_sandbox intent_id=%s reference=%s stage=%s http_status=%s provider_status=%s code=%s',
                   intent.pk, intent.provider_reference, item['stage'], item['http_status'],
                   item['provider_status'], item['code'])


def test_scenario(value):
    """Official RequestToPay scenarios; return a label, never the payer number."""
    if not isinstance(value, str) or not value.isascii() or not value.isdigit() or not 10 <= len(value) <= 15:
        return 'UNAVAILABLE'
    scenarios = ['FAILED', 'REJECTED', 'EXPIRED', 'ONGOING', 'DELAYED', 'PAYER_NOT_FOUND',
                 'PAYEE_NOT_ALLOWED', 'NOT_ALLOWED', 'WRONG_ENVIRONMENT', 'INVALID_CALLBACK',
                 'INVALID_CURRENCY', 'INTERNAL_ERROR', 'SERVICE_UNAVAILABLE', 'CANNOT_PERFORM',
                 'UNKNOWN_TRANSFER_TYPE']
    return dict(zip((str(46733123450 + i) for i in range(len(scenarios))), scenarios)).get(value, 'ORDINARY_SUCCESS')
