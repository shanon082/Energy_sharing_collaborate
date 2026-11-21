"""UGX instruction support inside the existing MTN settlement transaction.

No provider I/O, FX conversion, independent payment pipeline or credit balance.
"""
import json
from decimal import Decimal
from hashlib import sha256
from backend.ugx_authorization import POLICY, PROVIDER_AMOUNT, require_recovery_profile
from transactions.payment_settlement import PaymentSettlementError
from transactions.sandbox_models import SandboxUGXInstruction, SandboxUGXSettlement

AUTHORIZATION = {'policy': POLICY, 'provider': 'MTN_SANDBOX', 'currency': 'EUR', 'amount': '1.00', 'no_real_money': True}


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def binding(intent, quote, amount):
    return {'policy': POLICY, 'intent_id': intent.pk, 'reference': str(intent.provider_reference),
        'external_id': intent.provider_external_id, 'request_id': str(intent.client_request_id),
        'owner_id': intent.owner_id, 'meter_id': quote.meter_id, 'purpose': intent.purpose,
        'loan_id': str(intent.sandbox_loan_id) if intent.sandbox_loan_id else None,
        'amount': str(amount.quantize(Decimal('1'))), 'currency': 'UGX', 'environment': 'UGX_DEMO',
        'quote_id': str(quote.pk), 'terms_hash': quote.terms_hash, 'terms': quote.terms,
        'provider_authorization': AUTHORIZATION}


def create_instruction(intent, quote, amount, instruction_id):
    snapshot = binding(intent, quote, amount)
    return SandboxUGXInstruction.objects.create(id=instruction_id, intent=intent, quote=quote,
        owner_id=intent.owner_id, meter_id=quote.meter_id, loan_id=intent.sandbox_loan_id,
        amount=amount, purpose=intent.purpose, snapshot=snapshot, snapshot_hash=digest(snapshot))


def instruction_for(intent):
    return getattr(intent, 'ugx_instruction', None)


def validate_instruction(intent):
    require_recovery_profile()
    instruction = instruction_for(intent)
    ctx = intent.sandbox_context or {}
    if instruction is None:
        raise PaymentSettlementError('Missing immutable UGX instruction; reconciliation required.')
    quote = instruction.quote
    if (intent.provider != 'MTN_SANDBOX' or intent.currency != 'EUR' or intent.amount != PROVIDER_AMOUNT
            or instruction.policy_version != POLICY or instruction.currency != 'UGX' or instruction.environment != 'UGX_DEMO'
            or instruction.owner_id != intent.owner_id or instruction.purpose != intent.purpose
            or instruction.loan_id != intent.sandbox_loan_id or instruction.quote_id != intent.sandbox_quote_id
            or instruction.meter_id != quote.meter_id or quote.owner_id != intent.owner_id
            or quote.purpose != intent.purpose or quote.amount != instruction.amount
            or (quote.currency, quote.environment) != ('UGX', 'UGX_DEMO')
            or quote.terms != ctx.get('terms') or digest(quote.terms) != quote.terms_hash
            or ctx.get('authorization_policy') != POLICY or ctx.get('instruction_id') != str(instruction.pk)
            or instruction.snapshot != binding(intent, quote, instruction.amount)
            or digest(instruction.snapshot) != instruction.snapshot_hash):
        raise PaymentSettlementError('UGX test instruction/source binding does not match.')
    if intent.purpose == 'PURCHASE':
        from loan.demo_tariffs import validate_frozen_pricing
        if (intent.meter_id != instruction.meter_id or intent.sandbox_loan_id
                or quote.terms.get('energy_environment') != 'SANDBOX'
                or quote.terms.get('policy', {}).get('authorization') != AUTHORIZATION):
            raise PaymentSettlementError('UGX purchase authorization domain does not match.')
        try:
            valid = validate_frozen_pricing(instruction.amount, quote.terms)
        except (KeyError, TypeError, ValueError, ArithmeticError):
            valid = False
        if not valid:
            raise PaymentSettlementError('Frozen UGX pricing does not reproduce the purchase.')
    elif intent.purpose == 'LOAN_REPAYMENT':
        loan = instruction.loan
        if (intent.meter_id or loan is None or loan.owner_id != intent.owner_id or loan.meter_id != instruction.meter_id
                or (loan.currency, loan.environment) != ('UGX', 'UGX_DEMO')
                or quote.terms.get('loan_id') != str(loan.pk) or quote.terms.get('authorization') != AUTHORIZATION
                or quote.terms.get('loan_terms_hash') != digest(loan.terms)):
            raise PaymentSettlementError('UGX repayment debt/authorization domain does not match.')
    else:
        raise PaymentSettlementError('Unsupported UGX test purpose.')
    return instruction


def apply_business_settlement(intent):
    from django.utils import timezone
    from accounts.models import User
    from loan.models import SandboxLoan
    from loan.sandbox_service import owned_test_meter
    from meter.allocation_service import authorize_purchase_allocation
    from meter.prototype_device import require_mtn_purchase_tokens
    from transactions.models import SandboxSettlement
    instruction = validate_instruction(intent)
    User.objects.select_for_update().get(pk=intent.owner_id)
    # All EUR1 is retained as test evidence, never UGX receipts or energy pricing.
    SandboxSettlement.objects.create(intent=intent, currency='EUR', environment='MTN_SANDBOX',
        received=PROVIDER_AMOUNT, residual=PROVIDER_AMOUNT)
    if intent.purpose == 'PURCHASE':
        owned_test_meter(intent.owner, instruction.meter_id, lock=True)
        terms = instruction.quote.terms
        require_mtn_purchase_tokens(terms, recovery=True)
        SandboxUGXSettlement.objects.create(instruction=instruction, authorized=instruction.amount,
            billed=Decimal(terms['billed']), residual=Decimal(terms['residual']))
        authorize_purchase_allocation(intent, Decimal(terms['energy_kwh']))
        from loan.demo_assessment import refresh_demo_purchase_contribution
        refresh_demo_purchase_contribution(intent.owner, instruction.meter)
    else:
        loan = SandboxLoan.objects.select_for_update().get(pk=instruction.loan_id, owner=intent.owner)
        if loan.status not in {'DISBURSED', 'COMPLETED'}:
            raise PaymentSettlementError('UGX prototype loan is not repayable.')
        applied = min(instruction.amount, loan.outstanding)
        SandboxUGXSettlement.objects.create(instruction=instruction, authorized=instruction.amount,
            applied=applied, excess=instruction.amount-applied)
        if loan.outstanding == 0 and loan.status != 'COMPLETED':
            loan.status = 'COMPLETED'; loan.closed_at = timezone.now()
            loan.save(update_fields=['status', 'closed_at'])


def purchase_source_valid(intent, allocation):
    """Same source proof used for token issuance and commissioned device redemption."""
    try:
        instruction = validate_instruction(intent)
        effect = instruction.business_settlement
        provider = intent.sandbox_settlement
        return (intent.status == 'SETTLED' and intent.purpose == 'PURCHASE'
            and effect.authorized == instruction.amount and effect.billed + effect.residual == instruction.amount
            and provider.currency == 'EUR' and provider.received == PROVIDER_AMOUNT and provider.residual == PROVIDER_AMOUNT
            and allocation.owner_id == instruction.owner_id and allocation.meter_id == instruction.meter_id
            and allocation.accounting_environment == 'SANDBOX'
            and allocation.amount_kwh == Decimal(instruction.quote.terms['energy_kwh']))
    except (PaymentSettlementError, AttributeError, KeyError, TypeError, ValueError, ArithmeticError):
        return False


def business_receipt(intent, base):
    instruction = instruction_for(intent)
    if instruction is None:
        return base
    effect = getattr(instruction, 'business_settlement', None)
    base['provider_receipt'] = {'reference': str(intent.provider_reference), 'external_id': intent.provider_external_id,
        'transaction_id': intent.provider_transaction_id or None, 'amount': str(intent.amount), 'currency': intent.currency,
        'environment': 'MTN_SANDBOX', 'status': intent.status, 'purpose': 'TEST_AUTHORIZATION', 'no_real_money': True}
    base.update(currency='UGX', environment='UGX_DEMO', label='UGX TEST / NO REAL MONEY',
        amount=str(instruction.amount.quantize(Decimal('1'))), instruction_id=str(instruction.pk), authorization_policy=instruction.policy_version,
        billed=str(effect.billed) if effect else None, residual=str(effect.residual) if effect else None,
        applied=str(effect.applied) if effect else None, excess=str(effect.excess) if effect else None)
    return base
