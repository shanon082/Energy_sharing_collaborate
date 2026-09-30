"""Deployment-owned feature configuration; never populated from requests."""

from django.core.exceptions import ImproperlyConfigured


FEATURE_ENV_VARS = {
    "peer_sharing": "FEATURE_PEER_SHARING_ENABLED",
    "meter_transfers": "FEATURE_METER_TRANSFERS_ENABLED",
    "third_party_repayment": "FEATURE_THIRD_PARTY_REPAYMENT_ENABLED",
    "ussd": "FEATURE_USSD_ENABLED",
    "wallet_deposits": "FEATURE_WALLET_DEPOSITS_ENABLED",
    "wallet_withdrawals": "FEATURE_WALLET_WITHDRAWALS_ENABLED",
    "external_crb": "FEATURE_EXTERNAL_CRB_ENABLED",
}


def parse_feature_bool(value, *, name="feature flag"):
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off", ""}:
        return False
    raise ImproperlyConfigured(f"{name} must be an explicit boolean")


def load_feature_flags(environ):
    return {
        feature: parse_feature_bool(environ.get(env, "false"), name=env)
        for feature, env in FEATURE_ENV_VARS.items()
    }
