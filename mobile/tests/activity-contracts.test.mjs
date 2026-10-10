import test from 'node:test';
import assert from 'node:assert/strict';
import { parseReceipts, parseReceipt, parseNotices, parseHistory, parseDeliveries } from '../src/api/activity-contracts.ts';
import { parseConsumption } from '../src/api/contracts.ts';

const meter = { id: 7, meter_number: 'TEST-7', label: 'Home', architecture: 'AMI', status: 'ACTIVE' };
const pagination = { has_more: false, next_before_id: null };
const receipt = { external_id: 'test-reference', purpose: 'PURCHASE', status: 'PENDING', amount_ugx: '1000.00',
  currency: 'UGX', meter_no: 'TEST-7', loan_id: null, purchase_billed_ugx: null, purchase_residual_ugx: null,
  repayment_applied_ugx: null, repayment_excess_ugx: null, environment: 'SIMULATOR', settlement_recorded: false,
  initiated_at: '2026-10-10T10:00:00Z', settled_at: null };
test('receipt parsing preserves exact amounts, simulation and settlement evidence', () => {
  assert.equal(parseReceipt(receipt).amount_ugx, '1000.00');
  assert.equal(parseReceipt(receipt).settlement_recorded, false);
  assert.equal(parseReceipt(receipt).environment, 'SIMULATOR');
  assert.throws(() => parseReceipt({ ...receipt, amount_ugx: 1000 }));
  assert.throws(() => parseReceipt({ ...receipt, currency: 'USD' }));
  assert.throws(() => parseReceipt({ ...receipt, settlement_recorded: true }));
  assert.equal(parseReceipts({ receipts: [receipt], pagination }).rows.length, 1);
  assert.throws(() => parseReceipts({ receipts: [], pagination: { has_more: true, next_before_id: null } }));
});
test('delivery parsing refuses another meter and missing application evidence', () => {
  const delivery = { id: 1, command_id: 'command', request_id: null, amount_kwh: '0.01', status: 'OUTCOME_UNKNOWN',
    created_at: receipt.initiated_at, applied_at: null, application_confirmed: false, environment: 'UNCONFIRMED', source: 'PURCHASE' };
  const payload = { meter, meter_no: meter.meter_number, deliveries: [delivery], pagination };
  assert.equal(parseDeliveries(payload, meter).rows[0].status, 'OUTCOME_UNKNOWN');
  assert.throws(() => parseDeliveries({ ...payload, meter: { ...meter, id: 8 } }, meter));
  assert.throws(() => parseDeliveries({ ...payload, deliveries: [{ ...delivery, status: 'APPLIED', application_confirmed: true }] }, meter));
});
test('historical unknown units remain raw strings and alerts require explicit read state', () => {
  const data = { transactions: [{ id: 1, transaction_type_display: 'Legacy event', status: 'PENDING',
    recorded_amount: '-0.13', recorded_units: '0.01', created_at: receipt.initiated_at,
    units_confirmed: false, source: 'TRANSACTION_LOG' }], pagination };
  assert.equal(parseHistory(data).rows[0].recorded_amount, '-0.13');
  assert.throws(() => parseHistory({ ...data, transactions: [{ ...data.transactions[0], recorded_amount: 0.13 }] }));
  assert.throws(() => parseNotices({ pagination, notifications: [{ id: 1, message: 'Alert', occurred_at: receipt.initiated_at, meter_no: null, is_read: 'false' }] }));
});
test('telemetry keeps integer Wh exact and cannot change the selected meter', () => {
  const payload = { meter, meter_no: meter.meter_number, daily_usage: [], consumer_attribution_available: false,
    simulator_telemetry: [{ event_id: 'event', cumulative_wh_exact: '9007199254740993', cumulative_wh: 9007199254740992,
      measured_at: receipt.initiated_at, received_at: receipt.initiated_at, classification: 'RESET' }] };
  assert.equal(parseConsumption(payload, meter).simulator_telemetry[0].cumulative_wh, '9007199254740993');
  assert.throws(() => parseConsumption({ ...payload, meter: { ...meter, id: 8 } }, meter));
  assert.throws(() => parseConsumption({ ...payload, simulator_telemetry: [{ ...payload.simulator_telemetry[0], cumulative_wh_exact: undefined }] }, meter));
});
