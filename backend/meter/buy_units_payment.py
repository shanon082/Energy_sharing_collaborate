import logging
from decimal import Decimal, InvalidOperation

from django.db import transaction as db_transaction

from loan.models import LoanRepayment
from loan.services import get_disbursed_loan_balances
from meter.models import Meter
from meter.models import Transaction as MeterLedgerTransaction
from meter.models import generate_random_string
from transactions.models import Transaction, TransactionType, UnitTransaction
from transactions.services import record_transaction_log
from utils.billing import calculate_units_from_payment, get_active_domestic_tariff
from wallet.models import Wallet as UnitWallet

logger = logging.getLogger(__name__)


def _calculate_units_from_tariff(amount, user):
  tariff = get_active_domestic_tariff()
  if user is None:
    fallback_rate = Decimal("756.2")
    return (Decimal(str(amount)) / fallback_rate).quantize(Decimal("0.01")), None
  units, _breakdown = calculate_units_from_payment(
    Decimal(str(amount)),
    user,
    tariff=tariff,
    apply_deductions=False,
  )
  return units, tariff


def _apply_auto_loan_repayment(user, payment_amount, channel="WEB_PORTAL"):
  remaining = Decimal(str(payment_amount))
  total_repaid = Decimal("0")
  loans_with_balance, _ = get_disbursed_loan_balances(user)

  for loan, outstanding in loans_with_balance:
    if remaining <= 0:
      break
    paid = min(remaining, outstanding)
    payment_ref = generate_random_string(12)
    LoanRepayment.objects.create(
      loan=loan,
      amount_paid=paid,
      units_paid=0,
      payment_reference=payment_ref,
      is_on_time=True,
      payment_method="MOBILE_MONEY",
      payment_status="SUCCESS",
    )
    record_transaction_log(
      user,
      TransactionType.LOAN_REPAYMENT,
      amount=paid,
      status="COMPLETED",
      reference_id=payment_ref,
      details={
        "channel": channel,
        "loan_id": loan.loan_id,
        "auto_from_purchase": True,
        "payment_method": "MOBILE_MONEY",
      },
    )
    remaining -= paid
    total_repaid += paid
    loan.refresh_from_db()
    if loan.outstanding_balance <= 0:
      loan.status = "COMPLETED"
      loan.save()

  return remaining, total_repaid


def _detect_channel(transaction: Transaction) -> str:
  message = (transaction.message or "").upper()
  if "USSD" in message:
    return "USSD"
  return MeterLedgerTransaction.CHANNEL_WEB


def complete_buy_units_payment(user, amount_decimal, transaction_id, meter_id, channel=None):
  """
  Credit unit wallet after a successful payment. Safe to call once; skips if already COMPLETED.
  Returns (success: bool, units_purchased: Decimal, error: str|None).
  """
  try:
    amount_decimal = Decimal(str(amount_decimal))
  except (InvalidOperation, TypeError, ValueError):
    return False, Decimal("0"), "Invalid amount"

  try:
    with db_transaction.atomic():
      transaction = Transaction.objects.select_for_update().get(id=transaction_id)
      if transaction.status == "COMPLETED":
        unit_tx = UnitTransaction.objects.filter(
          sender=user,
          receiver=user,
          direction="IN",
          status="COMPLETED",
          create_date__gte=transaction.create_date,
        ).order_by("-create_date").first()
        return True, Decimal(str(unit_tx.units if unit_tx else 0)), None

      meter = Meter.objects.get(id=meter_id, user=user)
      payment_channel = channel or _detect_channel(transaction)
      amount_for_units, repaid_to_loans = _apply_auto_loan_repayment(
        user, amount_decimal, channel=payment_channel
      )
      units_purchased, tariff = _calculate_units_from_tariff(amount_for_units, user)

      unit_wallet, _ = UnitWallet.objects.get_or_create(user=user)
      unit_wallet.balance += units_purchased
      unit_wallet.save()

      transaction.status = "COMPLETED"
      transaction.message = (
        f"Buy units - {amount_decimal} UGX | Loan repaid: {repaid_to_loans} UGX | "
        f"Units to wallet: {units_purchased} | Tariff: {tariff.tariff_code if tariff else 'DEFAULT_500'}"
      )
      transaction.save()

      if user.email:
        from accounts.tasks import handle_send_payment_receipt_email
        from utils.general import dispatch_task

        dispatch_task(
          handle_send_payment_receipt_email,
          user.id,
          float(amount_decimal),
          float(units_purchased),
          transaction.id,
          transaction.transaction_reference or "",
        )

      if units_purchased > 0:
        UnitTransaction.objects.create(
          sender=user,
          receiver=user,
          units=float(units_purchased),
          meter=meter,
          direction="IN",
          status="COMPLETED",
          message="Purchased units to wallet via mobile money",
        )
        MeterLedgerTransaction.objects.create(
          user=user,
          meter=meter,
          transaction_type=MeterLedgerTransaction.TYPE_PURCHASE,
          amount_kwh=units_purchased,
          amount_ugx=amount_decimal,
          status=MeterLedgerTransaction.STATUS_COMPLETED,
          channel=payment_channel,
          payment_reference=transaction.transaction_reference or "",
          source="wallet_purchase",
          destination=meter.meter_no,
        )

      record_transaction_log(
        user,
        TransactionType.UNIT_PURCHASE,
        amount=amount_decimal,
        units=units_purchased,
        status="COMPLETED",
        reference_id=transaction.transaction_reference or f"BUY-{transaction.id}",
        details={
          "channel": payment_channel,
          "meter_no": meter.meter_no,
          "loan_repaid_ugx": float(repaid_to_loans),
          "tariff": tariff.tariff_code if tariff else "DEFAULT_500",
          "transaction_id": transaction.id,
        },
      )

    logger.info(
      "Buy-units payment complete user=%s loan_repaid=%s units=%s",
      user.id,
      repaid_to_loans,
      units_purchased,
    )
    return True, units_purchased, None
  except Transaction.DoesNotExist:
    return False, Decimal("0"), "Transaction not found"
  except Meter.DoesNotExist:
    try:
      transaction = Transaction.objects.get(id=transaction_id)
      transaction.status = "FAILED"
      transaction.save(update_fields=["status"])
    except Transaction.DoesNotExist:
      pass
    return False, Decimal("0"), "Meter not found"
  except Exception as exc:
    logger.exception("complete_buy_units_payment failed: %s", exc)
    try:
      transaction = Transaction.objects.get(id=transaction_id)
      transaction.status = "FAILED"
      transaction.save(update_fields=["status"])
    except Exception:
      pass
    return False, Decimal("0"), str(exc)
