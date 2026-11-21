"""Approved noncash test authorization; never an exchange-rate/production adapter."""
import os
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from backend.feature_config import parse_feature_bool

POLICY = 'UGX-MTN-TEST-AUTH-v1'
PROVIDER_AMOUNT = Decimal('1.00')


def selected():
    return parse_feature_bool(getattr(settings, 'SANDBOX_UGX_AUTHORIZATION_ENABLED',
        os.environ.get('SANDBOX_UGX_AUTHORIZATION_ENABLED', 'false')), name='SANDBOX_UGX_AUTHORIZATION_ENABLED')


def testing_profile():
    return (getattr(settings, 'ALWAYSDATA_TESTING', False) is True
        and getattr(settings, 'CONSUMER_SANDBOX_ENABLED', False) is True)


def enabled():
    return selected() and testing_profile() and getattr(settings, 'PROTOTYPE_PAYMENT_PROVIDER', '') == 'MTN_SANDBOX'


def business_domain():
    """The UGX-only profile keeps reads/amounts in UGX even during a pause."""
    return enabled() or (testing_profile() and getattr(settings, 'PROTOTYPE_PAYMENT_PROVIDER', '') == 'MTN_SANDBOX'
        and getattr(settings, 'SANDBOX_UGX_AUTHORIZATION_REQUIRED', False) is True)


def missing_required_authorization():
    return business_domain() and not enabled()


def validate_configuration():
    if not selected():
        return
    cfg = getattr(settings, 'MTN_SANDBOX_CONFIG', {})
    if (not enabled() or cfg.get('BASE_URL') != 'https://sandbox.momodeveloper.mtn.com'
            or cfg.get('CURRENCY') != 'EUR' or cfg.get('ENVIRONMENT') != 'sandbox'
            or getattr(settings, 'SANDBOX_UGX_AUTHORIZATION_POLICY', POLICY) != POLICY):
        raise ImproperlyConfigured('UGX test authorization requires the alwaysdata consumer sandbox, MTN_SANDBOX/EUR and UGX-MTN-TEST-AUTH-v1; production is forbidden.')


def require_recovery_profile():
    # Old instructions keep their frozen policy after pausing new instructions.
    if not testing_profile():
        from transactions.payment_settlement import PaymentSettlementError
        raise PaymentSettlementError('UGX test authorization cannot settle outside its isolated testing profile.')
