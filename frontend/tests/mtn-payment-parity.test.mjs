import test from 'node:test';
import assert from 'node:assert/strict';
import { paymentStatusMethod, parseTestPayment, sandboxCapabilities, demoCountdown, canClearRecoveredRetry } from '../src/lib/sandbox.ts';

test('web MTN status waits for Django; a timer or provider HTTP202 is not settlement', () => {
  const row = parseTestPayment({ reference: '00000000-0000-4000-8000-000000000001', purpose: 'PURCHASE', status: 'PENDING',
    amount: '2.00', currency: 'EUR', provider: 'MTN_SANDBOX', environment: 'MTN_SANDBOX', meter_id: 7,
    initiated_at: '2026-11-17T10:00:00Z', next_check_at: '2026-11-17T10:00:30Z' });
  const time = Date.parse(row.initiated_at);
  assert.equal(demoCountdown(row, time + 5000), null);
  assert.equal(paymentStatusMethod(row, time + 5000), 'GET');
  assert.equal(paymentStatusMethod(row, time + 30000), 'POST');
  assert.equal(row.status, 'PENDING');
  assert.throws(() => parseTestPayment({ ...row, status: 'SUCCESSFUL' }));
  assert.throws(() => parseTestPayment({ ...row, provider: 'LOCAL_DEMO' }));
});
test('web exposes the explicit EUR domain and unavailable payments without demo fallback', () => {
  const result = sandboxCapabilities({ enabled: true, currency: 'EUR', environment: 'MTN_SANDBOX', provider: 'MTN_SANDBOX',
    physical_delivery: false, loans: false, purchases: false, repayments: false, payment_message: 'Sandbox payments unavailable' });
  assert.equal(result.provider, 'MTN_SANDBOX'); assert.equal(result.currency, 'EUR');
  assert.equal(result.purchases, false); assert.equal(result.repayments, false);
  assert.equal(result.paymentMessage, 'Sandbox payments unavailable');
});
test('a not-found recovery cannot clear an uncertain charge identity', () => {
  assert.equal(canClearRecoveredRetry(null), false);
  assert.equal(canClearRecoveredRetry({status: 'PENDING'}), false);
  assert.equal(canClearRecoveredRetry({status: 'UNKNOWN'}), false);
  assert.equal(canClearRecoveredRetry({status: 'FAILED'}), true);
});
