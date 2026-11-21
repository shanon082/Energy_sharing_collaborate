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

test('both clients require domain-bound lab capability and disabled physical output', () => {
  const base = {enabled: true, currency: 'EUR', environment: 'MTN_SANDBOX', provider: 'MTN_SANDBOX', physical_delivery: false,
    purchases: true, repayments: true, loans: false};
  const lab = {enabled: true, environment: 'SANDBOX', protocol: 'GPAWA_PZEM_V2', physical_output: false};
  const valid = sandboxCapabilities({...base, ac_lab: lab});
  assert.equal(valid.labEnabled, true);
  assert.equal(valid.labEnvironment, 'SANDBOX');
  for (const invalid of [{...lab, environment: 'UGX_DEMO'}, {...lab, protocol: 'GPAWA_PZEM_V1'}, {...lab, physical_output: true}, {...lab, enabled: 'true'}]) {
    assert.equal(sandboxCapabilities({...base, ac_lab: invalid}).labEnabled, false);
  }
  assert.equal(sandboxCapabilities(base).labEnabled, undefined);
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
test('both clients explain unavailable loan origination before the Amount step', () => {
  for (const surface of ['web', 'mobile']) {
    const html = render({ ...props, surface, view: 'apply', purpose: 'LOAN', selectedMeter: {...props.selectedMeter, sandbox_inventory: true},
      loanReason: 'EUR test loan assessment policy unavailable. UGX demo assessments cannot authorize EUR debt.' });
    assert.match(html, /Loan applications unavailable/);
    assert.match(html, /EUR test loan assessment policy unavailable/);
    assert.doesNotMatch(html, /loan-stepper|<form|Submit application|Review terms/);
  }
});
test('eligible EUR purchases remain reviewable and older UGX debts explain the currency boundary', () => {
  for (const surface of ['web', 'mobile']) {
    const ready = {...props, surface, selectedMeter: {...props.selectedMeter, sandbox_inventory: true}, pending: false,
      policy: {id: 'SANDBOX-TEST-v1', minimum: '1.00', maximum: '20.00'}};
    const buy = render({...ready, view: 'purchase', purpose: 'PURCHASE'});
    assert.match(buy, /Review terms/);
    assert.match(buy, /<button(?:(?!disabled)[^>])*>Review terms/);
    assert.match(buy, /Amount \(EUR/);
    const old = {id: 'old-ugx-loan', meter_id: 7, status: 'DISBURSED', currency: 'UGX', environment: 'UGX_DEMO', principal: '1000',
      total_due: '1050', outstanding: '750', applied_repayments: '300', due_at: pending.initiated_at, allocated_kwh: null, allocation_id: null,
      terms: {policy: {id: 'DEMO-UGX-v2'}}, reason: 'Historical demo loan'};
    const loans = render({...ready, view: 'loans', loans: [old]});
    assert.match(loans, /UGX debt cannot be repaid with EUR payments/);
    assert.match(loans, /750/); assert.match(loans, /300|1,?050/);
    const activity = render({...ready, view: 'activity', payments: [{...pending, status: 'SETTLED', provider: 'LOCAL_DEMO', environment: 'UGX_DEMO', currency: 'UGX', amount: '1000'}]});
    assert.match(activity, /1,?000/);
    assert.match(activity, /UGX/);
  }
});
test('enabled LOCAL_DEMO loans retain Amount, Terms and explicit-consent progression', () => {
  for (const surface of ['web', 'mobile']) {
    const policy = {id: 'DEMO-UGX-v2', currency: 'UGX', environment: 'UGX_DEMO', minimum: '1000', maximum: '50000',
      interest_percent: '5', fee: '0', due_days: 7, penalty_percent: '0', rounding: 'Whole UGX; 10 Wh allocations'};
    const ready = {...props, surface, demo: true, currency: 'UGX', environment: 'UGX_DEMO', view: 'apply', purpose: 'LOAN',
      capabilities: {...props.capabilities, loans: true}, policy, loanReason: null, pending: false, amount: '1000',
      assessment: {score: 85, assessment_status: 'READY', eligible: true, maximum: '37500'},
      selectedMeter: {...props.selectedMeter, sandbox_inventory: true}};
    const amount = render(ready);
    assert.match(amount, /loan-stepper/); assert.match(amount, /<button(?:(?!disabled)[^>])*>Review terms/);
    const quote = {id: 'synthetic-quote', expires_at: '2030-01-01T00:00:00Z', terms: {policy, purpose: 'LOAN', amount: '1000', energy_kwh: '1.00',
      billed: '1000', residual: '0', interest: '50', fee: '0', total_due: '1050', due_at: '2030-01-01T00:00:00Z'}};
    const review = render({...ready, quote});
    assert.match(review, /Review loan terms/); assert.match(review, /<button[^>]*disabled[^>]*>Continue/);
    const accepted = render({...ready, quote, accepted: true});
    assert.match(accepted, /<button(?:(?!disabled)[^>])*>Continue/);
  }
});
test('Next.js and Android present the same pending, settled and failed server receipt', () => {
  for (const surface of ['web', 'mobile']) {
    const wait = render({ ...props, surface });
    assert.match(wait, /Waiting for MTN sandbox confirmation/);
    assert.doesNotMatch(wait, /Sandbox payment verified|simulating phone authorization|seconds/);
    const done = render({ ...props, surface, pending: false, payments: [{ ...pending, status: 'SETTLED', billed: '2.00', residual: '0', allocated_kwh: '2.00', settled_at: pending.next_check_at }] });
    assert.match(done, /Sandbox payment verified/); assert.match(done, /EUR/);
    assert.match(done, /SANDBOX\/GPAWA_PZEM_V2/);
    const failed = render({ ...props, surface, pending: false, payments: [{ ...pending, status: 'FAILED' }] });
    assert.match(failed, /Payment failed/); assert.doesNotMatch(failed, /Sandbox payment verified/);
    const repay = render({ ...props, surface, pending: false, payments: [{ ...pending, purpose: 'LOAN_REPAYMENT', status: 'SETTLED', applied: '2.00', excess: '0' }] });
    assert.match(repay, /Loan repayment/); assert.doesNotMatch(repay, /Electricity tokens|15-digit/);
  }
});

test('UGX loan quotes and EUR MTN receipts remain different on web and Android', () => {
  const caps = sandboxCapabilities({enabled: true, provider: 'MTN_SANDBOX', currency: 'EUR', environment: 'MTN_SANDBOX',
    physical_delivery: false, loans: true, purchases: true, repayments: true,
    lending: {enabled: true, currency: 'UGX', environment: 'UGX_DEMO', energy_environment: 'SANDBOX', policy: 'DEMO-UGX-ACLAB-v1', repayment_available: false}});
  assert.equal(caps.currency, 'EUR'); assert.equal(caps.loanCurrency, 'UGX');
  const policy = {id: 'DEMO-UGX-ACLAB-v1', currency: 'UGX', environment: 'UGX_DEMO', minimum: '1000', maximum: '50000',
    interest_percent: '5', fee: '0', due_days: 7, penalty_percent: '0', purchase_per_point: '10000', purchase_score_cap: 10, rounding: 'Whole UGX; 10 Wh',
    repayment_message: 'UGX debt cannot be repaid with EUR MTN sandbox payments. No repayment mapping is approved.'};
  for (const surface of ['web', 'mobile']) {
    const loan = {...props, surface, capabilities: caps, view: 'apply', purpose: 'LOAN', currency: 'UGX', environment: 'UGX_DEMO',
      paymentCurrency: 'EUR', paymentEnvironment: 'MTN_SANDBOX', loanCurrency: 'UGX', loanEnvironment: 'UGX_DEMO',
      selectedMeter: {...props.selectedMeter, sandbox_inventory: true}, amount: '10000', pending: false, policy,
      assessment: {score: 85, eligible: true, assessment_status: 'READY', maximum: '37500'}};
    const amount = render(loan);
    assert.match(amount, /Amount \(UGX\)/); assert.doesNotMatch(amount, /Use EUR test amounts/);
    const quote = {id: 'synthetic-quote', expires_at: '2030-01-01T00:00:00Z', terms: {policy, purpose: 'LOAN', amount: '10000', energy_kwh: '10.00', billed: '10000', residual: '0', interest: '500', fee: '0', total_due: '10500'}};
    const terms = render({...loan, quote});
    assert.match(terms, /No repayment mapping is approved/); assert.match(terms, /10,?500/);
    assert.match(terms, /disabled[^>]*>Continue/); assert.doesNotMatch(terms, /MTN sandbox number/);
    const purchase = render({...loan, view: 'home', currency: 'EUR', environment: 'MTN_SANDBOX', assessmentPolicy: policy, policy: {...policy, currency: 'EUR', purchase_per_point: '10'}, payments: [{...pending, status: 'SETTLED', billed: '2.00', allocated_kwh: '2.00'}]});
    assert.match(purchase, /EUR/); assert.doesNotMatch(purchase, /UGX(?: DEMO)? 2\.00/);
  }
});

test('paused new payments hide EUR entry on both surfaces while retaining receipts', () => {
  const capabilities=sandboxCapabilities({enabled:true,provider:'MTN_SANDBOX',currency:'EUR',environment:'MTN_SANDBOX',physical_delivery:false,new_payments_paused:true,purchases:true,repayments:true,loans:false});
  for(const surface of ['web','mobile']) {
    const html=render({...props,surface,view:'purchase',capabilities,pending:false,payments:[{...pending,status:'SETTLED',billed:'2.00',allocated_kwh:'2.00'}]});
    assert.match(html,/UGX purchases unavailable/);assert.doesNotMatch(html,/Amount \(EUR TEST\)/);assert.match(html,/EUR/);
  }
});

// Exact public hosted response shape observed on 2026-11-21. mobile_actions are
// intentionally not an input to sandboxCapabilities on either surface.
test('hosted purchases=true is not overridden by legacy EUR loans=false or mobile_actions=false',()=>{
  const caps=sandboxCapabilities({enabled:true,currency:'EUR',environment:'MTN_SANDBOX',provider:'MTN_SANDBOX',physical_delivery:false,
    purchases:true,repayments:true,loans:false});
  assert.equal(caps.purchases,true);assert.equal(caps.repayments,true);assert.equal(caps.loans,false);
  for(const surface of ['web','mobile']){
    const ready={...props,surface,capabilities:caps,pending:false,selectedMeter:{...props.selectedMeter,sandbox_inventory:true},
      policy:{id:'SANDBOX-TEST-v1',minimum:'1.00',maximum:'20.00'}};
    assert.match(render({...ready,view:'purchase'}),/<button(?:(?!disabled)[^>])*>Review terms/);
    assert.match(render({...ready,view:'apply',purpose:'LOAN'}),/backend has not advertised the UGX lending contract/);
  }
});
test('both surfaces explain pricing, assessment, recovery and server action failures',()=>{
  const ready={...props,pending:false,selectedMeter:{...props.selectedMeter,sandbox_inventory:true},
    policy:{id:'SANDBOX-TEST-v1',minimum:'1.00',maximum:'20.00'}};
  for(const surface of ['web','mobile']){
    for(const [change,reason] of [
      [{setupError:'Purchase terms request failed: HTTP 503',policy:null},/Purchase terms request failed: HTTP 503/],
      [{capabilities:{...props.capabilities,purchases:false,purchaseMessage:'Missing versioned EUR pricing'}},/Missing versioned EUR pricing/],
      [{unresolved:true,blocked:true},/previous request needs reconciliation/],
      [{refreshing:true,blocked:true},/Refreshing your account and pricing/],
    ]){
      const html=render({...ready,surface,view:'purchase',...change});
      assert.match(html,reason);assert.match(html,/<button[^>]*disabled[^>]*>Review terms/);
    }
    const lending=sandboxCapabilities({enabled:true,provider:'MTN_SANDBOX',currency:'EUR',environment:'MTN_SANDBOX',physical_delivery:false,
      purchases:true,repayments:true,loans:false,lending:{enabled:true,currency:'UGX',environment:'UGX_DEMO',energy_environment:'SANDBOX',policy:'DEMO-UGX-ACLAB-v1',repayment_available:false}});
    const html=render({...ready,surface,capabilities:lending,view:'apply',purpose:'LOAN',currency:'UGX',amount:'10000',
      assessment:{score:85,eligible:true,assessment_status:'READY',maximum:'37500'},loanReason:null});
    assert.match(html,/<button(?:(?!disabled)[^>])*>Review terms/);
    assert.doesNotMatch(html,/Loan applications unavailable/);
    const unavailable=render({...ready,surface,capabilities:lending,view:'apply',purpose:'LOAN',currency:'UGX',
      loanReason:'Loan assessment request failed: HTTP 503',setupError:'Loan assessment request failed: HTTP 503'});
    assert.match(unavailable,/Loan assessment request failed: HTTP 503/);
  }
});

test('approved UGX instructions keep provider EUR1 evidence separate on web and Android',()=>{
  const authorization={policy:'UGX-MTN-TEST-AUTH-v1',provider:'MTN_SANDBOX',currency:'EUR',amount:'1.00',no_real_money:true,energy_environment:'SANDBOX'};
  const caps=sandboxCapabilities({enabled:true,currency:'UGX',environment:'UGX_DEMO',provider:'MTN_SANDBOX',physical_delivery:false,
    purchases:true,repayments:true,loans:false,authorization,lending:{enabled:true,currency:'UGX',environment:'UGX_DEMO',energy_environment:'SANDBOX',policy:'DEMO-UGX-ACLAB-v1',repayment_available:true}});
  assert.equal(caps.currency,'UGX');assert.equal(caps.loans,true);assert.equal(caps.energyEnvironment,'SANDBOX');
  const receipt={...pending,currency:'UGX',environment:'UGX_DEMO',amount:'10000',authorization_policy:authorization.policy,instruction_id:pending.client_request_id,
    provider_receipt:{reference:pending.reference,external_id:'test-only-reference',transaction_id:null,amount:'1.00',currency:'EUR',environment:'MTN_SANDBOX',status:'PENDING',purpose:'TEST_AUTHORIZATION',no_real_money:true}};
  const record=parseTestPayment(receipt);
  assert.equal(demoCountdown(record),null);assert.equal(paymentStatusMethod(record,Date.parse(pending.next_check_at)),'POST');
  assert.throws(()=>parseTestPayment({...receipt,provider_receipt:{...receipt.provider_receipt,currency:'UGX'}}));
  assert.throws(()=>parseTestPayment({...receipt,authorization_policy:'unapproved'}));
  for(const surface of ['web','mobile']){
    const ready={...props,surface,capabilities:caps,currency:'UGX',environment:'UGX_DEMO',paymentCurrency:'UGX',paymentEnvironment:'UGX_DEMO',
      amount:'10000',pending:false,payments:[],view:'purchase',selectedMeter:{...props.selectedMeter,sandbox_inventory:true},
      policy:{id:'DEMO-UGX-MTN-AUTH-v1',currency:'UGX',environment:'UGX_DEMO',minimum:'1000',maximum:'50000'}};
    const html=render(ready);
    assert.match(html,/Amount \(UGX\)/);assert.doesNotMatch(html,/Amount \(EUR/);
    assert.match(html,/<button(?:(?!disabled)[^>])*>Review terms/);
    const pendingHtml=render({...ready,pending:true,payments:[receipt]});
    assert.match(pendingHtml,/Waiting for MTN sandbox confirmation/);assert.doesNotMatch(pendingHtml,/seconds|simulating phone authorization/);
    const settled={...receipt,status:'SETTLED',billed:'9999',residual:'1',allocated_kwh:'8.00',allocation_id:22,
      provider_receipt:{...receipt.provider_receipt,status:'SETTLED',transaction_id:'synthetic-provider-id'}};
    assert.equal(parseTestPayment(settled).currency,'UGX');
    const receiptHtml=render({...ready,payments:[settled]});
    assert.match(receiptHtml,/MTN test authorization \(not a conversion\)/);assert.match(receiptHtml,/EUR 1\.00/);
    const repay=render({...ready,view:'home',payments:[{...settled,purpose:'LOAN_REPAYMENT',loan_id:'synthetic-loan',allocation_id:null,allocated_kwh:null,applied:'4000',excess:'0'}]});
    assert.match(repay,/Loan repayment/);assert.doesNotMatch(repay,/Electricity tokens/);
  }
});

test('UGX home overview excludes legacy EUR activity while accurate history remains accessible',()=>{
 for(const surface of ['web','mobile']){
  const current={...props,surface,view:'home',currency:'UGX',environment:'UGX_DEMO',paymentCurrency:'UGX',paymentEnvironment:'UGX_DEMO',
    pending:false,payments:[{...pending,status:'SETTLED',amount:'2.00',currency:'EUR',environment:'MTN_SANDBOX'}]};
  const home=render(current);
  assert.doesNotMatch(home,/EUR/);assert.match(home,/Recent activity/);
  const history=render({...current,view:'activity'});
  assert.match(history,/EUR/);assert.match(history,/2(?:\.00)?/);
 }
});

test('missing provider capability explains UGX repayment denial without a false same-currency mismatch',()=>{
 for(const surface of ['web','mobile']){
  const html=render({...props,surface,view:'home',currency:'UGX',environment:'UGX_DEMO',paymentCurrency:'UGX',paymentEnvironment:'UGX_DEMO',
   pending:false,payments:[],capabilities:{...props.capabilities,repayments:false,repaymentMessage:'Sandbox payments unavailable: MTN credentials missing.'},
   loans:[{id:'synthetic-ugx-loan',meter_id:7,currency:'UGX',environment:'UGX_DEMO',status:'DISBURSED',principal:'10000',total_due:'10500',outstanding:'6500',
    repayment_available:true,repayment_message:'',terms:{policy:{id:'DEMO-UGX-ACLAB-v1'}},reason:'Approved test loan',due_at:pending.initiated_at,closed_at:null,allocation_id:null,allocated_kwh:null}]});
  assert.match(html,/MTN credentials missing/);assert.doesNotMatch(html,/UGX debt cannot be repaid with UGX/);assert.doesNotMatch(html,/EUR/);
 }
});
