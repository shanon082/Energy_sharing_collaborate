#!/usr/bin/env bash
set -euo pipefail
export DJANGO_SETTINGS_MODULE=backend.render_settings
export DJANGO_LOAD_LOCAL_ENV=false
exec gunicorn backend.wsgi:application \
  --bind "0.0.0.0:${PORT:-10000}" \
  --workers "${WEB_CONCURRENCY:-1}" \
  --timeout 60 \
  --forwarded-allow-ips '*' \
  --access-logfile - \
  --access-logformat '%(m)s %(U)s %(s)s %(L)s' \
  --error-logfile -
# URL path only: access logs exclude query strings, request bodies and headers.
