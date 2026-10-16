"""Private token storage configuration; independent of consumer/provider secrets."""
from django.core.exceptions import ImproperlyConfigured
from backend.feature_config import parse_feature_bool


def token_configuration(environ):
    enabled = parse_feature_bool(environ.get("ENERGY_TOKEN_ISSUANCE_ENABLED", "false"), name="ENERGY_TOKEN_ISSUANCE_ENABLED")
    keys = [item.strip() for item in environ.get("ENERGY_TOKEN_ENCRYPTION_KEYS", "").split(",") if item.strip()]
    lookup = environ.get("ENERGY_TOKEN_LOOKUP_KEY", "")
    if enabled:
        if not keys or len(lookup) < 32:
            raise ImproperlyConfigured("Configure private ENERGY_TOKEN_ENCRYPTION_KEYS and ENERGY_TOKEN_LOOKUP_KEY before enabling issuance")
        from cryptography.fernet import Fernet
        try:
            for key in keys:
                Fernet(key.encode("ascii"))
        except (ValueError, UnicodeError):
            raise ImproperlyConfigured("ENERGY_TOKEN_ENCRYPTION_KEYS must contain valid Fernet keys") from None
    return enabled, keys, lookup
