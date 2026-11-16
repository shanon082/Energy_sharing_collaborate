import test from 'node:test';
import assert from 'node:assert/strict';
import { parseMeterDashboard, parseConsumption, microWhDisplay } from '../src/api/contracts.ts';
const meter = { id: 3, meter_number: '00000001234' };
const snapshot = { meter, unit: 'kWh', quantum_kwh: '0.01', available_kwh: '0.00', pending_kwh: '0.00', confirmed_kwh: '1.00',
  contact_source: 'AC_LAB', delivery_environment: 'AC_LAB', contact_status: 'STALE', last_meter_contact: '2026-11-16T10:00:00Z',
  lab_remaining_credit_uwh: '9007199254740993', lab_consumed_uwh: '1000001', lab_sensor_status: 'OK',
  meter_reported_remaining_wh: null, reported_relay_state: 'UNKNOWN' };

test('selected meter receives exact lab readings, stale status and unknown load feedback', () => {
  const parsed = parseMeterDashboard(snapshot, meter);
  assert.equal(parsed.contact_source, 'AC_LAB');
  assert.equal(parsed.lab_remaining_credit_uwh, '9007199254740993');
  assert.equal(parsed.contact_status, 'STALE');
  assert.equal(parsed.meter_reported_remaining_wh, null);
  assert.equal(parsed.reported_relay_state, 'UNKNOWN');
  assert.equal(microWhDisplay(parsed.lab_consumed_uwh), '1.000001 Wh');
  assert.equal(microWhDisplay(undefined), 'Unavailable');
  assert.equal(microWhDisplay(null), 'Unavailable');
  assert.equal(microWhDisplay('0'), '0 Wh');
  assert.throws(() => parseMeterDashboard({ ...snapshot, lab_consumed_uwh: 1.5 }, meter));
  assert.throws(() => parseMeterDashboard(snapshot, { ...meter, id: 4 }));
});

test('fault and missing readings stay unavailable, old backend remains compatible', () => {
  assert.equal(parseMeterDashboard({ ...snapshot, lab_sensor_status: 'FAULT', lab_consumed_uwh: null }, meter).lab_consumed_uwh, null);
  const base = { meter, meter_no: meter.meter_number, daily_usage: [], simulator_telemetry: [] };
  assert.deepEqual(parseConsumption(base, meter).ac_lab_telemetry, []);
  const history = [{ boot_id: 'synthetic-boot', sequence: '2', measured_at: snapshot.last_meter_contact,
    received_at: snapshot.last_meter_contact, consumed_uwh: null, remaining_credit_uwh: '999999999',
    uncertain_uwh: '1', sensor_status: 'FAULT', pzem_wh: null }];
  assert.equal(parseConsumption({ ...base, ac_lab_telemetry: history }, meter).ac_lab_telemetry[0].consumed_uwh, null);
  assert.throws(() => parseConsumption({ ...base, ac_lab_telemetry: [{ ...history[0], sequence: 2 }] }, meter));
});

test('cached lab snapshots expire without another successful network response', async () => {
  const { labReadingStatus } = await import('../src/api/contracts.ts');
  const instant = '2026-11-16T10:00:00Z';
  const reading = { ...parseMeterDashboard(snapshot, meter), contact_status: 'RECENT', last_measurement_at: instant, lab_received_at: instant };
  assert.equal(labReadingStatus(reading, Date.parse(instant) + 89_000), 'RECENT');
  assert.equal(labReadingStatus(reading, Date.parse(instant) + 91_000), 'STALE');
  assert.equal(labReadingStatus({ ...reading, last_measurement_at: null }, Date.parse(instant)), 'UNAVAILABLE');
});
