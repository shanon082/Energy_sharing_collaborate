"""Existing V2 contract without PZEM evidence; no backend relaxation is needed."""
import uuid
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient
from meter.models import EnergyAllocation, MeterDelivery, PrototypeTelemetry
from meter.sandbox_enrollment import enroll_sandbox_meter
from meter.tests_mtn_device import MTNFixture, LAB
from meter.energy_tokens import token_record


@override_settings(**LAB)
class AuthenticatedCreditOnlyTests(MTNFixture, TransactionTestCase):
    def reboot(self, command=None, receipt=None, ack_pending=False):
        self.device.refresh_from_db()
        self.boot = str(uuid.uuid4())
        body = {**self.handshake, 'initialize': False, 'boot_id': self.boot,
                'boot_counter': self.device.boot_counter + 1}
        if command:
            body.update(application_counter=command['command_sequence'], ack_pending=ack_pending,
                        credited_uwh=command['credit_wh'] * 1_000_000,
                        last_command_id=command['command_id'], last_payload_digest=command['payload_digest'],
                        last_receipt_id=receipt['receipt_id'])
        return self.post('session', body)

    def test_first_redemption_heartbeat_and_owner_reads_need_no_sensor_values(self):
        code = self.token()
        self.start()  # No baseline or fabricated voltage/consumption in this body.
        command = self.redeem(code)['command']
        self.assertEqual(command, self.redeem(code)['command'])
        receipt = self.receipt(command)
        self.post('ack', receipt); self.post('ack', receipt)
        self.redeem(code, counter=1, status=409)
        heartbeat = {**self.handshake, 'initialize': False, 'application_counter': 1,
                     'credited_uwh': command['credit_wh'] * 1_000_000,
                     'last_command_id': command['command_id'], 'last_payload_digest': command['payload_digest'],
                     'last_receipt_id': receipt['receipt_id']}
        self.post('session', heartbeat); self.post('session', heartbeat)
        self.reboot(command, receipt)
        self.assertEqual(EnergyAllocation.objects.count(), 1)
        self.assertEqual(MeterDelivery.objects.count(), 1)
        self.assertFalse(PrototypeTelemetry.objects.exists())
        dashboard = self.client.get(f'/api/v1/meter/mobile-meters/{self.meter.pk}/?environment=SANDBOX', **self.headers)
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.data['confirmed_kwh'], '2.00')
        self.assertIsNotNone(dashboard.data['last_meter_contact'])
        for field in ('lab_consumed_uwh', 'lab_pzem_wh', 'lab_remaining_credit_uwh', 'last_measurement_at'):
            self.assertIsNone(dashboard.data[field], field)
        self.assertEqual(dashboard.data['reported_relay_state'], 'UNKNOWN')
        self.assertFalse(dashboard.data['output_enabled'])

    def test_ack_response_lost_then_reboot_keeps_the_same_receipt(self):
        code = self.token(); self.start()
        command = self.redeem(code)['command']; receipt = self.receipt(command)
        self.post('ack', receipt)  # Server saved it; pretend the response never arrived.
        self.reboot(command, receipt, ack_pending=True)
        self.post('ack', receipt)
        self.assertEqual(self.device.commands.count(), 1)
        self.assertEqual(MeterDelivery.objects.count(), 1)
        self.assertFalse(PrototypeTelemetry.objects.exists())

    def test_restart_before_ack_recovers_the_same_command_then_survives_ack_restart(self):
        code = self.token(); self.start()
        command = self.redeem(code)['command']; receipt = self.receipt(command)
        self.reboot(command, receipt, ack_pending=True)
        self.assertEqual(command, self.redeem(code, counter=1)['command'])
        self.post('ack', receipt); self.post('ack', receipt)
        self.reboot(command, receipt)
        self.redeem(code, counter=1, status=409)
        self.assertEqual(self.device.commands.count(), 1)
        self.assertEqual(MeterDelivery.objects.get().status, 'APPLIED')
        self.assertFalse(PrototypeTelemetry.objects.exists())

    def test_sensor_free_operation_does_not_bypass_meter_binding_or_owner_access(self):
        self.start()
        other_meter = enroll_sandbox_meter(self.owner, '00000009876')[0]
        payment = self.purchase(meter=other_meter); self.settle(payment)
        code = token_record(payment.energy_allocation.keypad_token)['token']
        self.redeem(code, status=404)
        self.assertFalse(MeterDelivery.objects.exists())
        stranger = APIClient(); stranger.force_authenticate(self.other)
        self.assertEqual(stranger.get(f'/api/v1/meter/mobile-meters/{self.meter.pk}/?environment=SANDBOX', **self.headers).status_code, 404)
        self.post('session', self.handshake, 401, **self.headers)
