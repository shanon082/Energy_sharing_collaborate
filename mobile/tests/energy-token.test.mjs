import test from 'node:test';
import assert from 'node:assert/strict';
import { parseEnergyTokens, tokenLoadingLabel } from '../../frontend/src/lib/energy-token.ts';
import { normalizePrototypeMeterNumber } from '../../frontend/src/lib/meter-enrollment.ts';
import { parseMeters } from '../src/api/contracts.ts';

const token = { id: 'test-token-id', allocation_id: 7, token: '000123456789012', meter_number: '00012345678',
  energy_wh: '1250', energy_kwh: '1.25', environment: 'UGX_DEMO', source: 'PURCHASE', source_reference: 'test-purchase',
  state: 'ISSUED', application_environment: 'UNCONFIRMED', created_at: '2026-10-16T10:00:00Z' };

test('token remains exact15-digit text and binds the selected allocation', () => {
  assert.deepEqual(parseEnergyTokens({ tokens: [token] }, 7), [token]);
  assert.equal(parseEnergyTokens({ tokens: [token] })[0].token, '000123456789012');
  assert.throws(() => parseEnergyTokens({ tokens: [token] }, 8));
  for (const value of [123456789012345, '0'.repeat(14), '0'.repeat(16), '١'.repeat(15), '12345 678901234']) {
    assert.throws(() => parseEnergyTokens({ tokens: [{ ...token, token: value }] }));
  }
});
test('funding success and pending delivery cannot imply loaded energy', () => {
  assert.match(tokenLoadingLabel(token), /Awaiting/);
  assert.match(tokenLoadingLabel({ ...token, state: 'DELIVERY_PENDING' }), /Awaiting/);
  assert.throws(() => parseEnergyTokens({ tokens: [{ ...token, state: 'APPLIED' }] }));
  const applied = parseEnergyTokens({ tokens: [{ ...token, state: 'APPLIED', application_environment: 'SOFTWARE_BENCH' }] })[0];
  assert.match(tokenLoadingLabel(applied), /software bench/);
  assert.throws(() => parseEnergyTokens({ tokens: [{ ...token, environment: 'PRODUCTION' }] }));
});
test('new enrollment is11 digits but historical meter selection does not reinterpret identifiers', () => {
  assert.equal(normalizePrototypeMeterNumber(' 00012345678 '), '00012345678');
  assert.throws(() => normalizePrototypeMeterNumber('OLD-A/001'));
  const legacy = { id: 3, meter_number: 'OLD-A/001', label: 'Historical', architecture: 'AMI', status: 'ACTIVE' };
  assert.deepEqual(parseMeters({ success: true, data: { has_meter: true, meters: [legacy] } }), [legacy]);
});
