import test from 'node:test';
import assert from 'node:assert/strict';
import { measuredConsumptionPath, measuredFreshness, parseMeasuredConsumption, sameUsageScope } from '../src/lib/measured-consumption.ts';
import { LatestRead } from '../../mobile/src/api/read-scope.ts';

const asOf = '2026-11-26T12:00:00Z';
const selected = { id: 11, meter_number: '00000000011', environment: 'SANDBOX', days: 1 };
const replacement = { ...selected, id: 12, meter_number: '00000000012' };
const total = { measured_kwh: null, interval_count: 0, covered_ms: 0, window_ms: 43200000, coverage: 'UNAVAILABLE' };
function packet(scope, overrides = {}) {
  return {
    meter: { id: scope.id, meter_number: scope.meter_number }, environment: scope.environment, source: 'AC_LAB_PZEM',
    as_of: asOf, device_bound: true, stale_after_seconds: 90, latest_interval: null,
    latest: { device_id: 'synthetic-device', binding_epoch: 1, baseline: 'LEGACY', measured_at: asOf, received_at: asOf,
      freshness: 'RECENT', sensor_state: 'OK', fault_status: null, voltage_v: '230', current_a: '0', power_w: '0',
      cumulative_kwh: '22.153', remaining_credit_kwh: '0.000000001', output_command: 'OFF' },
    relay: { authorized: false, state: 'ACTIVE', expires_at: '2026-11-26T13:00:00Z', restart_policy: 'MANUAL', contact: 'UNKNOWN' },
    period: { ...total, days: scope.days, timezone: 'UTC', start_at: '2026-11-26T00:00:00Z', end_at: asOf,
      unallocated_kwh: null, unallocated_interval_count: 0 }, daily: [{ date: '2026-11-26', ...total }],
    history: [], history_truncated: false, ...overrides,
  };
}

test('the shared consumer contract distinguishes zero power, missing usage and stale evidence', () => {
  const parsed = parseMeasuredConsumption(packet(selected), selected);
  assert.equal(parsed.latest.power_w, '0');
  assert.equal(parsed.latest.remaining_credit_kwh, '0.000000001');
  assert.equal(parsed.daily[0].measured_kwh, null);
  assert.equal(parsed.relay.restart_policy, 'MANUAL');
  assert.equal(parsed.relay.contact, 'UNKNOWN');
  const persistent = parseMeasuredConsumption(packet(selected, {
    relay: { ...packet(selected).relay, mode: 'PERSISTENT', restart_policy: 'AUTO', expires_at: null },
  }), selected);
  assert.equal(persistent.relay.mode, 'PERSISTENT');
  assert.equal(persistent.relay.expires_at, null);
  const untimed = parseMeasuredConsumption(packet(selected, {
    latest: { ...packet(selected).latest, measured_at: null },
    relay: { ...packet(selected).relay, offline_allowed: true },
  }), selected);
  assert.equal(untimed.relay.offline_allowed, true);
  assert.equal(measuredFreshness(untimed, Date.parse(asOf)), 'STALE');
  assert.equal(measuredFreshness(parsed, Date.parse(asOf) + 89999), 'RECENT');
  assert.equal(measuredFreshness(parsed, Date.parse(asOf) + 90001), 'STALE');
  assert.equal(measuredFreshness(parseMeasuredConsumption(packet(selected, { latest: null }), selected), Date.parse(asOf)), 'UNAVAILABLE');
  assert.throws(() => parseMeasuredConsumption(packet(selected, { relay: { ...packet(selected).relay, contact: 'CLOSED' } }), selected));
});

test('a delayed response for the previous meter or domain cannot replace the current reading', async () => {
  assert.equal(measuredConsumptionPath(replacement), 'meter/mobile-meters/12/measured-consumption/?environment=SANDBOX&days=1');
  const reads = new LatestRead();
  let resolveFirst;
  const late = new Promise(resolve => { resolveFirst = resolve; });
  let visible = null;
  const pending = (async () => {
    const ticket = reads.begin();
    const previous = parseMeasuredConsumption(await late, selected);
    if (reads.current(ticket) && sameUsageScope(previous.scope, replacement)) visible = previous;
  })();
  const ticket = reads.begin();
  const current = parseMeasuredConsumption(packet(replacement), replacement);
  if (reads.current(ticket) && sameUsageScope(current.scope, replacement)) visible = current;
  resolveFirst(packet(selected));
  await pending;
  assert.equal(visible.scope.id, 12);
  assert.throws(() => parseMeasuredConsumption(packet(selected), replacement));
  assert.throws(() => parseMeasuredConsumption(packet(replacement), { ...replacement, environment: 'UGX_DEMO' }));
  assert.throws(() => parseMeasuredConsumption(packet(replacement), { ...replacement, days: 7 }));
});
