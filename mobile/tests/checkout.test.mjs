import test from 'node:test';
import assert from 'node:assert/strict';
import {canClearRecoveredRetry, parseTestPayment, paymentConflictReason, checkoutCountdown, paymentStatusMethod} from '../../frontend/src/lib/sandbox.ts';
import {withRequestDeadline, RequestTimeout} from '../../frontend/src/lib/request-deadline.ts';

const base={reference:'00000000-0000-4000-8000-000000000001',client_request_id:'00000000-0000-4000-8000-000000000002',
 purpose:'PURCHASE',status:'PENDING',amount:'2.00',currency:'EUR',environment:'MTN_SANDBOX',provider:'MTN_SANDBOX',meter_id:7,loan_id:null,
 initiated_at:'2026-11-21T10:00:00Z',server_time:'2026-11-21T10:00:00Z',next_check_at:'2026-11-21T10:01:00Z',
 checkout:{expires_at:'2026-11-21T10:05:00Z',expired:false,state:'OPEN',classification:'SUBMITTED',provider_cancelled:false,
  operation_reference:'00000000-0000-4000-8000-000000000001',replaces_reference:null,fulfilled_reference:null,business_effect:'NONE',retry_available:false,message:'Waiting for confirmation.'}};

test('client 299/300-second display never authorizes retry or changes provider outcome',()=>{
 const row=parseTestPayment(base), initial=row.observed_at;
 assert.equal(checkoutCountdown(row,initial+299000),1);assert.equal(checkoutCountdown(row,initial+300000),0);
 assert.ok(paymentConflictReason([row],'PURCHASE',7));assert.ok(paymentConflictReason([row],'PURCHASE',7));
 assert.equal(row.checkout.expired,false);assert.equal(row.status,'PENDING');
 assert.equal(paymentConflictReason([row],'PURCHASE',8),null);
 assert.equal(paymentConflictReason([row],'LOAN_REPAYMENT',undefined,'other-loan'),null);
});
test('server expiry and fulfillment metadata distinguish retry, local closure and late evidence',()=>{
 const expired=parseTestPayment({...base,authorization_policy:'legacy-test',checkout:{...base.checkout,expired:true,state:'EXPIRED',retry_available:true}});
 assert.match(paymentConflictReason([expired],'PURCHASE',7),/Start a new sandbox attempt/);
 const done=parseTestPayment({...base,checkout:{...base.checkout,expired:true,state:'EXPIRED',fulfilled_reference:'winner'}});
 assert.equal(paymentConflictReason([done],'PURCHASE',7),null);
 const closed=parseTestPayment({...base,checkout:{...base.checkout,expired:true,state:'LOCAL_INITIATION_CANCELLED'}});
 assert.equal(paymentStatusMethod(closed), 'GET');
 assert.equal(canClearRecoveredRetry(closed),true);assert.equal(canClearRecoveredRetry(null),false);assert.equal(canClearRecoveredRetry(parseTestPayment(base)),false);
 assert.equal(paymentConflictReason([closed],'PURCHASE',7),null);
 assert.throws(()=>parseTestPayment({...base,checkout:{...base.checkout,provider_cancelled:true}}));
});
test('bounded reads and stalled response bodies reject instead of leaving loading forever',async()=>{
 let signal;
 await assert.rejects(withRequestDeadline(value=>{signal=value;return new Promise(()=>{});},5),RequestTimeout);
 assert.equal(signal.aborted,true);
 assert.equal(await withRequestDeadline(async()=>42,100),42);
});
