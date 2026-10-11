"""Managed alwaysdata uWSGI entry point; management uses the same settings."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.alwaysdata_settings"

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
