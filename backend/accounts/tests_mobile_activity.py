"""Stage 3 reads/alert metadata against isolated PostgreSQL, never live systems."""
from decimal import Decimal
from unittest.mock import patch
import uuid

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User, Wallet
from meter.models import Meter, MeterUsageDaily, SimulatedMeter, SimulatedTelemetry, SimulatedCommand, EnergyAllocation, MeterDelivery
from transactions.models import PaymentIntent, Transaction, TransactionLog


class MobileActivityTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="activity-owner@example.invalid", password="Test-only-123")
        self.other = User.objects.create_user(email="activity-other@example.invalid", password="Test-only-123")
        for user in (self.owner, self.other):
            user.profile.email_verified = True
            user.profile.save(update_fields=["email_verified"])
        self.meter = Meter.objects.create(user=self.owner, meter_no="ACTIVITY-OWN")
        self.foreign = Meter.objects.create(user=self.other, meter_no="ACTIVITY-OTHER")
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(self.owner).access_token}")

    def intent(self, user=None, meter=None):
        user, meter = user or self.owner, meter or self.meter
        wallet, _ = Wallet.objects.get_or_create(user=user)
        purchase = Transaction.objects.create(wallet=wallet, amount=Decimal("1000"), phone_number="+256700000000")
        reference = uuid.uuid4()
        return PaymentIntent.objects.create(owner=user, meter=meter, purchase=purchase,
            purpose=PaymentIntent.PURCHASE, amount=Decimal("1000"), provider="SIMULATED",
            provider_reference=reference, provider_external_id=str(reference))

    def test_pending_receipt_and_detail_are_owner_bound_read_only(self):
        own = self.intent()
        foreign = self.intent(self.other, self.foreign)
        with patch("transactions.payment_settlement.reconcile_payment") as settle:
            response = self.client.get("/api/v1/transactions/mobile-receipts/?owner=999")
            self.assertEqual(response.status_code, 200)
            self.assertEqual([r["external_id"] for r in response.data["receipts"]], [str(own.provider_reference)])
            self.assertFalse(response.data["receipts"][0]["settlement_recorded"])
            self.assertEqual(response.data["receipts"][0]["environment"], "SIMULATOR")
            self.assertEqual(self.client.get(f"/api/v1/transactions/mobile-receipts/{foreign.provider_reference}/").status_code, 404)
            self.assertEqual(self.client.get(f"/api/v1/transactions/mobile-receipts/{own.provider_reference}/").status_code, 200)
            settle.assert_not_called()
        own.refresh_from_db()
        self.assertEqual(own.status, PaymentIntent.PENDING)
        self.assertFalse(EnergyAllocation.objects.exists())

    def test_exact_residuals_survive_receipt_and_no_history_repair(self):
        intent = self.intent()
        intent.status = PaymentIntent.SETTLED
        intent.settled_at = timezone.now()
        intent.purchase_billed_ugx = Decimal("999.37")
        intent.purchase_residual_ugx = Decimal("0.63")
        intent.save()
        response = self.client.get(f"/api/v1/transactions/mobile-receipts/{intent.provider_reference}/")
        row = response.data["receipt"]
        self.assertTrue(row["settlement_recorded"])
        self.assertEqual((row["amount_ugx"], row["purchase_billed_ugx"], row["purchase_residual_ugx"]), ("1000.00", "999.37", "0.63"))
        self.assertFalse(EnergyAllocation.objects.exists())

    def test_delivery_identity_states_and_no_new_owner_entitlement(self):
        allocation = EnergyAllocation.objects.create(owner=self.owner, meter=self.meter, amount_kwh=Decimal("1.00"), purchase_intent=self.intent())
        for status in (MeterDelivery.QUEUED, MeterDelivery.DISPATCHED, MeterDelivery.OUTCOME_UNKNOWN, MeterDelivery.APPLIED):
            MeterDelivery.objects.create(allocation=allocation, amount_kwh=Decimal("0.10"), status=status)
        result = self.client.get(f"/api/v1/meter/mobile-deliveries/?meter_id={self.meter.pk}")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.data["deliveries"]), 4)
        self.assertTrue(all(not r["application_confirmed"] for r in result.data["deliveries"]))
        row = MeterDelivery.objects.filter(status=MeterDelivery.APPLIED).get()
        row.applied_at = timezone.now(); row.save(update_fields=["applied_at"])
        result = self.client.get(f"/api/v1/meter/mobile-deliveries/?meter_id={self.meter.pk}")
        self.assertFalse(any(r["application_confirmed"] for r in result.data["deliveries"]))
        device = SimulatedMeter.objects.create(meter=self.foreign, credential_hash="synthetic-hash")
        command = SimulatedCommand.objects.create(device=device, delivery=row, command_id=row.command_id, amount_kwh=row.amount_kwh)
        result = self.client.get(f"/api/v1/meter/mobile-deliveries/?meter_id={self.meter.pk}")
        self.assertFalse(any(r["application_confirmed"] for r in result.data["deliveries"]))
        device = SimulatedMeter.objects.create(meter=self.meter, credential_hash="synthetic-hash")
        command.device = device; command.save(update_fields=["device"])
        result = self.client.get(f"/api/v1/meter/mobile-deliveries/?meter_id={self.meter.pk}")
        self.assertEqual(sum(r["application_confirmed"] for r in result.data["deliveries"]), 1)
        Meter.objects.filter(pk=self.meter.pk).update(user=self.other)
        self.assertEqual(self.client.get(f"/api/v1/meter/mobile-deliveries/?meter_id={self.meter.pk}").status_code, 404)
        other = APIClient(); other.force_authenticate(self.other)
        self.assertEqual(other.get(f"/api/v1/meter/mobile-deliveries/?meter_id={self.meter.pk}").data["deliveries"], [])

    def test_consumption_requires_matching_identity_and_keeps_wh_exact(self):
        MeterUsageDaily.objects.create(meter=self.meter, usage_date="2026-10-10", kwh_used=Decimal("0.0001"), source="STUB")
        device = SimulatedMeter.objects.create(meter=self.meter, credential_hash="synthetic-hash")
        SimulatedTelemetry.objects.create(device=device, event_id=uuid.uuid4(), boot_id=uuid.uuid4(), sequence=4,
            cumulative_wh=9007199254740993, measured_at=timezone.now(), reported_relay_state="OPEN", classification="REORDERED")
        response = self.client.get(f"/api/v1/meter/mobile-consumption/?meter_id={self.meter.pk}")
        self.assertEqual(response.data["daily_usage"][0]["kwh"], "0.0001")
        self.assertEqual(response.data["simulator_telemetry"][0]["cumulative_wh_exact"], "9007199254740993")
        self.assertFalse(response.data["consumer_attribution_available"])
        self.assertEqual(self.client.get(f"/api/v1/meter/mobile-consumption/?meter_id={self.meter.pk}&meter_no=wrong").status_code, 400)
        self.assertEqual(self.client.get(f"/api/v1/meter/mobile-consumption/?meter_id={self.foreign.pk}").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/meter/mobile-consumption/?meter_id=" + "9" * 100).status_code, 400)

    def test_notifications_do_not_expose_device_keys_and_read_only_targets_owner(self):
        from meter.models import MeterNotification
        own = MeterNotification.objects.create(user=self.owner, meter=self.meter, units_kwh=Decimal("0.0001"),
            occurred_at=timezone.now(), device_token="never-return-this", message="Test alert")
        foreign = MeterNotification.objects.create(user=self.other, meter=self.foreign, units_kwh=0, occurred_at=timezone.now())
        listing = self.client.get("/api/v1/meter/mobile-notifications/")
        self.assertEqual([r["id"] for r in listing.data["notifications"]], [own.pk])
        self.assertNotIn("device_token", listing.data["notifications"][0])
        self.assertEqual(self.client.patch("/api/v1/meter/mobile-notifications/", {"ids": [own.pk, foreign.pk]}, format="json").status_code, 404)
        own.refresh_from_db(); self.assertFalse(own.is_read)
        for payload in ({"all": "false"}, {"ids": [own.pk], "user": self.other.pk}, {"ids": []}, {"ids": [True]}):
            self.assertEqual(self.client.patch("/api/v1/meter/mobile-notifications/", payload, format="json").status_code, 400)
        response = self.client.patch("/api/v1/meter/mobile-notifications/", {"ids": [own.pk]}, format="json")
        self.assertEqual(response.data["marked_read"], 1)
        self.assertEqual(self.client.patch("/api/v1/meter/mobile-notifications/", {"ids": [own.pk]}, format="json").data["marked_read"], 0)
        foreign.refresh_from_db(); self.assertFalse(foreign.is_read)

    def test_pagination_is_bounded_and_stable_when_new_records_arrive(self):
        rows = [TransactionLog.objects.create(user=self.owner, transaction_type="UNIT_PURCHASE", amount=Decimal("0.13")) for _ in range(3)]
        TransactionLog.objects.create(user=self.other, transaction_type="UNIT_PURCHASE", amount=900)
        first = self.client.get("/api/v1/transactions/mobile-history/?limit=2")
        self.assertEqual([r["id"] for r in first.data["transactions"]], [rows[2].pk, rows[1].pk])
        self.assertEqual(first.data["transactions"][0]["recorded_amount"], "0.13")
        self.assertFalse(first.data["transactions"][0]["units_confirmed"])
        TransactionLog.objects.create(user=self.owner, transaction_type="UNIT_PURCHASE", amount=1)
        second = self.client.get(f"/api/v1/transactions/mobile-history/?before_id={first.data['pagination']['next_before_id']}&limit=2")
        self.assertEqual([r["id"] for r in second.data["transactions"]], [rows[0].pk])
        self.assertFalse(second.data["pagination"]["has_more"])
        for query in ("limit=0", "limit=51", "before_id=-1", "before_id=not-an-id"):
            self.assertEqual(self.client.get("/api/v1/transactions/mobile-history/?" + query).status_code, 400)

    def test_mobile_session_authentication_enforces_consumer_and_account_state(self):
        session = APIClient(); session.force_login(self.owner)
        endpoints = ["/api/v1/transactions/mobile-history/", "/api/v1/transactions/mobile-receipts/", "/api/v1/meter/mobile-notifications/"]
        self.owner.is_staff = True; self.owner.save(update_fields=["is_staff"])
        for path in endpoints: self.assertEqual(session.get(path).status_code, 403)
        self.owner.is_staff = False; self.owner.must_change_password = True
        self.owner.save(update_fields=["is_staff", "must_change_password"])
        for path in endpoints: self.assertEqual(session.get(path).status_code, 403)
        self.owner.must_change_password = False; self.owner.save(update_fields=["must_change_password"])
        self.owner.profile.email_verified = False; self.owner.profile.save(update_fields=["email_verified"])
        for path in endpoints: self.assertEqual(session.get(path).status_code, 403)
        public = APIClient()
        for path in endpoints: self.assertIn(public.get(path).status_code, (401, 403))
