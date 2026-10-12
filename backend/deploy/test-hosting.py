"""Local-only mocked hosting regressions against the documented /tmp PG cluster."""

import atexit
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

root = Path(__file__).resolve().parent.parent
cluster = Path('/tmp/gpawa-alwaysdata/pg')
try:
    pid_lines = (cluster / 'postmaster.pid').read_text().splitlines()
    valid_cluster = (cluster.stat().st_uid == os.getuid() and pid_lines[3] == '55445'
                     and Path(pid_lines[1]).resolve() == cluster.resolve())
except (OSError, IndexError):
    valid_cluster = False
if not valid_cluster:
    raise SystemExit('Start the documented isolated /tmp PostgreSQL cluster on port 55445 first')
extra_path = os.environ.get('HOSTING_TEST_EXTRA_PATH')
path = os.environ.get('PATH', '')
os.environ.clear()
os.environ.update(
    PATH=path, DJANGO_LOAD_LOCAL_ENV='false', DEBUG='True',
    SECRET_KEY='synthetic-hosting-tests-only-abcdefghijklmnopqrstuvwxyz-0123456789012345',
    DB_NAME='gpawa_alwaysdata_tests', DB_USER='gpawa_alwaysdata_test',
    DB_PASSWORD='isolated-test-only', DB_HOST='127.0.0.1', DB_PORT='55445',
    DJANGO_SETTINGS_MODULE='backend.settings', MOBILE_APP_ORIGIN='http://localhost',
    MTN_USE_SIMULATED_PAYMENTS='false',
)
sys.path.insert(0, str(root))
if extra_path:
    sys.path.insert(0, extra_path)
import psycopg

with psycopg.connect(host='127.0.0.1', port=55445, user='gpawa_alwaysdata_test',
                     dbname='postgres', autocommit=True) as conn:
    if conn.execute('SELECT current_user').fetchone()[0] != 'gpawa_alwaysdata_test':
        raise SystemExit('Unexpected isolated test role')
    if not conn.execute("SELECT 1 FROM pg_database WHERE datname='gpawa_alwaysdata_tests'").fetchone():
        conn.execute('CREATE DATABASE gpawa_alwaysdata_tests')
if '--render' in sys.argv:
    sys.argv.remove('--render')
    os.environ.update(
        DJANGO_SETTINGS_MODULE='backend.render_settings', DEBUG='False',
        RENDER_EXTERNAL_HOSTNAME='test.onrender.com', FRONTEND_URL='https://web.example.invalid',
        DB_SSLMODE='disable', EMAIL_HOST='smtp.example.invalid', EMAIL_HOST_USER='test-only',
        EMAIL_HOST_PASSWORD='test-only', DEFAULT_EMAIL_SENDER='test@example.invalid',
        CELERY_BROKER_URL='redis://127.0.0.1:6399/0',
    )
sandbox_profile = '--sandbox-profile' in sys.argv
if '--profile' in sys.argv or sandbox_profile:
    sys.argv.remove('--sandbox-profile' if sandbox_profile else '--profile')
    private = tempfile.TemporaryDirectory(prefix='gpawa-hosting-test-')
    atexit.register(private.cleanup)
    envfile = Path(private.name) / 'backend.env'
    envfile.write_text('ALWAYSDATA_HOSTNAME=test.alwaysdata.net\n'
                       'DB_SSLMODE=disable\n'
                       'EMAIL_HOST=smtp.example.invalid\nEMAIL_HOST_USER=test-only\n'
                       'EMAIL_HOST_PASSWORD=test-only\nDEFAULT_EMAIL_SENDER=test@example.invalid\n')
    envfile.chmod(0o600)
    os.environ.update(ALWAYSDATA_ENV_FILE=str(envfile),
                      DJANGO_SETTINGS_MODULE='backend.alwaysdata_sandbox_settings' if sandbox_profile else 'backend.alwaysdata_settings', DEBUG='False')
import django

django.setup()
from django.conf import settings
from django.core.management import call_command
from django.test.utils import get_runner

settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
settings.DATABASES['default']['CONN_MAX_AGE'] = 0
settings.PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
if getattr(settings, 'ALWAYSDATA_TESTING', False):
    # Exercise real manifest/WhiteNoise rendering without generating repository
    # artifacts or relying on previously collected development static files.
    settings.STATIC_ROOT = str(Path(private.name) / 'staticfiles')
    call_command('collectstatic', interactive=False, verbosity=0)
labels = sys.argv[1:] or ['backend.tests_alwaysdata.PrivateEnvironmentTests',
                         'backend.tests_alwaysdata.AccountMailOutboxTests',
                         'accounts.tests_authentication', 'backend.tests_feature_flags']
with patch('requests.sessions.Session.request', side_effect=AssertionError('External HTTP prohibited')):
    failures = get_runner(settings)(verbosity=1, interactive=False).run_tests(labels)
raise SystemExit(bool(failures))
