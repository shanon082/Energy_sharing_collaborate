import test from 'node:test';
import assert from 'node:assert/strict';
import { sandboxCapabilities, NO_SANDBOX, parseTestLoan, parseTestPayment, mergePayments, testAmount, testPhone,
  readRetry, writeRetry } from '../../frontend/src/lib/sandbox.ts';
import { clearOwnerRequestIds } from '../src/api/request-id.ts';
import { parseMeters } from '../src/api/contracts.ts';

test('sandbox actions fail closed on missing currency/provider/isolation; optional flags stay independent', () => {
  const good = { enabled: true, loans: true, purchases: true, repayments: true, currency: 'EUR', provider: 'MTN_SANDBOX', physical_delivery: false };
  assert.deepEqual(sandboxCapabilities(good), { enabled: true, loans: true, purchases: true, repayments: true });
  for (const raw of [undefined, { ...good, enabled: 'true' }, { ...good, currency: 'UGX' }, { ...good, provider: 'MTN_PRODUCTION' }, { ...good, physical_delivery: true }])
    assert.deepEqual(sandboxCapabilities(raw), NO_SANDBOX);
  assert.equal(sandboxCapabilities({ ...good, purchases: 'true' }).purchases, false);
});
test('EUR payment contracts never relabel UGX, and pending history deduplicates stable references', () => {
  const payment = { reference: '00000000-0000-4000-8000-000000000001', amount: '1.00', status: 'PENDING', purpose: 'PURCHASE',
    currency: 'EUR', environment: 'MTN_SANDBOX', meter_id: 7 };
  assert.equal(parseTestPayment(payment).amount, '1.00');
  assert.equal(mergePayments([payment], [payment]).length, 1);
  assert.throws(() => parseTestPayment({ ...payment, currency: 'UGX' }));
  assert.throws(() => parseTestPayment({ ...payment, amount: 1.00 }));
  assert.throws(() => parseTestPayment({ ...payment, status: 'SUCCESS' }));
  assert.throws(() => parseTestLoan({ currency: 'UGX', environment: 'MTN_SANDBOX' }));
});
test('sandbox retry handles survive restart, isolate accounts and clear with existing logout', () => {
  const rows = new Map();
  globalThis.localStorage = { getItem: key => rows.get(key) ?? null, setItem: (key, value) => rows.set(key, value),
    removeItem: key => rows.delete(key), get length() { return rows.size; }, key: index => [...rows.keys()][index] ?? null };
  const id = '00000000-0000-4000-8000-000000000001';
  writeRetry(7, 'LOAN', id); writeRetry(8, 'LOAN', id); writeRetry(7, 'PURCHASE', id);
  assert.equal(readRetry(7, 'LOAN'), id); assert.equal(readRetry(9, 'LOAN'), null);
  clearOwnerRequestIds(7);
  assert.equal(readRetry(7, 'PURCHASE'), null); assert.equal(readRetry(8, 'LOAN'), id);
  assert.equal([...rows.values()].some(value => /password|token/.test(value)), false);
});
test('test-money inputs and meter inventory are explicit; missing inventory is never eligible', () => {
  for (const raw of ['0', '-1', '1.001', 'NaN', 'Infinity', '10001', '1e2']) assert.equal(testAmount(raw), false);
  assert.equal(testAmount('0.01'), true); assert.equal(testPhone('46733123499'), true);
  assert.equal(testPhone('+46733123499'), false);
  const row = { id: 7, meter_number: 'SANDBOX-1', architecture: 'AMI', status: 'ACTIVE' };
  const parse = value => parseMeters({ success: true, data: { meters: [value] } })[0];
  assert.equal(parse(row).sandbox_inventory, undefined);
  assert.equal(parse({ ...row, sandbox_inventory: true }).sandbox_inventory, true);
  assert.notEqual(parse({ ...row, sandbox_inventory: 'true' }).sandbox_inventory, true);
});

test('demo capabilities require the distinct UGX environment and local provider', () => {
  const good = { enabled: true, loans: true, purchases: true, repayments: true, currency: 'UGX', environment: 'UGX_DEMO', provider: 'LOCAL_DEMO', physical_delivery: false };
  assert.equal(sandboxCapabilities(good).provider, 'LOCAL_DEMO');
  for (const raw of [{ ...good, environment: 'MTN_SANDBOX' }, { ...good, currency: 'EUR' }, { ...good, provider: 'MTN_PRODUCTION' }])
    assert.deepEqual(sandboxCapabilities(raw), NO_SANDBOX);
});
test('demo countdown cannot settle and validates server deadlines despite clock skew', async () => {
  const { demoCountdown, testDemoAmount, testMoney } = await import('../../frontend/src/lib/sandbox.ts');
  const raw = { reference: '00000000-0000-4000-8000-000000000002', amount: '1003.00', status: 'PENDING', purpose: 'PURCHASE',
    currency: 'UGX', environment: 'UGX_DEMO', provider: 'LOCAL_DEMO', meter_id: 7,
    initiated_at: '2026-01-01T00:00:00Z', demo_eligible_at: '2026-01-01T00:00:05Z', server_time: '2026-01-01T00:00:00Z' };
  const receipt = parseTestPayment(raw);
  assert.equal(demoCountdown(receipt, receipt.observed_at), 5);
  assert.equal(demoCountdown(receipt, receipt.observed_at + 5000), 0);
  assert.equal(receipt.status, 'PENDING', 'elapsed time never fabricates success');
  assert.equal(demoCountdown({ ...receipt, status: 'SETTLED' }), null);
  assert.throws(() => parseTestPayment({ ...raw, amount: '1003.50' }));
  assert.throws(() => parseTestPayment({ ...raw, demo_eligible_at: '2026-01-01T00:00:04Z' }));
  assert.throws(() => parseTestPayment({ ...raw, initiated_at: 'invalid' }));
  assert.equal(testMoney('1003', 'UGX'), 'UGX DEMO 1003');
  assert.equal(testMoney('2.10', 'EUR'), 'EUR TEST 2.10');
  assert.equal(testDemoAmount('1000'), true);
  for (const value of ['1.5', '1.00', '1e3', 'NaN', '0', '1000001']) assert.equal(testDemoAmount(value), false);
});
test('demo retry recovery cannot overwrite old EUR handles and logout clears both', () => {
  const rows = new Map();
  globalThis.localStorage = { getItem: key => rows.get(key) ?? null, setItem: (key, value) => rows.set(key, value),
    removeItem: key => rows.delete(key), get length() { return rows.size; }, key: index => [...rows.keys()][index] ?? null };
  const eur = '00000000-0000-4000-8000-000000000001', ugx = '00000000-0000-4000-8000-000000000002';
  writeRetry(7, 'PURCHASE', eur); writeRetry(7, 'PURCHASE', ugx, 'UGX_DEMO');
  assert.equal(readRetry(7, 'PURCHASE'), eur); assert.equal(readRetry(7, 'PURCHASE', 'UGX_DEMO'), ugx);
  clearOwnerRequestIds(7);
  assert.equal(readRetry(7, 'PURCHASE'), null); assert.equal(readRetry(7, 'PURCHASE', 'UGX_DEMO'), null);
});

test('stored demo assessment distinguishes pending/unavailable from a real zero, with synthetic provenance', async () => {
  const { parseStoredDemoAssessment } = await import('../../frontend/src/lib/sandbox.ts');
  const pending = { assessment_status: 'PENDING', provider: 'SIMULATED_ACCOUNT_V1', input_source: 'SIMULATED_ACCOUNT_INFORMATION',
    currency: 'UGX', environment: 'UGX_DEMO', reason: 'Add a meter', eligible: false, score: null, profile_score: null,
    maximum: null, factors: null, scoring_policy_version: 'DEMO-SCORE-v1' };
  assert.equal(parseStoredDemoAssessment(pending).score, null);
  assert.equal(parseStoredDemoAssessment({ ...pending, assessment_status: 'UNAVAILABLE' }).maximum, null);
  for (const changed of [{ score: 0 }, { maximum: '5000' }, { eligible: true }, { provider: 'REAL_CRB' }])
    assert.throws(() => parseStoredDemoAssessment({ ...pending, ...changed }));
  const ready = { ...pending, assessment_status: 'READY', eligible: true, score: 85, profile_score: 85, maximum: '37500',
    purchase_points: 0, factors: { payment_history: 92, energy_consumption: 71, financial_capacity: 92 }, assessed_at: '2026-10-13T12:00:00Z' };
  assert.equal(parseStoredDemoAssessment(ready).score, 85);
  assert.equal(parseStoredDemoAssessment({ ...ready, eligible: false, score: 0 }).score, 0, 'an explicit established zero is distinct from missing data');
  assert.throws(() => parseStoredDemoAssessment({ ...ready, assessed_at: null }));
});
