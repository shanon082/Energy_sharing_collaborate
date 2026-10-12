"""Deliberately separate site entry point; default WSGI remains read-only."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["DJANGO_SETTINGS_MODULE"] = "backend.alwaysdata_sandbox_settings"
from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
