import test from "node:test";
import assert from "node:assert/strict";
import {loanSummary} from "../src/lib/dashboard-loan-summary.ts";
const row = {environment:"UGX_DEMO",currency:"UGX",id:"a",status:"DISBURSED",principal:"5000.00",total_due:"5250.00",outstanding:"2750.000000"};
const read = loans => loanSummary({loans},"UGX_DEMO");
test("partially repaid phone loan matches the web summary; other domains and declines excluded", () => {
  assert.deepEqual(read([row,{...row,id:"b",status:"REJECTED"},{...row,id:"c",currency:"EUR",environment:"MTN_SANDBOX"}]),
    {active:1,borrowed:5000,repaid:2500,outstanding:2750,currency:"UGX",limited:false});
});
test("completed loans have applied debt but are not active",()=>assert.equal(read([{...row,status:"COMPLETED",outstanding:"0"}]).repaid,5250));
test("only a confirmed empty history yields valid empty totals",()=>{
  assert.equal(read([]).outstanding,0);
  for (const bad of [undefined,{}, {loans:null},{loans:[{...row,outstanding:null}]},{loans:[row,row]}])
    assert.throws(()=>loanSummary(bad,"UGX_DEMO"));
});
test("bounded histories are identified and EUR retains cents",()=>{
  assert.equal(read(Array.from({length:100},(_,i)=>({...row,id:String(i)}))).limited,true);
  assert.equal(loanSummary({loans:[{...row,environment:"MTN_SANDBOX",currency:"EUR",total_due:"5.25",outstanding:"2.70"}]},"MTN_SANDBOX").repaid,2.55);
});
