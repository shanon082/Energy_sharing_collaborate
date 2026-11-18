import test from 'node:test';
import assert from 'node:assert/strict';
import { quoteAvailabilityReason } from '../../frontend/src/lib/quote-availability.ts';
const ready = {busy:false,refreshing:false,offline:false,unresolved:false,pending:false,blocked:false,policy:true,allowed:true,
  pricing:{available:true,message:''},validAmount:true,purpose:'LOAN',assessmentReady:true,loanReason:null};
test('eligible demo loan review remains available; blocked Amount states explain their cause', () => {
  assert.equal(quoteAvailabilityReason(ready),null);
  assert.match(quoteAvailabilityReason({...ready,pricing:{available:false,message:'Configure the active DOMESTIC tariff.'}}),/DOMESTIC tariff/);
  assert.match(quoteAvailabilityReason({...ready,assessmentReady:false,loanReason:'Select your meter assessment.'}),/Select your meter/);
  assert.match(quoteAvailabilityReason({...ready,pending:true}),/payment is pending/);
  assert.match(quoteAvailabilityReason({...ready,unresolved:true}),/reconciliation/);
  assert.match(quoteAvailabilityReason({...ready,validAmount:false}),/positive amount/);
});
