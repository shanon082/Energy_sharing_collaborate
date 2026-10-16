"""Stored consumption evidence only; no gateway calls or synthetic readings."""

from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import ConsumerAccountPermission
from backend.mobile_reads import read_page
from meter.allocation_service import entitlement_summary
from meter.api.delivery_views import require_simulation_available
from meter.models import (
    Meter, MeterDelivery, MeterNotification, MeterUsageDaily, SimulatedMeter, SimulatedTelemetry,
)


def selected_meter(request):
    """New clients bind a stable ID; retain the existing number-only read alias."""
    meter_id = request.query_params.get("meter_id")
    meter_no = str(request.query_params.get("meter_no") or "").strip()
    if meter_id is not None:
        if len(str(meter_id)) > 19 or not str(meter_id).isdigit() or not 0 < int(meter_id) < 2**63:
            raise ValidationError({"meter_id": "Use a positive meter ID."})
        meter = get_object_or_404(Meter, pk=int(meter_id), user=request.user, is_deleted=False)
        if meter_no and meter.meter_no != meter_no:
            raise ValidationError({"meter_no": "Meter number and selected ID do not match."})
        return meter
    if not meter_no:
        raise ValidationError({"code": "METER_REQUIRED"})
    return get_object_or_404(Meter, user=request.user, meter_no=meter_no, is_deleted=False)


def mobile_meter_record(meter):
    declared = getattr(meter, "sandbox_enrollment", None)
    # Legacy units, IP addresses and device credentials are deliberately absent.
    return {"id": meter.pk, "meter_number": meter.meter_no, "label": meter.label,
            "architecture": meter.architecture, "status": meter.status,
            **({"sandbox_inventory": True} if meter.sandbox_inventory else {}),
            **({"ownership_provenance": "SELF_DECLARED", "enrolled_at": declared.enrolled_at.isoformat(),
                "hardware_connection": "PENDING"} if declared else {})}


def application_confirmed(delivery):
    if delivery.transport == "KEYPAD_BENCH":
        receipt = getattr(delivery, "bench_receipt", None)
        return bool(delivery.status == MeterDelivery.APPLIED and delivery.applied_at and receipt
                    and receipt.device_id == delivery.bench_device_id
                    and receipt.payload_digest == delivery.command_payload.get("payload_digest"))
    command = getattr(delivery, "simulated_command", None)
    return bool(delivery.status == MeterDelivery.APPLIED and delivery.applied_at is not None
        and command is not None and command.command_id == delivery.command_id
        and command.amount_kwh == delivery.amount_kwh
        and command.device.meter_id == delivery.allocation.meter_id)


class MobileMeterListView(APIView):
    permission_classes = [IsAuthenticated, ConsumerAccountPermission]

    def get(self, request):
        rows = Meter.objects.filter(user=request.user, is_deleted=False).order_by("create_date", "pk")
        meters = [mobile_meter_record(row) for row in rows]
        return Response({"success": True, "data": {"has_meter": bool(meters), "meters": meters}})


class MobileMeterDashboardView(APIView):
    permission_classes = [IsAuthenticated, ConsumerAccountPermission]

    def get(self, request, meter_id):
        meter = get_object_or_404(Meter, pk=meter_id, user=request.user, is_deleted=False)
        device = SimulatedMeter.objects.filter(meter=meter).first()
        simulated = device is not None and require_simulation_available()
        last_contact = device.last_contact_at if device else None
        stale_after = getattr(settings, "MOBILE_METER_STALE_SECONDS", 120)
        stale = last_contact is None or (timezone.now() - last_contact).total_seconds() > stale_after
        # Simulator consumption is the accepted boot-aware delta ledger, not an
        # arbitrary cumulative counter subtracted from cloud purchases.
        remaining = max(0, int(device.applied_kwh * Decimal("1000")) - device.consumed_wh) if device else None
        uncertain = bool(device and (device.reset_count > 0 or device.telemetry.filter(
            classification__in=["INITIAL", "RESET"], cumulative_wh__gt=0,
        ).exists() or device.telemetry.filter(classification="DISCONTINUITY").exists()))
        return Response({
            "meter": mobile_meter_record(meter),
            "unit": "kWh", "quantum_kwh": "0.01",
            "observed_at": timezone.now().isoformat(), "stale_after_seconds": stale_after,
            "contact_status": "UNAVAILABLE" if last_contact is None else "STALE" if stale else "RECENT",
            "meter_reported_remaining_wh": None,  # physical contract not implemented
            "simulator_remaining_wh": str(remaining) if remaining is not None and not uncertain else None,
            "simulator_remaining_basis": "APPLIED_MINUS_ACCEPTED_DELTAS" if device else None,
            "consumption_reconciliation_required": uncertain,
            "reported_relay_state": device.reported_relay_state if device else None,
            "relay_source": "SIMULATOR" if device else "UNAVAILABLE",
            "last_measurement_at": device.last_measured_at.isoformat() if device and device.last_measured_at else None,
            **{key: str(value) for key, value in entitlement_summary(request.user, meter).items()},
            "last_meter_contact": device.last_contact_at.isoformat()
                if device is not None and device.last_contact_at else None,
            "delivery_environment": "SIMULATOR" if simulated else "UNAVAILABLE",
            "contact_source": "SIMULATOR" if device is not None else "UNAVAILABLE",
        })


class MobileConsumptionHistoryView(APIView):
    permission_classes = [IsAuthenticated, ConsumerAccountPermission]

    def get(self, request):
        if request.user.user_role != User.CLIENT:
            return Response({"code": "CONSUMER_ONLY"}, status=403)
        meter = selected_meter(request)
        daily = MeterUsageDaily.objects.filter(meter=meter).order_by("-usage_date")[:30]
        telemetry = SimulatedTelemetry.objects.filter(device__meter=meter).order_by("-received_at")[:30]
        return Response({
            "meter_no": meter.meter_no, "meter": mobile_meter_record(meter),
            "history_scope": "CURRENT_ASSIGNED_METER",
            "consumer_attribution_available": False,
            "daily_usage": [{
                "date": row.usage_date.isoformat(), "kwh": str(row.kwh_used),
                "source": row.source,
            } for row in daily],
            "simulator_telemetry": [{
                "event_id": str(row.event_id), "cumulative_wh": row.cumulative_wh,
                "cumulative_wh_exact": str(row.cumulative_wh),
                "boot_id": str(row.boot_id), "sequence_exact": str(row.sequence),
                "reported_relay_state": row.reported_relay_state,
                "measured_at": row.measured_at.isoformat(),
                "received_at": row.received_at.isoformat(),
                "classification": row.classification,
            } for row in telemetry],
        })


class MobileDeliveryHistoryView(APIView):
    permission_classes = [IsAuthenticated, ConsumerAccountPermission]

    def get(self, request):
        if request.user.user_role != User.CLIENT:
            return Response({"code": "CONSUMER_ONLY"}, status=403)
        meter = selected_meter(request)
        rows, page = read_page(MeterDelivery.objects.filter(allocation__owner=request.user,
                          allocation__meter=meter).select_related("allocation", "simulated_command__device"), request.query_params)
        return Response({"meter_no": meter.meter_no, "meter": mobile_meter_record(meter),
                         "pagination": page, "deliveries": [{
            "id": row.pk, "command_id": str(row.command_id),
            "request_id": str(row.request_id) if row.request_id else None,
            "amount_kwh": str(row.amount_kwh), "status": row.status,
            "allocation_id": row.allocation_id,
            "source": "PURCHASE" if row.allocation.purchase_intent_id else "SANDBOX_LOAN" if row.allocation.sandbox_loan_id else "APPROVED_LOAN",
            "application_confirmed": application_confirmed(row),
            "environment": "SOFTWARE_BENCH" if row.transport == "KEYPAD_BENCH" else "SIMULATOR" if hasattr(row, "simulated_command") else "UNCONFIRMED",
            "created_at": row.created_at.isoformat(),
            "applied_at": row.applied_at.isoformat() if row.applied_at else None,
        } for row in rows]})


class MobileNotificationView(APIView):
    """Owner-bound alert metadata; changing read state never changes finances."""
    permission_classes = [IsAuthenticated, ConsumerAccountPermission]

    def get(self, request):
        queryset = MeterNotification.objects.filter(user=request.user)
        unread = request.query_params.get("unread", "false")
        if unread not in {"true", "false"}:
            raise ValidationError({"unread": "Use true or false."})
        if unread == "true":
            queryset = queryset.filter(is_read=False)
        rows, page = read_page(queryset.select_related("meter"), request.query_params)
        return Response({"notifications": [{
            "id": row.pk, "notification_type": row.notification_type,
            "message": row.message, "units_kwh": str(row.units_kwh),
            "occurred_at": row.occurred_at.isoformat(), "is_read": row.is_read,
            "meter_no": row.meter.meter_no if row.meter_id else None,
        } for row in rows], "pagination": page,
            "unread_count": MeterNotification.objects.filter(user=request.user, is_read=False).count()})

    def patch(self, request):
        if not isinstance(request.data, dict) or set(request.data) != {"ids"}:
            raise ValidationError({"ids": "Supply only explicit notification IDs."})
        field = serializers.ListField(child=serializers.IntegerField(min_value=1),
                                      allow_empty=False, max_length=50)
        ids = field.run_validation(request.data["ids"])
        queryset = MeterNotification.objects.filter(user=request.user, pk__in=ids)
        if queryset.count() != len(set(ids)):
            return Response({"code": "NOTIFICATION_NOT_FOUND"}, status=404)
        updated = queryset.filter(is_read=False).update(is_read=True)
        return Response({"marked_read": updated})


class MobilePurchaseQuoteView(APIView):
    """Current tariff preview, never a payment or promised allocation."""
    permission_classes = [IsAuthenticated, ConsumerAccountPermission]

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
        can_buy, reason = user_can_purchase_units(request.user, reconcile=False)
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
