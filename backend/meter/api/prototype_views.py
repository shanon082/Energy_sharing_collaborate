"""Only authenticated, explicitly commissioned AC lab firmware may mutate here."""
import json
from django.db import transaction
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from meter import prototype_device as service
from meter.diagnostics import trace_request, mark_stage, safe_code, safe_trace, log_result


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

    def operation_options(self, request):
        return {}

    def dispatch(self, request, *args, **kwargs):
        operation = 'ack' if self.operation.__name__ == 'acknowledge' else self.operation.__name__
        with trace_request(request, operation) as self.diagnostic:
            try:
                response = super().dispatch(request, *args, **kwargs)
                # Keep serialization failures inside the redacted diagnostic boundary.
                if hasattr(response, 'render'):
                    stage = self.diagnostic['stage']
                    self.diagnostic['stage'] = 'response_serialization'
                    response.render()
                    self.diagnostic['stage'] = stage
                data = getattr(response, 'data', None)
                log_result(self.diagnostic, response.status_code,
                           self.diagnostic.get('result_code', safe_code(data, response.status_code)), data)
                return response
            except Exception as exc:
                self.diagnostic['traceback'] = safe_trace(exc)
                log_result(self.diagnostic, 500, 'INTERNAL_ERROR')
                response = JsonResponse({'code': 'INTERNAL_ERROR', 'message': 'Device request failed; share the request ID with the operator.',
                                         'request_id': self.diagnostic['request_id']}, status=500)
                response['X-Request-ID'] = self.diagnostic['request_id']
                response['Cache-Control'] = 'private, no-store'
                response['Referrer-Policy'] = 'no-referrer'
                return response

    def handle_exception(self, exc):
        if isinstance(exc, APIException):
            return super().handle_exception(exc)
        self.diagnostic['traceback'] = safe_trace(exc)
        return Response({'code': 'INTERNAL_ERROR', 'message': 'Device request failed; share the request ID with the operator.'}, status=500)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        response['Referrer-Policy'] = 'no-referrer'
        response['X-Request-ID'] = self.diagnostic['request_id']
        code = safe_code(getattr(response, 'data', None), response.status_code)
        self.diagnostic['result_code'] = code
        if response.status_code >= 400:
            public = 'TOKEN_UNAVAILABLE' if code == 'TOKEN_LOOKUP_MISS' else code
            messages = {'TOKEN_UNAVAILABLE': 'Token unavailable for this device.',
                        'DEVICE_UNAUTHORIZED': 'Device authentication failed.',
                        'INTERNAL_ERROR': 'Device request failed; share the request ID with the operator.'}
            response.data = {'code': public, 'message': messages.get(public, 'Device request rejected.'),
                             'request_id': self.diagnostic['request_id']}
        return response

    @sensitive_variables()
    def post(self, request):
        mark_stage('authentication')
        device = service.authenticate(request)
        mark_stage('request_validation')
        if request.content_type != 'application/json':
            service.fail('REQUEST_INVALID', 'Use application/json.', 400)
        raw = request.stream.read(4097) if request.stream is not None else b""
        if len(raw) > 4096:
            service.fail('REQUEST_TOO_LARGE', 'Request exceeds the firmware limit.', 413)
        try:
            body = json.loads(raw, object_pairs_hook=unique_object)
        except (ValueError, UnicodeError, RecursionError):
            service.fail('REQUEST_INVALID', 'Invalid JSON object.', 400)
        return Response(self.operation(device, body, **self.operation_options(request)))


class PrototypeSessionView(PrototypeView):
    operation = staticmethod(service.session)


class PrototypeRedeemView(PrototypeView):
    operation = staticmethod(service.redeem)


class PrototypeAckView(PrototypeView):
    operation = staticmethod(service.acknowledge)


class PrototypeTelemetryView(PrototypeView):
    operation = staticmethod(service.telemetry)

    def operation_options(self, request):
        # A retry keeps the original body byte-for-byte. This header can only
        # suppress a lease, even if the original request never arrived.
        return {'replay': request.headers.get('X-Gpawa-Telemetry-Replay') == '1'}


class PrototypeMeasurementPrepareView(PrototypeView):
    operation = staticmethod(service.prepare_measurement)


class PrototypeMeasurementCommitView(PrototypeView):
    operation = staticmethod(service.commit_measurement)
