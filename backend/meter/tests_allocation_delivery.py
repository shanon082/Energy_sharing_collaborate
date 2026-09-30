"""PostgreSQL conservation and restart tests for new simulated entitlement."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import importlib
from threading import Barrier
from unittest.mock import patch
import uuid

from django.contrib.auth.hashers import make_password
from django.db import close_old_connections, connection
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User, Wallet as AccountWallet
from loan.models import LoanApplication
from loan.services import LoanOperationError, disburse_loan
from meter.allocation_service import (
    AllocationError, authorize_purchase_allocation, entitlement_summary,
    reserve_for_delivery,
)
from meter.models import (
    EnergyAllocation, Meter, MeterDelivery, SimulatedCommand, SimulatedMeter,
    SimulatedTelemetry,
)
from meter.simulation import (
    acknowledge_application, apply_simulated_command,
    dispatch_delivery, record_telemetry, simulate_consumption,
)
import meter.simulation as simulation_module
from meter.tasks import dispatch_simulated_outbox
from transactions.models import PaymentIntent, Transaction
from wallet.models import UnitBalance


@override_settings(DEBUG=True, SIMULATED_METER_ENABLED=True)
class AllocationDeliveryTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="allocated@example.invalid", password="test-only")
        self.other = User.objects.create_user(email="other@example.invalid", password="test-only")
        self.meter = Meter.objects.create(
            user=self.user, meter_no="SIM-OWN-1", architecture=Meter.ARCH_AMI,
        )
        self.other_meter = Meter.objects.create(
            user=self.other, meter_no="SIM-OTHER-1", architecture=Meter.ARCH_AMI,
        )
        self.device = SimulatedMeter.objects.create(
            meter=self.meter, credential_hash=make_password("simulator-only-credential"),
        )
        self.other_device = SimulatedMeter.objects.create(
            meter=self.other_meter, credential_hash=make_password("other-simulator-credential"),
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def allocation(self, amount="1.00"):
        reference = uuid.uuid4()
        wallet = AccountWallet.objects.create(user=self.user)
        purchase = Transaction.objects.create(
            wallet=wallet, amount=Decimal("10000.00"),
            phone_number="+256700000001", status="COMPLETED",
            transaction_reference=str(reference),
        )
        intent = PaymentIntent.objects.create(
            owner=self.user, purpose=PaymentIntent.PURCHASE,
            amount=Decimal("10000.00"), currency="UGX",
            provider="MTN_PRODUCTION", provider_reference=reference,
            provider_external_id=f"gpawa-purchase-{reference}",
            purchase=purchase, meter=self.meter, status=PaymentIntent.SETTLED,
            provider_transaction_id=str(uuid.uuid4()),
        )
        return authorize_purchase_allocation(intent, Decimal(amount))

    def test_historical_unit_balance_cannot_authorize_delivery(self):
        balance = UnitBalance.objects.get(user=self.user)
        balance.balance = Decimal("100.00")
        balance.save(update_fields=["balance"])
        with self.assertRaises(AllocationError):
            reserve_for_delivery(owner=self.user, meter_no=self.meter.meter_no, amount_kwh="1.00")
        self.assertEqual(MeterDelivery.objects.count(), 0)

    def test_unenrolled_simulator_does_not_reserve_allocation(self):
        self.allocation()
        self.device.delete()
        response = self.client.post("/api/v1/meter/deliver/", {
            "meter_no": self.meter.meter_no, "amount": "0.25",
        }, format="json")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "SIMULATOR_NOT_ENROLLED")
        self.assertEqual(MeterDelivery.objects.count(), 0)

    def test_concurrent_reservations_do_not_exceed_one_allocation(self):
        allocation = self.allocation()
        barrier = Barrier(2)

        def request_reservation():
            close_old_connections()
            barrier.wait(timeout=10)
            try:
                try:
                    return len(reserve_for_delivery(
                        owner=self.user, meter_no=self.meter.meter_no,
                        amount_kwh="0.75",
                    ))
                except AllocationError:
                    return 0
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _: request_reservation(), range(2)))
        self.assertEqual(sorted(outcomes), [0, 1])
        self.assertEqual(sum(row.amount_kwh for row in allocation.deliveries.all()), Decimal("0.75"))
        summary = entitlement_summary(self.user, self.meter)
        self.assertEqual(summary["available_kwh"], Decimal("0.25"))
        self.assertEqual(summary["pending_kwh"], Decimal("0.75"))

    def test_reservation_spanning_sources_preserves_each_allocation(self):
        first = self.allocation("1.00")
        second = self.allocation("1.00")
        deliveries = reserve_for_delivery(
            owner=self.user, meter_no=self.meter.meter_no, amount_kwh="1.50",
        )
        self.assertEqual(len(deliveries), 2)
        self.assertEqual(
            {row.allocation_id: row.amount_kwh for row in deliveries},
            {first.pk: Decimal("1.00"), second.pk: Decimal("0.50")},
        )
        self.assertEqual(entitlement_summary(self.user, self.meter)["available_kwh"], Decimal("0.50"))

    def test_duplicate_dispatch_and_acknowledgement_apply_once(self):
        self.allocation()
        delivery = reserve_for_delivery(
            owner=self.user, meter_no=self.meter.meter_no, amount_kwh="0.50",
        )[0]
        first, changed = dispatch_delivery(delivery.pk)
        self.assertTrue(changed)
        self.assertEqual(first.status, MeterDelivery.APPLIED)
        second, changed = dispatch_delivery(delivery.pk)
        self.assertFalse(changed)
        ack, changed = acknowledge_application(
            device_id=self.device.device_id, command_id=delivery.command_id,
            delivery_id=delivery.pk, amount_kwh="0.50",
        )
        self.assertFalse(changed)
        self.assertEqual(ack.status, MeterDelivery.APPLIED)
        self.device.refresh_from_db()
        self.assertEqual(self.device.applied_kwh, Decimal("0.50"))
        self.assertEqual(SimulatedCommand.objects.count(), 1)

    def test_concurrent_dispatch_uses_one_durable_command(self):
        self.allocation()
        delivery = reserve_for_delivery(
            owner=self.user, meter_no=self.meter.meter_no, amount_kwh="0.50",
        )[0]
        barrier = Barrier(2)

        def dispatch_in_thread():
            close_old_connections()
            barrier.wait(timeout=10)
            try:
                return dispatch_delivery(delivery.pk)[0].status
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(lambda _: dispatch_in_thread(), range(2)))
        delivery.refresh_from_db()
        self.device.refresh_from_db()
        self.assertEqual(delivery.status, MeterDelivery.APPLIED)
        self.assertEqual(self.device.applied_kwh, Decimal("0.50"))
        self.assertEqual(SimulatedCommand.objects.filter(command_id=delivery.command_id).count(), 1)

    def test_lost_ack_after_application_retries_same_command(self):
        self.allocation()
        delivery = reserve_for_delivery(
            owner=self.user, meter_no=self.meter.meter_no, amount_kwh="0.40",
        )[0]
        with patch("meter.simulation.acknowledge_application", side_effect=simulation_module.SimulationError("lost")):
            first, changed = dispatch_delivery(delivery.pk)
        self.assertFalse(changed)
        self.assertEqual(first.status, MeterDelivery.OUTCOME_UNKNOWN)
        self.device.refresh_from_db()
        self.assertEqual(self.device.applied_kwh, Decimal("0.40"))
        # The application identity is in PostgreSQL, not process memory.
        importlib.reload(simulation_module)
        second, changed = dispatch_delivery(delivery.pk)
        self.assertTrue(changed)
        self.assertEqual(second.status, MeterDelivery.APPLIED)
        self.device.refresh_from_db()
        self.assertEqual(self.device.applied_kwh, Decimal("0.40"))
        self.assertEqual(SimulatedCommand.objects.count(), 1)
        self.assertEqual(delivery.command_id, second.command_id)

    def test_worker_restart_uses_persisted_outbox(self):
        self.allocation()
        delivery = reserve_for_delivery(
            owner=self.user, meter_no=self.meter.meter_no, amount_kwh="0.30",
        )[0]
        importlib.reload(simulation_module)
        self.assertEqual(dispatch_simulated_outbox(), 1)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, MeterDelivery.APPLIED)
        self.assertEqual(dispatch_simulated_outbox(), 0)
        self.assertEqual(SimulatedCommand.objects.count(), 1)

    def test_wrong_device_and_assignment_change_never_apply(self):
        self.allocation()
        delivery = reserve_for_delivery(
            owner=self.user, meter_no=self.meter.meter_no, amount_kwh="0.20",
        )[0]
        delivery.status = MeterDelivery.DISPATCHED
        delivery.save(update_fields=["status"])
        with self.assertRaises(simulation_module.SimulationError):
            apply_simulated_command(delivery.pk, self.other_device.device_id)
        with self.assertRaises(simulation_module.SimulationError):
            acknowledge_application(
                device_id=self.other_device.device_id, command_id=delivery.command_id,
                delivery_id=delivery.pk, amount_kwh="0.20",
            )
        Meter.objects.filter(pk=self.meter.pk).update(user=self.other)
        result, changed = dispatch_delivery(delivery.pk)
        self.assertFalse(changed)
        self.assertEqual(result.status, MeterDelivery.FAILED)
        self.assertEqual(SimulatedCommand.objects.count(), 0)
        self.assertEqual(entitlement_summary(self.user)["pending_kwh"], Decimal("0.20"))

    def test_telemetry_duplicate_gap_reorder_delay_and_reset(self):
        now = timezone.now()
        boot = uuid.uuid4()
        first, _ = record_telemetry(
            device=self.device, event_id=uuid.uuid4(), boot_id=boot,
            sequence=1, cumulative_wh=1000, measured_at=now,
            reported_relay_state="CLOSED",
        )
        gap, _ = record_telemetry(
            device=self.device, event_id=uuid.uuid4(), boot_id=boot,
            sequence=3, cumulative_wh=1300, measured_at=now + timezone.timedelta(seconds=2),
            reported_relay_state="CLOSED",
        )
        repeated, created = record_telemetry(
            device=self.device, event_id=gap.event_id, boot_id=boot,
            sequence=3, cumulative_wh=1300, measured_at=now + timezone.timedelta(seconds=2),
            reported_relay_state="CLOSED",
        )
        reordered, _ = record_telemetry(
            device=self.device, event_id=uuid.uuid4(), boot_id=boot,
            sequence=2, cumulative_wh=1200, measured_at=now + timezone.timedelta(seconds=1),
            reported_relay_state="OPEN",
        )
        delayed, _ = record_telemetry(
            device=self.device, event_id=uuid.uuid4(), boot_id=boot,
            sequence=4, cumulative_wh=1400, measured_at=now + timezone.timedelta(seconds=1),
            reported_relay_state="OPEN",
        )
        next_boot = uuid.uuid4()
        reset, _ = record_telemetry(
            device=self.device, event_id=uuid.uuid4(), boot_id=next_boot,
            sequence=0, cumulative_wh=10, measured_at=now + timezone.timedelta(seconds=3),
            reported_relay_state="UNKNOWN",
        )
        prior_boot_delayed, _ = record_telemetry(
            device=self.device, event_id=uuid.uuid4(), boot_id=boot,
            sequence=5, cumulative_wh=1500,
            measured_at=now + timezone.timedelta(milliseconds=2500),
            reported_relay_state="CLOSED",
        )
        discontinuity, _ = record_telemetry(
            device=self.device, event_id=uuid.uuid4(), boot_id=next_boot,
            sequence=1, cumulative_wh=5, measured_at=now + timezone.timedelta(seconds=4),
            reported_relay_state="UNKNOWN",
        )
        with self.assertRaises(simulation_module.SimulationError):
            record_telemetry(
                device=self.device, event_id=gap.event_id, boot_id=boot,
                sequence=3, cumulative_wh=9999,
                measured_at=now + timezone.timedelta(seconds=2),
                reported_relay_state="CLOSED",
            )
        self.device.refresh_from_db()
        self.assertEqual(first.classification, "INITIAL")
        self.assertEqual(gap.classification, "GAP")
        self.assertFalse(created)
        self.assertEqual(repeated.pk, gap.pk)
        self.assertEqual(reordered.classification, "REORDERED")
        self.assertEqual(delayed.classification, "DELAYED")
        self.assertEqual(reset.classification, "RESET")
        self.assertEqual(prior_boot_delayed.classification, "DELAYED")
        self.assertEqual(discontinuity.classification, "DISCONTINUITY")
        self.assertEqual(self.device.consumed_wh, 300)
        self.assertEqual(self.device.reset_count, 1)
        self.assertEqual(self.device.boot_id, next_boot)
        self.assertEqual(SimulatedTelemetry.objects.count(), 7)

    def test_simulator_enforces_local_remaining_energy(self):
        self.allocation()
        delivery = reserve_for_delivery(
            owner=self.user, meter_no=self.meter.meter_no, amount_kwh="0.10",
        )[0]
        dispatch_delivery(delivery.pk)
        simulate_consumption(self.device.device_id, 60)
        simulate_consumption(self.device.device_id, 40)
        with self.assertRaises(simulation_module.SimulationError):
            simulate_consumption(self.device.device_id, 1)
        self.device.refresh_from_db()
        self.assertEqual(self.device.consumed_wh, 100)
        self.assertEqual(self.device.reported_relay_state, "OPEN")

    def test_concurrent_simulated_consumption_cannot_exceed_applied_energy(self):
        self.allocation()
        delivery = reserve_for_delivery(
            owner=self.user, meter_no=self.meter.meter_no, amount_kwh="0.10",
        )[0]
        dispatch_delivery(delivery.pk)
        barrier = Barrier(2)

        def consume_in_thread():
            close_old_connections()
            barrier.wait(timeout=10)
            try:
                try:
                    simulate_consumption(self.device.device_id, 60)
                    return True
                except simulation_module.SimulationError:
                    return False
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _: consume_in_thread(), range(2)))
        self.assertEqual(sorted(outcomes), [False, True])
        self.device.refresh_from_db()
        self.assertEqual(self.device.consumed_wh, 60)

    def test_duplicate_loan_disbursement_produces_one_allocation(self):
        loan = LoanApplication.objects.create(
            user=self.user, intended_meter=self.meter,
            amount_requested=Decimal("10000"), amount_approved=Decimal("10000"),
            tenure_months=1, interest_rate=Decimal("0"), status="APPROVED",
            purpose="Electricity",
        )
        with patch("loan.services.dispatch_task"):
            result = disburse_loan(self.user, loan.pk, channel="TEST")
            with self.assertRaises(LoanOperationError):
                disburse_loan(self.user, loan.pk, channel="RETRY")
        self.assertEqual(EnergyAllocation.objects.filter(loan_disbursement__loan_application=loan).count(), 1)
        self.assertEqual(result["meter_no"], self.meter.meter_no)

    def test_concurrent_loan_disbursement_allocates_once(self):
        loan = LoanApplication.objects.create(
            user=self.user, intended_meter=self.meter,
            amount_requested=Decimal("10000"), amount_approved=Decimal("10000"),
            tenure_months=1, interest_rate=Decimal("0"), status="APPROVED",
            purpose="Electricity",
        )
        barrier = Barrier(2)

        def disburse_in_thread():
            close_old_connections()
            barrier.wait(timeout=10)
            try:
                try:
                    disburse_loan(self.user, loan.pk, channel="TEST")
                    return True
                except LoanOperationError:
                    return False
            finally:
                connection.close()

        with patch("loan.services.dispatch_task"):
            with ThreadPoolExecutor(max_workers=2) as executor:
                outcomes = list(executor.map(lambda _: disburse_in_thread(), range(2)))
        self.assertEqual(sorted(outcomes), [False, True])
        self.assertEqual(EnergyAllocation.objects.filter(loan_disbursement__loan_application=loan).count(), 1)

    def test_admin_legacy_disbursement_requires_meter_and_allocates_once(self):
        loan = LoanApplication.objects.create(
            user=self.user, amount_requested=Decimal("10000"),
            amount_approved=Decimal("10000"), tenure_months=1,
            interest_rate=Decimal("0"), status="APPROVED", purpose="Electricity",
        )
        self.other.user_role = User.OPERATOR
        self.other.save(update_fields=["user_role"])
        self.client.force_authenticate(user=self.other)
        url = f"/api/v1/admin/loans/{loan.pk}/disburse/"
        with patch("loan.services.dispatch_task"):
            missing = self.client.post(url, {}, format="json")
            self.assertEqual(missing.status_code, 400)
            self.assertEqual(EnergyAllocation.objects.count(), 0)
            first = self.client.post(url, {"meter_no": self.meter.meter_no}, format="json")
            self.assertEqual(first.status_code, 200, first.data)
            duplicate = self.client.post(url, {"meter_no": self.meter.meter_no}, format="json")
            self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(EnergyAllocation.objects.filter(loan_disbursement__loan_application=loan).count(), 1)

    def test_owner_api_requires_attributable_entitlement_and_device_auth(self):
        self.allocation()
        response = self.client.post("/api/v1/meter/deliver/", {
            "meter_no": self.meter.meter_no, "amount": "0.25",
        }, format="json")
        self.assertEqual(response.status_code, 202, response.data)
        status = self.client.get(f"/api/v1/meter/allocation-status/?meter_no={self.meter.meter_no}")
        self.assertEqual(status.data["available_kwh"], "0.75")
        self.assertEqual(status.data["pending_kwh"], "0.25")
        self.assertEqual(status.data["confirmed_kwh"], "0.00")
        self.client.force_authenticate(user=None)
        bad_ack = self.client.post("/api/v1/meter/simulator/ack/", {
            "delivery_id": response.data["deliveries"][0]["id"],
            "command_id": response.data["deliveries"][0]["command_id"],
            "amount_kwh": "0.25",
        }, format="json")
        self.assertEqual(bad_ack.status_code, 401)
        delivery = MeterDelivery.objects.get(pk=response.data["deliveries"][0]["id"])
        dispatch_delivery(delivery.pk)
        payload = {
            "contract_version": 1, "delivery_id": delivery.pk,
            "command_id": str(delivery.command_id), "amount_kwh": "0.25",
        }
        wrong_device = self.client.post(
            "/api/v1/meter/simulator/ack/", payload, format="json",
            HTTP_X_SIM_DEVICE_ID=str(self.other_device.device_id),
            HTTP_X_SIM_DEVICE_TOKEN="other-simulator-credential",
        )
        self.assertEqual(wrong_device.status_code, 409)
        correct = self.client.post(
            "/api/v1/meter/simulator/ack/", payload, format="json",
            HTTP_X_SIM_DEVICE_ID=str(self.device.device_id),
            HTTP_X_SIM_DEVICE_TOKEN="simulator-only-credential",
        )
        self.assertEqual(correct.status_code, 200)
        self.assertFalse(correct.data["newly_applied"])
