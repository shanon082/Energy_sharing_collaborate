import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.db import close_old_connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from meter.models import Meter, PrototypeOutputAuthorization, PrototypeOutputAuthorizationEvent
from meter.prototype_device import RECOVERY_PROTOCOL, identity
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

    def test_admin_grant_issues_bounded_lease_and_revocation_fails_closed(self):
        command, receipt = self.establish_metered_state()
        self.grant(user=self.operator, status=403)
        self.grant()

        session = self.recovery_session(command, receipt)
        self.assertFalse(self.post('session', session)['output_authorized'])
        sample = self.recovered_sample(command, 2)
        response = self.post('telemetry', sample)
        self.assertTrue(response['output_authorized'])
        self.assertGreater(response['output_lease_seconds'], 0)
        self.assertLessEqual(response['output_lease_seconds'], 90)
        self.assertEqual(response['output_restart_policy'], 'MANUAL')
        self.assertFalse(self.post('telemetry', sample)['output_authorized'])

        client = APIClient()
        client.force_authenticate(self.admin)
        revoked = client.post(
            f'/api/v1/admin/prototype-devices/{self.device.pk}/output-authorization/revoke/',
            {'reason': 'Controlled test concluded and output inhibited'}, format='json',
        )
        self.assertEqual(revoked.status_code, 200, revoked.data)
        self.assertFalse(self.post('telemetry', self.recovered_sample(command, 3))['output_authorized'])
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
