import test from 'node:test';
import assert from 'node:assert/strict';
import {readFinanceSetup} from '../../frontend/src/lib/finance-setup.ts';

const payment={currency:'EUR',environment:'MTN_SANDBOX'};
const loan={currency:'UGX',environment:'UGX_DEMO'};
const context=domain=>({assessment:{score:null,eligible:false},policy:{...domain,id:'stored-policy',minimum:'1',maximum:'20'},pricing:{available:true,message:''}});
test('legacy hosted contract loads EUR purchase terms despite unavailable loan assessment',async()=>{
  const calls=[];
  const client={get:async path=>{calls.push(path);return context(payment);}};
  const result=await readFinanceSetup(client,3,false,payment,payment);
  assert.deepEqual(calls,['sandbox/assessment/?meter_id=3']);
  assert.equal(result.purchase.status,'fulfilled');
  assert.equal(result.purchase.value.policy.currency,'EUR');
});
test('UGX assessment HTTP failure does not block independently readable EUR purchase terms',async()=>{
  const client={get:async path=>{if(path.includes('lending=ugx'))throw Error('Assessment service unavailable');return context(payment);}};
  const result=await readFinanceSetup(client,3,true,payment,loan);
  assert.equal(result.lending.status,'rejected');
  assert.match(result.lending.reason.message,/Assessment service/);
  assert.equal(result.purchase.status,'fulfilled');
  assert.equal(result.purchase.value.policy.currency,'EUR');
});
test('purchase-context failure leaves the UGX assessment usable and never invents pricing',async()=>{
  const client={get:async path=>{if(path.includes('lending=ugx'))return context(loan);throw Error('Purchase pricing request failed');}};
  const result=await readFinanceSetup(client,3,true,payment,loan);
  assert.equal(result.lending.status,'fulfilled');assert.equal(result.purchase.status,'rejected');
});
test('wrong domain cannot turn EUR terms into UGX or an unavailable score into approval',async()=>{
  const client={get:async()=>context(payment)};
  const result=await readFinanceSetup(client,3,true,payment,loan);
  assert.equal(result.lending.status,'rejected');assert.match(result.lending.reason.message,/currency and environment/);
  assert.equal(result.purchase.status,'fulfilled');
});
