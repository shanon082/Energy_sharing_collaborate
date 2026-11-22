import test from 'node:test';
import assert from 'node:assert/strict';
import {paymentStatusMessage, parseTestPayment} from '../src/lib/sandbox.ts';

const row = parseTestPayment({reference:'00000000-0000-4000-8000-000000000001',purpose:'PURCHASE',status:'PENDING',
  amount:'1.00',currency:'EUR',provider:'MTN_SANDBOX',environment:'MTN_SANDBOX',meter_id:7,
  initiated_at:'2026-11-23T10:00:00Z',next_check_at:'2026-11-23T10:00:05Z',submission_state:'ACCEPTED',reconciliation_error:''});

test('shared web/Android status text uses Django settlement, never elapsed time or HTTP success',()=>{
  assert.equal(paymentStatusMessage(row),'Checking sandbox payment status…');
  for(const code of ['MTN_AUTH_HTTP','MTN_STATUS_TRANSPORT','EVIDENCE_AMOUNT'])
    assert.equal(paymentStatusMessage({...row,reconciliation_error:code}),'Confirmation delayed');
  assert.equal(paymentStatusMessage({...row,submission_state:'OUTCOME_UNKNOWN'}),'Confirmation delayed');
  assert.equal(paymentStatusMessage({...row,checkout:{expired:true}}),'Confirmation delayed');
  assert.equal(paymentStatusMessage({...row,status:'FAILED'}),'Payment failed');
  assert.equal(paymentStatusMessage({...row,status:'SETTLED'}),'Payment completed');
  assert.throws(()=>parseTestPayment({...row,status:200}));
  assert.throws(()=>parseTestPayment({...row,status:202}));
  assert.throws(()=>parseTestPayment({...row,status:'SUCCESSFUL'}));
});
