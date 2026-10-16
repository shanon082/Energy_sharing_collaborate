from django.db import transaction
from django.core.exceptions import ImproperlyConfigured
from django.http import Http404
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import ConsumerAccountPermission
from meter.bench_device import authenticate_device, redeem, acknowledge, device_session
from meter.energy_tokens import token_record
from meter.models import EnergyKeypadToken


class EnergyTokensView(APIView):
    permission_classes = [IsAuthenticated, ConsumerAccountPermission]

    def get(self, request):
        rows = EnergyKeypadToken.objects.filter(owner=request.user).select_related("allocation__purchase_intent", "allocation__loan_disbursement__loan_application")
        for key in ("allocation_id", "meter_id"):
            value = request.query_params.get(key)
            if value is not None:
                if len(value) > 19 or not value.isascii() or not value.isdigit() or not 0 < int(value) <= 2**63 - 1:
                    raise Http404
                rows = rows.filter(**{key: int(value)})
        try:
            response = Response({"tokens": [token_record(row) for row in rows.order_by("-created_at")[:100]], "bench_only": True})
        except ImproperlyConfigured:
            response = Response({"code": "ENERGY_TOKEN_STORAGE_UNAVAILABLE", "message": "Token storage needs operator configuration. Do not repeat payment."}, status=503)
        response["Cache-Control"] = "private, no-store"
        response["Referrer-Policy"] = "no-referrer"
        return response


@method_decorator(transaction.non_atomic_requests, name="dispatch")
@method_decorator(sensitive_post_parameters("token"), name="dispatch")
class BenchDeviceView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        device = authenticate_device(request)
        result = self.operation(device, request.data)
        response = Response(result)
        response["Cache-Control"] = "no-store"
        return response


class BenchRedeemView(BenchDeviceView):
    @staticmethod
    def operation(device, body):
        return {"command": redeem(device, body)}


class BenchAcknowledgeView(BenchDeviceView):
    @staticmethod
    def operation(device, body):
        return {"state": "APPLIED", "newly_applied": acknowledge(device, body), "application_environment": "SOFTWARE_BENCH"}


class BenchSessionView(BenchDeviceView):
    operation = staticmethod(device_session)
