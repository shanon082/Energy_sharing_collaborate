import uuid

from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from meter.models import PrototypeMeasurementTransition, PrototypeTelemetry
from meter.prototype_device import identity
from meter.tests_prototype_device import LAB, LabFixtures


@override_settings(**LAB)
class AuthenticatedMeasurementTransitionTests(LabFixtures, TransactionTestCase):
    def migration_proposal(self, command, receipt, baseline=500):
        body = {
            **identity(self.device),
            'transition_id': str(uuid.uuid4()),
            'transition_protocol': 'GPAWA_BASELINE_V1',
            'source_state': 'AUTH_CREDIT_ONLY_V3',
            'had_baseline': False,
            'old_baseline_wh': None,
            'baseline_wh': baseline,
            'application_counter': command['command_sequence'],
            'ack_pending': False,
            'credited_uwh': command['credit_wh'] * 1_000_000,
            'consumed_uwh': 0,
            'uncertain_uwh': 0,
            'last_command_id': command['command_id'],
            'last_payload_digest': command['payload_digest'],
            'last_receipt_id': receipt['receipt_id'],
        }
        return body

    def accepted_sample(self, command, baseline, sequence, energy_delta, consumed):
        credit = command['credit_wh'] * 1_000_000
        body = {
            **self.sample(command, seq=sequence),
            'pzem_wh': baseline + energy_delta,
            'consumed_uwh': consumed,
            'remaining_credit_uwh': credit - consumed,
            'measured_at': timezone.now().isoformat(),
        }
        return body

    def test_baseline_transition_is_retry_safe_preserves_credit_and_accounts_only_new_energy(self):
        self.start()
        command = self.redeem(self.token())['command']
        receipt = self.receipt(command)
        self.post('ack', receipt)
        proposal = self.migration_proposal(command, receipt)

        prepared = self.post('measurement/prepare', proposal)
        self.assertEqual(prepared['status'], 'PREPARED')
        self.assertEqual(prepared['baseline_wh'], 500)
        self.assertFalse(prepared['output_authorized'])
        self.assertEqual(self.post('measurement/prepare', proposal), prepared)
        self.assertEqual(PrototypeMeasurementTransition.objects.count(), 1)

        commit = {
            **identity(self.device),
            'transition_id': proposal['transition_id'],
            'receipt_id': prepared['receipt_id'],
        }
        committed = self.post('measurement/commit', commit)
        self.assertEqual(committed['status'], 'COMMITTED')
        self.assertEqual(self.post('measurement/commit', commit), committed)
        self.assertFalse(committed['output_authorized'])
        transition = PrototypeMeasurementTransition.objects.get(device=self.device)
        self.assertEqual(transition.state, PrototypeMeasurementTransition.COMMITTED)
        self.assertEqual(transition.credited_uwh, command['credit_wh'] * 1_000_000)
        self.assertEqual(transition.consumed_uwh, 0)

        one_wh = self.accepted_sample(command, 500, 1, 1, 1_000_000)
        self.post('telemetry', one_wh)
        self.assertEqual(self.post('telemetry', one_wh)['status'], 'ACCEPTED')
        five_wh = self.accepted_sample(command, 500, 2, 5, 5_000_000)
        self.post('telemetry', five_wh)
        self.assertEqual(PrototypeTelemetry.objects.count(), 2)

        invalid = {**five_wh, 'sequence': 3, 'pzem_wh': 504, 'consumed_uwh': 4_000_000,
                   'remaining_credit_uwh': five_wh['credited_uwh'] - 4_000_000}
        self.post('telemetry', invalid, 409)

        fault = {
            **five_wh, 'sequence': 3, 'sensor_status': 'FAULT',
            'voltage_mv': None, 'current_ma': None, 'power_mw': None,
            'pzem_wh': None, 'frequency_cHz': None, 'power_factor_pct': None,
            'fault_status': 'SENSOR_UNAVAILABLE',
        }
        self.post('telemetry', fault)
        self.assertEqual(PrototypeTelemetry.objects.count(), 3)
        dashboard = self.client.get(
            f'/api/v1/meter/mobile-meters/{self.meter.pk}/?environment=UGX_DEMO',
            **self.headers,
        )
        self.assertEqual(dashboard.data['lab_measurement_state'], 'BASELINED')
        self.assertIsNone(dashboard.data['lab_voltage_mv'])
        self.assertIsNone(dashboard.data['lab_pzem_wh'])
        self.assertEqual(dashboard.data['lab_fault_status'], 'SENSOR_UNAVAILABLE')
        self.assertEqual(dashboard.data['lab_output_command'], 'OFF')
        self.assertEqual(dashboard.data['reported_relay_state'], 'UNKNOWN')

    def test_prepare_rejects_pending_ack_replay_and_conflicting_transition(self):
        self.start()
        command = self.redeem(self.token())['command']
        receipt = self.receipt(command)
        proposal = self.migration_proposal(command, receipt)
        proposal['ack_pending'] = True
        self.post('measurement/prepare', proposal, 409)
        self.assertFalse(PrototypeMeasurementTransition.objects.exists())

        self.post('ack', receipt)
        proposal['ack_pending'] = False
        prepared = self.post('measurement/prepare', proposal)
        altered = {**proposal, 'baseline_wh': proposal['baseline_wh'] + 1}
        self.post('measurement/prepare', altered, 409)
        self.post('measurement/commit', {
            **identity(self.device), 'transition_id': proposal['transition_id'],
            'receipt_id': str(uuid.uuid4()),
        }, 409)
        self.assertEqual(prepared['status'], 'PREPARED')
        self.assertEqual(PrototypeMeasurementTransition.objects.count(), 1)
