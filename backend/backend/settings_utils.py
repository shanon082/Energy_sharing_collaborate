import os
from django.core.exceptions import ImproperlyConfigured

def get_env_variable(env_variable, default=None, allow_none=False, cast=str):
    """
    Fetch environment variable safely.
    - Trims whitespace
    - Supports defaults and optional None
    - Casts to correct type if specified
    """
    value = os.environ.get(env_variable, default)
    if value is None and not allow_none:
        raise ImproperlyConfigured(f"Set the {env_variable} environment variable")
    return cast(value) if value is not None else None
