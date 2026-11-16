import test from 'node:test';
import assert from 'node:assert/strict';
import { buildSync } from 'esbuild';
import { paymentStatusMethod, parseTestPayment, sandboxCapabilities, demoCountdown, canClearRecoveredRetry } from '../../frontend/src/lib/sandbox.ts';

const pending = {
  reference: '00000000-0000-4000-8000-000000000001', client_request_id: '00000000-0000-4000-8000-000000000002',
  purpose: 'PURCHASE', status: 'PENDING', amount: '2.00', currency: 'EUR', environment: 'MTN_SANDBOX', provider: 'MTN_SANDBOX',
  meter_id: 7, loan_id: null, billed: null, residual: null, applied: null, excess: null, allocation_id: null, allocated_kwh: null,
  initiated_at: '2026-11-17T10:00:00Z', settled_at: null, submission_state: 'ACCEPTED', reconciliation_error: '', next_check_at: '2026-11-17T10:00:30Z',
};
test('MTN status timing asks Django, never turns elapsed five seconds into success', () => {
  const row = parseTestPayment(pending);
  assert.equal(demoCountdown(row, Date.parse(pending.initiated_at) + 5000), null);
  assert.equal(paymentStatusMethod(row, Date.parse(pending.initiated_at) + 5000), 'GET');
  assert.equal(paymentStatusMethod(row, Date.parse(pending.next_check_at)), 'POST');
  assert.equal(row.status, 'PENDING');
  assert.throws(() => parseTestPayment({ ...pending, provider: 'LOCAL_DEMO' }));
  const unavailable = sandboxCapabilities({ enabled: true, provider: 'MTN_SANDBOX', currency: 'EUR', environment: 'MTN_SANDBOX', physical_delivery: false,
    loans: false, purchases: false, repayments: false, payment_message: 'Sandbox payments unavailable' });
  assert.equal(unavailable.paymentMessage, 'Sandbox payments unavailable');
  assert.equal(unavailable.provider, 'MTN_SANDBOX');
  assert.equal(unavailable.purchases, false);
});
test('missing recovery after a timeout retains identity and cannot authorize another charge', () => {
  assert.equal(canClearRecoveredRetry(null), false);
  assert.equal(canClearRecoveredRetry({ status: 'PENDING' }), false);
  assert.equal(canClearRecoveredRetry({ status: 'UNKNOWN' }), false);
  assert.equal(canClearRecoveredRetry({ status: 'SETTLED' }), true);
  assert.equal(canClearRecoveredRetry({ status: 'FAILED' }), true);
});

// Exercise the shared actual TSX presentation for both clients, with no DOM,
// credentials, network, provider, fake settlement or duplicated payment pipeline.
const compiled = buildSync({
  stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server';
    import View from './frontend/src/components/sandbox-mobile-view.tsx';
    export function render(props) { return renderToStaticMarkup(React.createElement(View, props)); }`,
    resolveDir: new URL('../../', import.meta.url).pathname, sourcefile: 'mtn-parity-fixture.tsx', loader: 'tsx' },
  bundle: true, platform: 'node', format: 'esm', jsx: 'automatic', write: false,
  nodePaths: [new URL('../../frontend/node_modules', import.meta.url).pathname, new URL('../node_modules', import.meta.url).pathname],
  banner: {js: "import {createRequire} from 'node:module'; const require = createRequire(" + JSON.stringify(import.meta.url) + ");"},
});
const { render } = await import('data:text/javascript;base64,' + Buffer.from(compiled.outputFiles[0].text).toString('base64'));
const noop = () => {};
const props = {
  client: { get: () => { throw Error('No network'); } }, owner: 1, view: 'home', demo: false, currency: 'EUR', environment: 'MTN_SANDBOX',
  capabilities: { enabled: true, loans: false, purchases: true, repayments: true }, pricingStatus: { available: true, message: '' },
  assessment: null, policy: null, loanReason: null, loans: [], payments: [pending], meters: [{ id: 7, meter_number: '00000000007', sandbox_inventory: true }],
  selectedMeter: { id: 7, meter_number: '00000000007' }, purpose: 'PURCHASE', amount: '2.00', quote: null, accepted: false, phone: '', loanId: '', repayment: '',
  repayAccepted: false, blocked: false, busy: false, refreshing: false, offline: false, unresolved: false, pending: true,
  error: null, notice: null, fetched: pending.initiated_at, clock: Date.parse(pending.initiated_at) + 6000,
  navigate: noop, setSelectedMeter: noop, setAmount: noop, clearQuote: noop, setAccepted: noop, setPhone: noop, selectLoan: noop,
  setRepayment: noop, setRepayAccepted: noop, validAmount: () => true, validPhone: true, refresh: noop, getQuote: noop, submit: noop, repay: noop, checkPayment: noop,
};
test('Next.js and Android present the same pending, settled and failed server receipt', () => {
  for (const surface of ['web', 'mobile']) {
    const wait = render({ ...props, surface });
    assert.match(wait, /Waiting for MTN sandbox confirmation/);
    assert.doesNotMatch(wait, /Sandbox payment verified|simulating phone authorization|seconds/);
    const done = render({ ...props, surface, pending: false, payments: [{ ...pending, status: 'SETTLED', billed: '2.00', residual: '0', allocated_kwh: '2.00', settled_at: pending.next_check_at }] });
    assert.match(done, /Sandbox payment verified/); assert.match(done, /EUR/);
    assert.match(done, /UGX_DEMO-only AC lab/);
    const failed = render({ ...props, surface, pending: false, payments: [{ ...pending, status: 'FAILED' }] });
    assert.match(failed, /Payment failed/); assert.doesNotMatch(failed, /Sandbox payment verified/);
    const repay = render({ ...props, surface, pending: false, payments: [{ ...pending, purpose: 'LOAN_REPAYMENT', status: 'SETTLED', applied: '2.00', excess: '0' }] });
    assert.match(repay, /Loan repayment/); assert.doesNotMatch(repay, /Electricity tokens|15-digit/);
  }
});
