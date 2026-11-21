"""UGX prototype lending, separate from MTN's EUR payment domain."""
from copy import deepcopy
from django.conf import settings
from rest_framework.exceptions import ValidationError
from backend.demo_config import provider_mode, demo_configuration

CONTRACT = 'UGX-PROTOTYPE-SANDBOX-v1'
REPAYMENT_MESSAGE = 'UGX debt cannot be repaid with EUR MTN sandbox payments. No repayment mapping is approved; this prototype obligation remains recorded.'


def enabled():
    return (getattr(settings, 'CONSUMER_SANDBOX_ENABLED', False) is True
            and getattr(settings, 'ALWAYSDATA_TESTING', False) is True
            and getattr(settings, 'SANDBOX_UGX_LOANS_ENABLED', False) is True
            and provider_mode() == 'MTN_SANDBOX')


def automatic_assessment_enabled():
    return getattr(settings, 'CONSUMER_SANDBOX_ENABLED', False) is True and (provider_mode() == 'LOCAL_DEMO' or enabled())


def assessment_policy():
    return getattr(settings, 'DEMO_POLICY', None) or demo_configuration({})[1]


def lending_policy():
    from loan.sandbox_service import policy
    if not enabled():
        return policy()
    cfg = deepcopy(assessment_policy())
    cfg.update(id='DEMO-UGX-ACLAB-v1', assessment_policy_id=cfg['id'],
               lending_contract=CONTRACT, energy_environment='SANDBOX',
               label='UGX PROTOTYPE LOAN / SIMULATED ASSESSMENT',
               repayment_mapping='UNAVAILABLE', repayment_message=REPAYMENT_MESSAGE)
    from backend.ugx_authorization import enabled as authorization_enabled, POLICY
    if authorization_enabled():
        cfg.update(repayment_mapping=POLICY, repayment_message='Test repayment—no real money. A fixed EUR1 MTN sandbox authorization is recorded separately; it is not an exchange rate.')
    from backend.ugx_authorization import missing_required_authorization
    if missing_required_authorization():
        cfg['repayment_message'] = 'UGX test repayment authorization is disabled by server configuration.'
    return cfg


def lending_domain():
    from backend.demo_config import test_domain
    return ('UGX', 'UGX_DEMO') if enabled() else test_domain()[:2]


def is_lab_terms(terms):
    return isinstance(terms, dict) and isinstance(terms.get('policy'), dict) and terms['policy'].get('lending_contract') == CONTRACT


def loan_energy_environment(loan):
    """Frozen source authorization, never a current-setting currency conversion."""
    legacy = 'UGX_DEMO' if (loan.currency, loan.environment) == ('UGX', 'UGX_DEMO') else 'SANDBOX'
    terms = loan.terms or {}
    if not is_lab_terms(terms):
        return legacy if 'energy_environment' not in terms else None
    quote = loan.quote
    cfg = terms['policy']
    if ((loan.currency, loan.environment) != ('UGX', 'UGX_DEMO') or cfg.get('currency') != 'UGX'
            or cfg.get('environment') != 'UGX_DEMO' or cfg.get('id') != 'DEMO-UGX-ACLAB-v1'
            or cfg.get('energy_environment') != 'SANDBOX' or terms.get('energy_environment') != 'SANDBOX'
            or quote.purpose != 'LOAN' or terms.get('purpose') != 'LOAN'
            or quote.terms != terms or quote.owner_id != loan.owner_id or quote.meter_id != loan.meter_id
            or (quote.currency, quote.environment) != ('UGX', 'UGX_DEMO') or quote.amount != loan.principal):
        return None
    try:
        import json
        from hashlib import sha256
        from loan.demo_tariffs import validate_frozen_pricing
        if quote.terms_hash != sha256(json.dumps(terms, sort_keys=True, separators=(',', ':')).encode()).hexdigest() or not validate_frozen_pricing(loan.principal, terms):
            return None
    except (KeyError, TypeError, ValueError, ArithmeticError, ValidationError):
        return None
    return 'SANDBOX'


def require_lab_tokens(terms=None):
    from meter.prototype_device import require_mtn_purchase_tokens
    from transactions.payment_settlement import PaymentSettlementError
    try:
        require_mtn_purchase_tokens(terms, recovery=True)
    except PaymentSettlementError:
        raise ValidationError({'code': 'TOKEN_SERVICE_UNAVAILABLE', 'message': 'Prototype loan token service unavailable; no loan or energy was issued.'}) from None


def ugx_assessment(owner, meter_id=None):
    from loan.sandbox_service import owned_test_meter
    from loan.demo_assessment import stored_demo_eligibility
    meter = owned_test_meter(owner, meter_id) if meter_id is not None else None
    from backend.ugx_authorization import enabled as authorization_enabled
    result = stored_demo_eligibility(owner, assessment_policy(), meter)
    return {**result, 'policy_id': lending_policy()['id'], 'assessment_policy_id': result['policy_id'],
            'energy_environment': 'SANDBOX', 'lending_contract': CONTRACT,
            'repayment_available': authorization_enabled(), 'repayment_message': lending_policy()['repayment_message']}
