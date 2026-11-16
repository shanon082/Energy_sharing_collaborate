"""Only authenticated, explicitly commissioned AC lab firmware may mutate here."""
import json
from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from meter import prototype_device as service


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate field')
        result[key] = value
    return result


@method_decorator(transaction.non_atomic_requests, name='dispatch')
@method_decorator(sensitive_post_parameters(), name='dispatch')
class PrototypeView(APIView):
    authentication_classes = []  # Consumer JWT/session credentials are never device credentials.
    permission_classes = [AllowAny]
    parser_classes = []

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        response['Referrer-Policy'] = 'no-referrer'
        return response

    @sensitive_variables()
    def post(self, request):
        device = service.authenticate(request)
        if request.content_type != 'application/json':
            service.fail('REQUEST_INVALID', 'Use application/json.', 400)
        raw = request.stream.read(4097) if request.stream is not None else b""
        if len(raw) > 4096:
            service.fail('REQUEST_TOO_LARGE', 'Request exceeds the firmware limit.', 413)
        try:
            body = json.loads(raw, object_pairs_hook=unique_object)
        except (ValueError, UnicodeError, RecursionError):
            service.fail('REQUEST_INVALID', 'Invalid JSON object.', 400)
        return Response(self.operation(device, body))


class PrototypeSessionView(PrototypeView):
    operation = staticmethod(service.session)


class PrototypeRedeemView(PrototypeView):
    operation = staticmethod(service.redeem)


class PrototypeAckView(PrototypeView):
    operation = staticmethod(service.acknowledge)


class PrototypeTelemetryView(PrototypeView):
    operation = staticmethod(service.telemetry)
