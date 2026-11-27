import uuid
from datetime import datetime, timedelta, timezone as utc
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from meter.models import PrototypeDevice, PrototypeMeasurementTransition, PrototypeTelemetry
from meter.prototype_device import identity
from meter.tests_prototype_device import LAB, LabFixtures


@override_settings(**LAB)
class MeasuredConsumptionTests(LabFixtures, TestCase):
    def usage(self, *, now=None, days=7, environment='UGX_DEMO', client=None, status=200):
        with patch('meter.measured_consumption.timezone.now', return_value=now or timezone.now()):
            response = (client or self.client).get(
                f'/api/v1/meter/mobile-meters/{self.meter.pk}/measured-consumption/',
                {'days': days, 'environment': environment}, **self.headers,
            )
        self.assertEqual(response.status_code, status, response.data)
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        return response.data

    def observation(self, seq, when, wh, *, device=None, boot=None, **overrides):
        device = device or self.device
        # Historical stored evidence, including legacy discontinuities.
        data = {**identity(device), 'sensor_status': 'OK', 'voltage_mv': 230100,
                'current_ma': 500, 'power_mw': 100000, 'pzem_wh': wh,
                'consumed_uwh': 999_000_000, 'remaining_credit_uwh': 5_000_000,
                'output_requested': True, **overrides}
        reading = PrototypeTelemetry.objects.create(device=device, sequence=seq, boot_id=boot or self.boot,
                                                     measured_at=when, payload=data)
        PrototypeTelemetry.objects.filter(pk=reading.pk).update(received_at=when + timedelta(seconds=1))

    def test_positive_zero_and_missing_coverage_exclude_credit(self):
        now = datetime(2026, 11, 26, 12, tzinfo=utc.utc)
        self.observation(1, now - timedelta(seconds=75), 1234)
        self.observation(2, now - timedelta(seconds=45), 1234, current_ma=0, power_mw=0)
        usage = self.usage(now=now)
        self.assertEqual(usage['period']['measured_kwh'], '0')
        self.assertEqual(usage['latest']['power_w'], '0')
        self.assertIsNone(usage['daily'][0]['measured_kwh'])
        self.observation(3, now - timedelta(seconds=15), 1236)
        usage = self.usage(now=now)
        self.assertEqual(usage['period']['measured_kwh'], '0.002')
        self.assertEqual(usage['period']['coverage'], 'PARTIAL')
        self.assertEqual(usage['period']['covered_ms'], 60_000)
        self.assertEqual(usage['latest']['cumulative_kwh'], '1.236')
        self.assertEqual(usage['latest']['remaining_credit_kwh'], '0.005')
        self.assertEqual(usage['latest']['voltage_v'], '230.1')
        self.assertEqual(usage['latest']['current_a'], '0.5')
        self.assertEqual(usage['latest']['power_w'], '100')
        self.assertEqual(usage['latest']['freshness'], 'RECENT')
        self.assertEqual(usage['relay']['contact'], 'UNKNOWN')

    def test_authenticated_replay_counts_once(self):
        self.start()
        command = self.redeem(self.token())['command']
        self.post('ack', self.receipt(command))
        now = timezone.now()
        first = {**self.sample(command), 'measured_at': (now - timedelta(seconds=35)).isoformat()}
        second = {**first, 'sequence': 2, 'pzem_wh': first['pzem_wh'] + 3,
                  'measured_at': (now - timedelta(seconds=5)).isoformat()}
        for sample in (first, second, second):
            self.assertEqual(self.post('telemetry', sample)['status'], 'ACCEPTED')
        usage = self.usage()
        self.assertEqual(usage['period']['interval_count'], 1)
        self.assertEqual(usage['period']['measured_kwh'], '0.003')

    def test_fault_stale_and_counter_reset(self):
        now = datetime(2026, 11, 26, 12, tzinfo=utc.utc)
        for n, counter in enumerate((100, 101, None, 104, 1, 2, None), start=1):
            self.observation(n, now - timedelta(seconds=600-n*30), counter,
                             sensor_status='FAULT' if counter is None else 'OK')
        usage = self.usage(days=1, now=now)
        self.assertEqual(usage['period']['measured_kwh'], '0.002')
        self.assertIsNone(usage['period']['unallocated_kwh'])
        self.assertEqual(usage['latest']['freshness'], 'STALE')
        self.assertEqual(usage['latest']['sensor_state'], 'FAULT')
        self.assertIsNone(usage['latest']['power_w'])
        self.assertIn('COUNTER_RESET', [row['classification'] for row in usage['history']])

    def test_offline_checkpoints_expose_unknown_time_and_consecutive_upload_gaps(self):
        now = datetime(2026, 11, 26, 12, tzinfo=utc.utc)
        self.observation(1, now - timedelta(seconds=75), 100)
        self.observation(2, now - timedelta(seconds=45), 104, offline_gap=True)
        self.observation(3, now - timedelta(seconds=15), 107, clock_status='OFFLINE_UNTIMED',
                         fault_status='SENSOR_UNAVAILABLE')
        usage = self.usage(days=1, now=now)
        self.assertIsNone(usage['period']['measured_kwh'])
        self.assertEqual(usage['period']['unallocated_kwh'], '0.007')
        self.assertEqual([row['classification'] for row in usage['history'][:2]], ['TIME_UNRESOLVED', 'UPLOAD_GAP'])
        self.assertIsNone(usage['history'][0]['measured_at'])
        self.assertIsNone(usage['latest']['measured_at'])
        self.assertIsNone(usage['latest']['power_w'])
        self.assertEqual(usage['latest']['cumulative_kwh'], '0.107')
        self.assertEqual(usage['latest']['freshness'], 'STALE')

    def test_midnight_period_edge_restart_and_upload_gap(self):
        midnight = datetime(2026, 11, 26, tzinfo=utc.utc)
        boot = str(uuid.uuid4())
        for seq, offset, wh, boot_id in [(1, -15, 100, None), (2, 15, 103, None), (3, 45, 104, None),
                                         (5, 75, 106, None), (1, 105, 107, boot), (2, 245, 111, boot)]:
            self.observation(seq, midnight + timedelta(seconds=offset), wh, boot=boot_id)
        now = midnight + timedelta(minutes=5)
        usage = self.usage(now=now)
        self.assertEqual(usage['period']['timezone'], 'UTC')
        self.assertEqual(usage['period']['measured_kwh'], '0.001')
        self.assertEqual(usage['period']['unallocated_kwh'], '0.01')
        self.assertEqual(usage['period']['unallocated_interval_count'], 4)
        self.assertIsNone(usage['daily'][-2]['measured_kwh'])
        self.assertEqual(usage['daily'][-1]['measured_kwh'], '0.001')
        today = self.usage(days=1, now=now)
        self.assertEqual(today['period']['start_at'], midnight.isoformat())
        self.assertEqual(today['period']['unallocated_kwh'], '0.007')
        self.assertIn('PERIOD_BOUNDARY', [row['classification'] for row in today['history']])

    def test_baseline_binding_and_replacement_do_not_bridge_counters(self):
        now = datetime(2026, 11, 26, 12, tzinfo=utc.utc)
        start = now - timedelta(minutes=10)
        self.observation(1, start, 1)
        self.observation(2, start + timedelta(seconds=30), 2)
        transition = PrototypeMeasurementTransition.objects.create(
            device=self.device, transition_id=uuid.uuid4(), state='COMMITTED', had_baseline=True,
            old_baseline_wh=2, baseline_wh=2000, application_counter=0, credited_uwh=0,
            consumed_uwh=0, uncertain_uwh=0, payload={}, committed_at=start + timedelta(seconds=49),
        )
        PrototypeMeasurementTransition.objects.filter(pk=transition.pk).update(prepared_at=start + timedelta(seconds=48))
        self.observation(3, start + timedelta(seconds=60), 2001)
        self.observation(4, start + timedelta(seconds=90), 9000, binding_epoch=2)
        self.observation(5, start + timedelta(seconds=120), 9002, binding_epoch=2)
        PrototypeDevice.objects.filter(pk=self.device.pk).update(active=False, revoked_at=start + timedelta(seconds=130))
        replacement = PrototypeDevice.objects.create(meter=self.meter, owner=self.owner, provisioned_by=self.operator,
            credential_hash='fixture', credential_fingerprint='replacement-fixture', environment='UGX_DEMO')
        self.observation(1, start + timedelta(seconds=150), 20000, device=replacement)
        self.observation(2, start + timedelta(seconds=180), 20001, device=replacement)
        usage = self.usage(days=1, now=now)
        self.assertEqual(usage['period']['measured_kwh'], '0.004')
        self.assertEqual(usage['latest']['device_id'], str(replacement.pk))
        categories = [row['classification'] for row in usage['history']]
        for reason in ('BASELINE_CHANGED', 'BINDING_CHANGED', 'DEVICE_CHANGED'):
            self.assertIn(reason, categories)

    def test_owner_and_environment_scope(self):
        self.observation(1, timezone.now()-timedelta(seconds=32), 100)
        other = APIClient()
        other.force_authenticate(self.other)
        self.usage(client=other, status=404)
        unknown = self.usage(environment='SANDBOX')
        self.assertFalse(unknown['device_bound'])
        self.assertIsNone(unknown['period']['measured_kwh'])
        self.assertFalse(unknown['history'])
