"""Read-only hosted migration plan from LOCAL migration sources; no upload/DDL.

Uses existing noninteractive SSH authentication. Never reads local .env or keys.
The remote process loads its existing private environment via Django settings.
"""
import json
from pathlib import Path
import shlex
import subprocess
import sys

REMOTE = r'''
import json, os, sys, types
os.chdir('/home/shanonsimon/energy-sharing')
sys.path.insert(0, os.getcwd())
from unittest.mock import patch
with patch('requests.sessions.Session.request', side_effect=RuntimeError('Provider HTTP prohibited during plan review')):
    import django
    django.setup()
    from django.apps import apps
    from django.conf import settings
    from django.db import connection
    from django.db.migrations.loader import MigrationLoader
    from django.db.migrations.executor import MigrationExecutor
    db = settings.DATABASES['default']
    expected = ('postgresql-shanonsimon.alwaysdata.net', 'shanonsimon_energy_test', 'shanonsimon')
    if (db['HOST'], db['NAME'], db['USER']) != expected:
        raise SystemExit('REFUSED: unexpected database target')
    with connection.cursor() as cursor:
        cursor.execute('SET default_transaction_read_only = on')
        cursor.execute('SELECT current_database(), current_user')
        if cursor.fetchone() != expected[1:]:
            raise SystemExit('REFUSED: unexpected connected database')
        cursor.execute('SELECT ssl, version FROM pg_stat_ssl WHERE pid=pg_backend_pid()')
        tls = cursor.fetchone()
        if not tls or tls[0] is not True:
            raise SystemExit('REFUSED: encrypted PostgreSQL connection required')
    print('Testing database identity verified; encrypted=True; protocol=' + str(tls[1]))
    payload = json.load(sys.stdin)
    labels = {app.name: app.label for app in apps.get_app_configs()}
    class CheckoutLoader(MigrationLoader):
        def load_disk(self):
            super().load_disk()
            project_labels = {labels[row['package']] for row in payload if row['package'] in labels}
            self.disk_migrations = {key: value for key, value in self.disk_migrations.items() if key[0] not in project_labels}
            self.migrated_apps.update(project_labels)
            self.unmigrated_apps.difference_update(project_labels)
            for source in payload:
                package, name, code = source['package'], source['name'], source['source']
                if package not in labels:
                    continue
                label = labels[package]
                module = types.ModuleType(package + '.migrations.' + name)
                module.__file__ = '<read-only local checkout migration>'
                module.__package__ = package + '.migrations'
                exec(compile(code, module.__file__, 'exec'), module.__dict__)
                self.disk_migrations[(label, name)] = module.Migration(name, label)
    executor = MigrationExecutor(connection)
    executor.loader = CheckoutLoader(connection)
    project_labels = {labels[row['package']] for row in payload if row['package'] in labels}
    for key in executor.loader.applied_migrations:
        if key[0] in project_labels and key not in executor.loader.disk_migrations:
            raise SystemExit('REFUSED: hosted migration absent from local checkout: '+'.'.join(key))
    executor.loader.check_consistent_history(connection)
    targets = executor.loader.graph.leaf_nodes()
    plan = executor.migration_plan(targets)
    print('READ-ONLY PLAN using current checkout migrations and hosted django_migrations:')
    for migration, backwards in plan:
        if backwards:
            raise SystemExit('REFUSED: backwards migration in rollout plan')
        print(migration.app_label + '.' + migration.name)
        for operation in migration.operations:
            print('  ' + operation.describe())
    if not plan:
        print('No planned migrations')
    print('No schema, account, payment, device or file changes performed')
'''


def payload(root):
    return [{"package": path.parts[-3], "name": path.stem, "source": path.read_text()}
            for path in sorted(root.glob("*/migrations/[0-9]*.py"))]


def main():
    root = Path(__file__).resolve().parent.parent
    sources = payload(root)
    if not any(row["name"].startswith("0032_prototypedevice") for row in sources):
        raise SystemExit("Missing local AC_LAB migration0032")
    remote = ("PYTHONDONTWRITEBYTECODE=1 DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings "
              "ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env "
              "/home/shanonsimon/energy-venv/bin/python -c " + shlex.quote(REMOTE))
    result = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=10",
                             "shanonsimon@ssh-shanonsimon.alwaysdata.net", remote],
                            input=json.dumps(sources), text=True)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
