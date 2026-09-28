import logging
import threading
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction as db_transaction
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.models import Wallet as AccountWallet
from loan.models import LoanApplication
from loan.services import (
    LoanOperationError,
    create_loan_application,
    format_loan_apply_preview_ussd,
    format_loan_stats_ussd,
    format_repay_loan_menu_ussd,
    format_wallet_loan_summary,
    get_disbursed_loan_balances,
    get_repayable_loan,
    get_user_loan_stats,
    repay_loan,
    user_can_purchase_units,
)
from loan.tenure import TENURE_PROMPT, validate_tenure_months
from meter.api.views import BuyUnitsView
from meter.models import Meter, MeterToken
from meter.models import Transaction as MeterLedgerTransaction
from meter.services import push_units_to_thingsboard, query_latest_units_from_thingsboard, record_balance_snapshot
from utils.ami_gateway import apply_units_to_meter
from share.flow import ShareFlowError, build_share_summary, execute_share_units
from transactions.models import Transaction, TransactionLog, TransactionType, UnitTransaction
from transactions.services import record_transaction_log
from transactions.api.generate_token import generate_numeric_token
from transactions.tasks import handle_send_transaction_statement_email
from ussd.models import UssdSession, ussd_session_timeout_seconds
from utils.general import dispatch_task
from wallet.models import Wallet as UnitWallet

logger = logging.getLogger(__name__)



@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ussd_phone_numbers(request):
    """
    Web USSD simulator helper — returns only the logged-in portal user's phone.
    """
    user = request.user
    if not user.phone_number:
        return Response({"results": []})
    return Response(
        {
            "results": [
                {
                    "phone_number": str(user.phone_number),
                    "email": user.email,
                }
            ]
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ussd_receiver_meters(request):
    """
    Web USSD simulator helper — receiver meters for share flows.
    Locked to the authenticated portal account (ignores phoneNumber query param).
    """
    sender_user = request.user
    sender_meter_no = None

    sender_meter = Meter.objects.filter(user=sender_user).only("meter_no").first()
    sender_meter_no = sender_meter.meter_no if sender_meter else None

    meters_qs = Meter.objects.select_related("user").only("meter_no", "user__email").order_by("meter_no")
    if sender_meter_no:
        meters_qs = meters_qs.exclude(meter_no=sender_meter_no)

    items = [{"meter_no": meter.meter_no, "email": meter.user.email} for meter in meters_qs[:200]]
    return Response({"results": items})


def _normalize_phone(phone: str) -> str:
    return "".join(ch for ch in str(phone or "") if ch.isdigit())


def _find_user_by_phone(phone_number: str):
    from accounts.models import User

    incoming = _normalize_phone(phone_number)
    if not incoming:
        return None

    candidates = []
    for user in User.objects.exclude(phone_number__isnull=True).exclude(phone_number="").only(
        "id", "phone_number"
    ):
        stored = _normalize_phone(user.phone_number)
        if not stored:
            continue
        if stored == incoming:
            return user
        if stored.endswith(incoming[-9:]) or incoming.endswith(stored[-9:]):
            candidates.append(user)

    return candidates[0] if len(candidates) == 1 else None


# USSD navigation keys (shown on every submenu / prompt / result screen).
NAV_MAIN = "*"
NAV_BACK = "#"
MAIN_MENU_OPTION = "*: Main Menu"
BACK_OPTION = "#: Back"


def _menu(text: str) -> list[str]:
    """
    Parse Africa's Talking cumulative USSD text into steps.

    `*` separates levels; a trailing `*` is the main-menu shortcut (otherwise lost
    on split). `#` is the back shortcut (usually its own final segment).
    """
    if not text:
        return []
    raw = str(text).strip()
    steps = [segment.strip() for segment in raw.split("*") if segment.strip() != ""]
    if raw == NAV_MAIN or raw.endswith(NAV_MAIN):
        if not steps or steps[-1] != NAV_MAIN:
            steps.append(NAV_MAIN)
    if steps and steps[-1] != NAV_BACK and steps[-1].endswith(NAV_BACK):
        base = steps[-1][:-1].strip()
        if base:
            steps[-1] = base
        else:
            steps.pop()
        steps.append(NAV_BACK)
    return steps


def _resp(prefix: str, message: str):
    return Response(f"{prefix} {message}", content_type="text/plain")


def _ussd_timeout_message() -> str:
    seconds = ussd_session_timeout_seconds()
    return (
        f"Session expired ({seconds}s with no input). "
        "Dial the service code again to start a new session."
    )


def _parse_statement_date(raw: str):
    try:
        return datetime.strptime(str(raw).strip(), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


# Parent menu for "#: Back" from result / submenu screens.
MENU_PARENT: dict[str, str] = {
    "wallet_menu": "root",
    "wallet_overview": "wallet_menu",
    "check_units": "wallet_menu",
    "check_units_pick": "wallet_menu",
    "buy_menu": "root",
    "buy_amount": "buy_menu",
    "buy_result": "buy_menu",
    "buy_status": "buy_menu",
    "buy_status_result": "buy_menu",
    "loans_menu": "root",
    "loan_latest": "loans_menu",
    "loan_apply_ineligible": "loans_menu",
    "loan_apply_amount": "loans_menu",
    "loan_apply_tenure": "loans_menu",
    "loan_apply_result": "loans_menu",
    "loan_repay_pick": "loans_menu",
    "loan_repay_partial": "loan_repay_pick",
    "loan_repay_result": "loans_menu",
    "loan_stats": "loans_menu",
    "share_meter": "root",
    "share_units": "root",
    "share_preview_error": "root",
    "share_result": "root",
    "tokens_menu": "root",
    "tokens": "tokens_menu",
    "token_generate_amount": "tokens_menu",
    "token_generate": "tokens_menu",
    "manage_menu": "root",
    "manage_meters": "manage_menu",
    "manage_alerts": "manage_menu",
    "apply_ami": "manage_menu",
    "apply_ami_pick": "manage_menu",
    "apply_ami_amount": "manage_menu",
    "statement_start_date": "manage_menu",
    "statement_end_date": "manage_menu",
    "statement_email_requested": "manage_menu",
    "alerts": "root",
    "power_usage": "root",
    "power_usage_pick": "root",
    "error": "root",
}

# USSD path prefix when returning to a parent menu (for cumulative text replay).
MENU_PATH: dict[str, str] = {
    "root": "",
    "wallet_menu": "1",
    "buy_menu": "2",
    "loans_menu": "3",
    "tokens_menu": "5",
    "manage_menu": "6",
}


def _session_reply(session: UssdSession, prefix: str, message: str, menu: str = "", context: dict | None = None):
    merged_context = dict(session.context or {})
    if context:
        merged_context.update(context)
    merged_context["last_response"] = f"{prefix} {message}"
    session.current_menu = menu or session.current_menu
    session.context = merged_context
    if prefix.strip().upper() == "CON":
        session.expires_at = UssdSession.default_expiry()
        session.is_active = True
        session.save(
            update_fields=[
                "current_menu",
                "context",
                "expires_at",
                "is_active",
                "updated_at",
            ]
        )
    else:
        session.is_active = False
        session.save(
            update_fields=["current_menu", "context", "is_active", "updated_at"]
        )
    return _resp(prefix, message)


def _nav_footer(menu: str) -> str:
    """Back + main menu shortcuts on submenus and result screens."""
    lines: list[str] = []
    if menu and menu != "root":
        lines.append(BACK_OPTION)
    lines.append(MAIN_MENU_OPTION)
    return "\n".join(lines)


def _effective_steps(text: str, session: UssdSession) -> list[str]:
    """
    Africa's Talking sends cumulative dial strings. After Back (#) or Main Menu (*),
    replay only choices made since that navigation point.
    """
    steps = _menu(text)
    if not steps:
        return []
    ctx = session.context or {}
    nav_reset_at = ctx.get("nav_reset_at")
    if nav_reset_at is None:
        return steps
    nav_prefix = str(ctx.get("nav_prefix", "") or "")
    prefix_steps = _menu(nav_prefix) if nav_prefix else []
    tail = steps[nav_reset_at:]
    return prefix_steps + tail


def _wants_back(steps: list[str], session: UssdSession) -> bool:
    if not steps or steps[-1] != NAV_BACK:
        return False
    menu = (session.current_menu or "root").strip()
    return menu != "root"


def _wallet_menu_message() -> str:
    return (
        "Wallet & Meter\n"
        "1. Summary\n"
        "2. Check units (AMI)"
    )


def _loans_menu_message() -> str:
    return (
        "Loans\n"
        "1. Latest loan\n"
        "2. Apply for loan\n"
        "3. Repay loan\n"
        "4. Loan stats"
    )


def _render_menu_by_key(session: UssdSession, user, menu_key: str):
    if menu_key == "root":
        return _reply_main_menu(session, nav_reset_at=len(_menu(session.last_text or "")))
    if menu_key == "wallet_menu":
        return _reply_submenu(session, _wallet_menu_message(), menu="wallet_menu")
    if menu_key == "buy_menu":
        return _reply_submenu(
            session,
            "Buy Units\n1. Start purchase\n2. Check payment status",
            menu="buy_menu",
        )
    if menu_key == "loans_menu":
        return _reply_submenu(session, _loans_menu_message(), menu="loans_menu")
    if menu_key == "tokens_menu":
        return _reply_submenu(
            session,
            "My Tokens\n1. List unused\n2. Generate STS token",
            menu="tokens_menu",
        )
    if menu_key == "manage_menu":
        return _reply_submenu(
            session,
            (
                "Manage\n"
                "1. My meters\n"
                "2. Alerts\n"
                "3. Apply wallet (AMI)\n"
                "4. Email statement (PDF)"
            ),
            menu="manage_menu",
        )
    return _reply_main_menu(session, nav_reset_at=len(_menu(session.last_text or "")))


def _reply_parent_menu(session: UssdSession, user, raw_steps: list[str]):
    parent = MENU_PARENT.get(session.current_menu or "", "root")
    nav_reset_at = len(raw_steps)
    nav_prefix = MENU_PATH.get(parent, "")
    ctx = dict(session.context or {})
    ctx["nav_reset_at"] = nav_reset_at
    ctx["nav_prefix"] = nav_prefix
    ctx["awaiting_main_menu"] = False
    session.context = ctx
    return _render_menu_by_key(session, user, parent)


def _main_menu_text() -> str:
    return (
        "gPawa\n"
        "1. Wallet & Meter\n"
        "2. Buy Units\n"
        "3. Loans\n"
        "4. Share Units\n"
        "5. My Tokens\n"
        "6. Manage\n"
        "7. Alerts\n"
        "8. Exit\n"
        "9. Energy Usage"
    )


def _reply_main_menu(session: UssdSession, nav_reset_at: int | None = None):
    ctx: dict = {
        "awaiting_main_menu": False,
        "nav_prefix": "",
    }
    if nav_reset_at is not None:
        ctx["nav_reset_at"] = nav_reset_at
    return _session_reply(
        session,
        "CON",
        _main_menu_text(),
        menu="root",
        context=ctx,
    )


def _reply_submenu(session: UssdSession, message: str, menu: str = "", context: dict | None = None):
    merged = dict(context or {})
    footer = _nav_footer(menu)
    return _session_reply(session, "CON", f"{message}\n{footer}", menu=menu, context=merged)


def _reply_done(session: UssdSession, message: str, menu: str = "", context: dict | None = None):
    merged: dict = {"awaiting_main_menu": True}
    if context:
        merged.update(context)
    footer = _nav_footer(menu)
    return _session_reply(
        session,
        "CON",
        f"{message}\n\n{footer}",
        menu=menu,
        context=merged,
    )


def _reply_prompt(session: UssdSession, message: str, menu: str, context: dict | None = None):
    """Single-field CON prompt with Back / Main Menu shortcuts."""
    merged = dict(context or {})
    footer = _nav_footer(menu)
    return _session_reply(session, "CON", f"{message}\n{footer}", menu=menu, context=merged)


def _wants_main_menu(steps: list[str], session: UssdSession) -> bool:
    if not steps or steps[-1] != NAV_MAIN:
        return False
    if len(steps) == 1:
        return True
    ctx = session.context or {}
    if ctx.get("awaiting_main_menu"):
        return True
    # e.g. 3* -> main menu from a first-level submenu
    return len(steps) == 2



def _start_buy_units(user, phone_number: str, amount_raw: str):
    meter = Meter.objects.filter(user=user).first()
    if not meter:
        return False, "No meter found. Register your meter in app first."

    can_buy, purchase_message = user_can_purchase_units(user)
    if not can_buy:
        return False, purchase_message

    try:
        amount = Decimal(str(amount_raw))
    except (InvalidOperation, TypeError, ValueError):
        return False, "Invalid amount."

    if amount <= 0:
        return False, "Amount must be greater than zero."

    account_wallet = AccountWallet.objects.filter(user=user).order_by("-create_date").first()
    if account_wallet is None:
        account_wallet = AccountWallet.objects.create(user=user)

    buy_view = BuyUnitsView()
    _, total_outstanding = get_disbursed_loan_balances(user)
    estimated_buy_amount = max(Decimal("0"), amount - total_outstanding)
    estimated_units, tariff = buy_view._calculate_units_from_tariff(estimated_buy_amount, user)

    momo_reference = str(uuid.uuid4())
    try:
        tx = Transaction.objects.create(
            wallet=account_wallet,
            amount=amount,
            phone_number=phone_number,
            status="PENDING",
            transaction_reference=momo_reference,
            message=f"USSD Buy units - {amount} UGX",
        )
    except Exception:
        return False, "Invalid phone number format."

    from mtn_momo.config import should_simulate_payments

    if should_simulate_payments():
        threading.Thread(
            target=buy_view._simulate_sandbox_payment,
            args=(user.id, str(amount), tx.id, meter.id),
            daemon=True,
        ).start()
        return True, (
            f"Payment initiated.\nTxID: {tx.id}\nStatus: PENDING\n"
            f"Estimated units: {estimated_units}\nTariff: {tariff.tariff_code if tariff else 'DEFAULT_500'}"
        )

    from mtn_momo.services import MTNMoMoService

    momo_service = MTNMoMoService()
    payment_result = momo_service.request_payment(
        amount=amount,
        phone_number=phone_number,
        reference_id=momo_reference,
        external_id=str(tx.id),
        payer_message=f"gPAWA USSD top-up {amount} UGX",
    )
    if payment_result.get("status") != "PENDING":
        tx.status = "FAILED"
        tx.message = payment_result.get("message", "MoMo request failed")
        tx.save(update_fields=["status", "message"])
        return False, payment_result.get("message", "Failed to start mobile money payment.")

    return True, (
        f"MoMo prompt sent.\nEnter PIN on phone.\nTxID: {tx.id}\n"
        f"Estimated units: {estimated_units}\nUse option 2 to check status."
    )


def _check_buy_status(user, tx_id_raw: str):
    try:
        tx_id = int(tx_id_raw)
    except (TypeError, ValueError):
        return False, "Invalid transaction ID."

    try:
        transaction = Transaction.objects.get(id=tx_id, wallet__user=user)
    except Transaction.DoesNotExist:
        return False, "Transaction not found."

    from mtn_momo.config import should_simulate_payments
    from meter.buy_units_payment import complete_buy_units_payment
    from mtn_momo.services import MTNMoMoService

    if transaction.status == "PENDING" and not should_simulate_payments() and transaction.transaction_reference:
        momo_status = MTNMoMoService().get_payment_status(transaction.transaction_reference)
        if momo_status.get("status") == "SUCCESS":
            meter = Meter.objects.filter(user=user).order_by("create_date").first()
            if meter:
                complete_buy_units_payment(
                    user, transaction.amount, transaction.id, meter.id, channel="USSD"
                )
            transaction.refresh_from_db()
        elif momo_status.get("status") == "FAILED":
            transaction.status = "FAILED"
            transaction.message = momo_status.get("message", "Payment failed")
            transaction.save(update_fields=["status", "message"])

    if transaction.status == "COMPLETED":
        unit_tx = UnitTransaction.objects.filter(
            sender=user,
            receiver=user,
            direction="IN",
            status="COMPLETED",
            create_date__gte=transaction.create_date,
        ).order_by("-create_date").first()
        units = float(unit_tx.units) if unit_tx else 0.0
        return True, f"SUCCESS\nAmount: UGX {transaction.amount}\nUnits: {units}\nTxID: {transaction.id}"
    if transaction.status == "FAILED":
        return True, f"FAILED\nTxID: {transaction.id}"
    return True, f"PENDING\nTxID: {transaction.id}"


def _apply_loan(user, amount_raw: str, tenure_months: int):
    try:
        loan = create_loan_application(
            user,
            amount_requested=amount_raw,
            purpose="USSD application",
            tenure_months=tenure_months,
            channel="USSD",
        )
    except LoanOperationError as exc:
        return False, exc.message

    if loan.status == "DISBURSED":
        disbursement = getattr(loan, "disbursement", None)
        units = disbursement.units_disbursed if disbursement else "-"
        return True, (
            f"Loan approved & disbursed!\nID: {loan.id}\nLoanRef: {loan.loan_id}\n"
            f"Approved UGX {loan.amount_approved}\n"
            f"Units added: {units}\n"
            f"Tenure: {loan.tenure_months} mo ({loan.tenure_months * 30} days)"
        )
    if loan.status == "APPROVED":
        return True, (
            f"Loan approved.\nID: {loan.id}\nLoanRef: {loan.loan_id}\n"
            f"Approved UGX {loan.amount_approved}\n"
            f"Tenure: {loan.tenure_months} mo ({loan.tenure_months * 30} days)\n"
            f"Units are being credited. If they don't arrive shortly, contact support."
        )
    return True, f"Loan rejected.\nReason: {loan.rejection_reason}"


def _repay_loan(user, loan_id_raw: str | None, amount_raw: str):
    try:
        loan_key = None if loan_id_raw in (None, "", "0") else loan_id_raw
        result = repay_loan(
            user,
            loan_key,
            amount_raw,
            channel="USSD",
            payment_method="MOBILE_MONEY",
        )
    except LoanOperationError as exc:
        return False, exc.message

    return True, (
        f"{result['message']}\nLoanRef: {result['loan_id']}\n"
        f"Outstanding: UGX {result['outstanding_balance']}\n"
        f"Units added: {result['units_added']}"
    )


def _share_preview_for_ussd(user, receiver_meter_no: str, units_raw: str):
    """Validate meter/units and return summary text before PIN entry."""
    try:
        units = Decimal(str(units_raw))
    except (InvalidOperation, ValueError):
        return False, "Invalid units."

    if units < Decimal("2"):
        return False, "Minimum 2 units required."

    sender_wallet, _ = UnitWallet.objects.get_or_create(user=user)
    if sender_wallet.balance < units:
        return False, f"Insufficient units. Wallet balance is {sender_wallet.balance}."

    try:
        receiver_meter = Meter.objects.select_related("user").get(meter_no=receiver_meter_no)
    except Meter.DoesNotExist:
        return False, "Receiver meter not found."

    if receiver_meter.user_id == user.id:
        return False, (
            "Cannot share to your own meter. "
            "Use Manage->4 Apply wallet (AMI) or Tokens->2 (STS) to load units."
        )

    summary = build_share_summary(receiver_meter, units)
    return True, summary


def _generate_sts_token(user, units_raw: str):
    meter = Meter.objects.filter(user=user, architecture=Meter.ARCH_STS).first()
    if not meter:
        return False, "No STS meter found."

    try:
        amount = Decimal(str(units_raw))
    except (InvalidOperation, ValueError):
        return False, "Invalid units."

    if amount <= 0:
        return False, "Units must be greater than zero."

    unit_wallet, _ = UnitWallet.objects.get_or_create(user=user)
    if unit_wallet.balance < amount:
        return False, f"Insufficient wallet. Balance: {float(unit_wallet.balance):.2f} kWh."

    try:
        with db_transaction.atomic():
            locked = UnitWallet.objects.select_for_update().get(user=user)
            if locked.balance < amount:
                return False, "Insufficient wallet balance."
            locked.balance -= amount
            locked.save(update_fields=["balance"])
            token_value = generate_numeric_token()
            MeterToken.objects.create(
                user=user,
                token=token_value,
                units=amount,
                meter=meter,
                source="PURCHASE",
            )
            MeterLedgerTransaction.objects.create(
                user=user,
                meter=meter,
                transaction_type=MeterLedgerTransaction.TYPE_GENERATE_TOKEN,
                amount_kwh=amount,
                status=MeterLedgerTransaction.STATUS_COMPLETED,
                channel=MeterLedgerTransaction.CHANNEL_USSD,
                sts_token=token_value,
                source="wallet",
                destination=meter.meter_no,
                payment_reference=f"TOKEN-{token_value}",
            )
            record_transaction_log(
                user,
                TransactionType.TOKEN_GENERATE,
                units=amount,
                status="COMPLETED",
                reference_id=f"TOKEN-{token_value}",
                details={
                    "channel": "USSD",
                    "meter_no": meter.meter_no,
                    "token": token_value,
                },
            )
        return True, f"Token: {token_value}\nUnits: {float(amount):.2f} kWh\nWallet: {float(locked.balance):.2f} kWh"
    except Exception:
        return False, "Failed to generate token."


def _apply_wallet_to_ami(user, units_raw: str, meter_no: str | None = None):
    qs = Meter.objects.filter(user=user, architecture=Meter.ARCH_AMI)
    if meter_no:
        qs = qs.filter(meter_no=meter_no)
    meter = qs.first()
    if not meter:
        return False, "No AMI meter found."

    try:
        amount = Decimal(str(units_raw))
    except (InvalidOperation, ValueError):
        return False, "Invalid units."

    if amount <= 0:
        return False, "Units must be greater than zero."

    unit_wallet, _ = UnitWallet.objects.get_or_create(user=user)
    if unit_wallet.balance < amount:
        return False, f"Insufficient wallet. Balance: {float(unit_wallet.balance):.2f} kWh."

    try:
        with db_transaction.atomic():
            locked = UnitWallet.objects.select_for_update().get(user=user)
            if locked.balance < amount:
                return False, "Insufficient wallet balance."
            locked.balance -= amount
            locked.save(update_fields=["balance"])
            if not apply_units_to_meter(meter, amount):
                raise ValueError("AMI apply failed")
            meter.refresh_from_db(fields=["units"])
            ref = uuid.uuid4().hex[:12]
            record_transaction_log(
                user,
                TransactionType.WALLET_LOAD_AMI,
                units=amount,
                status="COMPLETED",
                reference_id=f"USSD-AMI-{ref}",
                details={
                    "channel": "USSD",
                    "meter_no": meter.meter_no,
                },
            )
        return True, (
            f"Applied {float(amount):.2f} kWh to {meter.meter_no}.\n"
            f"Meter: {float(meter.units):.2f} kWh\n"
            f"Wallet: {float(locked.balance):.2f} kWh"
        )
    except ValueError as exc:
        return False, str(exc)
    except Exception:
        return False, "Failed to apply units to AMI meter."


def _user_meters_summary(user):
    meters = list(Meter.objects.filter(user=user).order_by("create_date"))
    if not meters:
        return False, "No meters registered."
    lines = ["Your meters:"]
    for m in meters:
        token_hint = "TB" if (m.iot_device_token or "").strip() else "no-token"
        label = f" ({m.label})" if m.label and m.label != "Home" else ""
        lines.append(
            f"{m.meter_no}{label} | {m.architecture} | {float(m.units):.2f} kWh ({token_hint})"
        )
    return True, "\n".join(lines)


def _ami_meters_for_user(user):
    return list(
        Meter.objects.filter(user=user, architecture=Meter.ARCH_AMI).order_by("create_date")
    )


def _ami_meter_picker_message(meters):
    lines = ["Check units - pick meter:"]
    for i, m in enumerate(meters, 1):
        lines.append(f"{i}. {m.meter_no}")
    return "\n".join(lines)


def _check_units_for_meter(user, meter_no: str):
    try:
        meter = Meter.objects.get(user=user, meter_no=meter_no, architecture=Meter.ARCH_AMI)
    except Meter.DoesNotExist:
        return False, "AMI meter not found on your account."

    ok, msg, data = query_latest_units_from_thingsboard(meter)
    if not ok or not data:
        return False, msg or "Could not read units from ThingsBoard."

    record_balance_snapshot(
        meter,
        data["units_kwh"],
        source=data.get("source", "thingsboard"),
    )

    return True, (
        f"Meter {meter.meter_no}\n"
        f"Units: {data['units_kwh']:.2f} kWh"
    )


def _reply_ussd_check_units(user, ussd_session, text, steps):
    """AMI check-units flow for paths like 1*2 or 1*2*<meter pick>."""
    ami_meters = _ami_meters_for_user(user)
    if not ami_meters:
        ussd_session.last_text = text
        ussd_session.save(update_fields=["user", "last_text", "updated_at"])
        return _reply_done(
            ussd_session,
            "No AMI meter on your account.",
            menu="check_units",
        )

    if len(ami_meters) == 1:
        ok, msg = _check_units_for_meter(user, ami_meters[0].meter_no)
        ussd_session.last_text = text
        ussd_session.save(update_fields=["user", "last_text", "updated_at"])
        return _reply_done(
            ussd_session,
            msg if ok else f"Error: {msg}",
            menu="check_units",
        )

    if len(steps) == 2:
        ussd_session.last_text = text
        ussd_session.save(update_fields=["user", "last_text", "updated_at"])
        return _reply_submenu(
            ussd_session,
            _ami_meter_picker_message(ami_meters),
            menu="check_units_pick",
            context={"ami_meter_nos": [m.meter_no for m in ami_meters]},
        )

    try:
        pick = int(steps[2])
        meter_nos = (ussd_session.context or {}).get("ami_meter_nos") or [
            m.meter_no for m in ami_meters
        ]
        if pick < 1 or pick > len(meter_nos):
            raise ValueError("out of range")
        meter_no = meter_nos[pick - 1]
    except (ValueError, TypeError, IndexError):
        ussd_session.last_text = text
        ussd_session.save(update_fields=["user", "last_text", "updated_at"])
        return _reply_done(ussd_session, "Invalid meter selection.", menu="check_units")

    ok, msg = _check_units_for_meter(user, meter_no)
    ussd_session.last_text = text
    ussd_session.save(update_fields=["user", "last_text", "updated_at"])
    return _reply_done(
        ussd_session,
        msg if ok else f"Error: {msg}",
        menu="check_units",
    )


def _notifications_summary(user):
    from meter.models import MeterNotification

    low_threshold = float(getattr(settings, "AMI_LOW_UNITS_THRESHOLD_KWH", 5))
    unread = MeterNotification.objects.filter(user=user, is_read=False).count()
    recent = list(
        MeterNotification.objects.filter(user=user)
        .select_related("meter")
        .order_by("-occurred_at")[:5]
    )
    if not recent:
        return True, f"No alerts.\nUnread: {unread}"

    lines = [f"Alerts (unread: {unread}):"]
    for n in recent:
        mark = "*" if not n.is_read else ""
        if n.notification_type == MeterNotification.TYPE_LOW_UNITS:
            mno = n.meter.meter_no if n.meter else "?"
            lines.append(
                f"{mark}LOW BALANCE <= {low_threshold:.0f} kWh | Meter {mno}: "
                f"{float(n.units_kwh):.2f} kWh remaining"
            )
        else:
            lines.append(f"{mark}{(n.message or 'Alert update')[:120]}")
    lines.append("Use menu 7 or Manage->2 to review alerts.")
    return True, "\n".join(lines)


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def ussd_entry(request):
    """
    USSD endpoint in Africa's Talking format:
    - sessionId
    - serviceCode
    - phoneNumber
    - text
    """
    session_id = str(request.data.get("sessionId", "")).strip() or f"fallback-{uuid.uuid4().hex[:10]}"
    service_code = str(request.data.get("serviceCode", "")).strip()
    phone_number = request.data.get("phoneNumber", "")
    if getattr(request.user, "is_authenticated", False):
        if not request.user.phone_number:
            return _resp(
                "END",
                "Add a phone number in your web account profile before using USSD.",
            )
        phone_number = str(request.user.phone_number)
    text = request.data.get("text", "")
    text_str = str(text or "").strip()

    ussd_session, created = UssdSession.objects.get_or_create(
        session_id=session_id,
        defaults={
            "service_code": service_code,
            "phone_number": str(phone_number),
            "expires_at": UssdSession.default_expiry(),
        },
    )
    session_timed_out = ussd_session.expired and not created

    ussd_session.service_code = service_code or ussd_session.service_code
    ussd_session.phone_number = str(phone_number)

    user = _find_user_by_phone(phone_number)
    if not user:
        ussd_session.user = None
        ussd_session.last_text = text_str
        ussd_session.is_active = False
        ussd_session.save(update_fields=["user", "last_text", "is_active", "updated_at"])
        return _session_reply(
            ussd_session,
            "END",
            "Account not found. Please register first on the web app.",
        )
    ussd_session.user = user

    if session_timed_out:
        had_prior_activity = bool((ussd_session.last_text or "").strip()) or bool(
            (ussd_session.context or {}).get("last_response")
        )
        ussd_session.reset()
        if had_prior_activity or text_str:
            ussd_session.user = user
            ussd_session.phone_number = str(phone_number)
            ussd_session.service_code = service_code or ussd_session.service_code
            ussd_session.last_text = text_str
            ussd_session.is_active = False
            ussd_session.save(
                update_fields=[
                    "user",
                    "last_text",
                    "is_active",
                    "phone_number",
                    "service_code",
                    "current_menu",
                    "context",
                    "expires_at",
                    "updated_at",
                ]
            )
            return _resp("END", _ussd_timeout_message())

    # Basic dedupe for provider retries to prevent duplicate side effects.
    if text and text == ussd_session.last_text:
        cached = (ussd_session.context or {}).get("last_response")
        if cached:
            return Response(cached, content_type="text/plain")

    meter = Meter.objects.filter(user=user).first()
    wallet, _ = UnitWallet.objects.get_or_create(user=user)
    raw_steps = _menu(text_str)

    try:
        if _wants_main_menu(raw_steps, ussd_session):
            ussd_session.last_text = text_str
            ussd_session.save(update_fields=["user", "last_text", "updated_at"])
            return _reply_main_menu(ussd_session, nav_reset_at=len(raw_steps))

        if _wants_back(raw_steps, ussd_session):
            ussd_session.last_text = text_str
            ussd_session.save(update_fields=["user", "last_text", "updated_at"])
            return _reply_parent_menu(ussd_session, user, raw_steps)

        steps = _effective_steps(text_str, ussd_session)

        if len(steps) == 0:
            ussd_session.last_text = text_str or ""
            ussd_session.save(update_fields=["user", "last_text", "updated_at"])
            return _reply_main_menu(ussd_session)

        # 1) Wallet and meter
        if steps[0] == "1":
            if len(steps) == 1:
                ussd_session.last_text = text
                ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                return _reply_submenu(
                    ussd_session,
                    _wallet_menu_message(),
                    menu="wallet_menu",
                )

            if steps[1] == "1":
                loan_stats = get_user_loan_stats(user)
                meter_no = meter.meter_no if meter else "Not registered"
                ussd_session.last_text = text
                ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                return _reply_done(
                    ussd_session,
                    (
                        f"Wallet: {wallet.balance} units\n"
                        f"Meter: {meter_no}\n"
                        f"{format_wallet_loan_summary(loan_stats)}"
                    ),
                    menu="wallet_overview",
                )

            if steps[1] == "2":
                return _reply_ussd_check_units(user, ussd_session, text, steps)

            ussd_session.last_text = text
            ussd_session.save(update_fields=["user", "last_text", "updated_at"])
            return _reply_done(ussd_session, "Invalid wallet option.")

        # 2) Buy units full flow
        if steps[0] == "2":
            if len(steps) == 1:
                ussd_session.last_text = text
                ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                return _reply_submenu(
                    ussd_session,
                    "Buy Units\n1. Start purchase\n2. Check payment status",
                    menu="buy_menu",
                )

            if steps[1] == "1":
                if len(steps) == 2:
                    ussd_session.last_text = text
                    ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                    return _reply_prompt(ussd_session, "Enter amount in UGX:", menu="buy_amount")
                if len(steps) == 3:
                    try:
                        purchase_amount = Decimal(str(steps[2]))
                        if purchase_amount <= 0:
                            raise ValueError("invalid")
                    except (InvalidOperation, TypeError, ValueError):
                        ussd_session.last_text = text
                        ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                        return _reply_done(
                            ussd_session,
                            "Error: Invalid amount.",
                            menu="buy_result",
                        )
                    ok, msg = _start_buy_units(user, phone_number, str(purchase_amount))
                    ctx = {}
                    if ok:
                        tx_line = [line for line in msg.split("\n") if line.startswith("TxID:")]
                        if tx_line:
                            try:
                                ctx["last_buy_transaction_id"] = int(tx_line[0].split(":")[1].strip())
                            except Exception:
                                pass
                    ussd_session.last_text = text
                    ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                    return _reply_done(
                        ussd_session,
                        msg if ok else f"Error: {msg}",
                        menu="buy_result",
                        context=ctx,
                    )
                ussd_session.last_text = text
                ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                return _reply_done(ussd_session, "Invalid buy-units option.", menu="buy_result")

            if steps[1] == "2":
                if len(steps) == 2:
                    ussd_session.last_text = text
                    ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                    hint = ""
                    last_tx = (ussd_session.context or {}).get("last_buy_transaction_id")
                    if last_tx:
                        hint = f"\nTip: use {last_tx}"
                    return _reply_prompt(ussd_session, f"Enter transaction ID:{hint}", menu="buy_status")
                tx_input = steps[2]
                if tx_input == "0":
                    tx_input = str((ussd_session.context or {}).get("last_buy_transaction_id", ""))
                ok, msg = _check_buy_status(user, tx_input)
                ussd_session.last_text = text
                ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                return _reply_done(
                    ussd_session,
                    msg if ok else f"Error: {msg}",
                    menu="buy_status_result",
                )

            ussd_session.last_text = text
            ussd_session.save(update_fields=["user", "last_text", "updated_at"])
            return _reply_done(ussd_session, "Invalid buy-units option.")

        # 3) Loans
        if steps[0] == "3":
            if len(steps) == 1:
                ussd_session.last_text = text
                ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                return _reply_submenu(
                    ussd_session,
                    _loans_menu_message(),
                    menu="loans_menu",
                )

            if steps[1] == "1":
                loan = LoanApplication.objects.filter(user=user).order_by("-created_at").first()
                if not loan:
                    ussd_session.last_text = text
                    ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                    return _reply_done(ussd_session, "No loan record found.", menu="loan_latest")
                ussd_session.last_text = text
                ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                return _reply_done(
                    ussd_session,
                    (
                        f"LoanID: {loan.id}\nRef: {loan.loan_id}\nStatus: {loan.status}\n"
                        f"Requested: UGX {loan.amount_requested}\nApproved: UGX {loan.amount_approved or 0}\n"
                        f"Tenure: {loan.tenure_months} mo ({loan.tenure_months * 30} days)\n"
                        f"Outstanding: UGX {loan.outstanding_balance}"
                    ),
                    menu="loan_latest",
                )

            if steps[1] == "2":
                loan_stats = get_user_loan_stats(user)
                if len(steps) == 2:
                    preview = format_loan_apply_preview_ussd(loan_stats)
                    ussd_session.last_text = text
                    ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                    if not loan_stats.get("is_loan_eligible"):
                        return _reply_done(ussd_session, preview, menu="loan_apply_ineligible")
                    return _reply_prompt(ussd_session, preview, menu="loan_apply_amount")
                if len(steps) == 3:
                    try:
                        purchase_amount = Decimal(str(steps[2]))
                        if purchase_amount <= 0:
                            raise ValueError("invalid")
                    except (InvalidOperation, TypeError, ValueError):
                        ussd_session.last_text = text
                        ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                        return _reply_done(
                            ussd_session,
                            "Error: Invalid amount.",
                            menu="loan_apply_result",
                        )
                    ussd_session.last_text = text
                    ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                    return _reply_prompt(
                        ussd_session,
                        TENURE_PROMPT,
                        menu="loan_apply_tenure",
                    )
                if len(steps) == 4:
                    try:
                        tenure = validate_tenure_months(steps[3])
                    except ValueError as exc:
                        ussd_session.last_text = text
                        ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                        return _reply_done(
                            ussd_session,
                            f"Error: {exc}",
                            menu="loan_apply_result",
                        )
                    ok, msg = _apply_loan(user, steps[2], tenure)
                    ussd_session.last_text = text
                    ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                    return _reply_done(ussd_session, msg if ok else f"Error: {msg}", menu="loan_apply_result")
                ussd_session.last_text = text
                ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                return _reply_done(ussd_session, "Invalid loan apply option.", menu="loan_apply_result")

            if steps[1] == "3":
                repayable = get_repayable_loan(user)
                if len(steps) == 2:
                    if not repayable:
                        ussd_session.last_text = text
                        ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                        return _reply_done(
                            ussd_session,
                            "No active loan to repay.",
                            menu="loan_repay_result",
                        )
                    ussd_session.last_text = text
                    ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                    return _reply_submenu(
                        ussd_session,
                        format_repay_loan_menu_ussd(repayable),
                        menu="loan_repay_pick",
                        context={
                            "repay_loan_pk": repayable.id,
                            "repay_outstanding": str(repayable.outstanding_balance),
                        },
                    )
                if len(steps) == 3:
                    if steps[2] == "1":
                        active = repayable or get_repayable_loan(user)
                        if not active:
                            ussd_session.last_text = text
                            ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                            return _reply_done(
                                ussd_session,
                                "No active loan to repay.",
                                menu="loan_repay_result",
                            )
                        outstanding = float(active.outstanding_balance)
                        ok, msg = _repay_loan(user, None, outstanding)
                        ussd_session.last_text = text
                        ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                        return _reply_done(
                            ussd_session,
                            msg if ok else f"Error: {msg}",
                            menu="loan_repay_result",
                        )
                    if steps[2] == "2":
                        ussd_session.last_text = text
                        ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                        return _reply_prompt(
                            ussd_session,
                            "Enter partial repayment amount UGX:",
                            menu="loan_repay_partial",
                        )
                    ussd_session.last_text = text
                    ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                    return _reply_done(ussd_session, "Invalid repayment option.", menu="loan_repay_result")
                if len(steps) == 4 and steps[2] == "2":
                    ok, msg = _repay_loan(user, None, steps[3])
                    ussd_session.last_text = text
                    ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                    return _reply_done(
                        ussd_session,
                        msg if ok else f"Error: {msg}",
                        menu="loan_repay_result",
                    )
                ussd_session.last_text = text
                ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                return _reply_done(ussd_session, "Invalid repayment option.", menu="loan_repay_result")

            if steps[1] == "4":
                loan_stats = get_user_loan_stats(user)
                ussd_session.last_text = text
                ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                return _reply_done(
                    ussd_session,
                    format_loan_stats_ussd(loan_stats),
                    menu="loan_stats",
                )

            ussd_session.last_text = text
            ussd_session.save(update_fields=["user", "last_text", "updated_at"])
            return _reply_done(ussd_session, "Invalid loan option.")

        # 4) Share units — meter → units → summary → account PIN
        if steps[0] == "4":
            if len(steps) == 1:
                ussd_session.last_text = text
                ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                return _reply_prompt(
                    ussd_session,
                    "Enter receiver meter number:",
                    menu="share_meter",
                )

            if len(steps) == 2:
                ussd_session.last_text = text
                ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                return _reply_prompt(
                    ussd_session,
                    "Enter units to share (min 2):",
                    menu="share_units",
                )

            if len(steps) == 3:
                preview_ok, preview_msg = _share_preview_for_ussd(user, steps[1], steps[2])
                if not preview_ok:
                    ussd_session.last_text = text
                    ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                    return _reply_done(ussd_session, f"Error: {preview_msg}", menu="share_preview_error")
                try:
                    units = Decimal(str(steps[2]))
                    result = execute_share_units(
                        sender=user,
                        receiver_meter_no=steps[1],
                        units=units,
                        channel="USSD",
                    )
                    msg_suffix = ""
                    if result.get("share_token"):
                        msg_suffix = f"\nToken: {result['share_token']}"
                    elif result.get("receiver_architecture") == Meter.ARCH_AMI:
                        msg_suffix = "\nAMI meter topped up."
                    share_msg = (
                        f"Share completed.\nRef: {result['transaction_id']}\n"
                        f"To: {result['receiver_meter']} ({result.get('receiver_name', '')})\n"
                        f"Units: {result['units_shared']}\n"
                        f"Wallet: {result['new_sender_wallet_balance']} kWh"
                        f"{msg_suffix}"
                    )
                    share_ok = True
                except ShareFlowError as exc:
                    share_msg = exc.message
                    share_ok = False
                ussd_session.last_text = text
                ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                return _reply_done(ussd_session, share_msg if share_ok else f"Error: {share_msg}", menu="share_result")

        # 5) Tokens — list or generate STS
        if steps[0] == "5":
            if len(steps) == 1:
                ussd_session.last_text = text
                ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                return _reply_submenu(
                    ussd_session,
                    "My Tokens\n1. List unused\n2. Generate STS token",
                    menu="tokens_menu",
                )

            if steps[1] == "1":
                tokens = MeterToken.objects.filter(user=user, is_used=False).order_by("-create_date")[:3]
                if not tokens:
                    ussd_session.last_text = text
                    ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                    return _reply_done(ussd_session, "No active tokens found.", menu="tokens")
                lines = ["Active tokens:"]
                for t in tokens:
                    lines.append(f"{t.token} | {t.units}u | {t.source}")
                ussd_session.last_text = text
                ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                return _reply_done(ussd_session, "\n".join(lines), menu="tokens")

            if steps[1] == "2":
                if len(steps) == 2:
                    ussd_session.last_text = text
                    ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                    return _reply_prompt(
                        ussd_session,
                        f"Enter kWh from wallet (max {float(wallet.balance):.2f}):",
                        menu="token_generate_amount",
                    )
                ok, msg = _generate_sts_token(user, steps[2])
                ussd_session.last_text = text
                ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                return _reply_done(ussd_session, msg if ok else f"Error: {msg}", menu="token_generate")

            ussd_session.last_text = text
            ussd_session.save(update_fields=["user", "last_text", "updated_at"])
            return _reply_done(ussd_session, "Invalid token option.")

        # 6) Manage — meters, check units (AMI), alerts, apply wallet
        if steps[0] == "6":
            if len(steps) == 1:
                ussd_session.last_text = text
                ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                return _reply_submenu(
                    ussd_session,
                    (
                        "Manage\n"
                        "1. My meters\n"
                        "2. Alerts\n"
                        "3. Apply wallet (AMI)\n"
                        "4. Email statement (PDF)"
                    ),
                    menu="manage_menu",
                )

            if steps[1] == "1":
                ok, msg = _user_meters_summary(user)
                ussd_session.last_text = text
                ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                return _reply_done(
                    ussd_session,
                    msg if ok else f"Error: {msg}",
                    menu="manage_meters",
                )

            if steps[1] == "2":
                ok, msg = _notifications_summary(user)
                ussd_session.last_text = text
                ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                return _reply_done(ussd_session, msg, menu="manage_alerts")

            if steps[1] == "3":
                ami_meters = _ami_meters_for_user(user)
                if not ami_meters:
                    ussd_session.last_text = text
                    ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                    return _reply_done(ussd_session, "No AMI meter on your account.", menu="apply_ami")

                if len(ami_meters) == 1 and len(steps) == 2:
                    ussd_session.last_text = text
                    ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                    return _reply_prompt(
                        ussd_session,
                        f"Apply kWh to {ami_meters[0].meter_no}\nEnter amount:",
                        menu="apply_ami_amount",
                        context={"apply_ami_meter": ami_meters[0].meter_no},
                    )

                if len(ami_meters) > 1 and len(steps) == 2:
                    ussd_session.last_text = text
                    ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                    return _reply_submenu(
                        ussd_session,
                        _ami_meter_picker_message(ami_meters).replace("Check units", "Apply to"),
                        menu="apply_ami_pick",
                        context={"ami_meter_nos": [m.meter_no for m in ami_meters]},
                    )

                meter_no = (ussd_session.context or {}).get("apply_ami_meter")
                if len(ami_meters) > 1 and len(steps) == 3 and not meter_no:
                    try:
                        pick = int(steps[2])
                        meter_nos = (ussd_session.context or {}).get("ami_meter_nos") or [
                            m.meter_no for m in ami_meters
                        ]
                        meter_no = meter_nos[pick - 1]
                    except (ValueError, TypeError, IndexError):
                        ussd_session.last_text = text
                        ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                        return _reply_done(ussd_session, "Invalid meter selection.", menu="apply_ami")
                    ussd_session.last_text = text
                    ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                    return _reply_prompt(
                        ussd_session,
                        f"Enter kWh to apply to {meter_no}:",
                        menu="apply_ami_amount",
                        context={"apply_ami_meter": meter_no},
                    )

                amount_raw = steps[-1]
                meter_no = meter_no or (ami_meters[0].meter_no if len(ami_meters) == 1 else None)
                ok, msg = _apply_wallet_to_ami(user, amount_raw, meter_no)
                ussd_session.last_text = text
                ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                return _reply_done(ussd_session, msg if ok else f"Error: {msg}", menu="apply_ami")

            if steps[1] == "4":
                if len(steps) == 2:
                    ussd_session.last_text = text
                    ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                    return _reply_prompt(
                        ussd_session,
                        "Statement start date (YYYY-MM-DD):",
                        menu="statement_start_date",
                    )
                if len(steps) == 3:
                    start_date = _parse_statement_date(steps[2])
                    if not start_date:
                        ussd_session.last_text = text
                        ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                        return _reply_done(
                            ussd_session,
                            "Error: Invalid start date format. Use YYYY-MM-DD.",
                            menu="statement_start_date",
                        )
                    ussd_session.last_text = text
                    ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                    return _reply_prompt(
                        ussd_session,
                        "Statement end date (YYYY-MM-DD):",
                        menu="statement_end_date",
                        context={"statement_start_date": start_date.isoformat()},
                    )

                start_date_raw = (ussd_session.context or {}).get("statement_start_date") or steps[2]
                start_date = _parse_statement_date(start_date_raw)
                end_date = _parse_statement_date(steps[3])
                if not start_date or not end_date:
                    ussd_session.last_text = text
                    ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                    return _reply_done(
                        ussd_session,
                        "Error: Invalid date format. Use YYYY-MM-DD.",
                        menu="statement_end_date",
                    )
                if end_date < start_date:
                    ussd_session.last_text = text
                    ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                    return _reply_done(
                        ussd_session,
                        "Error: End date cannot be before start date.",
                        menu="statement_end_date",
                    )
                dispatch_task(
                    handle_send_transaction_statement_email,
                    user.id,
                    start_date.isoformat(),
                    end_date.isoformat(),
                )
                ussd_session.last_text = text
                ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                return _reply_done(
                    ussd_session,
                    f"Statement requested. PDF will be sent to {user.email}.",
                    menu="statement_email_requested",
                )

            ussd_session.last_text = text
            ussd_session.save(update_fields=["user", "last_text", "updated_at"])
            return _reply_done(ussd_session, "Invalid manage option.")

        # 7) Alerts shortcut
        if steps[0] == "7":
            ok, msg = _notifications_summary(user)
            ussd_session.last_text = text
            ussd_session.save(update_fields=["user", "last_text", "updated_at"])
            return _reply_done(ussd_session, msg, menu="alerts")

        # 8) Exit
        if steps[0] == "8":
            ussd_session.last_text = text
            ussd_session.is_active = False
            ussd_session.save(update_fields=["user", "last_text", "is_active", "updated_at"])
            return _session_reply(ussd_session, "END", "Thank you for using gPawa.", menu="exit")

        # 9) Energy Usage — weekly text summary (AMI only)
        if steps[0] == "9":
            from meter.usage_service import format_weekly_usage_ussd, get_power_usage_report, get_user_ami_meters

            ami_meters = get_user_ami_meters(user)
            if not ami_meters:
                ussd_session.last_text = text
                ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                return _reply_done(
                    ussd_session,
                    "This is only for AMI meter users.",
                    menu="power_usage",
                )

            if len(ami_meters) == 1:
                report = get_power_usage_report(user, meter_no=ami_meters[0].meter_no, period="week")
                ok, msg = format_weekly_usage_ussd(report)
                ussd_session.last_text = text
                ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                return _reply_done(
                    ussd_session,
                    msg if ok else f"Error: {msg}",
                    menu="power_usage",
                )

            if len(steps) == 1:
                ussd_session.last_text = text
                ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                return _reply_submenu(
                    ussd_session,
                    _ami_meter_picker_message(ami_meters).replace("Check units", "Energy Usage"),
                    menu="power_usage_pick",
                    context={"power_usage_meter_nos": [m.meter_no for m in ami_meters]},
                )

            try:
                pick = int(steps[1])
                meter_nos = (ussd_session.context or {}).get("power_usage_meter_nos") or [
                    m.meter_no for m in ami_meters
                ]
                if pick < 1 or pick > len(meter_nos):
                    raise ValueError("out of range")
                meter_no = meter_nos[pick - 1]
            except (ValueError, TypeError, IndexError):
                ussd_session.last_text = text
                ussd_session.save(update_fields=["user", "last_text", "updated_at"])
                return _reply_done(ussd_session, "Invalid meter selection.", menu="power_usage")

            report = get_power_usage_report(user, meter_no=meter_no, period="week")
            ok, msg = format_weekly_usage_ussd(report)
            ussd_session.last_text = text
            ussd_session.save(update_fields=["user", "last_text", "updated_at"])
            return _reply_done(
                ussd_session,
                msg if ok else f"Error: {msg}",
                menu="power_usage",
            )

        ussd_session.last_text = text
        ussd_session.save(update_fields=["user", "last_text", "updated_at"])
        return _reply_done(ussd_session, "Invalid menu option.")
    except Exception as exc:
        logger.exception("USSD processing error")
        ussd_session.last_text = text
        ussd_session.save(update_fields=["user", "last_text", "updated_at"])
        return _reply_done(
            ussd_session,
            f"System error. Please try again later. ({exc.__class__.__name__})",
            menu="error",
        )
