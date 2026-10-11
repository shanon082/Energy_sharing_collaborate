"""Connection identity/schema metadata only; no records or migrations touched."""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Verify the confirmed alwaysdata testing target and report connection metadata only."

    def handle(self, *args, **options):
        database = settings.DATABASES["default"]
        if settings.SETTINGS_MODULE != "backend.alwaysdata_settings" or (
                database["HOST"], database["NAME"], database["USER"]) != (
                "postgresql-shanonsimon.alwaysdata.net", "shanonsimon_energy_test", "shanonsimon"):
            raise CommandError("Refusing a database other than the confirmed alwaysdata testing target")
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), current_user")
            name, user = cursor.fetchone()
            if (name, user) != ("shanonsimon_energy_test", "shanonsimon"):
                raise CommandError("Connected database identity does not match the testing target")
            cursor.execute("SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()")
            result = cursor.fetchone()
            cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'custom')")
            custom_exists = cursor.fetchone()[0]
        self.stdout.write(f"database={name} user={user} encrypted={bool(result and result[0])} custom_schema_exists={custom_exists}")
