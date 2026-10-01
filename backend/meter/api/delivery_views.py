"""Owner-facing allocation view and isolated simulated-device messages."""

import uuid
from decimal import InvalidOperation

from django.contrib.auth.hashers import check_password
from django.core.exceptions import ObjectDoesNotExist
from django.utils.dateparse import parse_datetime
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from meter.allocation_service import AllocationError, entitlement_summary, reserve_for_delivery
from meter.models import Meter, SimulatedMeter
from meter import simulation as simulation_module
from meter.simulation import (
    acknowledge_application, record_telemetry, require_simulation,
)


def reserve_delivery_response(request):
    try:
        require_simulation()
    except simulation_module.SimulationError as exc:
        return Response({"code": "DEVICE_PROTOCOL_UNAVAILABLE", "message": str(exc)}, status=503)
    meter_no = str(request.data.get("meter_no") or "").strip()
    if not meter_no:
        return Response({"error": "Select the intended AMI meter explicitly."}, status=400)
    meter = Meter.objects.filter(
        user=request.user, meter_no=meter_no,
        status=Meter.STATUS_ACTIVE, architecture=Meter.ARCH_AMI,
    ).first()
    if meter is None:
        return Response({
            "code": "ENTITLEMENT_UNAVAILABLE",
            "message": "Choose an active AMI meter assigned to your account.",
        }, status=409)
    if not SimulatedMeter.objects.filter(meter=meter).exists():
        return Response({
            "code": "SIMULATOR_NOT_ENROLLED",
            "message": "This active AMI meter is not enrolled in the simulator.",
        }, status=409)
    try:
        deliveries = reserve_for_delivery(
            owner=request.user, meter_no=meter_no,
            amount_kwh=request.data.get("amount"),
            request_id=request.data.get("request_id"),
        )
    except AllocationError as exc:
        return Response({"code": "ENTITLEMENT_UNAVAILABLE", "message": str(exc)}, status=409)
    return Response({
        "status": "QUEUED",
        "message": "Energy reserved for simulated delivery. Meter application is not confirmed yet.",
        "meter_no": meter_no,
        "request_id": str(deliveries[0].request_id) if deliveries[0].request_id else None,
        "deliveries": [
            {"id": row.pk, "command_id": str(row.command_id),
             "amount_kwh": str(row.amount_kwh), "status": row.status}
            for row in deliveries
        ],
    }, status=202)


class DeliveryRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return reserve_delivery_response(request)


class AllocationStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        meter_no = str(request.query_params.get("meter_no") or "").strip()
        meter = None
        if meter_no:
            meter = Meter.objects.filter(user=request.user, meter_no=meter_no).first()
            if meter is None:
                return Response({"error": "Meter not found or not owned by you."}, status=404)
        summary = entitlement_summary(request.user, meter)
        devices = SimulatedMeter.objects.filter(meter__user=request.user)
        if meter is not None:
            devices = devices.filter(meter=meter)
        last_contact = devices.filter(last_contact_at__isnull=False).order_by("-last_contact_at").values_list(
            "last_contact_at", flat=True,
        ).first()
        return Response({
            "unit": "kWh", "quantum_kwh": "0.01",
            "meter_no": meter_no or None,
            **{key: str(value) for key, value in summary.items()},
            "last_meter_contact": last_contact.isoformat() if last_contact else None,
            "delivery_environment": "SIMULATOR" if require_simulation_available() else "UNAVAILABLE",
        })


def require_simulation_available():
    try:
        require_simulation()
        return True
    except simulation_module.SimulationError:
        return False


def _authenticated_device(request):
    require_simulation()
    raw_id = request.headers.get("X-Sim-Device-Id")
    token = request.headers.get("X-Sim-Device-Token")
    try:
        device_id = uuid.UUID(str(raw_id))
    except (TypeError, ValueError):
        return None
    if not token:
        return None
    device = SimulatedMeter.objects.filter(device_id=device_id).first()
    if device is None or not check_password(token, device.credential_hash):
        return None
    return device


class SimulatorAcknowledgementView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            device = _authenticated_device(request)
        except simulation_module.SimulationError:
            return Response({"code": "SIMULATION_DISABLED"}, status=404)
        if device is None:
            return Response({"code": "DEVICE_UNAUTHORIZED"}, status=401)
        if request.data.get("contract_version") != 1:
            return Response({"code": "CONTRACT_VERSION_UNSUPPORTED"}, status=400)
        try:
            delivery_id = int(request.data.get("delivery_id"))
            command_id = uuid.UUID(str(request.data.get("command_id")))
            delivery, changed = acknowledge_application(
                device_id=device.device_id, command_id=command_id,
                delivery_id=delivery_id, amount_kwh=request.data.get("amount_kwh"),
            )
        except (TypeError, ValueError, InvalidOperation, ObjectDoesNotExist, simulation_module.SimulationError):
            return Response({"code": "ACK_BINDING_MISMATCH"}, status=409)
        return Response({"status": delivery.status, "newly_applied": changed})


class SimulatorTelemetryView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            device = _authenticated_device(request)
        except simulation_module.SimulationError:
            return Response({"code": "SIMULATION_DISABLED"}, status=404)
        if device is None:
            return Response({"code": "DEVICE_UNAUTHORIZED"}, status=401)
        if request.data.get("contract_version") != 1:
            return Response({"code": "CONTRACT_VERSION_UNSUPPORTED"}, status=400)
        try:
            event_id = uuid.UUID(str(request.data.get("event_id")))
            boot_id = uuid.UUID(str(request.data.get("boot_id")))
            sequence = int(request.data.get("sequence"))
            cumulative_wh = int(request.data.get("cumulative_wh"))
            measured_at = parse_datetime(str(request.data.get("measured_at")))
            if measured_at is None or measured_at.tzinfo is None:
                raise ValueError
            event, created = record_telemetry(
                device=device, event_id=event_id, boot_id=boot_id,
                sequence=sequence, cumulative_wh=cumulative_wh,
                measured_at=measured_at,
                reported_relay_state=str(request.data.get("reported_relay_state") or ""),
            )
        except (TypeError, ValueError, simulation_module.SimulationError):
            return Response({"code": "TELEMETRY_INVALID"}, status=400)
        return Response({
            "event_id": str(event.event_id), "classification": event.classification,
            "duplicate": not created, "received_at": event.received_at.isoformat(),
        })
