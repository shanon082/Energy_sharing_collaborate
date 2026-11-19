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

test('AC lab application means durable device credit, never load switching', () => {
  const applied = parseEnergyTokens({ tokens: [{ ...token, state: 'APPLIED', application_environment: 'AC_LAB' }] })[0];
  assert.match(tokenLoadingLabel(applied), /Credit saved on AC lab device/);
  assert.match(tokenLoadingLabel(applied), /relay output disabled/);
  assert.doesNotMatch(tokenLoadingLabel(applied), /Units loaded/);
});

test('EUR purchase energy requires an explicit SANDBOX V2 device contract, not payment success alone', () => {
  const sandbox = {...token, environment: 'SANDBOX', redemption_enabled: true, redemption_protocol: 'GPAWA_PZEM_V2'};
  const issued = parseEnergyTokens({tokens: [sandbox]})[0];
  assert.match(tokenLoadingLabel(issued), /Awaiting/);
  assert.match(tokenLoadingLabel({...issued, state: 'DELIVERY_PENDING'}), /Awaiting/);
  assert.match(tokenLoadingLabel({...issued, state: 'APPLIED', application_environment: 'AC_LAB'}), /Credit saved/);
  assert.throws(() => parseEnergyTokens({tokens: [{...sandbox, redemption_protocol: 'GPAWA_PZEM_V1'}]}));
  assert.throws(() => parseEnergyTokens({tokens: [{...sandbox, environment: 'UGX_DEMO'}]}));
  assert.throws(() => parseEnergyTokens({tokens: [{...sandbox, environment: 'CORE', redemption_protocol: 'UNSUPPORTED'}]}));
});
