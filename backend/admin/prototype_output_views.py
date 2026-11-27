from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from meter.bench_device import BenchError
from meter import prototype_device
from meter.models import PrototypeDevice
from .views import RBACMixin


class PrototypeOutputAuthorizationView(APIView, RBACMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request, device_id):
        allowed, response = self._require_role(request, User.ADMIN)
        if not allowed:
            return response
        device = PrototypeDevice.objects.filter(pk=device_id).first()
        if not device:
            return Response({'code': 'DEVICE_UNAVAILABLE'}, status=404)
        eligibility = prototype_device.output_authorization(device)
        authorization = device.output_authorizations.order_by('-granted_at', '-pk').first()
        events = device.output_authorization_events.select_related('actor').order_by(
            '-occurred_at', '-pk',
        )[:100]
        return Response({
            **eligibility,
            'device_id': str(device.pk),
            'authorization_state': authorization.state if authorization else 'NONE',
            'authorization_id': authorization.pk if authorization else None,
            'mode': authorization.mode if authorization else None,
            'offline_enabled': authorization.offline_enabled if authorization else False,
            'expires_at': authorization.expires_at.isoformat() if authorization and authorization.expires_at else None,
            'restart_policy': authorization.restart_policy if authorization else None,
            'events': [{
                'action': event.action,
                'occurred_at': event.occurred_at.isoformat(),
                'actor_id': event.actor_id,
                'reason': event.reason,
                'details': event.details,
            } for event in events],
        })

    def post(self, request, device_id):
        allowed, response = self._require_role(request, User.ADMIN)
        if not allowed:
            return response
        try:
            result = prototype_device.commission_output(device_id, request.user, request.data)
        except BenchError as exc:
            return Response(exc.detail, status=exc.status_code)
        return Response(result, status=201)


class PrototypeOutputPersistenceView(APIView, RBACMixin):
    permission_classes = [IsAuthenticated]

    def post(self, request, device_id):
        allowed, response = self._require_role(request, User.ADMIN)
        if not allowed:
            return response
        try:
            result, created = prototype_device.persist_output_commissioning(device_id, request.user, request.data)
        except BenchError as exc:
            return Response(exc.detail, status=exc.status_code)
        return Response(result, status=201 if created else 200)


class PrototypeOutputRevocationView(APIView, RBACMixin):
    permission_classes = [IsAuthenticated]

    def post(self, request, device_id):
        allowed, response = self._require_role(request, User.ADMIN)
        if not allowed:
            return response
        body = request.data
        if not isinstance(body, dict) or set(body) != {'reason'}:
            return Response({'code': 'REQUEST_INVALID', 'message': 'A reason is required.'}, status=400)
        try:
            result = prototype_device.revoke_output(device_id, request.user, body['reason'])
        except BenchError as exc:
            return Response(exc.detail, status=exc.status_code)
        return Response(result)
