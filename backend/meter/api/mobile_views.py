"""Stored consumption evidence only; no gateway calls or synthetic readings."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from meter.models import Meter, MeterDelivery, MeterUsageDaily, SimulatedTelemetry
from decimal import Decimal, InvalidOperation
from django.utils import timezone


class MobileConsumptionHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.user_role != User.CLIENT:
            return Response({"code": "CONSUMER_ONLY"}, status=403)
        meter_no = str(request.query_params.get("meter_no") or "").strip()
        if not meter_no:
            return Response({"code": "METER_REQUIRED"}, status=400)
        meter = Meter.objects.filter(user=request.user, meter_no=meter_no, is_deleted=False).first()
        if meter is None:
            return Response({"code": "METER_NOT_FOUND"}, status=404)
        daily = MeterUsageDaily.objects.filter(meter=meter).order_by("-usage_date")[:30]
        telemetry = SimulatedTelemetry.objects.filter(device__meter=meter).order_by("-received_at")[:30]
        return Response({
            "meter_no": meter_no,
            "daily_usage": [{
                "date": row.usage_date.isoformat(), "kwh": str(row.kwh_used),
                "source": row.source,
            } for row in daily],
            "simulator_telemetry": [{
                "event_id": str(row.event_id), "cumulative_wh": row.cumulative_wh,
                "measured_at": row.measured_at.isoformat(),
                "received_at": row.received_at.isoformat(),
                "classification": row.classification,
            } for row in telemetry],
        })


class MobileDeliveryHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.user_role != User.CLIENT:
            return Response({"code": "CONSUMER_ONLY"}, status=403)
        meter_no = str(request.query_params.get("meter_no") or "").strip()
        if not meter_no:
            return Response({"code": "METER_REQUIRED"}, status=400)
        meter = Meter.objects.filter(user=request.user, meter_no=meter_no, is_deleted=False).first()
        if meter is None:
            return Response({"code": "METER_NOT_FOUND"}, status=404)
        rows = MeterDelivery.objects.filter(allocation__owner=request.user,
                                            allocation__meter=meter).order_by("-created_at")[:50]
        return Response({"meter_no": meter_no, "deliveries": [{
            "id": row.pk, "command_id": str(row.command_id),
            "request_id": str(row.request_id) if row.request_id else None,
            "amount_kwh": str(row.amount_kwh), "status": row.status,
            "created_at": row.created_at.isoformat(),
            "applied_at": row.applied_at.isoformat() if row.applied_at else None,
        } for row in rows]})


class MobilePurchaseQuoteView(APIView):
    """Current tariff preview, never a payment or promised allocation."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.user_role != User.CLIENT:
            return Response({"code": "CONSUMER_ONLY"}, status=403)
        from loan.services import user_can_purchase_units
        from utils.billing import (
            calculate_units_from_payment, get_active_domestic_tariff,
            get_minimum_payment_for_units,
        )
        try:
            amount = Decimal(str(request.data.get("amount")))
        except (InvalidOperation, TypeError, ValueError):
            amount = Decimal("0")
        if not amount.is_finite() or amount <= 0 or amount != amount.to_integral_value():
            return Response({"error": "Use a positive whole-UGX amount."}, status=400)
        meter_no = str(request.data.get("meter_no") or "").strip()
        meter = Meter.objects.filter(user=request.user, meter_no=meter_no,
                                     status=Meter.STATUS_ACTIVE, is_deleted=False).first()
        if meter is None:
            return Response({"code": "METER_UNAVAILABLE"}, status=409)
        can_buy, reason = user_can_purchase_units(request.user)
        if not can_buy:
            return Response({"code": "PURCHASE_BLOCKED", "message": reason}, status=409)
        tariff = get_active_domestic_tariff()
        if tariff is None:
            return Response({"code": "TARIFF_POLICY_REQUIRED",
                             "message": "A current domestic tariff is required for a mobile quote."}, status=409)
        units, bill = calculate_units_from_payment(
            amount, request.user, tariff=tariff, apply_deductions=False,
        )
        if units <= 0:
            return Response({"code": "PURCHASE_BELOW_MINIMUM",
                             "minimum_payment_ugx": str(get_minimum_payment_for_units(request.user, tariff))},
                            status=409)
        return Response({
            "amount_ugx": str(amount), "meter_no": meter_no,
            "estimated_energy_kwh": str(units), "estimated_billed_ugx": str(bill.total),
            "estimated_residual_ugx": str(amount - bill.total),
            "tariff_id": tariff.pk, "tariff_code": tariff.tariff_code,
            "quoted_at": timezone.now().isoformat(), "binding": False,
        })
