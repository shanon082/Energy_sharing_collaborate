import test from 'node:test';
import assert from 'node:assert/strict';
import { ALLOCATION_LEDGERS, readLedgerBalance } from '../../frontend/src/lib/allocation-ledgers.ts';
test('allocation ledger reads stay exact and bound to the selected meter', () => {
  assert.deepEqual(ALLOCATION_LEDGERS, ['SANDBOX', 'UGX_DEMO', 'CORE']);
  const raw = {meter: {id: 7}, available_kwh: '1.01', pending_kwh: '2.00', confirmed_kwh: '3.00'};
  assert.deepEqual(readLedgerBalance(raw, 7), {available: '1.01', pending: '2.00', confirmed: '3.00'});
  for (const invalid of [null, {...raw, meter: {id: 8}}, {...raw, available_kwh: null}, {...raw, pending_kwh: 0}, {...raw, confirmed_kwh: '-1'}])
    assert.throws(() => readLedgerBalance(invalid, 7));
});
