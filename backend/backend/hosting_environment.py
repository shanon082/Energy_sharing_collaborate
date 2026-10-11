"""Private dotenv loading shared by alwaysdata WSGI and management commands."""

import os
import stat
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import dotenv_values


def load_private_environment(environ):
    value = environ.get("ALWAYSDATA_ENV_FILE", "")
    path = Path(value)
    if not value or not path.is_absolute():
        raise ImproperlyConfigured("ALWAYSDATA_ENV_FILE must be an absolute private-file path")
    project = Path(__file__).resolve().parent.parent
    if path.resolve().is_relative_to(project):
        raise ImproperlyConfigured("ALWAYSDATA_ENV_FILE must be outside the uploaded backend")
    try:
        with path.open("r", encoding="utf-8") as stream:
            info = os.fstat(stream.fileno())
            parent = path.parent.stat()
            if (path.is_symlink() or not stat.S_ISREG(info.st_mode)
                    or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600
                    or parent.st_uid != os.getuid() or stat.S_IMODE(parent.st_mode) != 0o700):
                raise ImproperlyConfigured("Private environment requires an owned 0600 file in an owned 0700 directory")
            values = dotenv_values(stream=stream, interpolate=False)
    except (OSError, UnicodeError):
        raise ImproperlyConfigured("Cannot read the private alwaysdata environment file") from None
    # The site/command environment wins; validation checks the effective values.
    # No shell execution or ${...} interpolation; secrets stay literal.
    for name, value in values.items():
        if value is None:
            raise ImproperlyConfigured(f"{name} requires an explicit environment-file value")
        environ.setdefault(name, value)


def positive_integer(environ, name, default, *, maximum):
    try:
        value = int(environ.get(name, str(default)))
    except (TypeError, ValueError):
        raise ImproperlyConfigured(f"{name} must be an integer") from None
    if not 1 <= value <= maximum:
        raise ImproperlyConfigured(f"{name} is outside its supported range")
    return value
