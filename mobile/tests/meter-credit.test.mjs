import test from 'node:test';
import assert from 'node:assert/strict';
import { assessmentContextKey, loanProgressionReason } from '../../frontend/src/lib/meter-credit.ts';
import { parseStoredDemoAssessment } from '../../frontend/src/lib/sandbox.ts';

const assessment = { owner_id: 1, meter_id: 7, assessment_id: 1, score: 85, profile_score: 85, eligible: true,
  reason: 'Stored evidence', maximum: '37500', factors: { payment_history: 92 }, purchase_points: 0, starter: false,
  assessment_status: 'READY', scoring_policy_version: 'DEMO-METER-SCORE-v2', assessed_at: '2026-10-15T00:00:00Z',
  environment: 'UGX_DEMO', currency: 'UGX', provider: 'SIMULATED_ACCOUNT_V1', input_source: 'SIMULATED_ACCOUNT_INFORMATION' };
test('each assessment response must match the authenticated owner and selected meter', () => {
  assert.equal(parseStoredDemoAssessment(assessment, { owner: 1, meterId: 7 }).score, 85);
  assert.throws(() => parseStoredDemoAssessment(assessment, { owner: 2, meterId: 7 }));
  assert.throws(() => parseStoredDemoAssessment(assessment, { owner: 1, meterId: 8 }));
});
test('79 percent is explained; 80 and 85 can progress only when eligible', () => {
  assert.equal(loanProgressionReason({ ...assessment, score: 79, eligible: false }, 7, '1000'),
    'This meter’s credit score is 79%. A minimum of 80% is required to apply for a loan.');
  for (const score of [80,85]) assert.equal(loanProgressionReason({ ...assessment, score }, 7, '1000'), null);
});
test('qualifying score never bypasses debt or exact loan limits', () => {
  assert.equal(loanProgressionReason({ ...assessment, eligible: false, reason: 'Repay existing debt.' }, 7, '1000'), 'Repay existing debt.');
  assert.match(loanProgressionReason(assessment, 7, '37500.01'), /exceeds/);
  assert.equal(loanProgressionReason(assessment, 7, '37500.00'), null);
});
test('unselected, pending, unavailable and wrong-meter evidence explain why review is blocked', () => {
  assert.match(loanProgressionReason(assessment, null, '1000'), /Select your meter/);
  assert.match(loanProgressionReason(assessment, 8, '1000'), /pending/);
  assert.equal(loanProgressionReason({ ...assessment, score: null, assessment_status: 'UNAVAILABLE', reason: 'Provider unavailable.' }, 7, '1000'), 'Provider unavailable.');
  assert.match(loanProgressionReason(null, 7, '1000'), /pending/);
});
test('quotes survive read timestamps but material meter/score/policy/tariff changes invalidate consent', () => {
  const cfg = { id: 'DEMO-UGX-v2' }, pricing = { available: true, message: '', revision: 'tariff1' };
  const key = assessmentContextKey(assessment,cfg,pricing);
  assert.equal(assessmentContextKey({ ...assessment, calculated_at: 'new read' },cfg,pricing),key);
  for (const update of [{ meter_id: 8 }, { score: 80 }, { evidence_updated_at: 'new evidence' }, { eligible: false }])
    assert.notEqual(assessmentContextKey({ ...assessment,...update },cfg,pricing),key);
  assert.notEqual(assessmentContextKey(assessment,{ ...cfg,id: 'new' },pricing),key);
  assert.notEqual(assessmentContextKey(assessment,cfg,{ ...pricing,revision: 'tariff2' }),key);
});
