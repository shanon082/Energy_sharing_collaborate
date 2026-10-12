import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeUgandanPhone, isUgandanPhone } from '../../frontend/src/lib/ugandan-phone.ts';
import { ForegroundPoller } from '../src/api/polling.ts';
import { parseMeterDashboard } from '../src/api/contracts.ts';
import { parsePaymentRecovery } from '../src/api/payment-recovery.ts';

test('phone canonicalization accepts only the three Ugandan forms without truncation', () => {
  for (const value of ['0771000111', '256771000111', '+256771000111', ' 0771000111 ']) {
    assert.equal(normalizeUgandanPhone(value), '+256771000111');
    assert.equal(isUgandanPhone(value), true);
  }
  for (const value of ['0771 000111', '0771-000111', '07710001111', '077100011', '25677100011',
    '+2560771000111', '٠771000111', '0771000111x', '']) {
    assert.throws(() => normalizeUgandanPhone(value));
    assert.equal(isUgandanPhone(value), false);
  }
});

test('foreground polling serializes reads, backs off and stops in the background', async () => {
  let resolve, calls = 0, next, delay, cleared = 0;
  const poller = new ForegroundPoller(() => {
    calls += 1; return new Promise((done) => { resolve = done; });
  }, 15_000, 120_000, (callback, ms) => { next = callback; delay = ms; return 1; }, () => { cleared += 1; });
  poller.setActive(true); poller.setActive(true);
  assert.equal(calls, 1);
  resolve(false); await Promise.resolve();
  assert.equal(delay, 30_000);
  next(); assert.equal(calls, 2);
  poller.setActive(false); resolve(false); await Promise.resolve();
  assert.equal(cleared, 1);
  poller.setActive(true); assert.equal(calls, 3);
  resolve(true); await Promise.resolve(); assert.equal(delay, 15_000);
  poller.dispose(); next(); assert.equal(calls, 3);
});

test('meter simulator credit stays exact and unavailable physical credit remains null', () => {
  const meter = { id: 4, meter_number: 'TEST-ONLY' };
  const payload = { meter, unit: 'kWh', quantum_kwh: '0.01', available_kwh: '1.00', pending_kwh: '0.00',
    confirmed_kwh: '0.00', delivery_environment: 'SIMULATOR', contact_source: 'SIMULATOR',
    contact_status: 'STALE', simulator_remaining_wh: '9007199254740993', meter_reported_remaining_wh: null,
    reported_relay_state: 'OPEN', last_measurement_at: null };
  const parsed = parseMeterDashboard(payload, meter);
  assert.equal(parsed.simulator_remaining_wh, '9007199254740993');
  assert.equal(parsed.meter_reported_remaining_wh, null);
  assert.equal(parsed.contact_status, 'STALE');
  assert.equal(parsed.reported_relay_state, 'OPEN');
  assert.throws(() => parseMeterDashboard({ ...payload, simulator_remaining_wh: 1.5 }, meter));
});

test('restart recovery fails closed on unreadable status or a different payment binding', () => {
  const expected = { purpose: 'PURCHASE', binding: 'MOBILE-1', requestId: 'saved-test-id' };
  const state = { pending: true, receipt: null, provider_polled: false, status_source: 'STORED_VERIFIED_SETTLEMENT' };
  assert.deepEqual(parsePaymentRecovery(state, expected), { pending: true, receipt: null });
  assert.throws(() => parsePaymentRecovery({ ...state, pending: undefined }, expected));
  assert.throws(() => parsePaymentRecovery({ ...state, provider_polled: true }, expected));
  const receipt = { external_id: 'test-reference', client_request_id: 'saved-test-id', purpose: 'PURCHASE',
    status: 'PENDING', amount_ugx: '1000.00', currency: 'UGX', meter_no: 'MOBILE-1', loan_id: null,
    purchase_billed_ugx: null, purchase_residual_ugx: null, repayment_applied_ugx: null, repayment_excess_ugx: null,
    environment: 'PROVIDER', settlement_recorded: false, initiated_at: '2026-10-12T00:00:00Z', settled_at: null };
  assert.equal(parsePaymentRecovery({ ...state, receipt }, expected).receipt.status, 'PENDING');
  assert.throws(() => parsePaymentRecovery({ ...state, receipt: { ...receipt, meter_no: 'OTHER' } }, expected));
  assert.throws(() => parsePaymentRecovery({ ...state, receipt: { ...receipt, client_request_id: 'other-id' } }, expected));
});
import { enrollmentLabel } from '../src/api/enrollment.ts';

test('final meter decisions never display as pending or granted access', () => {
  assert.equal(enrollmentLabel('REJECTED'), 'Request declined');
  assert.equal(enrollmentLabel('ASSIGNMENT_UNAVAILABLE'), 'Assignment unavailable — contact staff');
  assert.equal(enrollmentLabel('PENDING'), 'Awaiting staff verification');
  assert.equal(enrollmentLabel('LINKED'), 'Assigned');
});
