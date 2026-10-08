"""Refresh validation and rotation without changing the web/mobile JWT shape."""

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.utils import get_md5_hash_password


class AccountTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        refresh = self.token_class(attrs["refresh"])
        user_id = refresh.get(api_settings.USER_ID_CLAIM)
        user = get_user_model().objects.filter(**{api_settings.USER_ID_FIELD: user_id}).first()
        if user is None or not api_settings.USER_AUTHENTICATION_RULE(user):
            raise AuthenticationFailed("The account is unavailable.", code="no_active_account")
        if api_settings.CHECK_REVOKE_TOKEN and refresh.get(api_settings.REVOKE_TOKEN_CLAIM) != get_md5_hash_password(user.password):
            raise AuthenticationFailed("Sign in again after a password change.", code="password_changed")
        if user.user_role == user.CLIENT and not user.is_staff and not user.is_superuser:
            profile = getattr(user, "profile", None)
            if profile is None or not profile.email_verified:
                raise AuthenticationFailed("Verify your email before signing in.", code="UNVERIFIED")

        # Re-check the signed token under its durable row lock. Two refreshes of
        # the same token cannot both pass the parent's blacklist check/rotation.
        # No provider, email or other network call occurs in this transaction.
        with transaction.atomic():
            row = OutstandingToken.objects.select_for_update().filter(
                jti=refresh.get(api_settings.JTI_CLAIM), user=user,
            ).first()
            if row is None:
                raise InvalidToken("The refresh session is unavailable. Sign in again.")
            return super().validate(attrs)
