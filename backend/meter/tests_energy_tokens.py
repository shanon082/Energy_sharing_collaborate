"""New funded tokens and isolated durable device lifecycle on PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from io import StringIO
from pathlib import Path
import tempfile
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch
import uuid

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management import call_command
from django.db import close_old_connections, connection
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from accounts.models import User
from device_bench.client import DurableDevice
from meter.allocation_service import AllocationError, authorize_purchase_allocation, entitlement_summary, reserve_for_delivery
from meter.bench_device import BenchError, device_session, redeem, acknowledge, rate_attempt, payload_digest
from meter.energy_tokens import issue_energy_token, token_record, EnergyTokenError
from meter.models import (BenchApplicationReceipt, BenchDevice, DeviceAttemptBucket, EnergyAllocation,
                          EnergyKeypadToken, Meter, MeterDelivery, SimulatedCommand)
from meter.sandbox_enrollment import enroll_sandbox_meter
from transactions.models import PaymentIntent
from transactions.tests_demo_payments import Fixtures, DEMO


@skipUnless(getattr(settings, "DEVICE_BENCH_ISOLATED", False), "Run with --bench-profile on its isolated database")
@override_settings(**DEMO)
class KeypadWorkflowTests(Fixtures, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.device = BenchDevice.objects.create(meter=self.meter, owner=self.owner, environment="UGX_DEMO",
            credential_hash=make_password("isolated-bench-credential-0123456789"))
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.journal_path = Path(self.temp.name) / "device.sqlite"
        self.local = DurableDevice(self.journal_path, self.device.pk, initialize=True)
        self.addCleanup(lambda: self.local.close())
        device_session(self.device, self.local.handshake())
        self.device.refresh_from_db()
        self.headers_device = {"HTTP_X_BENCH_DEVICE_ID": str(self.device.pk), "HTTP_X_BENCH_DEVICE_TOKEN": "isolated-bench-credential-0123456789"}

    def purchased_token(self):
        intent = self.purchase(); self.settle(intent)
        return EnergyKeypadToken.objects.get(allocation__purchase_intent=intent)

    def code(self, token):
        return token_record(token)["token"]

    def test_secure_format_collision_retry_and_idempotent_new_source(self):
        with patch("meter.energy_tokens.secrets.randbelow", side_effect=[0, 0, 1]):
            first, second = self.purchased_token(), self.purchased_token()
        self.assertEqual(self.code(first), "0" * 15)
        self.assertEqual(self.code(second), "0" * 14 + "1")
        self.assertNotIn(self.code(first), first.ciphertext)
        self.assertNotEqual(first.lookup_digest, self.code(first))
        self.assertEqual(issue_energy_token(first.allocation).pk, first.pk)
        self.assertEqual(authorize_purchase_allocation(first.allocation.purchase_intent, first.allocation.amount_kwh).pk, first.allocation_id)
        self.settle(first.allocation.purchase_intent)
        self.assertEqual(EnergyKeypadToken.objects.count(), 2)

    def test_pending_failed_quote_and_repayment_do_not_issue_energy(self):
        intent = self.purchase()
        self.assertFalse(EnergyKeypadToken.objects.exists())
        intent.status = "FAILED"; intent.save(update_fields=["status"])
        self.settle(intent)
        self.assertFalse(EnergyKeypadToken.objects.exists())
        loan = self.loan()
        self.assertEqual(EnergyKeypadToken.objects.count(), 1)
        self.settle(self.repayment(loan, "500"))
        self.assertEqual(EnergyKeypadToken.objects.count(), 1)
        self.assertEqual(EnergyAllocation.objects.count(), 1)

    def test_rejected_loan_cannot_issue_a_token(self):
        from loan.sandbox_service import assessment, create_quote, apply_loan
        quote = create_quote(self.owner, self.meter.pk, "1000", "LOAN")
        rejected = {**assessment(self.owner, meter_id=self.meter.pk), "eligible": False,
                    "reason": "Controlled rejection fixture; no real credit decision."}
        with patch("loan.sandbox_service.assessment", return_value=rejected):
            loan, created = apply_loan(self.owner, quote.pk, quote.terms_hash, uuid.uuid4())
        self.assertTrue(created)
        self.assertEqual(loan.status, "REJECTED")
        self.assertFalse(EnergyAllocation.objects.exists())
        self.assertFalse(EnergyKeypadToken.objects.exists())

    def test_old_allocation_not_backfilled_or_auto_reserved_twice(self):
        with override_settings(ENERGY_TOKEN_ISSUANCE_ENABLED=False):
            intent = self.purchase(); self.settle(intent)
        intent.refresh_from_db()
        allocation = intent.energy_allocation
        authorize_purchase_allocation(intent, allocation.amount_kwh)
        self.assertFalse(EnergyKeypadToken.objects.exists())
        # Old automatic reservations prevent later explicit token issuance.
        MeterDelivery.objects.create(allocation=allocation, amount_kwh=Decimal("0.01"))
        with self.assertRaises(EnergyTokenError): issue_energy_token(allocation)
        token = self.purchased_token()
        with override_settings(DEBUG=True, SIMULATED_METER_ENABLED=True):
            with self.assertRaises(AllocationError):
                reserve_for_delivery(owner=self.owner, meter_no=self.meter.meter_no, amount_kwh=str(token.allocation.amount_kwh))
        self.assertFalse(token.allocation.deliveries.exists())

    def test_owner_retrieval_no_store_and_cross_account_denial(self):
        token = self.purchased_token()
        url = f"/api/v1/meter/energy-tokens/?allocation_id={token.allocation_id}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["tokens"][0]["token"], self.code(token))
        self.assertIn("no-store", response["Cache-Control"])
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(url).data["tokens"], [])
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(url).status_code, 401)

    def test_authenticated_json_routes_complete_the_owner_visible_lifecycle(self):
        token = self.purchased_token()
        root = "/api/v1/bench-device/v1/"
        response = self.client.post(root + "session/", self.local.handshake(), format="json", **self.headers_device)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(root + "redeem/", {"contract_version": 1, "token": self.code(token)}, format="json", **self.headers_device)
        self.assertEqual(response.status_code, 200)
        receipt = self.local.apply(response.data["command"])
        for expected in (True, False):
            response = self.client.post(root + "ack/", receipt, format="json", **self.headers_device)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["newly_applied"], expected)
        response = self.client.get(f"/api/v1/meter/energy-tokens/?allocation_id={token.allocation_id}")
        self.assertEqual(response.data["tokens"][0]["state"], "APPLIED")
        self.assertEqual(response.data["tokens"][0]["application_environment"], "SOFTWARE_BENCH")
        self.assertEqual(BenchApplicationReceipt.objects.count(), 1)

    def test_device_auth_not_consumer_jwt_and_revocation_fails_closed(self):
        token = self.purchased_token()
        path = "/api/v1/bench-device/v1/redeem/"
        body = {"contract_version": 1, "token": self.code(token)}
        self.assertEqual(self.client.post(path, body, format="json").status_code, 401)
        self.assertEqual(self.client.post(path, body, format="json", HTTP_X_BENCH_DEVICE_ID=str(self.device.pk), HTTP_X_BENCH_DEVICE_TOKEN="wrong").status_code, 401)
        BenchDevice.objects.filter(pk=self.device.pk).update(active=False, revoked_at=timezone.now())
        self.assertEqual(self.client.post(path, body, format="json", **self.headers_device).status_code, 401)
        self.assertFalse(MeterDelivery.objects.exists())

    def test_wrong_device_environment_and_reassignment_cannot_redeem(self):
        token = self.purchased_token(); body = {"contract_version": 1, "token": self.code(token)}
        foreign_meter = enroll_sandbox_meter(self.other, "00000000999")[0]
        other_device = BenchDevice.objects.create(meter=foreign_meter, owner=self.other, environment="UGX_DEMO", credential_hash="unused")
        with self.assertRaises(BenchError): redeem(other_device, body)
        BenchDevice.objects.filter(pk=self.device.pk).update(environment="SANDBOX")
        with self.assertRaises(BenchError): redeem(self.device, body)
        BenchDevice.objects.filter(pk=self.device.pk).update(environment="UGX_DEMO")
        Meter.objects.filter(pk=self.meter.pk).update(user=self.other)
        with self.assertRaises(BenchError): redeem(self.device, body)
        self.assertFalse(MeterDelivery.objects.exists())

    def test_lost_response_ack_restart_and_offline_consumption(self):
        token = self.purchased_token(); body = {"contract_version": 1, "token": self.code(token)}
        command = redeem(self.device, body)
        self.assertEqual(redeem(self.device, body), command)
        receipt = self.local.apply(command)
        self.local.close()
        self.local = DurableDevice(self.journal_path, self.device.pk)
        device_session(self.device, self.local.handshake())
        self.assertEqual(self.local.apply(command), receipt)
        self.assertEqual(self.local.pending_receipts(), [receipt])
        # App/server sees only pending until authenticated durable receipt.
        token.refresh_from_db(); self.assertEqual(token.state, "DELIVERY_PENDING")
        self.assertTrue(acknowledge(self.device, receipt))
        self.assertFalse(acknowledge(self.device, receipt))
        token.refresh_from_db(); self.assertEqual(token.state, "APPLIED")
        self.assertEqual(entitlement_summary(self.owner, self.meter)["confirmed_kwh"], token.allocation.amount_kwh)
        with self.assertRaises(BenchError) as used: redeem(self.device, body)
        self.assertEqual(used.exception.detail["code"], "TOKEN_ALREADY_USED")
        self.local.consume(1)  # Wh precision, not10Wh per reading/debit.
        remaining = self.local.db.execute("SELECT remaining FROM state").fetchone()[0]
        self.assertEqual(remaining, token.amount_wh - 1)
        self.assertEqual(BenchApplicationReceipt.objects.count(), 1)
        self.assertFalse(SimulatedCommand.objects.exists())

    def test_changed_command_or_receipt_rejected_without_second_credit(self):
        token = self.purchased_token()
        command = redeem(self.device, {"contract_version": 1, "token": self.code(token)})
        receipt = self.local.apply(command)
        changed = {**command, "credit_wh": command["credit_wh"] + 10}
        changed["payload_digest"] = payload_digest({key: value for key, value in changed.items() if key != "payload_digest"})
        with self.assertRaises(ValueError): self.local.apply(changed)
        for update in ({"credit_wh": receipt["credit_wh"]+10}, {"device_id": str(uuid.uuid4())}, {"environment": "CORE"}, {"command_id": str(uuid.uuid4())}):
            with self.assertRaises(BenchError): acknowledge(self.device, {**receipt, **update})
        self.assertFalse(BenchApplicationReceipt.objects.exists())
        acknowledge(self.device, receipt)
        with self.assertRaises(BenchError): acknowledge(self.device, {**receipt, "receipt_id": str(uuid.uuid4())})

    def test_journal_reset_or_server_binding_loss_requires_reconciliation(self):
        with self.assertRaises(BenchError):
            device_session(self.device, {**self.local.handshake(), "storage_id": str(uuid.uuid4()), "initialize": True})
        token = self.purchased_token()
        redeem(self.device, {"contract_version": 1, "token": self.code(token)})
        BenchDevice.objects.filter(pk=self.device.pk).update(storage_identity=None)
        with self.assertRaises(BenchError): device_session(self.device, self.local.handshake())
        with self.assertRaises(ValueError): DurableDevice(Path(self.temp.name) / "missing.sqlite", self.device.pk)

    def parallel(self, operation):
        barrier = Barrier(2)
        def run(_):
            close_old_connections(); barrier.wait(timeout=10)
            try: return operation()
            finally: connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool: return list(pool.map(run, range(2)))

    def test_concurrent_redemption_and_acknowledgement_once(self):
        token = self.purchased_token()
        body = {"contract_version": 1, "token": self.code(token)}
        commands = self.parallel(lambda: redeem(self.device, body))
        self.assertEqual(commands[0], commands[1])
        receipt = self.local.apply(commands[0])
        self.assertEqual(sorted(self.parallel(lambda: acknowledge(self.device, receipt))), [False, True])
        self.assertEqual(MeterDelivery.objects.count(), 1)
        self.assertEqual(BenchApplicationReceipt.objects.count(), 1)
        self.assertEqual(self.local.db.execute("SELECT applied FROM state").fetchone()[0], token.amount_wh)

    def test_concurrent_issuance_and_automatic_reservation_share_one_lock(self):
        with override_settings(ENERGY_TOKEN_ISSUANCE_ENABLED=False):
            intent = self.purchase(); self.settle(intent)
        allocation = EnergyAllocation.objects.get(purchase_intent=intent)
        issued = self.parallel(lambda: issue_energy_token(allocation).pk)
        self.assertEqual(issued[0], issued[1])
        self.assertEqual(EnergyKeypadToken.objects.count(), 1)
        with override_settings(ENERGY_TOKEN_ISSUANCE_ENABLED=False):
            other = self.purchase(); self.settle(other)
        other_allocation = EnergyAllocation.objects.get(purchase_intent=other)
        barrier = Barrier(2)
        def run(is_token):
            close_old_connections(); barrier.wait(timeout=10)
            try:
                if is_token:
                    issue_energy_token(other_allocation)
                else:
                    reserve_for_delivery(owner=self.owner, meter_no=self.meter.meter_no,
                                         amount_kwh=str(other_allocation.amount_kwh))
                return True
            except (EnergyTokenError, AllocationError):
                return False
            finally:
                connection.close()
        with override_settings(DEBUG=True, SIMULATED_METER_ENABLED=True):
            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertEqual(sorted(pool.map(run, (True, False))), [False, True])
        self.assertEqual(int(EnergyKeypadToken.objects.filter(allocation=other_allocation).exists()) +
                         int(other_allocation.deliveries.exists()), 1)

    def test_delayed_first_receipt_after_second_application(self):
        receipts = []
        for _ in range(2):
            token = self.purchased_token()
            receipts.append(self.local.apply(redeem(self.device, {"contract_version": 1, "token": self.code(token)})))
        self.assertTrue(acknowledge(self.device, receipts[1]))
        self.assertTrue(acknowledge(self.device, receipts[0]))
        self.assertFalse(acknowledge(self.device, receipts[0]))
        self.device.refresh_from_db()
        self.assertEqual(self.device.last_application_counter, 2)
        self.assertEqual(BenchApplicationReceipt.objects.count(), 2)

    def test_http_rate_limit_and_missing_redisplay_keys_fail_closed(self):
        for _ in range(120): rate_attempt("ip:127.0.0.1", 120)
        response = self.client.post("/api/v1/bench-device/v1/redeem/", {}, format="json", **self.headers_device)
        self.assertEqual(response.status_code, 429)
        token = self.purchased_token()
        with override_settings(ENERGY_TOKEN_ENCRYPTION_KEYS=[]):
            response = self.client.get(f"/api/v1/meter/energy-tokens/?allocation_id={token.allocation_id}")
        self.assertEqual(response.status_code, 503)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(token.state, "ISSUED")

    def test_shared_rate_limit_persists_and_api_does_not_log_tokens(self):
        for _ in range(3): rate_attempt("test-counter", 3)
        import meter.bench_device as module
        with self.assertRaises(module.BenchError): module.rate_attempt("test-counter", 3)
        self.assertEqual(DeviceAttemptBucket.objects.get(key=__import__('hashlib').sha256(b'test-counter').hexdigest()).count, 3)
        token = self.purchased_token()
        with patch("logging.Logger._log") as logged:
            response = self.client.post("/api/v1/bench-device/v1/redeem/", {"contract_version": 1, "token": self.code(token)}, format="json", **self.headers_device)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.code(token), str(logged.call_args_list))

    def test_historical_numbers_remain_readable_report_is_dry_run(self):
        legacy = Meter.all_objects.bulk_create([Meter(user=self.owner, meter_no="OLD-A/0001", sandbox_inventory=True)])[0]
        output = StringIO(); call_command("report_meter_numbers", stdout=output)
        self.assertIn(f"meter_id={legacy.pk}", output.getvalue())
        self.assertNotIn(self.owner.email, output.getvalue())
        legacy.refresh_from_db(); self.assertEqual(legacy.meter_no, "OLD-A/0001")
        self.assertEqual(self.client.get(f"/api/v1/meter/mobile-meters/{legacy.pk}/").status_code, 200)
