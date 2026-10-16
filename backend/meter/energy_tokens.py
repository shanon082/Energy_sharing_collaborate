"""New source-bound keypad tokens. No numeric decoding, legacy balance or I/O."""
import hashlib
import hmac
import re
import secrets
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError, transaction
from django.views.decorators.debug import sensitive_variables
from rest_framework.exceptions import APIException

from meter.models import EnergyAllocation, EnergyKeypadToken


class EnergyTokenError(APIException):
    status_code = 409
    default_code = "ENERGY_TOKEN_UNAVAILABLE"
    default_detail = {"code": "ENERGY_TOKEN_UNAVAILABLE", "message": "Token unavailable; retain the allocation for reconciliation."}


def cipher():
    from cryptography.fernet import Fernet, MultiFernet
    keys = getattr(settings, "ENERGY_TOKEN_ENCRYPTION_KEYS", [])
    if not keys or len(getattr(settings, "ENERGY_TOKEN_LOOKUP_KEY", "")) < 32:
        raise ImproperlyConfigured("Private energy-token encryption/lookup keys are required")
    try:
        return MultiFernet([Fernet(key.encode("ascii")) for key in keys])
    except (ValueError, UnicodeError):
        raise ImproperlyConfigured("Invalid private energy-token key configuration") from None


@sensitive_variables()
def digest_token(value):
    key = getattr(settings, "ENERGY_TOKEN_LOOKUP_KEY", "")
    if len(key) < 32:
        raise ImproperlyConfigured("Private ENERGY_TOKEN_LOOKUP_KEY is required")
    return hmac.new(key.encode(), value.encode("ascii"), hashlib.sha256).hexdigest()


def authorized_source(allocation):
    """Source status, meter/owner and exact source identity must still match."""
    if allocation.purchase_intent_id:
        intent = allocation.purchase_intent
        expected = "UGX_DEMO" if intent.provider == "LOCAL_DEMO" else "SANDBOX" if intent.provider == "MTN_SANDBOX" else "CORE"
        return (intent.status == "SETTLED" and intent.purpose == "PURCHASE"
                and intent.currency == ("EUR" if intent.provider == "MTN_SANDBOX" else "UGX")
                and intent.owner_id == allocation.owner_id and intent.meter_id == allocation.meter_id
                and expected == allocation.accounting_environment)
    if allocation.sandbox_loan_id:
        loan = allocation.sandbox_loan
        expected = "UGX_DEMO" if loan.environment == "UGX_DEMO" else "SANDBOX"
        return (loan.status in {"DISBURSED", "COMPLETED"} and loan.currency == ("UGX" if expected == "UGX_DEMO" else "EUR") and loan.owner_id == allocation.owner_id
                and loan.meter_id == allocation.meter_id and expected == allocation.accounting_environment)
    if allocation.loan_disbursement_id:
        source = allocation.loan_disbursement
        return (source.loan_application.status in {"DISBURSED", "COMPLETED"}
                and source.loan_application.user_id == allocation.owner_id and source.meter_id == allocation.meter_id
                and allocation.accounting_environment == "CORE")
    return False


@sensitive_variables()
def issue_energy_token(allocation):
    """Only called by NEW allocation creation inside its financial transaction.

    Explicit retries recover an existing token; no command backfills old rows.
    The allocation lock serializes token issuance and automatic reservations.
    """
    if getattr(settings, "ENERGY_TOKEN_ISSUANCE_ENABLED", False) is not True:
        return None
    with transaction.atomic():
        allocation = EnergyAllocation.objects.select_for_update().select_related("meter").get(pk=allocation.pk)
        existing = EnergyKeypadToken.objects.filter(allocation=allocation).first()
        if existing:
            return existing
        if (not authorized_source(allocation) or allocation.meter.user_id != allocation.owner_id
                or allocation.meter.is_deleted or allocation.meter.status != "ACTIVE"
                or allocation.deliveries.exists()):
            raise EnergyTokenError()
        wh = allocation.amount_kwh * Decimal("1000")
        if wh != wh.to_integral_value() or not 0 < wh <= 2**63 - 1 or int(wh) % 10:
            raise EnergyTokenError()
        encryption = cipher()
        for _ in range(12):
            value = f"{secrets.randbelow(10**15):015d}"
            try:
                with transaction.atomic():
                    return EnergyKeypadToken.objects.create(allocation=allocation, owner_id=allocation.owner_id,
                        meter=allocation.meter, meter_number=allocation.meter.meter_no,
                        environment=allocation.accounting_environment, amount_wh=int(wh),
                        lookup_digest=digest_token(value), ciphertext=encryption.encrypt(value.encode()).decode("ascii"))
            except IntegrityError:
                # A digest collision retries without poisoning the financial tx.
                # Allocation uniqueness is already serialized by the row lock.
                continue
        raise EnergyTokenError()


@sensitive_variables()
def token_record(token):
    from cryptography.fernet import InvalidToken
    try:
        value = cipher().decrypt(token.ciphertext.encode()).decode("ascii")
    except (InvalidToken, UnicodeError):
        raise EnergyTokenError() from None
    if not re.fullmatch(r"[0-9]{15}", value) or not hmac.compare_digest(digest_token(value), token.lookup_digest):
        raise EnergyTokenError()
    allocation = token.allocation
    reference = (str(allocation.purchase_intent.provider_reference) if allocation.purchase_intent_id else
                 str(allocation.sandbox_loan_id) if allocation.sandbox_loan_id else
                 allocation.loan_disbursement.loan_application.loan_id)
    return {"id": str(token.pk), "allocation_id": allocation.pk, "token": value,
            "meter_number": token.meter_number, "energy_wh": str(token.amount_wh),
            "energy_kwh": str(Decimal(token.amount_wh) / 1000), "environment": token.environment,
            "source": "PURCHASE" if allocation.purchase_intent_id else "LOAN", "source_reference": reference,
            "state": token.state, "application_environment": "SOFTWARE_BENCH" if token.state == "APPLIED" else "UNCONFIRMED",
            "created_at": token.created_at.isoformat()}
