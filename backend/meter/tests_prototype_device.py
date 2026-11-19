"""Firmware-shaped HTTPS transport tests, no board/provider/network access."""
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from io import StringIO
import json
from pathlib import Path
import tempfile
from threading import Barrier
from unittest.mock import patch
import uuid

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from accounts.models import User
from meter.bench_device import payload_digest
from meter.energy_tokens import token_record
from meter.models import (EnergyAllocation, EnergyKeypadToken, Meter, MeterDelivery, PrototypeDevice,
                          PrototypeCommand, PrototypeTelemetry)
from meter.prototype_device import identity
from meter.sandbox_enrollment import enroll_sandbox_meter
from transactions.tests_demo_payments import DEMO, Fixtures

LAB = {**DEMO, 'PROTOTYPE_AC_LAB_ENABLED': True, 'PROTOTYPE_RELAY_OUTPUT_ENABLED': False,
       'ALWAYSDATA_TESTING': True, 'ENERGY_TOKEN_ISSUANCE_ENABLED': True,
       'ENERGY_TOKEN_ENCRYPTION_KEYS': [base64.urlsafe_b64encode(b'P' * 32).decode()],
       'ENERGY_TOKEN_LOOKUP_KEY': 'isolated-ac-lab-token-lookup-test-only-abcdefghijklmnopqrstuvwxyz'}
ROOT = '/api/v1/prototype-device/v1/'
SECRET = 'synthetic-ac-lab-credential-do-not-use-in-firmware'


class LabFixtures(Fixtures):
    environment = "UGX_DEMO"
    def setUp(self):
        super().setUp()
        self.operator = User.objects.create_user(email='lab-operator@example.invalid', password='test-only', user_role=User.OPERATOR, is_staff=True)
        self.operator.profile.email_verified = True; self.operator.profile.save(update_fields=['email_verified'])
        self.device = PrototypeDevice.objects.create(meter=self.meter, owner=self.owner, provisioned_by=self.operator, environment=self.environment,
            credential_hash=make_password(SECRET), credential_fingerprint='test-only-unique-fingerprint')
        self.boot = str(uuid.uuid4())
        self.dev = APIClient()
        self.device_headers = {**self.headers, 'HTTP_X_DEVICE_ID': str(self.device.pk), 'HTTP_X_DEVICE_TOKEN': SECRET}
        self.handshake = {**identity(self.device), 'boot_id': self.boot, 'boot_counter': 1,
            'application_counter': 0, 'initialize': True, 'ack_pending': False,
            'credited_uwh': 0, 'consumed_uwh': 0, 'uncertain_uwh': 0}

    def post(self, route, body, status=200, **headers):
        response = self.dev.post(ROOT + route + '/', body, format='json', **(headers or self.device_headers))
        data = response.data if hasattr(response, "data") else response.json()
        self.assertEqual(response.status_code, status, data)
        self.assertIn('no-store', response['Cache-Control'])
        return data

    def start(self):
        self.post('session', self.handshake)

    def token(self):
        payment = self.purchase(); self.settle(payment)
        token = EnergyKeypadToken.objects.get(allocation__purchase_intent=payment)
        return token_record(token)['token']

    def redeem(self, code, counter=0, status=200):
        return self.post('redeem', {**identity(self.device), 'token': code, 'application_counter': counter}, status)

    def receipt(self, command):
        return {**command, 'type': 'AC_LAB_APPLIED', 'receipt_id': str(uuid.uuid4()),
                'applied_at': timezone.now().isoformat()}

    def sample(self, command, seq=1):
        credit = command['credit_wh'] * 1_000_000
        return {**identity(self.device), 'boot_id': self.boot, 'boot_counter': 1, 'sequence': seq,
            'measured_at': timezone.now().isoformat(), 'clock_status': 'NETWORK_TIME',
            'application_counter': command['command_sequence'], 'credited_uwh': credit,
            'consumed_uwh': 1_000_000, 'uncertain_uwh': 0, 'remaining_credit_uwh': credit - 1_000_000,
            'voltage_mv': 230000, 'current_ma': 100, 'power_mw': 23000, 'pzem_wh': 500,
            'output_requested': False, 'output_feedback': 'UNKNOWN', 'sensor_status': 'OK'}


@override_settings(**LAB)
class PrototypeTests(LabFixtures, TransactionTestCase):
    def test_purchase_token_session_lost_response_retry_ack_telemetry_owner_read(self):
        with patch('requests.sessions.Session.request', side_effect=AssertionError('No external provider/device I/O')):
            code = self.token()  # Existing app purchase/settlement/token issuer.
            self.start(); command = self.redeem(code)['command']
            self.assertEqual(len(command), 14)
            self.assertEqual(payload_digest({k: v for k, v in command.items() if k != 'payload_digest'}), command['payload_digest'])
            self.assertEqual(self.redeem(code)['command'], command)  # First response lost.
            self.assertEqual(MeterDelivery.objects.count(), 1)
            self.assertEqual(EnergyAllocation.objects.count(), 1)
            self.assertEqual(MeterDelivery.objects.get().status, 'DISPATCHED')
            reading = self.client.get(f'/api/v1/meter/mobile-meters/{self.meter.pk}/', **self.headers)
            self.assertIsNone(reading.data['lab_consumed_uwh'])
            ack = self.receipt(command)
            self.assertEqual(self.post('ack', ack), self.post('ack', ack))
            self.assertEqual(PrototypeCommand.objects.exclude(receipt_id=None).count(), 1)
            self.assertEqual(MeterDelivery.objects.get().status, 'APPLIED')
            self.assertEqual(EnergyKeypadToken.objects.get().state, 'APPLIED')
            self.assertEqual(token_record(EnergyKeypadToken.objects.get())['application_environment'], 'AC_LAB')
            self.redeem(code, 1, 409)
            sample = self.sample(command); self.post('telemetry', sample); self.post('telemetry', sample)
            self.assertEqual(PrototypeTelemetry.objects.count(), 1)
            reading = self.client.get(f'/api/v1/meter/mobile-meters/{self.meter.pk}/', **self.headers)
            self.assertEqual(reading.data['lab_consumed_uwh'], '1000000')
            self.assertEqual(reading.data['lab_remaining_credit_uwh'], str(command['credit_wh'] * 1_000_000 - 1_000_000))
            self.assertEqual(reading.data['contact_source'], 'AC_LAB')
            self.assertEqual(reading.data['contact_status'], 'RECENT')
            self.assertIsNone(reading.data['lab_interval_usage_wh'])
            next_sample = {**sample, 'sequence': 2, 'pzem_wh': 501, 'consumed_uwh': 2_000_000,
                           'remaining_credit_uwh': sample['credited_uwh'] - 2_000_000}
            self.post('telemetry', next_sample)
            current = self.client.get(f'/api/v1/meter/mobile-meters/{self.meter.pk}/', **self.headers)
            self.assertEqual(current.data['lab_interval_usage_wh'], '1')
            self.assertFalse(reading.data['output_enabled']); self.assertEqual(reading.data['reported_relay_state'], 'UNKNOWN')
            self.assertIn('no-store', reading['Cache-Control'])
            history = self.client.get(f'/api/v1/meter/mobile-consumption/?meter_id={self.meter.pk}', **self.headers)
            self.assertEqual(history.data['ac_lab_telemetry'][0]['consumed_uwh'], '2000000')
            self.client.force_authenticate(self.other)
            self.assertEqual(self.client.get(f'/api/v1/meter/mobile-meters/{self.meter.pk}/', **self.headers).status_code, 404)
            self.assertEqual(self.client.get(f'/api/v1/meter/mobile-consumption/?meter_id={self.meter.pk}', **self.headers).status_code, 404)

    def test_approved_demo_loan_is_authorized_but_wrong_domain_allocation_is_not(self):
        self.start()
        loan = self.loan()
        token = EnergyKeypadToken.objects.get(allocation__sandbox_loan=loan)
        self.assertEqual(loan.status, 'DISBURSED')
        command = self.redeem(token_record(token)['token'])['command']
        self.assertEqual(command['allocation_id'], token.allocation_id)
        self.post('ack', self.receipt(command))
        code = self.token()
        other = EnergyKeypadToken.objects.get(state='ISSUED')
        EnergyAllocation.objects.filter(pk=other.allocation_id).update(accounting_environment='SANDBOX')
        self.redeem(code, counter=1, status=404)
        self.assertEqual(MeterDelivery.objects.count(), 1)

    def test_authentication_revocation_and_capability_fail_closed(self):
        self.post('session', self.handshake, 401, **self.headers)
        self.post('session', self.handshake, 401, **{**self.device_headers, 'HTTP_X_DEVICE_TOKEN': 'wrong'})
        # Consumer credentials alone cannot impersonate a device.
        self.dev.force_authenticate(self.owner)
        self.post('session', self.handshake, 401, **self.headers)
        for overrides in ({'PROTOTYPE_AC_LAB_ENABLED': False}, {'ALWAYSDATA_TESTING': False},
                          {'PROTOTYPE_RELAY_OUTPUT_ENABLED': True}):
            with override_settings(**overrides): self.post('session', self.handshake, 503)
        with override_settings(PROTOTYPE_PAYMENT_PROVIDER='MTN_SANDBOX'):
            self.post('session', self.handshake, 401)  # Old UGX credential cannot cross domains.
        PrototypeDevice.objects.filter(pk=self.device.pk).update(revoked_at=timezone.now(), active=False)
        self.post('session', self.handshake, 401)
        self.assertFalse(MeterDelivery.objects.exists())

    def test_wrong_meter_owner_environment_and_storage(self):
        self.start(); code = self.token()
        for key, value in [('meter_number', '00000000999'), ('storage_id', str(uuid.uuid4())), ('environment', 'CORE'), ('binding_epoch', True)]:
            self.post('redeem', {**identity(self.device), 'token': code, 'application_counter': 0, key: value}, 400 if key == 'binding_epoch' else 403)
        second = enroll_sandbox_meter(self.other, '00000000999')[0]
        foreign = PrototypeDevice.objects.create(meter=second, owner=self.other, provisioned_by=self.operator,
            credential_hash=make_password(SECRET), credential_fingerprint='foreign-credential-fingerprint')
        from meter.prototype_device import redeem
        from meter.bench_device import BenchError
        from meter.prototype_device import session as start_session
        start_session(foreign, {**self.handshake, **identity(foreign), 'boot_id': str(uuid.uuid4())})
        with self.assertRaises(BenchError) as denied:
            redeem(foreign, {**identity(foreign), 'token': code, 'application_counter': 0})
        self.assertEqual(denied.exception.status_code, 404)
        Meter.objects.filter(pk=self.meter.pk).update(user=self.other)
        self.redeem(code, status=401)
        self.assertFalse(MeterDelivery.objects.exists())

    def test_pending_command_only_telemetry_cannot_ack_or_mint_credit(self):
        self.start(); code = self.token(); command = self.redeem(code)['command']; another = self.token()
        self.redeem(another, status=409)
        sample = self.sample(command)
        self.post('telemetry', {**sample, 'credited_uwh': sample['credited_uwh'] + 10}, 409)
        self.post('telemetry', sample)  # Exact pending application may be reported, but not ACKed.
        self.assertEqual(MeterDelivery.objects.get().status, 'DISPATCHED')
        self.assertEqual(EnergyKeypadToken.objects.get(delivery__isnull=False).state, 'DELIVERY_PENDING')
        self.assertIsNone(PrototypeCommand.objects.get().receipt_id)
        self.assertEqual(EnergyAllocation.objects.count(), 2)
        self.post('session', self.handshake, 409)  # Observed application cannot regress even before ACK.
        self.post('ack', self.receipt(command))

    def test_reboot_pending_ack_recovery_and_reset_denial(self):
        self.start(); command = self.redeem(self.token())['command']; ack = self.receipt(command)
        new_boot = {**self.handshake, 'boot_id': str(uuid.uuid4()), 'boot_counter': 2, 'initialize': False,
            'application_counter': 1, 'ack_pending': True, 'credited_uwh': command['credit_wh'] * 1_000_000,
            'last_command_id': command['command_id'], 'last_payload_digest': command['payload_digest'], 'last_receipt_id': ack['receipt_id']}
        self.post('session', new_boot); self.post('session', new_boot)
        self.post('ack', ack); self.post('ack', ack)
        self.post('session', {**new_boot, 'ack_pending': False})  # ACK response lost/restart.
        self.post('session', {**new_boot, 'boot_id': str(uuid.uuid4()), 'boot_counter': 3, 'credited_uwh': 0}, 409)
        self.post('session', self.handshake, 409)
        self.post('session', {**new_boot, 'storage_id': str(uuid.uuid4())}, 403)
        self.assertEqual(PrototypeCommand.objects.count(), 1)

    def test_ack_changed_fields_and_receipt_identity_rejected(self):
        self.start(); command = self.redeem(self.token())['command']; ack = self.receipt(command)
        self.post('ack', {**ack, 'credit_wh': command['credit_wh'] + 10}, 409)
        self.post('ack', {**ack, 'delivery_id': command['delivery_id'] + 1}, 404)
        self.post('ack', ack)
        self.post('ack', {**ack, 'receipt_id': str(uuid.uuid4())}, 409)
        self.assertEqual(PrototypeCommand.objects.exclude(receipt_id=None).count(), 1)

    def test_stale_order_conflict_counter_reset_fault_and_disabled_output(self):
        self.start(); command = self.redeem(self.token())['command']; self.post('ack', self.receipt(command))
        sample = self.sample(command, 2); self.post('telemetry', sample)
        self.post('telemetry', {**sample, 'power_mw': 1}, 409)
        self.post('telemetry', {**sample, 'sequence': 1}, 409)
        self.post('telemetry', {**sample, 'sequence': 3, 'consumed_uwh': 0, 'remaining_credit_uwh': sample['credited_uwh']}, 409)
        self.post('telemetry', {**sample, 'sequence': 3, 'pzem_wh': 1}, 409)
        self.post('telemetry', {**sample, 'sequence': 3, 'output_requested': True}, 403)
        self.post('telemetry', {**sample, 'sequence': 3, 'sensor_status': []}, 400)
        self.post('telemetry', {**sample, 'sequence': 3, 'sensor_status': 'FAULT'})
        response = self.client.get(f'/api/v1/meter/mobile-meters/{self.meter.pk}/', **self.headers)
        self.assertIsNone(response.data['lab_consumed_uwh'])
        with patch('django.utils.timezone.now', return_value=timezone.now() + timedelta(seconds=100)):
            response = self.client.get(f'/api/v1/meter/mobile-meters/{self.meter.pk}/', **self.headers)
            self.assertEqual(response.data['contact_status'], 'STALE')
        self.assertEqual(PrototypeTelemetry.objects.count(), 2)

    def test_strict_schema_body_limits_and_private_error_responses(self):
        self.post('session', {**self.handshake, 'initialize': 1}, 400)
        self.post('session', {**self.handshake, 'boot_counter': 1.0}, 400)
        self.post('session', {**self.handshake, 'boot_counter': True}, 400)
        self.post('session', {**self.handshake, 'extra': 'field'}, 400)
        response = self.dev.post(ROOT + 'session/', '{"a":1,"a":2}', content_type='application/json', **self.device_headers)
        self.assertEqual(response.status_code, 400)
        response = self.dev.post(ROOT + 'session/', ' ' * 4097, content_type='application/json', **self.device_headers)
        self.assertEqual(response.status_code, 413)

    def test_operator_provisioning_private_unique_and_no_rebind(self):
        meter = enroll_sandbox_meter(self.owner, '00000000998')[0]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'private.json'; stdout = StringIO()
            kwargs = dict(environment=self.environment, owner_id=self.owner.pk, operator_id=self.operator.pk, private_config=str(path), confirm_output_disabled=True, stdout=stdout)
            call_command('provision_ac_lab_device', meter.pk, **kwargs)
            data = json.loads(path.read_text()); self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn(data['device_secret'], stdout.getvalue())
            self.assertFalse(data['output_enabled']); self.assertEqual(data['meter_number'], '00000000998')
            bound = PrototypeDevice.objects.get(pk=data['device_id']); self.assertEqual(bound.provisioned_by, self.operator)
            kwargs['private_config'] = str(Path(directory) / 'retry.json')
            with self.assertRaises(CommandError): call_command('provision_ac_lab_device', meter.pk, **kwargs)
            self.assertFalse(Path(kwargs['private_config']).exists())
            call_command('revoke_ac_lab_device', str(bound.pk), operator_id=self.operator.pk, stdout=stdout)
            bound.refresh_from_db(); self.assertFalse(bound.active); self.assertEqual(bound.revoked_by, self.operator)

    def test_hosting_keeps_old_bench_and_physical_writes_blocked(self):
        if 'backend.hosting_middleware.FreeTestingMiddleware' not in settings.MIDDLEWARE:
            self.skipTest('Run --sandbox-profile to verify actual hosting middleware')
        for path in ('/api/v1/bench-device/v1/session/', '/api/v1/meter/simulator/ack/', '/api/v1/meter/test-push/', '/api/v1/prototype-device/v1/arbitrary/'):
            response = self.dev.post(path, {}, format='json', **self.headers)
            self.assertEqual(response.status_code, 503)


@override_settings(**LAB)
class PrototypeConcurrencyTests(LabFixtures, TransactionTestCase):
    def test_concurrent_redeem_and_ack_have_one_effect(self):
        self.assertEqual(connection.vendor, 'postgresql')
        self.start(); code = self.token()
        from meter.prototype_device import redeem, acknowledge
        def together(operation, body):
            barrier = Barrier(2)
            def worker():
                close_old_connections()
                try:
                    device = PrototypeDevice.objects.get(pk=self.device.pk)
                    barrier.wait(timeout=15)
                    return operation(device, body)
                finally:
                    close_old_connections()
            with ThreadPoolExecutor(max_workers=2) as pool:
                return list(pool.map(lambda _: worker(), range(2)))
        results = together(redeem, {**identity(self.device), 'token': code, 'application_counter': 0})
        self.assertEqual(results[0]['command'], results[1]['command'])
        self.assertEqual(MeterDelivery.objects.count(), 1)
        ack = self.receipt(results[0]['command'])
        results = together(acknowledge, ack)
        self.assertEqual(results[0], results[1]); self.assertEqual(PrototypeCommand.objects.exclude(receipt_id=None).count(), 1)
        self.assertEqual(EnergyAllocation.objects.count(), 1)
