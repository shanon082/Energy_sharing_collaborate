"""Five-minute local checkout expiry; never cancellation of a provider charge.

GET helpers below are pure reads. Expiry and submission serialize on the intent
lock. Successful replacements serialize on the owner and root checkout locks
inside the existing settlement transaction. No provider call holds those locks.
"""
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError
from transactions.models import PaymentIntent, SandboxCheckout

CHECKOUT_SECONDS = 300
SUBMISSION_PROOF = 'PRE_IO_CHECKOUT-v1'
TEST_PROVIDERS = ('LOCAL_DEMO', 'MTN_SANDBOX')


def deadline(intent):
    return intent.initiated_at + timedelta(seconds=CHECKOUT_SECONDS)


def classification(intent):
    if intent.status != 'PENDING':
        return 'TERMINAL_PROVIDER_OUTCOME'
    if intent.provider == 'LOCAL_DEMO':
        return 'LOCAL_SIMULATOR_NOT_COMPLETED'
    if (intent.submission_state == 'NEW' and intent.reconcile_attempts == 0
            and intent.reconcile_lease_id is None and intent.reconcile_lease_until is None
            and (intent.sandbox_context or {}).get('checkout_submission_proof') == SUBMISSION_PROOF):
        return 'NEVER_SUBMITTED'
    if intent.submission_state == 'ACCEPTED':
        return 'SUBMITTED'
    return 'SUBMISSION_UNKNOWN'


def ensure_checkout(intent):
    row, _ = SandboxCheckout.objects.get_or_create(intent=intent)
    return row


def expire_locked(intent, now=None):
    """Caller holds intent lock. A lease/uncertain attempt is NEVER cancelled."""
    now = now or timezone.now()
    if intent.provider not in TEST_PROVIDERS or intent.status != 'PENDING' or now < deadline(intent):
        return None
    checkout = ensure_checkout(intent)
    checkout = SandboxCheckout.objects.select_for_update().get(pk=checkout.pk)
    if checkout.initiation_cancelled_at:
        return checkout
    if checkout.expired_at is None:
        checkout.expired_at = deadline(intent)
        if classification(intent) in {'NEVER_SUBMITTED', 'LOCAL_SIMULATOR_NOT_COMPLETED'}:
            checkout.initiation_cancelled_at = now
            checkout.closure_reason = 'CHECKOUT_EXPIRED_BEFORE_SUBMISSION'
        checkout.save(update_fields=['expired_at', 'initiation_cancelled_at', 'closure_reason'])
    return checkout


def expire_checkout(intent_id):
    from loan.sandbox_service import require_sandbox
    require_sandbox()
    with transaction.atomic():
        intent = PaymentIntent.objects.select_for_update().get(pk=intent_id, provider__in=TEST_PROVIDERS)
        return expire_locked(intent)


def overdue_checkouts():
    from django.db.models import Q
    return PaymentIntent.objects.filter(provider__in=TEST_PROVIDERS, status='PENDING',
        initiated_at__lte=timezone.now()-timedelta(seconds=CHECKOUT_SECONDS)).filter(
        Q(checkout__isnull=True) | Q(checkout__expired_at__isnull=True)).order_by('initiated_at', 'pk')


def expire_due_checkouts(limit=20, stop_before=None):
    import time
    ids = list(overdue_checkouts().values_list('pk', flat=True)[:limit])
    completed = []
    for pk in ids:
        if stop_before is not None and time.monotonic() >= stop_before:
            break
        expire_checkout(pk)
        completed.append(pk)
    return completed


def checkout_info(intent):
    """Server-time presentation, without creating metadata or settling on GET."""
    now = timezone.now()
    checkout = getattr(intent, 'checkout', None)
    root = (checkout.root if checkout and checkout.root_id else checkout)
    expired = bool((checkout and checkout.expired_at) or (intent.status == 'PENDING' and now >= deadline(intent)))
    cancelled = bool(checkout and checkout.initiation_cancelled_at)
    winner = root.fulfilled_by if root and root.fulfilled_by_id else None
    additional = bool(intent.status == 'SETTLED' and winner and winner.pk != intent.pk)
    replaced = bool(checkout and SandboxCheckout.objects.filter(replaces=checkout).exists())
    mapped = bool((intent.sandbox_context or {}).get('authorization_policy') == 'UGX-MTN-TEST-AUTH-v1')
    return {'expires_at': deadline(intent).isoformat(), 'expired': expired,
        'state': 'LOCAL_INITIATION_CANCELLED' if cancelled else 'EXPIRED' if expired else 'OPEN',
        'classification': classification(intent), 'provider_cancelled': False,
        'operation_reference': str(root.intent.provider_reference) if root else str(intent.provider_reference),
        'replaces_reference': str(checkout.replaces.intent.provider_reference) if checkout and checkout.replaces_id else None,
        'fulfilled_reference': str(winner.provider_reference) if winner else None,
        'business_effect': 'ADDITIONAL_AUTHORIZATION_REVIEW' if additional else 'FULFILLED' if intent.status == 'SETTLED' else 'NONE',
        'retry_available': mapped and expired and intent.status == 'PENDING' and not replaced and not winner,
        'message': 'Additional successful test authorization retained for review; this operation was already fulfilled. No second financial effect.' if additional else
            'This operation was fulfilled by another attempt. This unsubmitted replacement was closed locally.' if cancelled and checkout.closure_reason == 'OPERATION_ALREADY_FULFILLED' else
            'Checkout expired before submission. No provider request was sent.' if cancelled and intent.status == 'PENDING' else
            'Request timed out; payment confirmation is still being checked.' if expired and intent.status == 'PENDING' else
            'Waiting for the confirmed payment outcome.' if intent.status == 'PENDING' else 'Provider outcome recorded.'}


def payment_conflicts(owner, *, purpose, meter_id=None, loan_id=None):
    """No account-wide payment lock; unrelated lending/purchases stay independent."""
    rows = PaymentIntent.objects.filter(owner=owner, provider__in=TEST_PROVIDERS, status='PENDING', purpose=purpose)
    if purpose == 'PURCHASE':
        rows = rows.filter(meter_id=meter_id)
    else:
        rows = rows.filter(sandbox_loan_id=loan_id)
    for row in rows:
        info = checkout_info(row)
        if info['fulfilled_reference'] or info['state'] == 'LOCAL_INITIATION_CANCELLED' and not (row.sandbox_context or {}).get('authorization_policy'):
            continue
        if not info['expired']:
            raise ValidationError({'code': 'PAYMENT_PENDING_RECONCILIATION', 'message': 'This operation has an open checkout. Check its existing reference.', 'reference': str(row.provider_reference)})
        if info['retry_available'] or ((row.sandbox_context or {}).get('authorization_policy') and not info['fulfilled_reference']):
            raise ValidationError({'code': 'CHECKOUT_REPLACEMENT_REQUIRED', 'message': 'Explicitly retry the expired checkout; the earlier reference remains under review.', 'reference': str(row.provider_reference)})


def close_unsubmitted_replacement_locked(intent):
    """Intent lock held, before reserving provider I/O. Never close uncertain sends."""
    checkout = getattr(intent, 'checkout', None)
    if not checkout or not checkout.root_id or classification(intent) != 'NEVER_SUBMITTED':
        return False
    from accounts.models import User
    User.objects.select_for_update().get(pk=intent.owner_id)
    root = SandboxCheckout.objects.select_for_update().get(pk=checkout.root_id)
    if not root.fulfilled_by_id:
        return False
    checkout.initiation_cancelled_at = timezone.now()
    checkout.closure_reason = 'OPERATION_ALREADY_FULFILLED'
    checkout.save(update_fields=['initiation_cancelled_at', 'closure_reason'])
    return True


def retry_checkout(owner, reference, data):
    """Explicit new authorization, same frozen operation. Never auto-recharge."""
    from backend.ugx_authorization import enabled, require_recovery_profile
    from backend.demo_config import require_mtn_sandbox
    from accounts.models import User
    from loan.models import SandboxQuote
    from loan.sandbox_service import verified_consumer, owned_test_meter, request_uuid
    from transactions.ugx_authorization import validate_instruction, create_instruction
    from mtn_momo.sandbox import MTNSandbox
    import uuid
    require_recovery_profile()
    if not enabled():
        raise ValidationError({'code': 'CHECKOUT_RETRY_UNAVAILABLE', 'message': 'Sandbox UGX test authorization is disabled.'})
    require_mtn_sandbox()
    MTNSandbox()  # configuration only, no external I/O
    if set(data) != {'client_request_id', 'accept_test_terms'} or data.get('accept_test_terms') is not True:
        raise ValidationError({'code': 'CHECKOUT_RETRY_CONSENT_REQUIRED', 'message': 'Explicitly accept a new test authorization while the earlier attempt remains under review.'})
    key = request_uuid(data.get('client_request_id'))
    original = PaymentIntent.objects.filter(owner=owner, provider='MTN_SANDBOX', provider_reference=reference).first()
    if not original:
        raise NotFound('Sandbox checkout not found.')
    expire_checkout(original.pk)
    with transaction.atomic():
        User.objects.select_for_update().get(pk=owner.pk)
        verified_consumer(owner)
        checkout = ensure_checkout(original)
        root_id = checkout.root_id or checkout.pk
        root = SandboxCheckout.objects.select_for_update().get(pk=root_id)
        prior = PaymentIntent.objects.filter(client_request_id=key).first()
        if prior:
            prior_checkout = getattr(prior, 'checkout', None)
            if prior.owner_id != owner.pk or not prior_checkout or prior_checkout.replaces_id != checkout.pk:
                raise ValidationError({'code': 'REQUEST_ID_CONFLICT'})
            return prior, False
        original.refresh_from_db()
        if not checkout.expired_at or (original.status not in {'PENDING', 'FAILED'} and not root.fulfilled_by_id):
            raise ValidationError({'code': 'CHECKOUT_RETRY_UNAVAILABLE', 'message': 'The checkout has not expired or its operation is already resolved. Refresh its receipt.'})
        existing = SandboxCheckout.objects.filter(replaces=checkout).first()
        if existing:
            raise ValidationError({'code': 'CHECKOUT_ALREADY_REPLACED', 'message': 'A replacement already exists. Recover its stored status.', 'reference': str(existing.intent.provider_reference)})
        source = validate_instruction(original)
        if root.fulfilled_by_id:
            # A late original success may win between display and explicit retry.
            # Persist a closed, never-submitted attempt for this request ID so
            # lost-response recovery cannot leave a phantom retry handle forever.
            pass
        elif original.purpose == 'PURCHASE':
            owned_test_meter(owner, source.meter_id, lock=True)
        elif source.loan.status != 'DISBURSED' or source.loan.outstanding <= 0:
            raise ValidationError({'code': 'LOAN_ALREADY_CLOSED', 'message': 'The loan has no repayable debt. Earlier provider outcomes remain under review.'})
        # Copy accepted immutable terms, not today's tariff or an expired new quote.
        quote = SandboxQuote.objects.create(owner=owner, meter_id=source.meter_id, purpose=source.purpose,
            amount=source.amount, currency=source.currency, environment=source.environment,
            terms=source.quote.terms, terms_hash=source.quote.terms_hash, expires_at=source.quote.expires_at)
        ref = uuid.uuid4(); instruction_id = uuid.uuid4(); now = timezone.now()
        context = {**original.sandbox_context, 'instruction_id': str(instruction_id), 'replaces_reference': str(reference),
            'operation_reference': str(root.intent.provider_reference), 'retry_consent_at': now.isoformat(),
            'checkout_submission_proof': SUBMISSION_PROOF}
        intent = PaymentIntent.objects.create(owner=owner, purpose=original.purpose, amount=original.amount,
            currency=original.currency, provider=original.provider, provider_reference=ref,
            provider_external_id=f'sandbox-{original.purpose.lower()}-{ref}', client_request_id=key,
            sandbox_quote=quote, meter_id=original.meter_id, sandbox_loan_id=original.sandbox_loan_id,
            sandbox_context=context, initiated_at=now, reconcile_after=now, submission_state='NEW')
        create_instruction(intent, quote, source.amount, instruction_id)
        SandboxCheckout.objects.create(intent=intent, root=root, replaces=checkout,
            initiation_cancelled_at=now if root.fulfilled_by_id else None,
            closure_reason='OPERATION_ALREADY_FULFILLED' if root.fulfilled_by_id else '')
        return intent, True
