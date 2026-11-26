import uuid
from datetime import timedelta

from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from meter.models import PrototypeTelemetry
from meter.prototype_device import RECOVERY_PROTOCOL, identity
from meter.tests_prototype_device import LAB, LabFixtures


@override_settings(**LAB)
class MeterRecoveryTests(LabFixtures, TransactionTestCase):
    def handshake_for(self, mode='METERED', consumed=0, **changes):
        body = {**self.handshake, 'initialize': False, 'accounting_protocol': RECOVERY_PROTOCOL,
                'journal_mode': mode, 'consumed_uwh': consumed}
        if mode == 'METERED':
            body['journal_counter_wh'] = 500
        if hasattr(self, 'legacy_command'):
            body.update(application_counter=1, credited_uwh=self.credit,
                        last_command_id=self.legacy_command['command_id'],
                        last_payload_digest=self.legacy_command['payload_digest'],
                        last_receipt_id=self.legacy_receipt['receipt_id'])
        return {**body, **changes}

    def commit_baseline(self, handshake, source, *, old=None, baseline=500):
        fields = ('application_counter', 'ack_pending', 'credited_uwh', 'consumed_uwh',
                  'uncertain_uwh', 'last_command_id', 'last_payload_digest', 'last_receipt_id')
        proposal = {**identity(self.device), **{k: handshake[k] for k in fields if k in handshake},
                    'transition_id': str(uuid.uuid4()), 'transition_protocol': 'GPAWA_BASELINE_V1',
                    'source_state': source, 'had_baseline': old is not None,
                    'old_baseline_wh': old, 'baseline_wh': baseline}
        prepared = self.post('measurement/prepare', proposal)
        self.assertEqual(self.post('measurement/prepare', proposal), prepared)
        commit = {**identity(self.device), 'transition_id': proposal['transition_id'],
                  'receipt_id': prepared['receipt_id']}
        self.assertEqual(self.post('measurement/commit', commit)['status'], 'COMMITTED')
        self.assertEqual(self.post('measurement/commit', commit)['status'], 'COMMITTED')

    def start_paused(self):
        self.start()
        self.legacy_command = self.redeem(self.token())['command']
        self.legacy_receipt = self.receipt(self.legacy_command)
        self.post('ack', self.legacy_receipt)
        self.credit = self.legacy_command['credit_wh'] * 1_000_000
        handshake = self.handshake_for(mode='PAUSED')
        self.assertEqual(self.post('session', handshake)['measurement_baseline'], 'REQUIRED')
        self.commit_baseline(handshake, 'AUTH_CREDIT_ONLY_V3')

    def reading(self, sequence, wh, consumed, **changes):
        amount = getattr(self, 'credit', 0)
        body = {**self.sample({'command_sequence': int(bool(amount)), 'credit_wh': amount // 1_000_000},
                              seq=sequence),
                'credited_uwh': amount, 'consumed_uwh': consumed,
                'remaining_credit_uwh': amount - consumed, 'pzem_wh': wh,
                'accounting_protocol': RECOVERY_PROTOCOL}
        return {**body, **changes}

    def test_network_restart_and_lost_reply_reconcile_without_overwriting_verified_debit(self):
        self.start_paused()
        initial = self.reading(1, 500, 0)
        self.post('telemetry', initial)
        lost = self.reading(2, 501, 1_000_000)
        # The first attempt never reached Django. Replaying it still verifies
        # the debit, but is ineligible for a lease even on first acceptance.
        replay = self.post('telemetry', lost, **self.device_headers, HTTP_X_GPAWA_TELEMETRY_REPLAY='1')
        self.assertTrue(replay['recovery_pending'])
        self.assertFalse(replay['output_authorized'])
        self.assertFalse(self.post('telemetry', lost)['output_authorized'])
        self.assertEqual(PrototypeTelemetry.objects.count(), 2)
        new_boot = str(uuid.uuid4())
        session = self.handshake_for(consumed=3_000_000, boot_id=new_boot, boot_counter=2, journal_counter_wh=503)
        result = self.post('session', session)
        self.assertFalse(result['output_authorized'])
        self.assertEqual(result['verified_consumed_uwh'], 1_000_000)
        self.assertEqual(result['verified_counter_wh'], 501)
        self.assertEqual(self.post('telemetry', lost, 409)['code'], 'DEVICE_SESSION_REQUIRED')
        incomplete = self.reading(1, 502, 2_000_000, boot_id=new_boot, boot_counter=2)
        self.assertTrue(self.post('telemetry', incomplete)['recovery_pending'])
        updated = self.reading(2, 503, 3_000_000, boot_id=new_boot, boot_counter=2)
        self.post('telemetry', {**updated, 'consumed_uwh': 4_000_000,
                                'remaining_credit_uwh': self.credit - 4_000_000}, 409)
        self.post('telemetry', updated)
        self.post('telemetry', updated)
        self.device.refresh_from_db()
        self.assertEqual(self.device.consumed_uwh, 3_000_000)
        self.assertEqual(PrototypeTelemetry.objects.count(), 4)
        self.assertFalse(self.device.recovery_pending)

    def test_fault_requires_retained_counter_evidence_and_never_renews_output(self):
        self.start_paused()
        self.post('telemetry', self.reading(1, 500, 0))
        fault = self.reading(3, None, 1_000_000, sensor_status='FAULT', fault_status='SENSOR_UNAVAILABLE',
                             **dict.fromkeys(('voltage_mv', 'current_ma', 'power_mw', 'frequency_cHz', 'power_factor_pct')))
        self.assertEqual(self.post('telemetry', fault, 409)['code'], 'METER_ACCOUNTING_MISMATCH')
        proof = self.reading(2, 501, 1_000_000, fault_status='SENSOR_UNAVAILABLE')
        self.assertFalse(self.post('telemetry', proof)['output_authorized'])
        fault['measured_at'] = timezone.now().isoformat()
        self.assertFalse(self.post('telemetry', fault)['output_authorized'])
        self.device.refresh_from_db()
        self.assertTrue(self.device.recovery_pending)
        self.assertEqual(self.device.consumed_uwh, 1_000_000)
        self.post('telemetry', self.reading(4, 501, 1_000_000))
        self.device.refresh_from_db()
        self.assertFalse(self.device.recovery_pending)

    def test_credit_checkpoint_fences_topup_at_depletion_and_survives_boot(self):
        self.start_paused()
        spent = self.credit - 1_000_000
        old_wh = 500 + spent // 1_000_000
        self.post('telemetry', self.reading(1, old_wh, spent))
        token = self.token()
        command = self.post('redeem', {**identity(self.device), 'token': token,
                                      'application_counter': 1, 'accounting_protocol': RECOVERY_PROTOCOL})['command']
        recovered = self.post('session', self.handshake_for(consumed=spent))
        self.assertEqual(command, recovered['pending_credit_command'])
        self.assertTrue(recovered['credit_checkpoint_required'])
        ack = self.receipt(command)
        self.assertEqual(self.post('ack', ack, 409)['code'], 'CREDIT_CHECKPOINT_REQUIRED')
        # Two more measured Wh close the old epoch. Only one was purchasable.
        closed = self.reading(2, old_wh + 2, self.credit)
        self.post('telemetry', closed)
        ack = {**self.receipt(command), 'credit_checkpoint': {'boot_id': self.boot, 'sequence': 2}}
        new_credit = self.credit + command['credit_wh'] * 1_000_000
        new_boot = str(uuid.uuid4())
        self.post('session', self.handshake_for(consumed=self.credit, boot_id=new_boot, boot_counter=2,
                  ack_pending=True, application_counter=2, credited_uwh=new_credit,
                  last_command_id=command['command_id'], last_payload_digest=command['payload_digest'],
                  last_receipt_id=ack['receipt_id']))
        self.post('ack', ack)
        self.post('ack', ack)
        self.assertEqual(self.post('ack', {**ack, 'credit_checkpoint': {'boot_id': self.boot, 'sequence': 1}}, 409)['code'],
                         'RECEIPT_CONFLICT')
        self.post('telemetry', self.reading(1, old_wh + 3, self.credit + 1_000_000, boot_id=new_boot,
                  boot_counter=2, application_counter=2, credited_uwh=new_credit,
                  remaining_credit_uwh=new_credit - self.credit - 1_000_000))
        self.device.refresh_from_db()
        self.assertEqual(self.device.application_counter, 2)
        self.assertEqual(self.device.consumed_uwh, self.credit + 1_000_000)

    def test_fresh_baseline_does_not_charge_lifetime_counter(self):
        handshake = self.handshake_for(mode='FRESH', initialize=True)
        self.post('session', handshake)
        self.commit_baseline(handshake, 'FRESH_METERED', baseline=500)
        self.post('telemetry', self.reading(1, 500, 0))
        self.post('telemetry', self.reading(2, 501, 0))
        self.device.refresh_from_db()
        self.assertEqual(self.device.consumed_uwh, 0)

    def test_existing_metered_ledger_adopts_server_evidence(self):
        self.start()
        self.legacy_command = self.redeem(self.token())['command']
        self.legacy_receipt = self.receipt(self.legacy_command)
        self.post('ack', self.legacy_receipt)
        self.credit = self.legacy_command['credit_wh'] * 1_000_000
        self.post('telemetry', self.sample(self.legacy_command))
        response = self.post('session', self.handshake_for(consumed=2_000_000))
        self.assertEqual(response['measurement_baseline'], 'COMMITTED')
        self.assertEqual(response['verified_consumed_uwh'], 1_000_000)
        self.assertEqual(response['verified_counter_wh'], 500)
        self.post('telemetry', self.reading(2, 501, 2_000_000))
        self.device.refresh_from_db()
        self.assertEqual(self.device.consumed_uwh, 2_000_000)

    def test_unanchored_legacy_journal_can_keep_its_zero_debit_baseline(self):
        self.start()
        handshake = self.handshake_for()
        self.assertEqual(self.post('session', handshake)['measurement_baseline'], 'REQUIRED')
        self.commit_baseline(handshake, 'LEGACY_METERED', old=500, baseline=500)
        self.post('telemetry', self.reading(1, 501, 0))
