from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, patch
from django.core.management.base import CommandError
from django.test import SimpleTestCase
from accounts.management.commands.check_alwaysdata_database import Command


class DatabaseTargetTests(SimpleTestCase):
    def run_check(self, tls):
        database = {"HOST": "postgresql-shanonsimon.alwaysdata.net", "NAME": "shanonsimon_energy_test", "USER": "shanonsimon"}
        config = SimpleNamespace(SETTINGS_MODULE="backend.alwaysdata_sandbox_settings", DATABASES={"default": database})
        cursor = Mock(); cursor.fetchone.side_effect = [(database["NAME"], database["USER"]), tls, (True,)]
        connection = Mock(); connection.cursor.return_value.__enter__ = Mock(return_value=cursor)
        connection.cursor.return_value.__exit__ = Mock(return_value=False)
        output = StringIO()
        with patch("accounts.management.commands.check_alwaysdata_database.settings", config), patch("accounts.management.commands.check_alwaysdata_database.connection", connection):
            Command(stdout=output).handle()
        return output.getvalue()

    def test_encrypted_target_reports_only_connection_metadata(self):
        text = self.run_check((True, "TLSv1.3", "synthetic-test-cipher"))
        self.assertIn("encrypted=True tls=TLSv1.3", text)
        self.assertNotIn("password", text.lower())

    def test_missing_or_unencrypted_connection_fails_before_migration(self):
        for result in (None, (False, None, None)):
            with self.assertRaises(CommandError): self.run_check(result)
