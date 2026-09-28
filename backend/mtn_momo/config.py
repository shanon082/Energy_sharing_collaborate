import os


def _env(name, default=""):
  return os.getenv(name, default) or default


def _subscription_key():
  return (
    _env("MTN_SUBSCRIPTION_KEY")
    or _env("PRIMARY_KEY")
    or _env("SECONDARY_KEY")
  )


MTN_MOMO_CONFIG = {
  "BASE_URL": _env("MTN_BASE_URL", "https://sandbox.momodeveloper.mtn.com"),
  "SUBSCRIPTION_KEY": _subscription_key(),
  "API_USER_ID": _env("MTN_API_USER_ID"),
  "API_KEY": _env("MTN_API_KEY"),
  "CALLBACK_HOST": _env("MTN_CALLBACK_HOST") or _env("CALLBACK_HOST", "http://localhost:8000"),
  "ENVIRONMENT": _env("MTN_ENVIRONMENT") or _env("ENVIRONMENT", "sandbox"),
}

MTN_TEST_NUMBERS = [
  "256771950092",
  "256786973581",
  "46733123454",
]


def is_momo_configured():
  cfg = MTN_MOMO_CONFIG
  return bool(
    cfg.get("SUBSCRIPTION_KEY")
    and cfg.get("API_USER_ID")
    and cfg.get("API_KEY")
    and cfg.get("CALLBACK_HOST")
  )


def should_simulate_payments():
  """Use local auto-complete when MoMo credentials are missing or explicitly forced."""
  forced = _env("MTN_USE_SIMULATED_PAYMENTS").lower()
  if forced in ("1", "true", "yes"):
    return True
  if forced in ("0", "false", "no"):
    return False
  return not is_momo_configured()
