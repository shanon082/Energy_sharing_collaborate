import test from 'node:test';
import assert from 'node:assert/strict';
import { parseMeters, parseMeterDashboard, selectedMeterStillAssigned } from '../src/api/contracts.ts';
import { parseAssessment, parseAccountDetails } from '../src/api/profile-contracts.ts';
import { LatestRead } from '../src/api/read-scope.ts';

const meter = { id: 7, meter_number: 'TEST-7', label: 'Home', architecture: 'AMI', status: 'ACTIVE' };
const dashboard = { meter, unit: 'kWh', quantum_kwh: '0.01', available_kwh: '1.50',
  pending_kwh: '0.31', confirmed_kwh: '0.20', delivery_environment: 'SIMULATOR',
  contact_source: 'SIMULATOR', last_meter_contact: null };
const list = (meters) => ({ success: true, data: { has_meter: Boolean(meters.length), meters } });

test('meter identity stays explicit and a replacement is never silently selected', () => {
  assert.deepEqual(parseMeters(list([])), []);
  assert.deepEqual(parseMeters(list([meter])), [meter]);
  assert.equal(selectedMeterStillAssigned(meter, [meter]), true);
  assert.equal(selectedMeterStillAssigned(meter, [{ ...meter, id: 8 }]), false);
  assert.equal(selectedMeterStillAssigned(meter, []), false);
  assert.throws(() => parseMeters(list([{ ...meter, id: undefined }])));
  assert.throws(() => parseMeters(list([meter, meter])));
});

test('dashboard preserves exact energy and refuses another meter response', () => {
  assert.equal(parseMeterDashboard(dashboard, meter).available_kwh, '1.50');
  assert.equal(parseMeterDashboard(dashboard, meter).last_meter_contact, null);
  assert.throws(() => parseMeterDashboard({ ...dashboard, meter: { ...meter, id: 8 } }, meter));
  assert.throws(() => parseMeterDashboard({ ...dashboard, available_kwh: 1.5 }, meter));
  assert.throws(() => parseMeterDashboard({ ...dashboard, available_kwh: undefined }, meter));
  assert.throws(() => parseMeterDashboard({ ...dashboard, quantum_kwh: '0.1' }, meter));
});

test('missing details remain unavailable and profile choices come from Django', () => {
  const options = { energy_preference: [{ value: 'HYDRO', label: 'Hydro' }], payment_method: [] };
  assert.equal(parseAccountDetails({ details_available: false, values: null, choices: options }).values, null);
  const values = { account_number: null, address: null, energy_preference: 'HYDRO', payment_method: null };
  assert.deepEqual(parseAccountDetails({ details_available: true, values, choices: options }).values, values);
  assert.throws(() => parseAccountDetails({ details_available: true, values: {}, choices: options }));
  assert.throws(() => parseAccountDetails({ details_available: false, values: {}, choices: options }));
  const assessment = { values: { monthly_income: null }, choices: { monthly_income: [] }, complete_for_scoring: false };
  assert.deepEqual(parseAssessment(assessment), assessment);
  assert.throws(() => parseAssessment({ ...assessment, values: {} }));
  assert.throws(() => parseAssessment({ ...assessment, complete_for_scoring: undefined }));
});

test('late responses cannot overwrite a newer read or a cleared account', () => {
  const scope = new LatestRead();
  const old = scope.begin(), fresh = scope.begin();
  assert.equal(scope.current(old), false);
  assert.equal(scope.current(fresh), true);
  scope.invalidate();
  assert.equal(scope.current(fresh), false);
  assert.equal(scope.current(scope.begin()), true);
});
