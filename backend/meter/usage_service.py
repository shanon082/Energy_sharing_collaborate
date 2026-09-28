"""
AMI Energy Usage aggregation and reporting.

Data sources (priority):
  1. ThingsBoard telemetry timeseries (when tenant API + telemetry key configured)
  2. ThingsBoard daily webhook (POST /webhooks/thingsboard/daily-usage)
  3. Balance snapshots of `remaining_units` — usage between readings is
     max(0, prev_remaining - curr_remaining); increases are treated as top-ups.
  4. Development stub for meters with dev-* tokens
"""
from __future__ import annotations

import logging
import random
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db.models import Sum
from django.db.models.functions import ExtractMonth
from django.utils import timezone

from meter.models import Meter, MeterBalanceSnapshot, MeterUsageDaily
from meter.services import (
    query_latest_units_from_thingsboard,
    query_usage_timeseries_from_thingsboard,
    record_balance_snapshot,
)

logger = logging.getLogger(__name__)


def _today_local() -> date:
    return timezone.localdate()


def _date_range_for_period(period: str, year: int | None, month: int | None) -> tuple[date, date]:
    today = _today_local()
    period = (period or "week").lower()

    if period == "week":
        start = today - timedelta(days=6)
        return start, today

    if period == "month":
        if year and month:
            start = date(year, month, 1)
            if month == 12:
                end = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                end = date(year, month + 1, 1) - timedelta(days=1)
            return start, min(end, today)
        start = today.replace(day=1)
        return start, today

    if period == "year":
        y = year or today.year
        start = date(y, 1, 1)
        end = date(y, 12, 31)
        if y == today.year:
            end = today
        return start, end

    # default: last 7 days
    return today - timedelta(days=6), today


def user_has_ami_meter(user) -> bool:
    return Meter.objects.filter(user=user, architecture=Meter.ARCH_AMI).exists()


def get_user_ami_meters(user):
    return list(
        Meter.objects.filter(user=user, architecture=Meter.ARCH_AMI).order_by("create_date")
    )


def aggregate_daily_from_snapshots(meter: Meter, usage_date: date) -> Decimal | None:
    """Compute kWh used on usage_date from consecutive balance snapshots."""
    day_start = timezone.make_aware(datetime.combine(usage_date, datetime.min.time()))
    day_end = day_start + timedelta(days=1)

    prev = (
        MeterBalanceSnapshot.objects.filter(meter=meter, recorded_at__lt=day_start)
        .order_by("-recorded_at")
        .first()
    )
    day_snaps = list(
        MeterBalanceSnapshot.objects.filter(
            meter=meter,
            recorded_at__gte=day_start,
            recorded_at__lt=day_end,
        ).order_by("recorded_at")
    )

    if not prev and not day_snaps:
        return None

    total = Decimal("0")
    cursor = prev.remaining_kwh if prev else None

    for snap in day_snaps:
        if cursor is not None:
            delta = cursor - snap.remaining_kwh
            if delta > 0:
                total += delta
        cursor = snap.remaining_kwh

    if total <= 0 and not day_snaps:
        return None

    return total.quantize(Decimal("0.0001"))


def upsert_daily_usage(
    meter: Meter,
    usage_date: date,
    kwh_used: Decimal,
    source: str,
) -> MeterUsageDaily:
    obj, _ = MeterUsageDaily.objects.update_or_create(
        meter=meter,
        usage_date=usage_date,
        defaults={
            "kwh_used": max(Decimal("0"), kwh_used),
            "source": source,
        },
    )
    return obj


def sync_thingsboard_daily_usage(meter: Meter, start: date, end: date) -> int:
    """Pull daily kWh from ThingsBoard telemetry and store in MeterUsageDaily."""
    ok, msg, rows = query_usage_timeseries_from_thingsboard(meter, start, end)
    if not ok or not rows:
        if msg:
            logger.debug("TB usage sync skipped for %s: %s", meter.meter_no, msg)
        return 0

    count = 0
    for row in rows:
        usage_date = row["date"]
        kwh = Decimal(str(row["kwh_used"]))
        upsert_daily_usage(meter, usage_date, kwh, MeterUsageDaily.SOURCE_THINGSBOARD)
        count += 1
    return count


def ensure_dev_stub_usage(meter: Meter, start: date, end: date) -> None:
    """Seed plausible daily usage for dev-* tokens when no real data exists."""
    token = (meter.iot_device_token or "").strip()
    if not token.startswith("dev-"):
        return

    rng = random.Random(hash(meter.meter_no) ^ start.toordinal())
    current = start
    while current <= end:
        if not MeterUsageDaily.objects.filter(meter=meter, usage_date=current).exists():
            base = 1.2 + (current.weekday() / 6) * 0.8
            kwh = Decimal(str(round(base + rng.uniform(-0.3, 1.5), 2)))
            upsert_daily_usage(meter, current, kwh, MeterUsageDaily.SOURCE_STUB)
        current += timedelta(days=1)


def sync_meter_usage(meter: Meter, start: date, end: date) -> None:
    """Refresh daily usage rows for a meter over a date range."""
    sync_thingsboard_daily_usage(meter, start, end)

    current = start
    while current <= end:
        existing = MeterUsageDaily.objects.filter(meter=meter, usage_date=current).first()
        if existing and existing.source in (
            MeterUsageDaily.SOURCE_THINGSBOARD,
            MeterUsageDaily.SOURCE_WEBHOOK,
        ):
            current += timedelta(days=1)
            continue

        computed = aggregate_daily_from_snapshots(meter, current)
        if computed is not None and computed > 0:
            upsert_daily_usage(meter, current, computed, MeterUsageDaily.SOURCE_SNAPSHOT)
        current += timedelta(days=1)

    ensure_dev_stub_usage(meter, start, end)


def snapshot_meter_balance(meter: Meter) -> bool:
    """Read live remaining_units from ThingsBoard and store a snapshot."""
    if meter.architecture != Meter.ARCH_AMI:
        return False
    ok, msg, data = query_latest_units_from_thingsboard(meter)
    if not ok or not data:
        logger.debug("Snapshot failed for %s: %s", meter.meter_no, msg)
        return False
    record_balance_snapshot(
        meter,
        Decimal(str(data["units_kwh"])),
        source=data.get("source", "thingsboard"),
    )
    return True


def snapshot_all_ami_meters() -> int:
    count = 0
    for meter in Meter.objects.filter(architecture=Meter.ARCH_AMI, status=Meter.STATUS_ACTIVE):
        if snapshot_meter_balance(meter):
            count += 1
    return count


def available_usage_years(meter: Meter) -> list[int]:
    years = (
        MeterUsageDaily.objects.filter(meter=meter)
        .dates("usage_date", "year", order="DESC")
    )
    result = [d.year for d in years]
    if not result:
        result = [_today_local().year]
    return sorted(set(result), reverse=True)


def _build_summary(daily_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not daily_rows:
        return {
            "total_kwh": 0.0,
            "average_daily_kwh": 0.0,
            "peak_day_kwh": 0.0,
            "peak_day_date": None,
            "lowest_day_kwh": 0.0,
            "lowest_day_date": None,
            "days_with_data": 0,
        }

    values = [float(r["kwh_used"]) for r in daily_rows if r.get("kwh_used") is not None]
    if not values:
        return {
            "total_kwh": 0.0,
            "average_daily_kwh": 0.0,
            "peak_day_kwh": 0.0,
            "peak_day_date": None,
            "lowest_day_kwh": 0.0,
            "lowest_day_date": None,
            "days_with_data": 0,
        }

    peak_row = max(daily_rows, key=lambda r: float(r["kwh_used"]))
    low_row = min(daily_rows, key=lambda r: float(r["kwh_used"]))
    total = sum(values)

    return {
        "total_kwh": round(total, 2),
        "average_daily_kwh": round(total / len(values), 2),
        "peak_day_kwh": round(float(peak_row["kwh_used"]), 2),
        "peak_day_date": peak_row["date"],
        "lowest_day_kwh": round(float(low_row["kwh_used"]), 2),
        "lowest_day_date": low_row["date"],
        "days_with_data": len(values),
    }


def _fill_missing_days(start: date, end: date, rows: list[MeterUsageDaily]) -> list[dict]:
    by_date = {r.usage_date: r for r in rows}
    result = []
    current = start
    while current <= end:
        row = by_date.get(current)
        result.append(
            {
                "date": current.isoformat(),
                "kwh_used": float(row.kwh_used) if row else 0.0,
                "source": row.source if row else None,
            }
        )
        current += timedelta(days=1)
    return result


def get_power_usage_report(
    user,
    meter_no: str | None,
    period: str = "week",
    year: int | None = None,
    month: int | None = None,
) -> dict[str, Any]:
    ami_meters = get_user_ami_meters(user)
    if not ami_meters:
        return {
            "eligible": False,
            "message": "This is only for AMI meter users.",
        }

    if meter_no:
        meter = next((m for m in ami_meters if m.meter_no == meter_no), None)
        if not meter:
            return {"eligible": False, "message": "AMI meter not found on your account."}
    else:
        meter = ami_meters[0]

    start, end = _date_range_for_period(period, year, month)
    sync_meter_usage(meter, start, end)

    rows = list(
        MeterUsageDaily.objects.filter(
            meter=meter,
            usage_date__gte=start,
            usage_date__lte=end,
        ).order_by("usage_date")
    )
    daily = _fill_missing_days(start, end, rows)
    summary = _build_summary([d for d in daily if d["kwh_used"] > 0])

    sources = {r.source for r in rows if r.source}
    if MeterUsageDaily.SOURCE_THINGSBOARD in sources or MeterUsageDaily.SOURCE_WEBHOOK in sources:
        data_source = "thingsboard"
    elif MeterUsageDaily.SOURCE_STUB in sources:
        data_source = "stub"
    else:
        data_source = "snapshot"

    monthly_breakdown = []
    if period == "year":
        agg = (
            MeterUsageDaily.objects.filter(
                meter=meter,
                usage_date__gte=start,
                usage_date__lte=end,
            )
            .annotate(month=ExtractMonth("usage_date"))
            .values("month")
            .annotate(
                total=Sum("kwh_used"),
                avg=Sum("kwh_used"),  # simplified; daily avg shown in UI from total/days
            )
            .order_by("month")
        )
        month_names = [
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        ]
        for item in agg:
            m = int(item["month"])
            monthly_breakdown.append(
                {
                    "month": m,
                    "label": month_names[m - 1],
                    "total_kwh": round(float(item["total"] or 0), 2),
                    "average_daily_kwh": round(float(item["total"] or 0) / 30, 2),
                }
            )

    return {
        "eligible": True,
        "meter_no": meter.meter_no,
        "meter_label": meter.label or "Home",
        "period": period,
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "summary": summary,
        "daily": daily,
        "monthly": monthly_breakdown,
        "available_years": available_usage_years(meter),
        "available_meters": [
            {"meter_no": m.meter_no, "label": m.label or "Home"}
            for m in ami_meters
        ],
        "data_source": data_source,
    }


def format_weekly_usage_ussd(report: dict[str, Any]) -> tuple[bool, str]:
    """
    Compact text-only weekly summary for USSD (character-conscious).
    Returns (ok, message).
    """
    if not report.get("eligible"):
        return False, report.get("message", "This is only for AMI meter users.")

    summary = report.get("summary") or {}
    daily = report.get("daily") or []
    meter_no = report.get("meter_no", "")

    day_abbr = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    lines = [
        "Energy Usage (7 days)",
        f"Meter {meter_no}",
        f"Total: {summary.get('total_kwh', 0)} kWh",
        f"Avg/day: {summary.get('average_daily_kwh', 0)} kWh",
        f"Peak: {summary.get('peak_day_kwh', 0)} kWh",
    ]

    peak_date = summary.get("peak_day_date")
    if peak_date:
        try:
            dd = date.fromisoformat(str(peak_date)[:10])
            lines[-1] += f" ({day_abbr[dd.weekday()]})"
        except ValueError:
            pass

    lines.append("---")
    for row in daily:
        kwh = float(row.get("kwh_used") or 0)
        if kwh <= 0:
            continue
        try:
            dd = date.fromisoformat(str(row["date"])[:10])
            lines.append(f"{day_abbr[dd.weekday()]} {kwh:.1f}")
        except (ValueError, KeyError):
            lines.append(f"{row.get('date', '?')} {kwh:.1f}")

    if len(lines) <= 6:
        lines.append("No usage recorded yet.")

    return True, "\n".join(lines)
