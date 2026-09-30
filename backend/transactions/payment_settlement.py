"""Provider-verified settlement for new purchases and self-repayments.

Provider I/O occurs before the atomic section. Historical payments without an
intent are deliberately not inferred or replayed here.
"""

from decimal import Decimal, InvalidOperation
import uuid
from urllib.parse import urlparse

from django.conf import settings
from django.db import transaction as db_transaction
from django.db import IntegrityError
from django.utils import timezone

from accounts.models import User
from loan.models import LoanApplication, LoanRepayment
from meter.allocation_service import authorize_purchase_allocation, quantize_source_kwh
from meter.models import Meter
from meter.models import Transaction as MeterLedgerTransaction
from mtn_momo.services import MTNMoMoService
from transactions.models import PaymentIntent, TransactionType, UnitTransaction
from transactions.services import record_transaction_log
from utils.billing import (
    FALLBACK_ENERGY_RATE, VAT_RATE, calculate_units_from_payment,
    get_active_domestic_tariff, get_monthly_units_consumed, is_lifeline_eligible,
)
from wallet.models import UnitBalance


class PaymentSettlementError(Exception):
    pass


def require_real_ugx_provider():
    cfg = getattr(settings, "MTN_MOMO_CONFIG", {})
    endpoint = urlparse(str(cfg.get("BASE_URL") or ""))
    if (cfg.get("ENVIRONMENT") != "production" or
            getattr(settings, "MTN_USE_SIMULATED_PAYMENTS", True) or
            endpoint.scheme != "https" or not endpoint.hostname or
            "sandbox" in endpoint.hostname.lower() or
            not all(cfg.get(key) for key in ("SUBSCRIPTION_KEY", "API_USER_ID", "API_KEY"))):
        raise PaymentSettlementError(
            "Verified UGX Mobile Money payments are unavailable in this environment."
        )


def create_purchase_intent(*, owner, meter, transaction, amount, reference):
    if meter.user_id != owner.pk or transaction.wallet.user_id != owner.pk:
        raise PaymentSettlementError("Purchase owner and meter must match.")
    try:
        amount = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError):
        raise PaymentSettlementError("Purchase amount must be positive whole UGX.") from None
    if not amount.is_finite() or amount <= 0 or amount != amount.to_integral_value():
        raise PaymentSettlementError("Purchase amount must be positive whole UGX.")
    intent = PaymentIntent.objects.create(
        owner=owner, purpose=PaymentIntent.PURCHASE, amount=amount,
        currency="UGX", provider="MTN_PRODUCTION", provider_reference=reference,
        provider_external_id=f"gpawa-purchase-{reference}",
        purchase=transaction, meter=meter,
    )
    return intent


def create_repayment_intent(*, owner, repayment):
    if repayment.loan.user_id != owner.pk or repayment.payment_status != "PENDING":
        raise PaymentSettlementError("Repayment owner or state is invalid.")
    if repayment.amount_paid <= 0 or repayment.amount_paid != repayment.amount_paid.to_integral_value():
        raise PaymentSettlementError("Repayment amount must be positive whole UGX.")
    reference = uuid.uuid4()
    return PaymentIntent.objects.create(
        owner=owner, purpose=PaymentIntent.LOAN_REPAYMENT,
        amount=repayment.amount_paid, currency="UGX", provider="MTN_PRODUCTION",
        provider_reference=reference,
        provider_external_id=f"gpawa-repayment-{reference}", repayment=repayment,
    )


def request_payment(intent, phone_number):
    require_real_ugx_provider()
    return MTNMoMoService().request_payment(
        amount=intent.amount, phone_number=phone_number,
        reference_id=str(intent.provider_reference),
        external_id=intent.provider_external_id,
        payer_message="gPawa electricity payment",
    )


def _validate_evidence(intent, evidence):
    if intent.provider != "MTN_PRODUCTION" or evidence.get("provider") != "MTN_PRODUCTION":
        raise PaymentSettlementError("Payment provider mode does not match.")
    if str(evidence.get("reference_id") or "") != str(intent.provider_reference):
        raise PaymentSettlementError("Provider reference does not match.")
    if str(evidence.get("external_id") or "") != intent.provider_external_id:
        raise PaymentSettlementError("Payment purpose/reference does not match.")
    if evidence.get("currency") != intent.currency or intent.currency != "UGX":
        raise PaymentSettlementError("Payment currency does not match.")
    try:
        observed_amount = Decimal(str(evidence.get("amount")))
    except (InvalidOperation, TypeError, ValueError):
        raise PaymentSettlementError("Provider amount is missing or invalid.") from None
    if observed_amount != intent.amount:
        raise PaymentSettlementError("Provider amount does not match.")
    if intent.purpose == PaymentIntent.PURCHASE:
        if not intent.purchase_id or intent.repayment_id or not intent.meter_id:
            raise PaymentSettlementError("Purchase binding is invalid.")
    elif intent.purpose == PaymentIntent.LOAN_REPAYMENT:
        if not intent.repayment_id or intent.purchase_id or intent.meter_id:
            raise PaymentSettlementError("Repayment binding is invalid.")
    else:
        raise PaymentSettlementError("Unknown payment purpose.")
    if evidence.get("status") == "SUCCESS" and not str(evidence.get("transaction_id") or "").strip():
        raise PaymentSettlementError("Provider transaction identity is missing.")


def _settle_purchase(intent):
    purchase = intent.purchase
    # Monthly purchase bands are per consumer, even when their payments target
    # different meters. Serialize pricing before reading prior allocations.
    User.objects.select_for_update().get(pk=intent.owner_id)
    meter = Meter.objects.select_for_update().get(pk=intent.meter_id)
    if (purchase.wallet.user_id != intent.owner_id or meter.user_id != intent.owner_id or
            purchase.status != "PENDING" or purchase.amount != intent.amount or
            str(purchase.transaction_reference) != str(intent.provider_reference)):
        raise PaymentSettlementError("Purchase allocation does not match payment.")

    month_date = timezone.localdate()
    tariff = get_active_domestic_tariff(month_date)
    prior_units = get_monthly_units_consumed(intent.owner, month_date)
    lifeline_eligible = is_lifeline_eligible(intent.owner)
    units, bill = calculate_units_from_payment(
        intent.amount, intent.owner, tariff=tariff, month_date=month_date,
        apply_deductions=False,
    )
    units = quantize_source_kwh(units) if units > 0 else Decimal("0.00")
    billed = bill.total if units > 0 else Decimal("0.00")
    residual = intent.amount - billed
    if residual < 0:
        raise PaymentSettlementError("Calculated bill exceeds verified receipt.")
    intent.purchase_billed_ugx = billed
    intent.purchase_residual_ugx = residual
    intent.purchase_calculation = {
        "version": 1, "pricing_date": month_date.isoformat(),
        "tariff_id": tariff.pk if tariff else None,
        "tariff_code": tariff.tariff_code if tariff else None,
        "tariff_service_charge_ugx": str(tariff.service_charge) if tariff else None,
        "tariff_blocks": [
            {"order": block.block_order, "min_kwh": str(block.min_units),
             "max_kwh": str(block.max_units) if block.max_units is not None else None,
             "rate_ugx_per_kwh": str(block.rate_per_unit),
             "non_lifeline_rate_ugx_per_kwh": str(block.non_lifeline_rate) if block.non_lifeline_rate is not None else None,
             "is_lifeline": block.is_lifeline_block}
            for block in tariff.blocks.order_by("block_order")
        ] if tariff else [],
        "fallback_rate_ugx_per_kwh": str(FALLBACK_ENERGY_RATE),
        "vat_rate": str(VAT_RATE),
        "prior_monthly_purchases_kwh": str(prior_units),
        "lifeline_eligible": lifeline_eligible,
        "units_kwh": str(units), "energy_cost_ugx": str(bill.energy_cost if units > 0 else Decimal("0.00")),
        "service_charge_ugx": str(bill.service_charge if units > 0 else Decimal("0.00")),
        "vat_ugx": str(bill.vat if units > 0 else Decimal("0.00")),
        "billed_ugx": str(billed), "residual_ugx": str(residual),
        "rounding": "UGX 0.01 half-even; energy 0.01 kWh downward",
    }
    intent.save(update_fields=["purchase_billed_ugx", "purchase_residual_ugx", "purchase_calculation"])
    if units > 0:
        balance, _ = UnitBalance.objects.select_for_update().get_or_create(user=intent.owner)
        balance.add_units(units, description="Verified electricity purchase", reference=str(intent.provider_reference))
        authorize_purchase_allocation(intent, units)
    purchase.status = "COMPLETED"
    purchase.message = (
        "Verified payment received; no energy allocated; reconcile full amount"
        if units <= 0 else "Verified Mobile Money electricity purchase"
    )
    purchase.save(update_fields=["status", "message"])
    if units > 0:
        UnitTransaction.objects.create(
            sender=intent.owner, receiver=intent.owner, units=float(units), meter=meter,
            direction="IN", status="COMPLETED", message="Verified purchase to unit balance",
        )
        MeterLedgerTransaction.objects.create(
            user=intent.owner, meter=meter,
            transaction_type=MeterLedgerTransaction.TYPE_PURCHASE,
            amount_kwh=units, amount_ugx=billed,
            status=MeterLedgerTransaction.STATUS_COMPLETED,
            channel=MeterLedgerTransaction.CHANNEL_WEB,
            payment_reference=str(intent.provider_reference),
            source="verified_mobile_money", destination=meter.meter_no,
        )
    record_transaction_log(
        intent.owner, TransactionType.UNIT_PURCHASE,
        amount=intent.amount, units=units,
        status="COMPLETED" if units > 0 else "RECONCILE",
        reference_id=str(intent.provider_reference),
        details={"meter_no": meter.meter_no, "payment_intent_id": intent.pk,
                 "billed_ugx": str(billed), "residual_ugx": str(residual)},
    )


def _settle_repayment(intent):
    repayment = LoanRepayment.objects.select_for_update().get(pk=intent.repayment_id)
    loan = LoanApplication.objects.select_for_update().get(pk=repayment.loan_id)
    if (loan.user_id != intent.owner_id or repayment.payment_status != "PENDING" or
            repayment.amount_paid != intent.amount or
            loan.status not in {"DISBURSED", "DEFAULTED", "COMPLETED"}):
        raise PaymentSettlementError("Repayment does not match an active owned loan.")
    # Distinct pending requests may both be paid. Keep all provider-confirmed
    # money visible even if an earlier settlement extinguished this debt.
    applied = min(intent.amount, loan.outstanding_balance)
    excess = intent.amount - applied
    # A repayment reduces debt. It does not create energy or send a device command.
    repayment.payment_status = "SUCCESS"
    repayment.amount_applied_ugx = applied
    repayment.excess_ugx = excess
    repayment.units_paid = 0
    repayment.momo_transaction_id = intent.provider_transaction_id
    repayment.save(update_fields=["payment_status", "amount_applied_ugx", "excess_ugx", "units_paid", "momo_transaction_id"])
    record_transaction_log(
        intent.owner, TransactionType.LOAN_REPAYMENT,
        amount=intent.amount, units=0, status="COMPLETED",
        reference_id=str(intent.provider_reference),
        details={"loan_id": loan.loan_id, "payment_intent_id": intent.pk,
                 "applied_ugx": str(applied), "excess_ugx": str(excess)},
    )
    if loan.status != "COMPLETED" and loan.outstanding_balance <= 0:
        loan.status = "COMPLETED"
        loan.save(update_fields=["status", "updated_at"])


def settle_from_provider_evidence(intent_id, evidence):
    """Apply one effect under a row lock; never accepts client-submitted evidence."""
    if evidence.get("status") not in {"SUCCESS", "PENDING", "FAILED", "UNKNOWN"}:
        raise PaymentSettlementError("Unknown provider status.")
    try:
        return _settle_locked(intent_id, evidence)
    except IntegrityError as exc:
        raise PaymentSettlementError("Provider transaction or allocation identity was already used.") from exc


def _settle_locked(intent_id, evidence):
    with db_transaction.atomic():
        intent = PaymentIntent.objects.select_for_update().get(pk=intent_id)
        if intent.status == PaymentIntent.SETTLED:
            return intent, False
        if intent.status == PaymentIntent.FAILED:
            return intent, False
        if evidence["status"] in {"PENDING", "UNKNOWN"}:
            return intent, False
        _validate_evidence(intent, evidence)
        if evidence["status"] == "FAILED":
            intent.status = PaymentIntent.FAILED
            intent.save(update_fields=["status"])
            if intent.purchase_id:
                intent.purchase.status = "FAILED"
                intent.purchase.save(update_fields=["status"])
            else:
                intent.repayment.payment_status = "FAILED"
                intent.repayment.save(update_fields=["payment_status"])
            return intent, False
        provider_transaction_id = str(evidence.get("transaction_id") or "").strip()
        if PaymentIntent.objects.filter(
            provider=intent.provider, provider_transaction_id=provider_transaction_id,
        ).exclude(pk=intent.pk).exists():
            raise PaymentSettlementError("Provider transaction was already used for another payment.")
        intent.provider_transaction_id = provider_transaction_id
        intent.status = PaymentIntent.SETTLED
        intent.save(update_fields=["status", "provider_transaction_id"])
        if intent.purpose == PaymentIntent.PURCHASE:
            _settle_purchase(intent)
        else:
            _settle_repayment(intent)
        intent.settled_at = timezone.now()
        intent.save(update_fields=["settled_at"])
        return intent, True


def reconcile_payment(intent_id):
    intent = PaymentIntent.objects.get(pk=intent_id)
    if intent.status != PaymentIntent.PENDING:
        return intent, False
    if intent.provider != "MTN_PRODUCTION":
        raise PaymentSettlementError("Simulation cannot settle real-provider records.")
    require_real_ugx_provider()
    # Provider network I/O is outside every database-locking transaction.
    evidence = MTNMoMoService().get_payment_status(str(intent.provider_reference))
    return settle_from_provider_evidence(intent.pk, evidence)
