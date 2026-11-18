"""Combined capabilities and retained ledger reads; isolated data, mocked I/O."""
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from loan.tests_sandbox import Fixtures, SANDBOX
from meter.prototype_device import enabled as lab_enabled


@override_settings(**{**SANDBOX, "SANDBOX_EUR_LOANS_ENABLED": False})
class CombinedRolloutTests(Fixtures, TestCase):
    def setUp(self):
        self.create_fixture()

    def test_mtn_capabilities_and_hosted_lab_denial(self):
        flags = self.client.get("/api/v1/features/", **self.headers).data
        self.assertFalse(any(flags["features"].values()))
        self.assertEqual(flags["sandbox"]["provider"], "MTN_SANDBOX")
        self.assertTrue(flags["sandbox"]["purchases"])
        self.assertTrue(flags["sandbox"]["repayments"])
        self.assertFalse(flags["sandbox"]["loans"])
        with override_settings(PROTOTYPE_AC_LAB_ENABLED=True, ALWAYSDATA_TESTING=True, PROTOTYPE_RELAY_OUTPUT_ENABLED=False):
            self.assertFalse(lab_enabled())
            if getattr(settings, "ROOT_URLCONF", "") == "backend.alwaysdata_urls":
                response = self.client.post("/api/v1/prototype-device/v1/redeem/", {}, **self.headers)
                self.assertEqual(response.status_code, 503)

    def test_0032_additive_plan_preview_on_simulated_previous_schema(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        executor = MigrationExecutor(connection)
        target = ("meter", "0032_prototypedevice_prototypecommand_prototypeboot_and_more")
        executor.loader.applied_migrations.pop(target, None)  # In-memory preview only.
        plan = executor.migration_plan([target])
        self.assertEqual([(item.app_label, item.name, backwards) for item, backwards in plan], [(target[0], target[1], False)])
        self.assertTrue(all(type(operation).__name__ in {"CreateModel", "AddConstraint"} for operation in plan[0][0].operations))
        self.assertEqual(sum(type(operation).__name__ == "CreateModel" for operation in plan[0][0].operations), 4)
        print("LOCAL PLAN PREVIEW (0031 assumed applied; not hosted): meter." + target[1] + "; four new AC lab models and constraints only")

    def test_readonly_checkout_loader_reproduces_the_local_migration_graph(self):
        import ast
        from pathlib import Path
        import runpy
        import types
        from django.apps import apps
        from django.db import connection
        from django.db.migrations.loader import MigrationLoader
        root = Path(__file__).resolve().parent.parent
        helper = runpy.run_path(str(root / "deploy/preview_combined_migrations.py"))
        tree = ast.parse(helper["REMOTE"])
        node = next(item for item in ast.walk(tree) if isinstance(item, ast.ClassDef) and item.name == "CheckoutLoader")
        namespace = {"MigrationLoader": MigrationLoader, "types": types,
                     "payload": helper["payload"](root), "labels": {app.name: app.label for app in apps.get_app_configs()}}
        exec(compile(ast.Module(body=[node], type_ignores=[]), "<checkout-loader-test>", "exec"), namespace)
        loader = namespace["CheckoutLoader"](connection)
        baseline = MigrationLoader(connection)
        self.assertEqual(set(loader.disk_migrations), set(baseline.disk_migrations))
        self.assertEqual(loader.graph.leaf_nodes(), baseline.graph.leaf_nodes())

    def test_ordinary_host_and_local_lab_capabilities_remain_distinct(self):
        with override_settings(CONSUMER_SANDBOX_ENABLED=False, PROTOTYPE_AC_LAB_ENABLED=True):
            flags = self.client.get("/api/v1/features/", **self.headers).data
            self.assertFalse(flags["sandbox"]["enabled"])
            self.assertFalse(flags["sandbox"]["purchases"])
            self.assertFalse(lab_enabled())
        with override_settings(PROTOTYPE_PAYMENT_PROVIDER="LOCAL_DEMO", ALWAYSDATA_TESTING=True,
                               PROTOTYPE_RELAY_OUTPUT_ENABLED=False, PROTOTYPE_AC_LAB_ENABLED=True):
            self.assertTrue(lab_enabled())
            flags = self.client.get("/api/v1/features/", **self.headers).data
            self.assertEqual(flags["sandbox"]["currency"], "UGX")
            self.assertFalse(flags["sandbox"]["physical_delivery"])
        with override_settings(MTN_SANDBOX_CONFIG={}):
            flags = self.client.get("/api/v1/features/", **self.headers).data["sandbox"]
            self.assertFalse(flags["purchases"])
            self.assertEqual(flags["payment_message"], "Sandbox payments unavailable")

    def test_original_demo_debt_receipts_and_balances_stay_owner_visible_in_mtn(self):
        from transactions.tests_demo_payments import Fixtures as DemoFixtures, DEMO
        from transactions.models import PaymentIntent
        from transactions.demo_payments import complete_demo_payment
        with override_settings(**DEMO):
            fixture = DemoFixtures(); fixture.addCleanup = self.addCleanup; fixture.setUp()
            loan = fixture.loan(); intent = fixture.purchase()
        PaymentIntent.objects.filter(pk=intent.pk).update(initiated_at=timezone.now()-timedelta(seconds=10), demo_eligible_at=timezone.now()-timedelta(seconds=5))
        with patch("requests.sessions.Session.request", side_effect=AssertionError("No network for old demo recovery")):
            complete_demo_payment(intent.pk)
        client = APIClient(); client.force_authenticate(fixture.owner)
        receipts = client.get("/api/v1/sandbox/payments/", **self.headers).data["payments"]
        self.assertEqual(receipts[0]["currency"], "UGX")
        self.assertEqual(receipts[0]["provider"], "LOCAL_DEMO")
        debt = client.get("/api/v1/sandbox/loans/", **self.headers).data["loans"][0]
        self.assertEqual(debt["id"], str(loan.pk)); self.assertEqual(debt["environment"], "UGX_DEMO")
        balances = {}
        for environment in ("CORE", "UGX_DEMO", "SANDBOX"):
            response = client.get(f"/api/v1/meter/mobile-meters/{fixture.meter.pk}/?environment={environment}", **self.headers)
            self.assertEqual(response.status_code, 200)
            balances[environment] = response.data["available_kwh"]
        self.assertEqual(balances, {"CORE": "0.00", "UGX_DEMO": "2.00", "SANDBOX": "0.00"})
        client.force_authenticate(self.other)
        self.assertEqual(client.get(f"/api/v1/meter/mobile-meters/{fixture.meter.pk}/?environment=UGX_DEMO", **self.headers).status_code, 404)
