import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from threading import Barrier
from unittest.mock import patch

from django.core.management import call_command
from django.db import close_old_connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from meter.models import Meter, PrototypeDevice, PrototypeOutputAuthorization, PrototypeOutputAuthorizationEvent
from meter.prototype_device import RECOVERY_PROTOCOL, identity, output_authorization
from meter.tests_prototype_device import LAB, LabFixtures


@override_settings(**{**LAB, 'PROTOTYPE_RELAY_OUTPUT_ENABLED': True})
class OutputAuthorizationTests(LabFixtures, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user(
            email='output-admin@example.invalid', password='test-only',
            user_role=User.ADMIN, is_staff=True,
        )
        self.admin.profile.email_verified = True
        self.admin.profile.save(update_fields=['email_verified'])

    def establish_metered_state(self):
        self.start()
        command = self.redeem(self.token())['command']
        receipt = self.receipt(command)
        self.post('ack', receipt)
        proposal = {
            **identity(self.device),
            'transition_id': str(uuid.uuid4()),
            'transition_protocol': 'GPAWA_BASELINE_V1',
            'source_state': 'AUTH_CREDIT_ONLY_V3',
            'had_baseline': False,
            'old_baseline_wh': None,
            'baseline_wh': 500,
            'application_counter': command['command_sequence'],
            'ack_pending': False,
            'credited_uwh': command['credit_wh'] * 1_000_000,
            'consumed_uwh': 0,
            'uncertain_uwh': 0,
            'last_command_id': command['command_id'],
            'last_payload_digest': command['payload_digest'],
            'last_receipt_id': receipt['receipt_id'],
        }
        prepared = self.post('measurement/prepare', proposal)
        self.post('measurement/commit', {
            **identity(self.device),
            'transition_id': proposal['transition_id'],
            'receipt_id': prepared['receipt_id'],
        })
        self.post('session', self.recovery_session(command, receipt))
        sample = self.sample(command)
        sample.update(fault_status='OK', consumed_uwh=0, accounting_protocol=RECOVERY_PROTOCOL,
                      remaining_credit_uwh=command['credit_wh'] * 1_000_000)
        self.post('telemetry', sample)
        return command, receipt

    def recovery_session(self, command, receipt):
        return {
            **self.handshake, 'initialize': False, 'application_counter': 1,
            'credited_uwh': command['credit_wh'] * 1_000_000,
            'last_command_id': command['command_id'],
            'last_payload_digest': command['payload_digest'],
            'last_receipt_id': receipt['receipt_id'],
            'accounting_protocol': RECOVERY_PROTOCOL, 'journal_mode': 'METERED', 'journal_counter_wh': 500,
        }

    def recovered_sample(self, command, sequence):
        return {**self.sample(command, seq=sequence), 'consumed_uwh': 0,
                'remaining_credit_uwh': command['credit_wh'] * 1_000_000,
                'accounting_protocol': RECOVERY_PROTOCOL}

    def authorization_body(self, **overrides):
        evidence = {
            'contact_tested_ac_disconnected': True,
            'startup_state_verified': True,
            'reset_state_verified': True,
            'controller_power_loss_verified': True,
            'relay_supply_loss_verified': True,
            'zero_credit_cutoff_verified': True,
            'meter_fault_cutoff_verified': True,
            'electrical_installation_reviewed': True,
            'relay_active_level': 'LOW',
            'evidence_reference': 'commissioning-record-2026-001',
        }
        return {
            'expires_at': (timezone.now() + timedelta(hours=2)).isoformat(),
            'reason': 'Approved controlled AC lab commissioning',
            'restart_policy': PrototypeOutputAuthorization.MANUAL,
            'evidence': {**evidence, **overrides.pop('evidence', {})},
            **overrides,
        }

    def grant(self, body=None, user=None, status=201):
        client = APIClient()
        client.force_authenticate(user or self.admin)
        response = client.post(
            f'/api/v1/admin/prototype-devices/{self.device.pk}/output-authorization/',
            body or self.authorization_body(), format='json',
        )
        self.assertEqual(response.status_code, status, getattr(response, 'data', None))
        return response

    def persistent(self, status=201, user=None, **policy):
        client = APIClient()
        client.force_authenticate(user or self.admin)
        response = client.post(
            f'/api/v1/admin/prototype-devices/{self.device.pk}/output-authorization/persistent/',
            {'reason': 'Approved ongoing automatic operation on recorded evidence', **policy}, format='json',
        )
        self.assertEqual(response.status_code, status, response.data)
        return response.data

    def test_persistent_auto_reuses_expired_legacy_evidence_and_survives_the_old_window(self):
        command, receipt = self.establish_metered_state()
        self.assertEqual(self.persistent(409)['code'], 'OUTPUT_COMMISSIONING_REVIEW_REQUIRED')
        temporary_id = self.grant().data['authorization_id']
        temporary = PrototypeOutputAuthorization.objects.get(pk=temporary_id)
        # Deployed pre-0037 grants have no binding snapshot. Their accepted
        # telemetry at the original grant establishes the scope of the evidence.
        PrototypeOutputAuthorization.objects.filter(pk=temporary_id).update(binding_snapshot=None,
            expires_at=timezone.now() - timedelta(seconds=1))
        self.persistent(403, user=self.operator)
        result = self.persistent()
        self.assertEqual(self.persistent(200), result)
        self.assertEqual((result['mode'], result['restart_policy'], result['expires_at']), ('PERSISTENT', 'AUTO', None))
        persistent = PrototypeOutputAuthorization.objects.get(pk=result['authorization_id'])
        self.assertEqual(persistent.evidence, temporary.evidence)
        self.assertEqual(persistent.events.get(action='PROMOTED').details['source_authorization_id'], temporary_id)
        self.assertEqual(PrototypeOutputAuthorization.objects.count(), 2)
        temporary.refresh_from_db()
        self.assertEqual(temporary.state, 'EXPIRED')

        future = timezone.now() + timedelta(days=3)
        new_boot = str(uuid.uuid4())
        with patch('meter.prototype_device.timezone.now', return_value=future):
            startup = self.post('session', {**self.recovery_session(command, receipt), 'boot_id': new_boot, 'boot_counter': 2})
            self.assertFalse(startup['output_authorized'])
            recovered = self.post('telemetry', {**self.recovered_sample(command, 1), 'boot_id': new_boot, 'boot_counter': 2})
            self.assertTrue(recovered['output_authorized'])
            self.assertEqual(recovered['output_commissioning_mode'], 'PERSISTENT')
            self.assertLessEqual(recovered['output_lease_seconds'], 90)
            self.assertIsNone(recovered['output_authorization_expires_at'])
            self.device.refresh_from_db()
            self.assertEqual(self.device.consumed_uwh, 0)
        self.assertEqual(output_authorization(self.device, future + timedelta(seconds=91))['output_reason'], 'OUTPUT_SAMPLE_STALE')
        client = APIClient()
        client.force_authenticate(self.admin)
        status = client.get(f'/api/v1/admin/prototype-devices/{self.device.pk}/output-authorization/')
        self.assertEqual((status.data['mode'], status.data['expires_at']), ('PERSISTENT', None))
        revoked = client.post(f'/api/v1/admin/prototype-devices/{self.device.pk}/output-authorization/revoke/',
                              {'reason': 'End ongoing commissioned operation'}, format='json')
        self.assertEqual(revoked.status_code, 200)
        self.assertEqual(self.persistent(409)['code'], 'OUTPUT_COMMISSIONING_REVIEW_REQUIRED')
        self.assertEqual(output_authorization(self.device)['output_reason'], 'OUTPUT_GRANT_REVOKED')

    def test_persistent_commissioning_is_terminated_by_binding_replacement(self):
        self.establish_metered_state()
        source = self.grant().data['authorization_id']
        result = self.persistent()
        self.assertEqual(PrototypeOutputAuthorization.objects.get(pk=source).state, 'REVOKED')
        PrototypeDevice.objects.filter(pk=self.device.pk).update(binding_epoch=2)
        self.device.refresh_from_db()
        self.assertEqual(output_authorization(self.device)['output_reason'], 'OUTPUT_BINDING_CHANGED')
        self.assertEqual(PrototypeOutputAuthorization.objects.get(pk=result['authorization_id']).state, 'REVOKED')
        self.assertEqual(self.persistent(409)['code'], 'OUTPUT_COMMISSIONING_REVIEW_REQUIRED')

    def test_persistent_auto_stops_at_depletion_and_resumes_after_ack_and_healthy_sample(self):
        command, _ = self.establish_metered_state()
        self.grant()
        grant_id = self.persistent()['authorization_id']
        consumed = command['credit_wh'] * 1_000_000
        counter = 500 + command['credit_wh']
        # Advance both receive and measurement times enough for the bounded
        # PZEM delta while verifying the grant has no wall-clock renewal window.
        future = timezone.now() + timedelta(days=2)
        with patch('meter.prototype_device.timezone.now', return_value=future):
            empty = {**self.recovered_sample(command, 2), 'pzem_wh': counter,
                     'consumed_uwh': consumed, 'remaining_credit_uwh': 0}
            self.assertEqual(self.post('telemetry', empty)['output_reason'], 'CREDIT_UNAVAILABLE')
            body = {**identity(self.device), 'token': self.token(), 'application_counter': 1,
                    'accounting_protocol': RECOVERY_PROTOCOL}
            pending = self.post('redeem', body)['command']
            self.assertEqual(self.post('redeem', body)['command'], pending)
            checkpoint = {**empty, 'sequence': 3}
            self.assertEqual(self.post('telemetry', checkpoint)['output_reason'], 'ACK_REQUIRED')
            receipt = {**self.receipt(pending), 'credit_checkpoint': {'boot_id': self.boot, 'sequence': 3}}
            self.assertEqual(self.post('ack', receipt), self.post('ack', receipt))
            self.assertEqual(self.post('redeem', {**body, 'application_counter': 2}, status=409)['code'], 'TOKEN_ALREADY_USED')
            fresh = {**checkpoint, 'sequence': 5, 'application_counter': 2,
                     'credited_uwh': consumed + pending['credit_wh'] * 1_000_000,
                     'remaining_credit_uwh': pending['credit_wh'] * 1_000_000}
            fault = {**fresh, 'sequence': 4, 'sensor_status': 'FAULT', 'fault_status': 'SENSOR_UNAVAILABLE'}
            for field in ('voltage_mv', 'current_ma', 'power_mw', 'pzem_wh', 'frequency_cHz', 'power_factor_pct'):
                fault[field] = None
            self.assertFalse(self.post('telemetry', fault)['output_authorized'])
            self.assertTrue(self.post('telemetry', fresh)['output_authorized'])
            self.assertFalse(self.post('telemetry', fresh)['output_authorized'])
        self.device.refresh_from_db()
        self.assertEqual(self.device.consumed_uwh, consumed)
        self.assertEqual(self.device.output_authorizations.get(state='ACTIVE').pk, grant_id)

    def test_revoking_device_credentials_revokes_persistent_grant(self):
        command, _ = self.establish_metered_state()
        self.grant()
        grant_id = self.persistent()['authorization_id']
        call_command('revoke_ac_lab_device', str(self.device.pk), operator_id=self.operator.pk, stdout=StringIO())
        self.assertEqual(self.post('telemetry', self.recovered_sample(command, 2), status=401)['code'], 'DEVICE_UNAUTHORIZED')
        grant = PrototypeOutputAuthorization.objects.get(pk=grant_id)
        self.assertEqual(grant.state, 'REVOKED')
        self.assertEqual(grant.events.get(action='REVOKED').actor, self.operator)
        self.assertFalse(output_authorization(self.device)['output_authorized'])

    def test_offline_policy_is_explicit_and_checked_during_reconnect(self):
        command, receipt = self.establish_metered_state()
        self.grant()
        ordinary = self.persistent()
        self.assertFalse(ordinary['offline_enabled'])
        self.persistent(status=403, user=self.operator, offline=True)
        offline = self.persistent(offline=True)
        self.assertTrue(offline['offline_enabled'])
        self.assertNotEqual(ordinary['authorization_id'], offline['authorization_id'])
        self.assertEqual(self.persistent(status=200, offline=True), offline)
        healthy = self.post('telemetry', self.recovered_sample(command, 2))
        self.assertTrue(healthy['output_offline_allowed'])
        self.assertTrue(healthy['output_authorized'])
        boot = str(uuid.uuid4())
        handshake = {**self.recovery_session(command, receipt), 'boot_id': boot, 'boot_counter': 2,
                     'relay_active_level': 'LOW', 'consumed_uwh': 20_000_000, 'journal_counter_wh': 520}
        future = timezone.now() + timedelta(hours=2)
        with patch('meter.prototype_device.timezone.now', return_value=future):
            session = self.post('session', handshake)
            self.assertTrue(session['output_offline_allowed'])
            self.assertFalse(session['output_authorized'])
            self.assertFalse(self.post('session', {**handshake, 'relay_active_level': 'HIGH'})['output_offline_allowed'])

            untimed = {**self.recovered_sample(command, 1), 'boot_id': boot, 'boot_counter': 2,
                       'pzem_wh': 520, 'consumed_uwh': 20_000_000, 'remaining_credit_uwh': command['credit_wh'] * 1_000_000 - 20_000_000,
                       'measured_at': None, 'clock_status': 'OFFLINE_UNTIMED',
                       'fault_status': 'SENSOR_UNAVAILABLE', 'offline_gap': True}
            response = self.post('telemetry', untimed)
            self.assertTrue(response['recovery_pending'])
            self.assertFalse(response['output_authorized'])
            retry = self.post('telemetry', untimed, **self.device_headers, HTTP_X_GPAWA_TELEMETRY_REPLAY='1')
            self.assertTrue(retry['output_offline_allowed'])
            self.assertFalse(retry['output_authorized'])
            journal = self.device.telemetry.get(boot_id=boot, sequence=1)
            self.assertIsNone(journal.observed_at)
            self.device.refresh_from_db()
            self.assertEqual(self.device.consumed_uwh, 20_000_000)

            recovered = {**untimed, 'sequence': 2, 'clock_status': 'NETWORK_TIME',
                         'measured_at': future.isoformat(), 'fault_status': 'OK'}
            self.assertFalse(self.post('telemetry', recovered)['recovery_pending'])
            self.device.refresh_from_db()
            self.assertEqual(self.device.consumed_uwh, 20_000_000)
            self.assertFalse(self.persistent(offline=False)['offline_enabled'])
            self.assertFalse(self.post('session', handshake)['output_offline_allowed'])

    def test_admin_grant_issues_bounded_lease_and_revocation_fails_closed(self):
        command, receipt = self.establish_metered_state()
        missing = self.post('telemetry', self.recovered_sample(command, 2))
        self.assertFalse(missing['output_authorized'])
        self.assertEqual(missing['output_reason'], 'OUTPUT_GRANT_MISSING')
        with override_settings(PROTOTYPE_RELAY_OUTPUT_ENABLED=False):
            disabled = self.post('telemetry', self.recovered_sample(command, 3))
        self.assertFalse(disabled['output_authorized'])
        self.assertEqual(disabled['output_reason'], 'OUTPUT_GLOBAL_DISABLE')
        self.grant(user=self.operator, status=403)
        self.grant(self.authorization_body(restart_policy=PrototypeOutputAuthorization.AUTO))

        session = self.recovery_session(command, receipt)
        recovering = self.post('session', session)
        self.assertFalse(recovering['output_authorized'])
        self.assertEqual(recovering['output_reason'], 'METER_RECOVERY_PENDING')
        mismatch = self.post('telemetry', {**self.recovered_sample(command, 4), 'relay_active_level': 'HIGH'})
        self.assertFalse(mismatch['output_authorized'])
        self.assertEqual(mismatch['output_reason'], 'RELAY_POLARITY_MISMATCH')
        sample = self.recovered_sample(command, 5)
        with self.assertLogs('meter.device', level='INFO') as logs:
            response = self.post('telemetry', sample)
        self.assertTrue(response['output_authorized'])
        self.assertEqual(response['output_reason'], 'LEASE_GRANTED')
        self.assertIn('output_reason=LEASE_GRANTED', logs.output[-1])
        self.assertGreater(response['output_lease_seconds'], 0)
        self.assertLessEqual(response['output_lease_seconds'], 90)
        self.assertEqual(response['output_restart_policy'], 'AUTO')
        self.assertFalse(self.post('telemetry', sample)['output_authorized'])

        client = APIClient()
        client.force_authenticate(self.admin)
        revoked = client.post(
            f'/api/v1/admin/prototype-devices/{self.device.pk}/output-authorization/revoke/',
            {'reason': 'Controlled test concluded and output inhibited'}, format='json',
        )
        self.assertEqual(revoked.status_code, 200, revoked.data)
        denied = self.post('telemetry', self.recovered_sample(command, 6))
        self.assertFalse(denied['output_authorized'])
        self.assertEqual(denied['output_reason'], 'OUTPUT_GRANT_REVOKED')
        self.assertEqual(
            list(PrototypeOutputAuthorizationEvent.objects.order_by('action').values_list('action', flat=True)),
            ['GRANTED', 'REVOKED'],
        )

    def test_global_kill_switch_and_missing_evidence_block_grant(self):
        self.establish_metered_state()
        incomplete = self.authorization_body(evidence={'meter_fault_cutoff_verified': False})
        self.grant(incomplete, status=400)
        with override_settings(PROTOTYPE_RELAY_OUTPUT_ENABLED=False):
            self.grant(status=503)
        self.assertFalse(PrototypeOutputAuthorization.objects.exists())

    def test_expired_authorization_is_audited_and_never_issues_a_lease(self):
        self.establish_metered_state()
        self.grant()
        authorization = PrototypeOutputAuthorization.objects.get(device=self.device)
        expired_at = timezone.now() - timedelta(seconds=1)
        PrototypeOutputAuthorization.objects.filter(pk=authorization.pk).update(expires_at=expired_at)
        session = {
            **identity(self.device), 'boot_id': self.boot, 'boot_counter': 1,
            'application_counter': 1, 'initialize': False, 'ack_pending': False,
            'credited_uwh': authorization.device.commands.first().delivery.command_payload['credit_wh'] * 1_000_000,
            'consumed_uwh': 0, 'uncertain_uwh': 0,
            'last_command_id': authorization.device.commands.first().delivery.command_payload['command_id'],
            'last_payload_digest': authorization.device.commands.first().delivery.command_payload['payload_digest'],
            'last_receipt_id': str(authorization.device.commands.first().receipt_id),
        }
        session.update(accounting_protocol=RECOVERY_PROTOCOL, journal_mode='METERED', journal_counter_wh=500)
        response = self.post('session', session)
        self.assertFalse(response['output_authorized'])
        command_payload = authorization.device.commands.first().delivery.command_payload
        denied = self.post('telemetry', self.recovered_sample(command_payload, 2))
        self.assertFalse(denied['output_authorized'])
        self.assertEqual(denied['output_reason'], 'OUTPUT_GRANT_EXPIRED')
        authorization.refresh_from_db()
        self.assertEqual(authorization.state, PrototypeOutputAuthorization.EXPIRED)
        self.assertTrue(PrototypeOutputAuthorizationEvent.objects.filter(
            authorization=authorization, action=PrototypeOutputAuthorizationEvent.EXPIRED,
        ).exists())

    def test_changed_meter_owner_blocks_commissioning(self):
        self.establish_metered_state()
        Meter.all_objects.filter(pk=self.meter.pk).update(user=self.other)
        self.assertEqual(self.grant(status=401).data['code'], 'DEVICE_UNAUTHORIZED')
        self.assertFalse(PrototypeOutputAuthorization.objects.exists())

    def test_simultaneous_grants_create_one_authorization_and_event(self):
        self.establish_metered_state()
        barrier = Barrier(2, timeout=10)
        body = self.authorization_body()

        def request_grant(_):
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(self.admin)
                barrier.wait()
                return client.post(
                    f'/api/v1/admin/prototype-devices/{self.device.pk}/output-authorization/',
                    body, format='json',
                ).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(request_grant, range(2))), [201, 409])
        self.assertEqual(PrototypeOutputAuthorization.objects.count(), 1)
        self.assertEqual(PrototypeOutputAuthorizationEvent.objects.count(), 1)
