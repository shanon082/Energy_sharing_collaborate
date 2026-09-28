"""Share completion emails and message text (USSD / web)."""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from django.utils import timezone

from meter.models import Meter

if TYPE_CHECKING:
    from accounts.models import User


def format_user_display_name(user) -> str:
    """Full name for emails; fall back to email or phone."""
    if user is None:
        return "Unknown sender"
    first = (getattr(user, "first_name", "") or "").strip()
    last = (getattr(user, "last_name", "") or "").strip()
    full = f"{first} {last}".strip()
    if full:
        return full
    email = (getattr(user, "email", "") or "").strip()
    if email:
        return email
    phone = getattr(user, "phone_number", None)
    if phone:
        return str(phone)
    return "gPAWA customer"


def format_user_contact_lines(user, *, prefix: str = "") -> list[str]:
    """Optional email / phone lines for notification bodies."""
    if user is None:
        return []
    lines = []
    label = f"{prefix} " if prefix else ""
    name = format_user_display_name(user)
    lines.append(f"{label}Name: {name}")
    email = (getattr(user, "email", "") or "").strip()
    if email:
        lines.append(f"{label}Email: {email}")
    phone = getattr(user, "phone_number", None)
    if phone:
        lines.append(f"{label}Phone: {phone}")
    return lines


def get_meter_balance_display(meter: Meter) -> dict:
    """
    Prefer live ThingsBoard remaining_units for AMI meters; fall back to gPAWA ledger.
    """
    ledger_kwh = float(meter.units or 0)
    result = {
        "ledger_kwh": ledger_kwh,
        "live_kwh": None,
        "display": f"{ledger_kwh:.2f} kWh",
        "source": "ledger",
    }
    if meter.architecture != Meter.ARCH_AMI:
        return result

    from meter.services import query_latest_units_from_thingsboard

    ok, _msg, data = query_latest_units_from_thingsboard(meter)
    if ok and data and data.get("units_kwh") is not None:
        live = float(data["units_kwh"])
        result.update(
            {
                "live_kwh": live,
                "display": f"{live:.2f} kWh (live ThingsBoard)",
                "source": "thingsboard",
            }
        )
    else:
        result["display"] = f"{ledger_kwh:.2f} kWh (app ledger; live reading unavailable)"
    return result


def build_sender_share_confirmation(
    *,
    units,
    receiver_meter_no: str,
    transaction_id: str,
    wallet_balance_kwh,
    channel: str = "WEB",
    receiver_user=None,
) -> str:
    units = Decimal(str(units))
    balance = Decimal(str(wallet_balance_kwh))
    lines = [
        "Share completed successfully.",
        f"Channel: {channel}",
        f"Units shared: {float(units):.2f} kWh",
        f"To meter: {receiver_meter_no}",
    ]
    if receiver_user is not None:
        lines.extend(format_user_contact_lines(receiver_user, prefix="Recipient"))
    lines.extend(
        [
            f"Transaction ID: {transaction_id}",
            f"Your wallet balance remaining: {float(balance):.2f} kWh",
            f"Date: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ]
    )
    return "\n".join(lines)


def build_receiver_ami_share_update(
    *,
    meter: Meter,
    units,
    transaction_id: str,
    sender_user=None,
    sender_meter_no: str | None = None,
) -> str:
    units = Decimal(str(units))
    balance = get_meter_balance_display(meter)
    lines = [
        "You received a unit share on gPAWA.",
        "",
        "--- Shared by ---",
    ]
    lines.extend(format_user_contact_lines(sender_user))
    if sender_meter_no:
        lines.append(f"Sender meter: {sender_meter_no}")
    lines.extend(
        [
            "",
            "--- Your meter ---",
            f"Units applied: {float(units):.2f} kWh",
            f"Your meter: {meter.meter_no} (AMI)",
            f"Transaction ID: {transaction_id}",
            f"Current meter balance: {balance['display']}",
        ]
    )
    if balance["source"] == "thingsboard" and balance["live_kwh"] is not None:
        lines.append(f"gPAWA delivery ledger: {balance['ledger_kwh']:.2f} kWh")
    lines.append(f"Date: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return "\n".join(lines)
