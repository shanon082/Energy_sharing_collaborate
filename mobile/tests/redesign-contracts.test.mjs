import test from 'node:test';
import assert from 'node:assert/strict';
import { parseCreditSummary } from '../src/api/credit-summary.ts';
import { financeBackAction } from '../../frontend/src/lib/finance-navigation.ts';
import { parseTestQuote, assertTestPaymentBinding } from '../../frontend/src/lib/sandbox.ts';
import { activeConsumerTab, CONSUMER_TABS } from '../src/consumer-navigation.ts';
import { energy, ugx } from '../src/format.ts';

test('five consumer destinations retain their parent tab for nested views', () => {
  assert.deepEqual(CONSUMER_TABS.map(row => row.label), ['Home', 'Meters', 'Loans', 'Buy Units', 'Account']);
  assert.equal(activeConsumerTab('apply'), 'loans');
  assert.equal(activeConsumerTab('consumption'), 'meters');
  assert.equal(activeConsumerTab('purchase-review'), 'purchase');
});
const evidence = { assessment_status: 'READY', provider: 'SIMULATED_ACCOUNT_V1', input_source: 'SIMULATED_ACCOUNT_INFORMATION',
  currency: 'UGX', environment: 'UGX_DEMO', score: 85, profile_score: 85, maximum: '37500', purchase_points: 0,
  factors: { payment_history: 92, energy_consumption: 71, financial_capacity: 92 }, eligible: true,
  reason: 'Synthetic test profile', assessed_at: '2026-10-15T09:00:00Z', scoring_policy_version: 'DEMO-SCORE-v1' };
test('credit overview uses stored demo maximum and assessment timestamp rather than legacy core fields', () => {
  const value = parseCreditSummary({ ...evidence, max_loan_ugx: '999999', calculated_at: '2026-10-15T10:00:00Z' });
  assert.equal(value.limit, '37500'); assert.equal(value.calculatedAt, evidence.assessed_at); assert.equal(value.simulated, true);
  assert.equal(value.score, 85);
});
test('pending assessment never creates a score or starter allowance', () => {
  const value = parseCreditSummary({ ...evidence, assessment_status: 'PENDING', score: null, profile_score: null,
    maximum: null, factors: null, eligible: false, assessed_at: null });
  assert.equal(value.score, null); assert.equal(value.limit, null);
  assert.throws(() => parseCreditSummary({ ...evidence, assessment_status: 'UNAVAILABLE', score: 0 }));
});
test('core records remain exact and separate from demo assessment', () => {
  assert.equal(parseCreditSummary({ score: 0, max_loan_ugx: '12345.67', factors: null }).limit, '12345.67');
  assert.equal(parseCreditSummary({ score: null, factors: null }).simulated, false);
  assert.throws(() => parseCreditSummary({ score: '85', factors: {} }));
  assert.throws(() => parseCreditSummary({ score: 85, factors: { financial: NaN } }));
  assert.equal(ugx('100000000000000001.01'), 'UGX 100,000,000,000,000,001.01');
  assert.equal(energy(null), 'Unavailable');
});
const expected = { owner: 9001, meterId: 7, amount: '001000', purpose: 'PURCHASE', currency: 'UGX', environment: 'UGX_DEMO' };
const quote = { id: '00000000-0000-4000-8000-000000000001', terms_hash: 'a'.repeat(64), expires_at: '2026-10-15T12:00:00Z',
  terms: { owner_id: 9001, meter_id: 7, amount: '1000', purpose: 'PURCHASE', energy_kwh: '1.00', billed: '1000',
    residual: '0', interest: '0', fee: '0', total_due: '0', policy: { id: 'DEMO-UGX-v1', currency: 'UGX', environment: 'UGX_DEMO' } } };
test('quotes bind exact amount, owner, meter, currency, purpose, hash and expiry', () => {
  assert.equal(parseTestQuote(quote, expected).id, quote.id);
  for (const changes of [{ owner_id: 9999 }, { meter_id: 8 }, { amount: '1001' }, { purpose: 'LOAN' }])
    assert.throws(() => parseTestQuote({ ...quote, terms: { ...quote.terms, ...changes } }, expected));
  assert.throws(() => parseTestQuote({ ...quote, terms_hash: 'bad' }, expected));
  assert.throws(() => parseTestQuote({ ...quote, expires_at: 'bad' }, expected));
  assert.throws(() => parseTestQuote({ ...quote, terms: { ...quote.terms, policy: { ...quote.terms.policy, currency: 'EUR' } } }, expected));
});
test('a status response for a different payment cannot produce success for the pending request', () => {
  const row = { reference: quote.id, client_request_id: quote.id, purpose: 'PURCHASE', amount: '1000',
    meter_id: 7, loan_id: null, currency: 'UGX', environment: 'UGX_DEMO' };
  assert.doesNotThrow(() => assertTestPaymentBinding({ ...row, status: 'SETTLED' }, row));
  for (const changes of [{ reference: 'different' }, { client_request_id: 'different' }, { meter_id: 8 }, { purpose: 'LOAN_REPAYMENT' },
                        { amount: '1001' }, { loan_id: 'different' }, { currency: 'EUR' }, { environment: 'MTN_SANDBOX' }])
    assert.throws(() => assertTestPaymentBinding({ ...row, ...changes, status: 'SETTLED' }, row));
});
test('Back returns through review steps without cancelling a payment', () => {
  const base = { view: 'apply', busy: false, pending: false, hasQuote: true, confirming: true, repaying: false, reviewingRepayment: false };
  assert.equal(financeBackAction(base), 'terms');
  assert.equal(financeBackAction({ ...base, confirming: false }), 'amount');
  assert.equal(financeBackAction({ ...base, hasQuote: false }), 'loans');
  assert.equal(financeBackAction({ ...base, busy: true }), 'wait');
  assert.equal(financeBackAction({ ...base, view: 'loans', pending: true, repaying: true }), 'none');
  assert.equal(financeBackAction({ ...base, view: 'loans', repaying: true, reviewingRepayment: true }), 'repayment');
});

test('foreground polling binds browser timer methods to the global receiver', async () => {
  const { ForegroundPoller } = await import('../src/api/polling.ts');
  const calls = [];
  function schedule(callback, delay) {
    assert.equal(this, globalThis, 'browser setTimeout must not receive the poller as this');
    calls.push(['schedule', delay]); return 42;
  }
  function cancel(id) {
    assert.equal(this, globalThis, 'browser clearTimeout must not receive the poller as this');
    calls.push(['cancel', id]);
  }
  const poller = new ForegroundPoller(async () => true, 1000, 5000, schedule, cancel);
  poller.setActive(true);
  await new Promise(resolve => setImmediate(resolve));
  poller.dispose();
  assert.deepEqual(calls, [['schedule', 1000], ['cancel', 42]]);
});
