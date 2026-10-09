#!/usr/bin/env bash
set -euo pipefail
export DJANGO_SETTINGS_MODULE=backend.render_settings
export DJANGO_LOAD_LOCAL_ENV=false
python -m pip install -r requirements-render.txt
python manage.py collectstatic --noinput
# Deliberately no migrate: database identity must be confirmed separately.
