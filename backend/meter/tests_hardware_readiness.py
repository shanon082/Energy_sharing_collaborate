"""Isolated device containment/replay tests; never contact gateways or hardware."""

from decimal import Decimal
from unittest.mock import patch
import uuid

from django.contrib.auth.hashers import make_password
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from meter.device_access import DeviceOperationUnavailable
from meter.models import (EnergyAllocation, Meter, MeterBalanceSnapshot, MeterDelivery,
                          MeterNotification, MeterUsageDaily, SimulatedCommand,
                          SimulatedMeter, SimulatedTelemetry)
from meter.simulation import SimulationError, record_telemetry


class HardwareFixture(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="bench@example.invalid", password="test-only")
        self.meter = Meter.objects.create(user=self.owner, meter_no="BENCH-001", architecture="AMI")
        self.device = SimulatedMeter.objects.create(meter=self.meter,
            credential_hash=make_password("simulator-only-test-credential"))
        self.client = APIClient()


@override_settings(DEBUG=True, SIMULATED_METER_ENABLED=True, ALWAYSDATA_TESTING=False,
                   CONSUMER_SANDBOX_ENABLED=False)
class TelemetryReadinessTests(HardwareFixture):
    def event(self, **overrides):
        values = dict(device=self.device, event_id=uuid.uuid4(), boot_id=uuid.uuid4(),
                      sequence=0, cumulative_wh=0, measured_at=timezone.now(),
                      reported_relay_state="UNKNOWN")
        values.update(overrides)
        return record_telemetry(**values)

    def test_retired_boot_with_later_clock_cannot_replace_current_state(self):
        old, new = uuid.uuid4(), uuid.uuid4()
        now = timezone.now()
        self.event(boot_id=old, measured_at=now)
        self.event(boot_id=new, measured_at=now + timezone.timedelta(seconds=1))
        event, _ = self.event(boot_id=old, sequence=99, cumulative_wh=5000,
                             measured_at=now + timezone.timedelta(seconds=2), reported_relay_state="CLOSED")
        self.device.refresh_from_db()
        self.assertEqual(event.classification, "DELAYED")
        self.assertEqual(self.device.boot_id, new)
        self.assertEqual(self.device.last_sequence, 0)
        self.assertEqual(self.device.consumed_wh, 0)
        self.assertEqual(self.device.reported_relay_state, "UNKNOWN")
        self.assertEqual(self.device.reset_count, 1)

    def test_exact_integer_payload_and_database_bounds_required(self):
        for field in ("sequence", "cumulative_wh"):
            for value in (True, 1.5, "2", -1, 2**63):
                with self.subTest(field=field, value=value), self.assertRaises(SimulationError):
                    self.event(**{field: value})
        self.assertFalse(SimulatedTelemetry.objects.exists())

    def test_suspended_deleted_or_unassigned_meter_cannot_submit(self):
        for changes in ({"status": "SUSPENDED"}, {"status": "ACTIVE", "is_deleted": True},
                        {"is_deleted": False, "user": None}):
            Meter.all_objects.filter(pk=self.meter.pk).update(**changes)
            with self.assertRaises(SimulationError):
                self.event()
        self.assertFalse(SimulatedTelemetry.objects.exists())

    def test_telemetry_never_creates_credit_or_application_receipt(self):
        self.event(cumulative_wh=900)
        self.device.refresh_from_db()
        self.assertEqual(self.device.applied_kwh, Decimal("0"))
        self.assertFalse(EnergyAllocation.objects.exists())
        self.assertFalse(MeterDelivery.objects.exists())
        self.assertFalse(SimulatedCommand.objects.exists())


class LegacyContainmentTests(HardwareFixture):
    def test_consumer_cannot_replace_device_identity_but_can_edit_label(self):
        self.client.force_authenticate(self.owner)
        for field, value in (("meter_no", "OTHER-DEVICE"), ("iot_device_token", "not-a-real-key"),
                             ("architecture", "STS"), ("static_ip", "127.0.0.1")):
            result = self.client.patch("/api/v1/meter/update/", {
                "current_meter_no": self.meter.meter_no, field: value,
            }, format="json")
            self.assertEqual(result.status_code, 403)
            self.assertEqual(result.data["code"], "DEVICE_PROVISIONING_FORBIDDEN")
        result = self.client.patch("/api/v1/meter/update/", {
            "current_meter_no": self.meter.meter_no, "label": "Kitchen",
        }, format="json")
        self.assertEqual(result.status_code, 200)
        self.meter.refresh_from_db()
        self.assertEqual(self.meter.label, "Kitchen")
        self.assertEqual(self.meter.meter_no, "BENCH-001")
        self.assertIsNone(self.meter.iot_device_token)
        self.assertEqual(self.meter.architecture, "AMI")
        denied = self.client.patch("/api/v1/meter/update/", {
            "current_meter_no": "FOREIGN-001", "label": "Mine",
        }, format="json")
        self.assertEqual(denied.status_code, 404)

    def test_staff_redelivery_does_not_log_token_or_claim_unsent_delivery(self):
        from admin.views import TokenRedeliveryView
        from rest_framework.test import APIRequestFactory, force_authenticate
        request = APIRequestFactory().post("/unused/", {}, format="json")
        self.owner.user_role = User.OPERATOR
        force_authenticate(request, user=self.owner)
        with patch("admin.views._write_audit") as audit:
            result = TokenRedeliveryView.as_view()(request, transaction_id=uuid.uuid4())
            self.assertEqual(result.status_code, 503)
            self.assertEqual(result.data["code"], "TOKEN_REDELIVERY_UNAVAILABLE")
            audit.assert_not_called()

    @override_settings(THINGSBOARD_WEBHOOK_SECRET="")
    def test_missing_credentials_fail_closed(self):
        for path in ("low-units", "daily-usage"):
            response = self.client.post(f"/webhooks/thingsboard/{path}", {}, format="json")
            self.assertEqual(response.status_code, 401)
        self.assertFalse(MeterBalanceSnapshot.objects.exists())
        self.assertFalse(MeterUsageDaily.objects.exists())

    @override_settings(THINGSBOARD_WEBHOOK_SECRET="test-webhook-only")
    def test_valid_shared_secret_cannot_enable_unversioned_writes(self):
        with patch("meter.services.record_balance_snapshot") as snapshot, \
                patch("meter.usage_service.upsert_daily_usage") as usage, \
                patch("utils.general.dispatch_task") as dispatch:
            for path in ("low-units", "daily-usage"):
                bad = self.client.post(f"/webhooks/thingsboard/{path}", {}, format="json",
                                       HTTP_X_THINGSBOARD_WEBHOOK_SECRET="wrong")
                self.assertEqual(bad.status_code, 401)
                response = self.client.post(f"/webhooks/thingsboard/{path}", {
                    "device_token": "not-a-secret", "units_kwh": "1.00", "kwh_used": "8.00",
                    "usage_date": "2026-10-01", "occurred_at": "2026-10-01T00:00:00Z",
                }, format="json", HTTP_X_THINGSBOARD_WEBHOOK_SECRET="test-webhook-only")
                self.assertEqual(response.status_code, 410)
                self.assertEqual(response.data["code"], "DEVICE_PROTOCOL_UNAVAILABLE")
            snapshot.assert_not_called(); usage.assert_not_called(); dispatch.assert_not_called()
        self.assertFalse(MeterNotification.objects.exists())

    def test_legacy_delivery_rejects_before_network_or_balance_changes(self):
        from meter.ami_delivery import attempt_ami_delivery, credit_ami_meter, retry_pending_for_meter, retry_all_pending_ami_deliveries
        from utils.ami_gateway import apply_units_to_meter
        self.meter.pending_units = Decimal("3.00")
        self.meter.save(update_fields=["pending_units"])
        with patch("meter.ami_delivery.push_units_to_thingsboard") as push:
            for call in (lambda: attempt_ami_delivery(self.meter, 1), lambda: credit_ami_meter(self.meter, 1),
                         lambda: retry_pending_for_meter(self.meter), retry_all_pending_ami_deliveries,
                         lambda: apply_units_to_meter(self.meter, Decimal("1"))):
                with self.assertRaises(DeviceOperationUnavailable):
                    call()
            push.assert_not_called()
        self.meter.refresh_from_db()
        self.assertEqual(self.meter.pending_units, Decimal("3.00"))
        self.assertEqual(self.meter.units, Decimal("0"))

    def test_sandbox_inventory_or_profile_cannot_use_transport_helpers(self):
        from meter.services import (push_units_to_thingsboard, set_shared_remaining_units,
                                    increment_shared_remaining_units, query_latest_units_from_thingsboard,
                                    query_usage_timeseries_from_thingsboard)
        with patch("requests.sessions.Session.request") as network:
            for profile, inventory in ((False, True), (True, False)):
                self.meter.sandbox_inventory = inventory
                with override_settings(ALWAYSDATA_TESTING=False, CONSUMER_SANDBOX_ENABLED=profile):
                    for call in (lambda: push_units_to_thingsboard(self.meter, 1),
                                 lambda: set_shared_remaining_units(self.meter, 1),
                                 lambda: increment_shared_remaining_units(self.meter, 1),
                                 lambda: query_latest_units_from_thingsboard(self.meter),
                                 lambda: query_usage_timeseries_from_thingsboard(self.meter, None, None)):
                        with self.assertRaises(DeviceOperationUnavailable):
                            call()
            network.assert_not_called()

    @override_settings(DEBUG=False, ALWAYSDATA_TESTING=False, CONSUMER_SANDBOX_ENABLED=False)
    def test_real_legacy_writes_are_unavailable_even_if_token_configured(self):
        from meter.services import push_units_to_thingsboard, set_shared_remaining_units
        self.meter.iot_device_token = "test-only-not-a-real-token"
        with patch("requests.sessions.Session.request") as network:
            for call in (lambda: push_units_to_thingsboard(self.meter, 1),
                         lambda: set_shared_remaining_units(self.meter, 1)):
                with self.assertRaises(DeviceOperationUnavailable):
                    call()
            network.assert_not_called()

    @override_settings(DEBUG=False, ALWAYSDATA_TESTING=False, CONSUMER_SANDBOX_ENABLED=False)
    def test_device_read_failure_does_not_disclose_token_in_logs_or_response(self):
        import requests
        from meter.services import query_latest_units_from_thingsboard
        self.meter.iot_device_token = "sensitive-test-marker"
        error = requests.ConnectionError("https://example.invalid/api/v1/sensitive-test-marker/attributes")
        with patch("meter.services.requests.get", side_effect=error), self.assertLogs("meter.services", level="WARNING") as logs:
            ok, message, data = query_latest_units_from_thingsboard(self.meter)
        self.assertFalse(ok)
        self.assertIsNone(data)
        self.assertNotIn("sensitive-test-marker", message)
        self.assertNotIn("sensitive-test-marker", "\n".join(logs.output))

    @override_settings(DEBUG=False, ALWAYSDATA_TESTING=False, CONSUMER_SANDBOX_ENABLED=False)
    def test_dev_token_cannot_fabricate_readings_outside_development(self):
        from meter.services import query_latest_units_from_thingsboard
        self.meter.iot_device_token = "dev-fixture-only"
        with self.assertRaises(DeviceOperationUnavailable):
            query_latest_units_from_thingsboard(self.meter)


class HostingDeviceContainmentTests(HardwareFixture):
    def test_testing_middleware_blocks_legacy_poll_and_device_aliases(self):
        from backend.hosting_middleware import FreeTestingMiddleware
        from django.test import RequestFactory
        from django.http import HttpResponse
        with patch("requests.sessions.Session.request") as network:
            gate = FreeTestingMiddleware(lambda request: HttpResponse("must not run"))
            for method, path in (("get", "/api/v1/meter/power-usage/"),
                ("get", "/api/v1/meter/check-units/"), ("post", "/api/v1/meter/deliver/"),
                ("post", "/api/v1/meter/apply-wallet-units/"), ("post", "/api/v1/meter/simulator/ack/"),
                ("post", "/api/v1/meter/simulator/telemetry/"), ("post", "/webhooks/thingsboard/low-units"),
                ("post", "/webhooks/thingsboard/daily-usage")):
                self.assertEqual(gate(getattr(RequestFactory(), method)(path)).status_code, 503)
            network.assert_not_called()
