"""Stored consumption evidence only; no gateway calls or synthetic readings."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from meter.models import Meter, MeterDelivery, MeterUsageDaily, SimulatedTelemetry


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
