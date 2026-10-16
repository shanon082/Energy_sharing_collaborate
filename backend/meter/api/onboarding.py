"""Physical declarations require review; sandbox uses explicit prototype ownership."""
from django.conf import settings
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import ConsumerAccountPermission
from meter.models import Meter, MeterEnrollmentRequest
from meter.validators import validate_meter_no
from meter.sandbox_enrollment import enroll_sandbox_meter, OWNERSHIP_NOTICE, normalized_number


class EnrollmentSerializer(serializers.Serializer):
    meter_no = serializers.CharField(max_length=100)

    def validate_meter_no(self, value):
        valid, result = validate_meter_no(value)
        if not valid or any(ord(char) < 32 for char in result):
            raise serializers.ValidationError("Enter your 11-digit meter number.")
        return result

    def to_internal_value(self, data):
        if isinstance(data, dict):
            normalized_number(data.get("meter_no"))
        return super().to_internal_value(data)


def enrollment_record(row, owned_numbers):
    review = getattr(row, "review", None)
    transition = getattr(row, "sandbox_transition", None)
    return {"id": str(row.request_id), "meter_number": row.meter_no,
            "status": ("REJECTED" if review and review.decision == "REJECTED" else
                       "SELF_DECLARED" if transition else "LINKED" if row.meter_no in owned_numbers else
                       "ASSIGNMENT_UNAVAILABLE" if review else "PENDING"),
            "decision_reason": review.consumer_reason if review else None,
            **({"transitioned_at": transition.enrolled_at.isoformat(), "ownership_provenance": "SELF_DECLARED"} if transition else {}),
            "requested_at": row.created_at.isoformat()}


class MeterEnrollmentView(APIView):
    permission_classes = [IsAuthenticated, ConsumerAccountPermission]

    def post(self, request):
        if getattr(settings, "CONSUMER_SANDBOX_ENABLED", False) is True:
            return sandbox_enrollment_response(request)
        # Do not look up the entered number in the meter inventory. The response
        # must not disclose whether an unassigned/foreign meter exists.
        serializer = EnrollmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row, _ = MeterEnrollmentRequest.objects.get_or_create(
            owner=request.user, meter_no=serializer.validated_data["meter_no"],
        )
        owned_numbers = set(Meter.objects.filter(user=request.user, status=Meter.STATUS_ACTIVE).values_list("meter_no", flat=True))
        record = enrollment_record(row, owned_numbers)
        message = ("Request recorded. Staff must verify and assign the meter before access is available."
                   if record["status"] == "PENDING" else
                   "Existing request retrieved. Check its final decision and current assignment.")
        return Response({"success": True, "status": record["status"], "request_id": str(row.request_id),
                         "message": message},
                        status=202)


def sandbox_enrollment_response(request):
    from meter.api.mobile_views import mobile_meter_record
    serializer = EnrollmentSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    meter, created = enroll_sandbox_meter(request.user, serializer.validated_data["meter_no"])
    declared = getattr(meter, "sandbox_enrollment", None)
    return Response({"success": True, "status": "SELF_DECLARED" if declared else "LINKED",
        "meter": mobile_meter_record(meter), "created": created,
        "message": OWNERSHIP_NOTICE if declared else "Existing authorized prototype meter retrieved; no ownership evidence was changed."},
        status=201 if created else 200)


class SandboxMeterEnrollmentView(APIView):
    permission_classes = [IsAuthenticated, ConsumerAccountPermission]

    def post(self, request):
        return sandbox_enrollment_response(request)


class MobileOnboardingView(APIView):
    permission_classes = [IsAuthenticated, ConsumerAccountPermission]

    def get(self, request):
        from meter.api.mobile_views import mobile_meter_record
        meters = list(Meter.objects.filter(user=request.user, is_deleted=False).order_by("pk"))
        active_numbers = {meter.meter_no for meter in meters if meter.status == Meter.STATUS_ACTIVE}
        rows = MeterEnrollmentRequest.objects.filter(owner=request.user).select_related("review", "sandbox_transition").order_by("-created_at")[:30]
        return Response({"needs_meter": not bool(active_numbers), "meters": [mobile_meter_record(m) for m in meters],
                         "sandbox_self_enrollment": getattr(settings, "CONSUMER_SANDBOX_ENABLED", False) is True,
                         "phone_ownership_verified": False,
                         "requests": [enrollment_record(row, active_numbers) for row in rows]})
