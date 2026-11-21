import test from 'node:test';
import assert from 'node:assert/strict';
import {sandboxCapabilities, parseTestQuote, assertTestPaymentBinding, parseTestPayment} from '../src/lib/sandbox.ts';

const base={enabled:true,provider:'MTN_SANDBOX',currency:'EUR',environment:'MTN_SANDBOX',physical_delivery:false,loans:false,purchases:true,repayments:true};
const lending={enabled:true,currency:'UGX',environment:'UGX_DEMO',energy_environment:'SANDBOX',policy:'DEMO-UGX-ACLAB-v1',repayment_available:false};
test('explicit UGX lending capability does not change EUR payments or unlock old EUR clients',()=>{
  assert.equal(sandboxCapabilities(base).loans,false);
  const caps=sandboxCapabilities({...base,lending});
  assert.equal(caps.loans,true);assert.equal(caps.loanCurrency,'UGX');assert.equal(caps.currency,'EUR');
  for(const bad of [{...lending,currency:'EUR'},{...lending,energy_environment:'UGX_DEMO'},{...lending,repayment_available:true}])
    assert.equal(sandboxCapabilities({...base,lending:bad}).loans,false);
});
test('UGX terms and EUR provider receipts cannot be relabelled as each other',()=>{
  const expected={owner:3,meterId:3,amount:'10000',purpose:'LOAN',currency:'UGX',environment:'UGX_DEMO'};
  const q={id:'00000000-0000-4000-8000-000000000001',terms_hash:'a'.repeat(64),expires_at:'2030-01-01T00:00:00Z',terms:{owner_id:3,meter_id:3,purpose:'LOAN',amount:'10000',due_at:'2030-01-02T00:00:00Z',policy:{id:'DEMO-UGX-ACLAB-v1',currency:'UGX',environment:'UGX_DEMO'},energy_kwh:'10.00',billed:'10000',residual:'0',interest:'500',fee:'0',total_due:'10500'}};
  assert.equal(parseTestQuote(q,expected).terms.amount,'10000');
  assert.throws(()=>parseTestQuote(q,{...expected,currency:'EUR',environment:'MTN_SANDBOX'}));
  const payment=parseTestPayment({reference:q.id,client_request_id:q.id,purpose:'PURCHASE',status:'PENDING',amount:'2.00',currency:'EUR',environment:'MTN_SANDBOX',provider:'MTN_SANDBOX',meter_id:3,loan_id:null});
  assert.throws(()=>assertTestPaymentBinding(payment,{client_request_id:q.id,purpose:'PURCHASE',amount:'2.00',currency:'UGX',environment:'UGX_DEMO',meter_id:3,loan_id:null}));
});

test('server pause blocks new EUR actions but preserves loan domain and history contract',()=>{
  const caps=sandboxCapabilities({...base,lending,new_payments_paused:true});
  assert.equal(caps.newPaymentsPaused,true);assert.equal(caps.purchases,false);assert.equal(caps.repayments,false);
  assert.equal(caps.loans,true);assert.equal(caps.loanCurrency,'UGX');assert.equal(caps.currency,'EUR');
});
