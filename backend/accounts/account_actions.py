"""Shared account-link rules. Mutations re-check tokens under account locks."""

from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.views.decorators.debug import sensitive_variables

from accounts.models import Profile, User
from accounts.utils import b64decode_hash, b64encode_user, handle_post_email_verification
from utils.auth import reset_password_token_generator, token_generator


class InvalidAccountLink(ValueError):
    pass


@sensitive_variables()
def account_email_link(user, *, reset=False):
    generator = reset_password_token_generator if reset else token_generator
    query = urlencode({"uid": b64encode_user(str(user.pk)), "token": generator.make_token(user)})
    if getattr(settings, "DJANGO_HOSTED_ACCOUNT_PAGES", False):
        name = "account-reset-password" if reset else "account-verify-email"
        # This origin comes exclusively from validated deployment configuration.
        return f"{settings.ACCOUNT_PAGES_ORIGIN}{reverse(name)}?{query}"
    path = "/auth/reset-password/" if reset else "/auth/verify-email"
    return f"{settings.FRONTEND_URL.rstrip('/')}{path}?{query}"


@sensitive_variables()
def account_link_user(uid, token, *, reset=False, lock=False):
    if not isinstance(uid, str) or not isinstance(token, str) or len(uid) > 256 or len(token) > 256:
        raise InvalidAccountLink()
    try:
        _, user_id = b64decode_hash(uid)
        query = User.objects.select_for_update() if lock else User.objects
        user = query.get(pk=user_id, is_active=True)
        # Both actions acquire these locks in the same order. Cache the fresh
        # profile for the existing verification token hash implementation.
        profiles = Profile.objects.select_for_update() if lock else Profile.objects
        user.profile = profiles.get(user=user)
    except (ValueError, TypeError, UnicodeError, User.DoesNotExist, Profile.DoesNotExist):
        raise InvalidAccountLink() from None
    generator = reset_password_token_generator if reset else token_generator
    if not generator.check_token(user, token) or (not reset and user.profile.email_verified):
        raise InvalidAccountLink()
    return user


@transaction.atomic
@sensitive_variables()
def confirm_account_email(uid, token):
    user = account_link_user(uid, token, lock=True)
    user.profile.email_verified = True
    user.profile.save(update_fields=["email_verified", "modify_date"])
    handle_post_email_verification(user)
    return user


@transaction.atomic
@sensitive_variables()
def complete_password_reset(uid, token, data):
    # Reuse exactly the API's confirmation, length and complexity validation.
    from accounts.api.serializers import ResetPasswordConfirmSerializer

    user = account_link_user(uid, token, reset=True, lock=True)
    serializer = ResetPasswordConfirmSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    user.set_password(serializer.validated_data["password"])
    user.must_change_password = False
    user.save()
    if not user.profile.email_verified:
        user.profile.email_verified = True
        user.profile.save(update_fields=["email_verified", "modify_date"])
        handle_post_email_verification(user)
    return user
