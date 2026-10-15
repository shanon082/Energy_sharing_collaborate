// Browser-only integration checks. All APIs are intercepted; nothing reaches Django.
import assert from 'node:assert/strict';
import { randomUUID, createHash } from 'node:crypto';
import { mkdir } from 'node:fs/promises';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.MOBILE_UI_URL || 'http://127.0.0.1:5173';
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname));
const browser = await chromium.launch({ headless: true });
const shots = process.env.MOBILE_UI_SCREENSHOTS;
if (shots) await mkdir(shots, { recursive: true });
const user = { id: 9001, email: 'ui@example.invalid', first_name: 'UI', last_name: 'Test', user_role: 'CLIENT', email_verified: true };
const policy = { id: 'DEMO-UGX-v1', currency: 'UGX', environment: 'UGX_DEMO', minimum: '1000', maximum: '50000', starter_limit: '5000',
  interest_percent: '5', fee: '0', rate_per_kwh: '1000', due_days: 7, penalty_percent: '0', rounding: 'Synthetic fixed test terms',
  purchase_per_point: '10000', purchase_score_cap: 10, score_threshold: 75 };
const meter = id => ({ id, meter_number: `00000${id}`, label: `Meter ${id}`, architecture: 'AMI', status: 'ACTIVE',
  sandbox_inventory: true, ownership_provenance: 'SELF_DECLARED', enrolled_at: new Date().toISOString(), hardware_connection: 'PENDING' });
let checks = 0;
async function scenario(name, run, initial = {}) {
  if (process.env.UI_SCENARIO_FILTER && !name.includes(process.env.UI_SCENARIO_FILTER)) return;
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true });
  const page = await context.newPage(); page.setDefaultTimeout(18000);
  const errors = []; const calls = []; const quotes = new Map();
  const s = { meters: [meter(7)], loans: [], payments: [], balance: '0.00', assessment: 'READY', score: 85,
    settle: false, mutations: true, capabilitiesFail: false, delayQuote: 0, expiredQuote: false, loseInitiation: false,
    failedProfile: false, ...initial };
  page.on('pageerror', e => errors.push(e.stack ?? e.message));
  const assessment = () => ({ eligible: s.assessment === 'READY' && s.score >= 75 && !s.loans.some(l => l.status === 'DISBURSED'),
    reason: s.assessment !== 'READY' ? 'Assessment pending. Add your meter.' : s.score < 75 ? 'Demo score is below the test threshold.' : 'Stored synthetic assessment.',
    score: s.assessment === 'READY' ? s.score : null, profile_score: s.assessment === 'READY' ? s.score : null, starter: false,
    assessment_status: s.assessment, input_source: 'SIMULATED_ACCOUNT_INFORMATION', provider: 'SIMULATED_ACCOUNT_V1',
    currency: 'UGX', environment: 'UGX_DEMO', maximum: s.assessment === 'READY' ? '37500' : null,
    factors: s.assessment === 'READY' ? { payment_history: 92, energy_consumption: 71, financial_capacity: 92 } : null,
    categories: { payment_history: 'GOOD', energy_consumption: 'MODERATE', financial_capacity: 'STRONG' },
    purchase_points: 0, qualifying_billed_test: '0', policy_id: policy.id, scoring_policy_version: 'DEMO-SCORE-v1',
    assessed_at: s.assessment === 'READY' ? new Date().toISOString() : null });
  const reply = (route, body, status = 200) => route.fulfill({ status, contentType: 'application/json',
    headers: { 'access-control-allow-origin': new URL(base).origin, 'access-control-allow-headers': 'authorization,content-type',
      'access-control-allow-methods': 'GET,POST,PATCH,OPTIONS' }, body: JSON.stringify(body) });
  await context.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url()), path = url.pathname;
    if (!path.startsWith('/api/v1/')) {
      if (s.nativeBack && path.endsWith('/@capacitor_core.js')) {
        const response = await route.fetch();
        return route.fulfill({ response, body: (await response.text()) + '\nCapacitor.isNativePlatform = () => true;\n' });
      }
      if (s.nativeBack && path.endsWith('/@capacitor_app.js')) return route.fulfill({ contentType: 'application/javascript', body: `
        globalThis.__testNativeEvents = new Map(); globalThis.__testMinimized = 0;
        export const App = { addListener: async (name, callback) => {
          const events = globalThis.__testNativeEvents.get(name) || new Set(); events.add(callback);
          globalThis.__testNativeEvents.set(name, events);
          return { remove: async () => events.delete(callback) };
        }, minimizeApp: async () => { globalThis.__testMinimized++; } };
      ` });
      if (url.origin === new URL(base).origin) return route.continue();
      return route.abort();
    }
    if (request.method() === 'OPTIONS') return reply(route, {});
    const input = request.method() === 'POST' || request.method() === 'PATCH' ? request.postDataJSON() : {};
    calls.push({ path, method: request.method(), input });
    if (path.endsWith('auth/login/')) return reply(route, { access: 'ui-test-access', refresh: 'ui-test-refresh', user });
    if (path.endsWith('auth/mobile-account/')) return reply(route, user);
    if (path.endsWith('auth/mobile-logout/')) return route.fulfill({ status: 204 });
    if (path.endsWith('features/')) {
      if (s.capabilitiesFail) return route.abort();
      return reply(route, { features: { peer_sharing: false, meter_transfers: false, third_party_repayment: false, ussd: false,
        wallet_deposits: false, wallet_withdrawals: false, external_crb: false }, mobile_actions: { purchase: false, repayment: false },
        sandbox: { enabled: true, provider: 'LOCAL_DEMO', currency: 'UGX', environment: 'UGX_DEMO', physical_delivery: false,
          loans: s.mutations, purchases: s.mutations, repayments: s.mutations } });
    }
    if (path.endsWith('meter/mobile-onboarding/')) return reply(route, { meters: s.meters, requests: [], sandbox_self_enrollment: true });
    if (path.endsWith('meter/sandbox-meter-enrollment/')) {
      assert.deepEqual(Object.keys(input), ['meter_no']);
      const linked = { ...meter(24), meter_number: input.meter_no };
      s.meters = [linked]; s.assessment = 'READY';
      return reply(route, { success: true, status: 'SELF_DECLARED', meter: linked,
        message: 'Meter linked for prototype testing. Ownership and live readings are not verified with the electricity provider.' }, 201);
    }
    if (/meter\/mobile-meters\/\d+\/$/.test(path)) {
      const selected = s.meters.find(m => m.id === Number(path.split('/').at(-2)));
      if (!selected) return reply(route, { detail: 'Not found.' }, 404);
      return reply(route, { meter: selected, unit: 'kWh', quantum_kwh: '0.01', available_kwh: s.balance,
        pending_kwh: '0.00', confirmed_kwh: '0.00', last_meter_contact: null,
        delivery_environment: 'UNAVAILABLE', contact_source: 'UNAVAILABLE', contact_status: 'UNAVAILABLE',
        meter_reported_remaining_wh: null, reported_relay_state: null });
    }
    if (path.endsWith('meter/mobile-consumption/')) {
      const selected = s.meters.find(m => m.id === Number(url.searchParams.get('meter_id')));
      return reply(route, { meter: selected, meter_no: selected?.meter_number, daily_usage: [], simulator_telemetry: [], consumer_attribution_available: false });
    }
    if (path.endsWith('loans/mobile-overview/')) return reply(route, { loans: [] });
    if (path.endsWith('sandbox/assessment/')) return reply(route, { assessment: assessment(), policy });
    if (path.endsWith('sandbox/quotes/')) {
      assert.deepEqual(Object.keys(input).sort(), ['amount','meter_id','purpose']);
      const amount = BigInt(input.amount), interest = input.purpose === 'LOAN' ? amount * 5n / 100n : 0n;
      const terms = { policy, owner_id: user.id, meter_id: input.meter_id, purpose: input.purpose, amount: String(amount),
        energy_kwh: `${amount / 1000n}.00`, billed: String(amount), residual: '0', interest: String(interest), fee: '0',
        total_due: input.purpose === 'LOAN' ? String(amount + interest) : '0', assessment: assessment() };
      const q = { id: randomUUID(), terms_hash: createHash('sha256').update(JSON.stringify(terms)).digest('hex'), terms,
        expires_at: new Date(Date.now() + (s.expiredQuote ? -1000 : 900000)).toISOString() };
      quotes.set(q.id, q);
      if (s.delayQuote) await new Promise(resolve => setTimeout(resolve, s.delayQuote));
      return reply(route, q, 201);
    }
    if (path.endsWith('sandbox/loans/')) {
      if (request.method() === 'GET') return reply(route, { loans: s.loans });
      assert.equal(input.accept_test_terms, true); assert.equal(typeof input.client_request_id, 'string');
      const q = quotes.get(input.quote_id); assert.equal(input.terms_hash, q.terms_hash);
      assert.equal(Object.keys(input).includes('score'), false);
      const approved = s.score >= 75;
      const loan = { id: randomUUID(), client_request_id: input.client_request_id, meter_id: q.terms.meter_id,
        status: approved ? 'DISBURSED' : 'REJECTED', reason: approved ? 'Approved under the test policy.' : 'Demo score is below the test threshold.',
        currency: 'UGX', environment: 'UGX_DEMO', principal: q.terms.amount, total_due: approved ? q.terms.total_due : '0',
        outstanding: approved ? q.terms.total_due : '0', due_at: new Date(Date.now()+604800000).toISOString(), closed_at: null,
        allocation_id: approved ? 1 : null, allocated_kwh: approved ? q.terms.energy_kwh : null, terms: q.terms, assessment: assessment() };
      s.loans.unshift(loan); if (approved) s.balance = q.terms.energy_kwh;
      return reply(route, { loan }, 201);
    }
    if (path.endsWith('sandbox/payments/')) {
      if (request.method() === 'GET') return reply(route, { payments: s.payments, pending: s.payments.filter(p => p.status === 'PENDING') });
      assert.equal(input.accept_test_terms, true); assert.equal('pin' in input, false); assert.equal('msisdn' in input, false);
      const q = input.purpose === 'PURCHASE' ? quotes.get(input.quote_id) : null;
      if (q) assert.equal(input.terms_hash, q.terms_hash);
      const loan = s.loans.find(l => l.id === input.loan_id);
      const p = { reference: randomUUID(), client_request_id: input.client_request_id, purpose: input.purpose, status: 'PENDING',
        provider: 'LOCAL_DEMO', currency: 'UGX', environment: 'UGX_DEMO', amount: q?.terms.amount ?? input.amount,
        meter_id: q?.terms.meter_id ?? loan.meter_id, loan_id: loan?.id ?? null, initiated_at: new Date().toISOString(),
        demo_eligible_at: new Date(Date.now()+5000).toISOString(), server_time: new Date().toISOString(), settled_at: null,
        billed: null, residual: null, applied: null, excess: null, allocated_kwh: null, submission_state: 'DEMO_PENDING',
        reconciliation_error: '', next_check_at: new Date(Date.now()+5000).toISOString() };
      s.payments.unshift(p);
      if (s.loseInitiation) return route.abort();
      return reply(route, { payment: p }, 202);
    }
    if (/sandbox\/payments\/[0-9a-f-]+\/$/.test(path)) {
      const p = s.payments.find(x => x.reference === path.split('/').at(-2));
      assert.ok(p);
      if (request.method() === 'POST' && s.settle && Date.now() >= Date.parse(p.demo_eligible_at) && p.status === 'PENDING') {
        p.status = 'SETTLED'; p.settled_at = new Date().toISOString(); p.submission_state = 'DEMO_SETTLED';
        if (p.purpose === 'PURCHASE') { p.billed = p.amount; p.residual = '0'; p.allocated_kwh = `${BigInt(p.amount)/1000n}.00`; s.balance = p.allocated_kwh; }
        else { const loan = s.loans.find(l => l.id === p.loan_id); p.applied = p.amount; p.excess = '0'; loan.outstanding = String(BigInt(loan.outstanding)-BigInt(p.amount));
          if (loan.outstanding === '0') { loan.status = 'COMPLETED'; loan.closed_at = p.settled_at; } }
      }
      return reply(route, { payment: { ...p, server_time: new Date().toISOString() } });
    }
    if (/sandbox\/payment-recovery\//.test(path)) return reply(route, { payment: s.payments.find(p => p.client_request_id === path.split('/').at(-2)) ?? null });
    if (/sandbox\/loan-recovery\//.test(path)) return reply(route, { loan: s.loans.find(p => p.client_request_id === path.split('/').at(-2)) ?? null });
    if (path.endsWith('auth/mobile-account-details/')) {
      if (s.failedProfile) return route.abort();
      return reply(route, { details_available: true, values: { account_number: 'TEST-9001', address: input.address ?? null,
        energy_preference: null, payment_method: null }, choices: { energy_preference: [], payment_method: [] } });
    }
    if (path.endsWith('meter/mobile-notifications/')) return reply(route, { notifications: [], unread_count: 0, pagination: { has_more: false, next_before_id: null } });
    if (path.endsWith('transactions/mobile-receipts/')) return reply(route, { receipts: [], pagination: { has_more: false, next_before_id: null } });
    if (path.endsWith('transactions/mobile-history/')) return reply(route, { transactions: [], pagination: { has_more: false, next_before_id: null } });
    if (/mobile-deliveries/.test(path)) { const selected = s.meters.find(m => m.id === Number(url.searchParams.get('meter_id')));
      return reply(route, { meter: selected, meter_no: selected.meter_number, deliveries: [], pagination: { has_more: false, next_before_id: null } }); }
    throw new Error(`Unhandled mocked API: ${request.method()} ${path}`);
  });
  const tab = name => page.getByRole('navigation', { name: 'Main navigation' }).getByRole('button', { name, exact: true }).click();
  const login = async () => {
    await page.goto(base); await page.getByRole('button', { name: /Already have an account/ }).click();
    await page.getByLabel('Email address').fill(user.email); await page.locator('input[autocomplete="current-password"]').fill('isolated-test-only');
    await page.locator('form button[type="submit"]').click(); await page.getByRole('heading', { name: 'Hello, UI', exact: true }).waitFor();
    await page.getByRole('region', { name: 'Credit overview' }).waitFor();
    await page.getByRole('button', { name: 'Refresh', exact: true }).waitFor();
    await page.waitForFunction(() => !document.body.textContent.includes('Loading your account…'));
  };
  const layout = async label => {
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `${label}: no horizontal overflow`);
    if (shots) await page.screenshot({ path: `${shots}/${name}-${label}.png`, fullPage: true });
  };
  try {
    await login(); await run({ page, s, calls, tab, login, layout });
    assert.deepEqual(errors, [], `${name}: no browser runtime errors`);
    assert.equal(calls.some(c => /share|ussd|wallet|transfer|mobile-profile/.test(c.path)), false);
    console.log(`PASS ${name}`); checks++;
  } finally { await context.close(); }
}
try {
  await scenario('home-and-navigation', async ({ page, tab, layout }) => {
    await page.locator('.credit-score').filter({ hasText: '85/100' }).waitFor(); await page.getByText('UGX 37,500', { exact: true }).first().waitFor();
    await page.getByText('Hardware contact unavailable', { exact: true }).waitFor();
    for (const width of [320,390,768]) { await page.setViewportSize({ width, height: 844 });
      for (const name of ['Home','Meters','Loans','Buy Units','Account']) { await tab(name); await layout(`${name}-${width}`); } }
    await tab('Buy Units'); await page.setViewportSize({ width: 390, height: 380 }); await page.getByLabel('Amount (UGX)', { exact: true }).focus(); await layout('keyboard-sized-viewport');
    await tab('Account'); await page.getByRole('button', { name: /Personal details/ }).click(); await page.getByLabel('Address', { exact: true }).fill('Synthetic address');
    await page.getByRole('button', { name: 'Save details', exact: true }).click(); await page.getByText('Account details saved.').waitFor();
    await page.getByRole('button', { name: 'Log out', exact: true }).click(); await page.getByRole('heading', { name: 'Your power. Your possibilities.' }).waitFor();
    assert.equal(await page.getByText(user.email, { exact: true }).count(),0);
  });
  await scenario('missing-meter-and-pending-assessment', async ({ page, s, tab }) => {
    await page.getByText('Assessment pending. Add your meter.').waitFor();
    assert.equal(await page.getByText('85', { exact: true }).count(),0);
    await page.getByRole('button', { name: /^Apply for Loan/ }).first().click();
    assert.equal(await page.getByRole('button', { name: 'Review terms →', exact: true }).count(),0);
    await tab('Meters'); await page.getByLabel('Meter number', { exact: true }).fill('000245');
    await page.getByRole('button', { name: 'Add your meter', exact: true }).click();
    await page.getByRole('button', { name: /Prototype meter|000245/ }).first().waitFor(); await tab('Home'); await page.locator('.credit-score').filter({ hasText: '85/100' }).waitFor();
    assert.equal(s.meters[0].meter_number,'000245');
  }, { meters: [], assessment: 'PENDING' });
  await scenario('loan-and-partial-full-repayment', async ({ page, s, tab, calls }) => {
    await page.getByRole('button', { name: /^Apply for Loan/ }).first().click();
    await page.getByLabel('Amount (UGX)', { exact: true }).fill('1000'); await page.getByRole('button', { name: 'Review terms →', exact: true }).click();
    await page.getByRole('heading', { name: 'Review loan terms', exact: true }).waitFor();
    assert.equal(await page.getByRole('button', { name: 'Continue →', exact: true }).isDisabled(), true);
    await page.getByLabel('I accept these test terms.').check(); await page.getByRole('button', { name: 'Continue →', exact: true }).click();
    await page.getByRole('heading', { name: 'Confirm your application' }).waitFor(); await page.getByRole('button', { name: 'Submit application', exact: true }).dblclick();
    await page.getByRole('button', { name: 'Pay Loan →', exact: true }).waitFor(); assert.equal(calls.filter(c => c.path.endsWith('sandbox/loans/') && c.method === 'POST').length,1);
    s.settle = true;
    for (const amount of ['300','750']) {
      await page.getByRole('button', { name: 'Pay Loan →', exact: true }).click(); await page.getByLabel('Repayment amount (UGX)').fill(amount);
      await page.getByRole('button', { name: 'Review repayment →', exact: true }).click();
      await page.getByText('Demo payment: no real money is deducted and no phone PIN is required.').waitFor();
      await page.getByLabel('I accept these test repayment terms.').check(); await page.getByRole('button', { name: 'Confirm repayment', exact: true }).click();
      await page.getByText('Demo payment successful. No real money was deducted.').first().waitFor();
      await page.waitForFunction(expected => document.querySelector('.loan-balance')?.textContent.trim() === expected, amount === '300' ? 'UGX 750' : 'UGX 0');
    }
    assert.equal(s.loans[0].outstanding, '0'); assert.equal(s.loans[0].status, 'COMPLETED');
    assert.equal(s.balance,'1.00'); await tab('Home'); await page.getByRole('heading', { name: 'No active loan' }).waitFor();
  });
  await scenario('rejected-loan', async ({ page }) => {
    await page.getByRole('button', { name: /^Apply for Loan/ }).first().click();
    await page.getByRole('button', { name: 'Review terms →', exact: true }).click(); await page.getByLabel('I accept these test terms.').check();
    await page.getByRole('button', { name: 'Continue →', exact: true }).click(); await page.getByRole('button', { name: 'Submit application', exact: true }).click();
    await page.getByText('Not approved', { exact: true }).waitFor(); await page.getByText('Demo score is below the test threshold.').first().waitFor();
    assert.equal(await page.getByRole('button', { name: 'Pay Loan →' }).count(),0);
  }, { score: 41 });
  await scenario('purchase-does-not-succeed-on-countdown', async ({ page, s, tab, calls }) => {
    await tab('Buy Units'); await page.getByLabel('Amount (UGX)', { exact: true }).fill('5000'); await page.getByRole('button', { name: 'Review terms →', exact: true }).click();
    await page.getByLabel('I accept these test terms.').check(); await page.getByRole('button', { name: 'Confirm purchase', exact: true }).dblclick();
    await page.getByText('Processing payment', { exact: true }).waitFor(); await tab('Account'); await tab('Buy Units');
    await page.getByText('Waiting for server confirmation', { exact: true }).waitFor();
    assert.equal(await page.getByText('Demo payment successful. No real money was deducted.').count(),0);
    assert.equal(s.payments[0].status,'PENDING'); assert.equal(calls.filter(c => c.path.endsWith('sandbox/payments/') && c.method === 'POST').length,1);
    const check = page.getByRole('button', { name: 'Check payment status', exact: true });
    await check.evaluate(element => element.scrollIntoView({ block: 'center' }));
    await check.click(); // Still pending: a status check itself is not success.
    assert.equal(s.payments[0].status,'PENDING'); s.settle = true;
    await page.getByText('Demo payment successful. No real money was deducted.').first().waitFor();
    await page.getByText('Receipt details', { exact: true }).click(); await page.getByText('Reference: '+s.payments[0].reference).waitFor();
    await tab('Home'); await page.getByText('5.00 kWh', { exact: true }).first().waitFor();
  });
  await scenario('lost-response-and-restart-recovery', async ({ page, s, tab, login, calls }) => {
    s.loseInitiation = true;
    await tab('Buy Units'); await page.getByRole('button', { name: 'Review terms →', exact: true }).click(); await page.getByLabel('I accept these test terms.').check();
    await page.getByRole('button', { name: 'Confirm purchase', exact: true }).click(); await page.getByRole('alert').waitFor();
    assert.equal(s.payments.length,1); const id = s.payments[0].client_request_id;
    await page.reload(); await login(); await tab('Buy Units'); await page.getByText('Processing payment', { exact: true }).waitFor();
    assert.equal(s.payments[0].client_request_id,id); assert.equal(calls.filter(c => c.path.endsWith('sandbox/payments/') && c.method === 'POST').length,1);
    s.settle = true; await page.getByText('Demo payment successful. No real money was deducted.').waitFor();
  });
  await scenario('quote-invalidated-by-meter-and-amount', async ({ page, s, tab, calls }) => {
    await tab('Meters'); await page.getByRole('button', { name: /Meter 7.*000007/ }).click(); await tab('Buy Units');
    s.delayQuote=1000; await page.getByRole('button', { name: 'Review terms →', exact: true }).click();
    await page.getByLabel('Amount (UGX)', { exact: true }).fill('2000'); await page.waitForTimeout(1200);
    assert.equal(await page.getByRole('heading', { name: 'Review your purchase', exact: true }).count(),0);
    s.delayQuote=0; await page.getByRole('button', { name: 'Review terms →', exact: true }).click(); await page.getByRole('heading', { name: 'Review your purchase' }).waitFor();
    await tab('Meters'); await page.getByRole('button', { name: /Meter 8.*000008/ }).click(); await tab('Buy Units');
    assert.equal(await page.getByRole('heading', { name: 'Review your purchase', exact: true }).count(),0);
    assert.equal(calls.some(c=>c.path.endsWith('sandbox/payments/')&&c.method==='POST'),false);
  }, { meters: [meter(7),meter(8)] });
  await scenario('expired-quote-and-disabled-capabilities', async ({ page, s, tab, calls }) => {
    await tab('Buy Units'); s.expiredQuote=true; await page.getByRole('button', { name: 'Review terms →', exact: true }).click();
    await page.getByText('This quote expired. Get a fresh quote.').waitFor(); assert.equal(await page.getByRole('button', { name: 'Confirm purchase' }).isDisabled(),true);
    await page.getByRole('button', { name: 'Edit amount' }).click(); s.mutations=false;
    await page.getByRole('button', { name: 'Refresh account', exact: true }).click(); await page.getByText('Purchases are currently unavailable. Refresh to check again.').waitFor();
    assert.equal(await page.getByRole('button', { name: 'Review terms →', exact: true }).isDisabled(),true);
    assert.equal(calls.some(c=>c.path.endsWith('sandbox/payments/')&&c.method==='POST'),false);
  });
  await scenario('pending-survives-capability-network-error', async ({ page, s, tab, calls }) => {
    await tab('Buy Units'); await page.getByRole('button', { name: 'Review terms →', exact: true }).click();
    await page.getByLabel('I accept these test terms.').check(); await page.getByRole('button', { name: 'Confirm purchase', exact: true }).click();
    await page.getByText('Processing payment', { exact: true }).waitFor();
    const reference = s.payments[0].reference; s.capabilitiesFail = true;
    await page.getByRole('button', { name: 'Refresh account', exact: true }).click();
    await page.getByText('Processing payment', { exact: true }).waitFor(); await tab('Home'); await tab('Buy Units');
    await page.getByText('Waiting for server confirmation', { exact: true }).waitFor();
    assert.equal(s.payments[0].reference, reference); assert.equal(s.payments.length,1);
    assert.equal(calls.filter(c => c.path.endsWith('sandbox/payments/') && c.method === 'POST').length,1);
    s.capabilitiesFail = false; s.settle = true;
    await page.getByRole('button', { name: 'Refresh account', exact: true }).click();
    await page.getByText('Demo payment successful. No real money was deducted.').first().waitFor();
  });
  await scenario('old-eur-history-stays-separate', async ({ page, s, tab }) => {
    const id = randomUUID();
    s.loans.push({ id, client_request_id: randomUUID(), meter_id: 7, status: 'DISBURSED', reason: 'Earlier EUR test obligation.',
      currency: 'EUR', environment: 'MTN_SANDBOX', principal: '2.00', total_due: '2.10', outstanding: '2.10',
      due_at: new Date().toISOString(), closed_at: null, allocation_id: null, allocated_kwh: null,
      terms: { policy: { ...policy, id: 'TEST-EUR-v1', currency: 'EUR', environment: 'MTN_SANDBOX' } } });
    await page.getByRole('button', { name: 'Refresh account', exact: true }).click(); await tab('Loans');
    await page.getByText('Earlier test-currency loans', { exact: true }).click();
    await page.getByText('EUR TEST 2.10', { exact: true }).first().waitFor();
    assert.equal(await page.getByRole('button', { name: 'Pay Loan →', exact: true }).count(),0);
    await tab('Home'); await page.getByRole('heading', { name: 'No active loan', exact: true }).waitFor();
    await page.getByText('UGX 37,500', { exact: true }).first().waitFor();
  });
  await scenario('native-back-through-review-steps', async ({ page, tab, calls }) => {
    const back = () => page.evaluate(() => { for (const callback of globalThis.__testNativeEvents.get('backButton') ?? []) callback({ canGoBack: false }); });
    await page.getByRole('button', { name: /^Apply for Loan/ }).first().click();
    await page.getByRole('button', { name: 'Review terms →', exact: true }).click(); await page.getByLabel('I accept these test terms.').check();
    await page.getByRole('button', { name: 'Continue →', exact: true }).click(); await page.getByRole('heading', { name: 'Confirm your application' }).waitFor();
    await back(); await page.getByRole('heading', { name: 'Review loan terms' }).waitFor();
    await back(); await page.getByLabel('Amount (UGX)', { exact: true }).waitFor();
    await back(); await page.getByRole('button', { name: 'My Loans', exact: true }).waitFor();
    assert.equal(calls.some(c=>c.method==='POST' && (c.path.endsWith('sandbox/loans/') || c.path.endsWith('sandbox/payments/'))), false);
    await back(); await page.getByRole('heading', { name: 'Hello, UI' }).waitFor();
    await back(); assert.equal(await page.evaluate(() => globalThis.__testMinimized), 1);
    await tab('Account'); await page.getByRole('button', { name: /Personal details/ }).click(); await page.getByLabel('Address', { exact: true }).waitFor();
    await back(); assert.equal(await page.getByLabel('Address', { exact: true }).count(),0);
  }, { nativeBack: true });
  console.log(`${checks} redesigned finance browser scenarios passed with entirely mocked APIs.`);
} finally { await browser.close(); }
