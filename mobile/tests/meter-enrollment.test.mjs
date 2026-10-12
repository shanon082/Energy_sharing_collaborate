import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizePrototypeMeterNumber, parsePrototypeEnrollment, PROTOTYPE_OWNERSHIP_NOTICE } from '../../frontend/src/lib/meter-enrollment.ts';
import { parseMeters } from '../src/api/contracts.ts';
import { enrollmentLabel } from '../src/api/enrollment.ts';

const meter = { id: 7, meter_number: '000123', label: 'Prototype meter', architecture: 'AMI', status: 'ACTIVE',
  sandbox_inventory: true, ownership_provenance: 'SELF_DECLARED', enrolled_at: '2026-10-13T00:00:00Z', hardware_connection: 'PENDING' };
const response = { success: true, status: 'SELF_DECLARED', meter, message: PROTOTYPE_OWNERSHIP_NOTICE };

test('prototype meter numbers preserve leading zeros and existing nonnumeric formats', () => {
  for (const number of ['000123', '0', '1', 'AMI-A/0009', 'A'.repeat(100)]) {
    assert.equal(normalizePrototypeMeterNumber(` ${number} `), number);
  }
  for (const number of [123, null, true, '', ' ', 'A'.repeat(101), 'X\0Y', 'X\x7fY']) assert.throws(() => normalizePrototypeMeterNumber(number));
});

test('only explicit linked sandbox identity can be automatically selected', () => {
  assert.deepEqual(parsePrototypeEnrollment(response, ' 000123 '), { meter, message: PROTOTYPE_OWNERSHIP_NOTICE });
  for (const payload of [null, { ...response, status: 'PENDING' }, { ...response, status: 'REJECTED' },
    { ...response, meter: { ...meter, id: -1 } }, { ...response, meter: { ...meter, meter_number: '123' } },
    { ...response, meter: { ...meter, sandbox_inventory: false } },
    { ...response, meter: { ...meter, ownership_provenance: 'UTILITY_VERIFIED' } },
    { ...response, meter: { ...meter, hardware_connection: 'CONNECTED' } }]) assert.throws(() => parsePrototypeEnrollment(payload, '000123'));
});

test('meter list preserves ownership assumption and pending hardware without fabricating evidence', () => {
  const parsed = parseMeters({ success: true, data: { has_meter: true, meters: [meter] } });
  assert.deepEqual(parsed, [meter]);
  assert.equal(enrollmentLabel('SELF_DECLARED'), 'Linked for prototype testing — self-declared');
  assert.equal(enrollmentLabel('REJECTED'), 'Request declined');
  assert.notEqual(enrollmentLabel('SELF_DECLARED'), 'Assigned');
});
