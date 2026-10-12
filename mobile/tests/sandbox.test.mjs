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
