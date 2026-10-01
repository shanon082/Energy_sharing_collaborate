"""Small, side-effect-free consumer account view and explicit refresh revocation."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from accounts.models import User
from accounts.api.serializers import UpdateUserProfileSerializer
from loan.scoring import profile_scoring_fields_complete, sync_credit_signal_from_profile


class MobileAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.user_role != User.CLIENT:
            return Response({"code": "CONSUMER_ONLY"}, status=403)
        return Response({
            "id": user.pk,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "user_role": user.user_role,
            "email_verified": user.profile.email_verified,
            "must_change_password": user.must_change_password,
        })


class MobileLogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        raw_refresh = request.data.get("refresh")
        if not isinstance(raw_refresh, str) or not raw_refresh:
            return Response({"code": "REFRESH_REQUIRED"}, status=400)
        try:
            token = RefreshToken(raw_refresh)
            if str(token.get("user_id")) != str(request.user.pk):
                return Response({"code": "TOKEN_OWNER_MISMATCH"}, status=403)
            token.blacklist()
        except TokenError:
            return Response({"code": "INVALID_REFRESH"}, status=400)
        return Response(status=204)


class MobileProfileView(APIView):
    """Only the existing consumer assessment fields are editable here."""
    permission_classes = [IsAuthenticated]

    def _consumer(self, request):
        return request.user.user_role == User.CLIENT

    def get(self, request):
        if not self._consumer(request):
            return Response({"code": "CONSUMER_ONLY"}, status=403)
        fields = UpdateUserProfileSerializer().fields
        return Response({
            "values": {name: getattr(request.user, name, None) for name in fields},
            "choices": {name: [{"value": value, "label": str(label)}
                        for value, label in User._meta.get_field(name).choices]
                        for name in fields},
            "complete_for_scoring": profile_scoring_fields_complete(request.user),
        })

    def patch(self, request):
        if not self._consumer(request):
            return Response({"code": "CONSUMER_ONLY"}, status=403)
        serializer = UpdateUserProfileSerializer(data=request.data)
        unknown = set(request.data) - set(serializer.fields)
        if unknown:
            return Response({"code": "PROFILE_FIELD_FORBIDDEN"}, status=400)
        serializer.is_valid(raise_exception=True)
        if not serializer.validated_data:
            return Response({"code": "NO_PROFILE_FIELDS"}, status=400)
        for field, value in serializer.validated_data.items():
            allowed = {choice for choice, _ in User._meta.get_field(field).choices}
            if value not in (None, "") and value not in allowed:
                return Response({"error": {field: "Choose a listed value."}}, status=400)
        user = request.user
        for field, value in serializer.validated_data.items():
            setattr(user, field, value)
        user.save(update_fields=[*serializer.validated_data.keys(), "modify_date"])
        sync_credit_signal_from_profile(user)
        return self.get(request)


class MobilePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.user_role != User.CLIENT:
            return Response({"code": "CONSUMER_ONLY"}, status=403)
        current = request.data.get("current_password")
        new = request.data.get("new_password")
        confirm = request.data.get("confirm_password")
        if not all(isinstance(value, str) and value for value in (current, new, confirm)):
            return Response({"error": "Current, new and confirmation passwords are required."}, status=400)
        if not user.check_password(current):
            return Response({"error": "Current password is incorrect."}, status=400)
        if new != confirm:
            return Response({"error": "New passwords do not match."}, status=400)
        if new == current:
            return Response({"error": "Choose a different password."}, status=400)
        try:
            validate_password(new, user=user)
        except ValidationError as exc:
            return Response({"error": " ".join(exc.messages)}, status=400)
        user.set_password(new)
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password", "modify_date"])
        return Response({"message": "Password changed. Sign in again."})
