from django.contrib.auth.tokens import PasswordResetTokenGenerator
from six import text_type
from accounts.models import User


class TokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user: User, timestamp: int) -> str:
        return (
            text_type(user.pk)
            + text_type(timestamp)
            + text_type(user.profile.email_verified)
        )


class ResetPasswordTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user: User, timestamp: int) -> str:
        return (
            text_type(user.pk)
            + text_type(timestamp)
            + text_type(user.password)
        )


token_generator = TokenGenerator()
reset_password_token_generator = ResetPasswordTokenGenerator()
