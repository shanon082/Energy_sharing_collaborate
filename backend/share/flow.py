"""
Single-step share execution (wallet → receiver meter) after password confirmation.
"""
from __future__ import annotations

import logging
import uuid
from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from accounts.models import User, Wallet as AccountWallet
from meter.models import Meter, MeterToken, Transaction as MeterLedgerTransaction
from share.models import Share, ShareTransaction
from share.notifications import (
    build_receiver_ami_share_update,
    build_sender_share_confirmation,
    format_user_display_name,
)
from transactions.api.generate_token import generate_numeric_token
from transactions.models import TransactionLog, TransactionType
from utils.ami_gateway import apply_units_to_meter
from utils.general import dispatch_task
from wallet.models import Wallet

from accounts.tasks import (
    handle_send_share_token,
    handle_send_wallet_update,
)

logger = logging.getLogger(__name__)


class ShareFlowError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def recipient_display_name(owner: User) -> str:
    display = f"{owner.first_name or ''} {owner.last_name or ''}".strip()
    return display or owner.email or "Unknown"


def build_share_summary(receiver_meter: Meter, units: Decimal) -> str:
    owner = receiver_meter.user
    name = recipient_display_name(owner)
    meter_type = (
        "AMI (networked)" if receiver_meter.architecture == Meter.ARCH_AMI else "STS (token)"
    )
    return (
        f"Share {units} kWh to {receiver_meter.meter_no}\n"
        f"Recipient: {name}\n"
        f"Type: {meter_type}"
    )


def execute_share_units(
    sender: User,
    receiver_meter_no: str,
    units: Decimal,
    *,
    channel: str = "WEB",
) -> dict:
    """
    Debit sender wallet and deliver units to receiver (STS token or AMI push).
    Raises ShareFlowError on validation failures.
    """
    if units < Decimal("2"):
        raise ShareFlowError("Minimum 2 units required to share.")

    sender_meters = Meter.objects.filter(user=sender)
    if sender_meters.count() == 0:
        raise ShareFlowError("No meter found for sender.")
    if sender_meters.count() > 1:
        raise ShareFlowError("Multiple meters found. Please specify which to send from.")
    sender_meter = sender_meters.first()

    try:
        receiver_meter = Meter.objects.select_related("user").get(meter_no=receiver_meter_no)
    except Meter.DoesNotExist:
        raise ShareFlowError("Receiver meter not found.")

    if receiver_meter.user_id == sender.id:
        raise ShareFlowError(
            "To load units onto your own meter, use Load Units instead of Share."
        )

    if receiver_meter.status != Meter.STATUS_ACTIVE:
        raise ShareFlowError("Receiver meter is not active.")

    transaction_ref = f"SHARE-{uuid.uuid4().hex[:8].upper()}"

    with db_transaction.atomic():
        sender_wallet, _ = Wallet.objects.select_for_update().get_or_create(user=sender)
        if sender_wallet.balance < units:
            raise ShareFlowError(
                f"Insufficient units in your wallet. Your balance: {sender_wallet.balance} kWh"
            )

        receiver_meter = Meter.objects.select_for_update().get(pk=receiver_meter.pk)
        sender_wallet.balance -= units
        sender_wallet.save(update_fields=["balance", "modify_date"])

        share_token = None
        token_issued = False

        if receiver_meter.architecture == Meter.ARCH_STS:
            share_token = generate_numeric_token()
            MeterToken.objects.create(
                token=share_token,
                units=units,
                meter=receiver_meter,
                user=receiver_meter.user,
                is_used=False,
                source="SHARE",
                share_transaction_id=transaction_ref,
                share_sender=sender,
            )
            token_issued = True
        else:
            if not apply_units_to_meter(
                receiver_meter,
                units,
                ledger_type=MeterLedgerTransaction.TYPE_TRANSFER_IN,
                ledger_source=sender_meter.meter_no,
                payment_reference=transaction_ref,
            ):
                from admin.system_errors import record_system_error

                record_system_error(
                    "ThingsBoard / AMI",
                    f"Failed to deliver {units} kWh to meter {receiver_meter_no} via ThingsBoard",
                    user=sender,
                    reference_id=transaction_ref,
                )
                raise ShareFlowError("Failed to deliver units to AMI meter via ThingsBoard.")

        sender_account_wallet = AccountWallet.objects.filter(user=sender).order_by("-create_date").first()
        if sender_account_wallet is None:
            sender_account_wallet = AccountWallet.objects.create(
                user=sender,
                currency="USD",
                balance=Decimal("0.00"),
            )

        Share.objects.create(
            share_transaction_id=transaction_ref,
            wallet=sender_account_wallet,
            units=units,
            status="COMPLETED",
            meter_number=receiver_meter,
            share_transaction_reference=transaction_ref,
        )

        ShareTransaction.objects.filter(sender=sender, status="PENDING").update(
            status="CANCELLED",
            message="Cancelled — share completed in one step",
        )

        ShareTransaction.objects.create(
            share_transaction_id=transaction_ref,
            sender=sender,
            receiver=receiver_meter.user,
            units=units,
            meter_send=sender_meter,
            meter_receive=receiver_meter,
            direction="OUT",
            status="COMPLETED",
            verified_at=timezone.now(),
            message=(
                f"Shared {units} units from {sender_meter.meter_no} to {receiver_meter_no}"
                + (" (STS token issued)" if token_issued else " (AMI device top-up)")
                + f" via {channel}"
            ),
        )

        TransactionLog.objects.create(
            user=sender,
            transaction_type=TransactionType.UNIT_SHARE,
            units=units,
            status="COMPLETED",
            reference_id=transaction_ref,
            details={
                "receiver_meter": receiver_meter_no,
                "sender_meter": sender_meter.meter_no,
                "channel": channel,
            },
        )

        if token_issued and share_token:
            dispatch_task(
                handle_send_share_token,
                receiver_meter.user.id,
                share_token,
                str(units),
                receiver_meter_no,
                sender_meter=sender_meter.meter_no,
                sender_email=sender.email,
                sender_name=format_user_display_name(sender),
            )
        elif receiver_meter.architecture == Meter.ARCH_AMI:
            receiver_meter.refresh_from_db(fields=["units"])
            receiver_update = build_receiver_ami_share_update(
                meter=receiver_meter,
                units=units,
                transaction_id=transaction_ref,
                sender_user=sender,
                sender_meter_no=sender_meter.meter_no,
            )
            dispatch_task(handle_send_wallet_update, receiver_meter.user.id, receiver_update)

        sender_update = build_sender_share_confirmation(
            units=units,
            receiver_meter_no=receiver_meter_no,
            transaction_id=transaction_ref,
            wallet_balance_kwh=sender_wallet.balance,
            channel=channel,
            receiver_user=receiver_meter.user,
        )
        dispatch_task(handle_send_wallet_update, sender.id, sender_update)

    logger.info("Share completed (%s): %s kWh to %s", channel, units, receiver_meter_no)

    return {
        "success": True,
        "message": "Units shared successfully.",
        "transaction_id": transaction_ref,
        "units_shared": str(units),
        "new_sender_wallet_balance": str(sender_wallet.balance),
        "token_sent": token_issued,
        "share_token": share_token if token_issued else None,
        "receiver_architecture": receiver_meter.architecture,
        "receiver_name": recipient_display_name(receiver_meter.user),
        "receiver_meter": receiver_meter_no,
        "timestamp": timezone.now().isoformat(),
    }
