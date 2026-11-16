import test from 'node:test';
import assert from 'node:assert/strict';
import { consumerScreen, defaultConsumerMeter, parseConsumerSummary, ConsumerReadScope } from '../src/lib/consumer-parity.ts';
import { formatMoney, exactDifference, formatEnergy } from '../src/lib/sandbox-presentation.ts';
import { parseStoredDemoAssessment } from '../src/lib/sandbox.ts';
import { loanProgressionReason } from '../src/lib/meter-credit.ts';

const summary = { owner_id: 7, scope: 'OWNER', meter_id: null, environment: 'UGX_DEMO', currency: 'UGX', loan_count: 104,
  active_loan_count: 1, principal: '5103', total_due: '5353', applied_repayments: '2603', outstanding: '2750.000000' };
const owned = [{ id: 11, meter_number: '00012345678' }, { id: 12, meter_number: '0001234567890' }];
const assessment = { owner_id: 7, meter_id: 11, score: 62, profile_score: 62, purchase_points: 0, maximum: '10000',
  assessment_status: 'READY', eligible: false, reason: 'Score below the required threshold.', starter: false,
  provider: 'SIMULATED_ACCOUNT_V1', input_source: 'SIMULATED_ACCOUNT_INFORMATION', currency: 'UGX', environment: 'UGX_DEMO',
  scoring_policy_version: 'ISOLATED-FIXTURE', assessed_at: '2026-11-16T10:00:00Z', factors: { payment_history: 62 } };

test('full-ledger summary and individual debt use exact server amounts', () => {
  const value = parseConsumerSummary(summary, 7, 'UGX_DEMO');
  assert.equal(value.loan_count, 104);
  assert.equal(formatMoney(value.outstanding, 'UGX'), 'UGX 2,750');
  assert.equal(formatMoney(exactDifference('5250', '2500'), 'UGX'), 'UGX 2,750');
  assert.equal(formatMoney('2750.125000', 'UGX'), 'UGX 2,750.125');
  assert.equal(formatEnergy('8.95'), '8.95 kWh');
});
test('unavailable, another owner and a different ledger cannot become a zero summary', () => {
  for (const raw of [null, {}, { ...summary, outstanding: null }, { ...summary, outstanding: 0 },
    { ...summary, currency: 'EUR' }, { ...summary, environment: 'MTN_SANDBOX' }, { ...summary, owner_id: 8 },
    { ...summary, scope: 'METER', meter_id: 11 }, { ...summary, loan_count: -1 }, { ...summary, active_loan_count: 105 }]) {
    assert.throws(() => parseConsumerSummary(raw, 7, 'UGX_DEMO'));
  }
  const empty = parseConsumerSummary({ ...summary, loan_count: 0, active_loan_count: 0, principal: '0', total_due: '0', applied_repayments: '0', outstanding: '0' }, 7, 'UGX_DEMO');
  assert.equal(formatMoney(empty.outstanding, 'UGX'), 'UGX 0');
  assert.equal(formatMoney(undefined, 'UGX'), 'Unavailable');
});
test('one meter defaults, multiple meters require selection, historical identifiers remain strings', () => {
  assert.equal(defaultConsumerMeter([owned[0]], null), owned[0]);
  assert.equal(defaultConsumerMeter(owned, null), null);
  assert.equal(defaultConsumerMeter(owned, '12').meter_number, '0001234567890');
  assert.equal(defaultConsumerMeter([owned[0]], '12'), null);
  assert.equal(defaultConsumerMeter([], '11'), null);
});
test('late read tickets cannot restore a previous selection or logged-out account', () => {
  const scope = new ConsumerReadScope(), first = scope.begin(), second = scope.begin();
  assert.equal(scope.current(first), false); assert.equal(scope.current(second), true);
  scope.invalidate(); assert.equal(scope.current(second), false);
});
test('stored selected-meter assessment explains the 80 percent gate without inventing a score', () => {
  const parsed = parseStoredDemoAssessment(assessment, { owner: 7, meterId: 11 });
  assert.match(loanProgressionReason(parsed, 11, '5000'), /minimum of 80%/);
  assert.throws(() => parseStoredDemoAssessment(assessment, { owner: 7, meterId: 12 }));
  assert.throws(() => parseStoredDemoAssessment(assessment, { owner: 8, meterId: 11 }));
  assert.match(loanProgressionReason(null, 11, '5000'), /pending/);
  assert.match(loanProgressionReason(null, null, '5000'), /Select your meter/);
});
test('focused navigation keeps apply under loans and legacy wallet links read-only', () => {
  assert.equal(consumerScreen('/dashboard'), 'home');
  assert.equal(consumerScreen('/dashboard/loans', 'apply'), 'apply');
  assert.equal(consumerScreen('/dashboard/my-meters'), 'meters');
  assert.equal(consumerScreen('/dashboard/wallet'), 'home');
  assert.equal(consumerScreen('/dashboard/share'), null);
  assert.equal(consumerScreen('/admin/dashboard'), null);
});
