// Synthetic loopback browser fixtures only. Never imported by application code.
import http from 'node:http';
import https from 'node:https';
import { randomUUID } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
const mapped = process.env.CONSUMER_FIXTURE_UGX_AUTHORIZATION === '1';
const authorization = {policy:'UGX-MTN-TEST-AUTH-v1',provider:'MTN_SANDBOX',currency:'EUR',amount:'1.00',no_real_money:true};
const owner = 7, now = () => new Date().toISOString();
const ago = seconds => new Date(Date.now() - seconds * 1000).toISOString();
const policy = { id: 'BROWSER-FIXTURE-ONLY', currency: 'UGX', environment: 'UGX_DEMO', minimum: '1000', maximum: '50000', starter_limit: '5000', interest_percent: '5', fee: '0', rate_per_kwh: null, due_days: 7, penalty_percent: '0', rounding: 'Stored synthetic fixture', purchase_per_point: '10000', purchase_score_cap: 10, score_threshold: 80 };
if(mapped)Object.assign(policy,{id:'DEMO-UGX-MTN-AUTH-v1',authorization,energy_environment:'SANDBOX'});
const loanPolicy = () => mapped ? {...policy,authorization:undefined,id:'DEMO-UGX-ACLAB-v1',lending_contract:'UGX-PROTOTYPE-SANDBOX-v1'} : policy;
const initialMeters = [{ id: 11, meter_number: '00012345678', label: 'Home', status: 'ACTIVE', architecture: 'AMI', sandbox_inventory: true }, { id: 12, meter_number: '0001234567890', label: 'Shop', status: 'ACTIVE', architecture: 'AMI', sandbox_inventory: true }];
const account = { id: owner, first_name: 'Amina', last_name: 'Demo', email: 'consumer@example.invalid', email_verified: true, user_role: 'CLIENT', must_change_password: false, profile: { email_verified: true } };
const features = { features: { peer_sharing: false, meter_transfers: false, third_party_repayment: false, ussd: false, wallet_deposits: false, wallet_withdrawals: false, external_crb: false }, sandbox: { enabled: true, provider: 'LOCAL_DEMO', currency: 'UGX', environment: 'UGX_DEMO', loans: true, purchases: true, repayments: true, physical_delivery: false } };
if(mapped)Object.assign(features.sandbox,{provider:'MTN_SANDBOX',loans:false,authorization:{...authorization,energy_environment:'SANDBOX'},lending:{enabled:true,currency:'UGX',environment:'UGX_DEMO',energy_environment:'SANDBOX',policy:'DEMO-UGX-ACLAB-v1',repayment_available:true}});
const pricing = amount => ({ inputs_hash: 'f'.repeat(64), inputs: { version: 'BROWSER-FIXTURE', month: now().slice(0,7), scope: 'OWNER_MONTH', vat_rate: '0', tariff: { id: 1, code: 'FIXTURE', name: 'Synthetic browser tariff' }, monthly_purchased_kwh: '8.95' }, breakdown: { energy_cost: amount, service_charge: '0', subtotal: amount, vat: '0', total: amount, lifeline_applied: false } });
const loanId = '11111111-1111-4111-8111-111111111111';
const dueAt = () => new Date(Date.now()+7*86400000).toISOString();
const terms = (amount='5000', meter=11, purpose='LOAN') => ({ owner_id: owner, meter_id: meter, policy:purpose==='LOAN'?loanPolicy():policy, ...(mapped?{energy_environment:'SANDBOX'}:{}), purpose, amount, energy_kwh: `${BigInt(amount)/1000n}.${String(BigInt(amount)%1000n/10n).padStart(2,'0')}`, billed: amount, residual: '0', interest: purpose === 'LOAN' ? String(BigInt(amount)*5n/100n) : '0', fee: '0', total_due: purpose === 'LOAN' ? String(BigInt(amount)*105n/100n) : '0', due_at: dueAt(), pricing: pricing(amount), assessment: null });
let loans, payments, mode, stats, quotes, meters, profile;
const sum = (rows,key) => rows.reduce((total,row)=> total + BigInt(String(row[key]).split('.')[0]),0n).toString();
function reset() {
 mode = { unavailable:false, delay:false, hold:false, empty:false, pendingAssessment:false, rejectSubmit:false, noMeters:false, assessmentError:false, purchaseError:false, featuresDelay:0, confirmPayments:false };
 stats = { requests:[], initiations:0, applications:0, completions:0, profileUpdates:[] };
 quotes = new Map(); meters=initialMeters.map(row=>({...row}));
 profile = { account_number:'DEMO-007', address:'Prototype address', energy_preference:'HISTORICAL_CHOICE', payment_method:null };
 loans = [{ id:loanId, client_request_id:randomUUID(), meter_id:11, currency:'UGX', environment:'UGX_DEMO', status:'DISBURSED', principal:'5000.00', total_due:'5250.00', applied_repayments:'2500.00', outstanding:'2750.00', created_at:ago(120), due_at:dueAt(), closed_at:null, allocation_id:101, allocated_kwh:'5.00', reason:'Approved using your stored assessment.', terms:terms(), assessment:{} }];
 // Completed historical receipts still obey the minimum authorization interval.
 payments = [{ reference:randomUUID(), client_request_id:randomUUID(), meter_id:11, loan_id:loanId, provider:'LOCAL_DEMO', currency:'UGX', environment:'UGX_DEMO', purpose:'LOAN_REPAYMENT', amount:'2500', applied:'2500', excess:'0', billed:'0', residual:'0', allocated_kwh:null, allocation_id:null, status:'SETTLED', initiated_at:ago(100), settled_at:ago(90), demo_eligible_at:ago(95), server_time:now(), submission_state:'SUBMITTED', reconciliation_error:'', next_check_at:now() }];
}
reset();
function assessment(id) {
 const score=id===12?62:85, ready=Boolean(id)&&!mode.pendingAssessment, debt=loans.some(row=>row.status==='DISBURSED');
 return { owner_id:owner, meter_id:id||null, assessment_id:id||null, minimum_score:80, eligible:ready&&score>=80&&!debt, reason:!ready?'Assessment pending for this meter.':score<80?'A minimum of 80% is required.':debt?'Repay your current loan before applying again.':'You are eligible for electricity credit.', starter:false, score:ready?score:null, profile_score:ready?score:null, purchase_points:ready?0:null, maximum:ready?'37500':null, factors:ready?{payment_history:92,energy_consumption:71,financial_capacity:92}:null, assessment_status:ready?'READY':'PENDING', provider:'SIMULATED_ACCOUNT_V1', input_source:'SIMULATED_ACCOUNT_INFORMATION', currency:'UGX', environment:'UGX_DEMO', scoring_policy_version:'DEMO-METER-SCORE-v2', assessed_at:ready?'2026-11-01T12:00:00Z':null, evidence_updated_at:'2026-11-01T12:00:00Z', qualifying_billed_test:'0', policy_id:policy.id };
}
function result(res,status,data) { res.writeHead(status,{'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify(data)); }
function finish(payment) {
 if ((mapped&&!mode.confirmPayments)||mode.hold||Date.now()<Date.parse(payment.demo_eligible_at)||payment.status!=='PENDING') return;
 stats.completions++;payment.status='SETTLED';if(payment.provider_receipt){payment.provider_receipt.status='SETTLED';payment.provider_receipt.transaction_id='synthetic-provider-'+payment.reference;}payment.settled_at=now();
 if(payment.purpose==='PURCHASE'){payment.billed=payment.amount;payment.allocation_id=303;payment.allocated_kwh=terms(payment.amount).energy_kwh;return;}
 const loan=loans.find(row=>row.id===payment.loan_id), debt=BigInt(loan.outstanding.split('.')[0]), received=BigInt(payment.amount);
 const applied=debt<received?debt:received;payment.applied=String(applied);payment.excess=String(received-applied);
 loan.applied_repayments=String(BigInt(loan.applied_repayments.split('.')[0])+applied);loan.outstanding=String(debt-applied);
 if(loan.outstanding==='0'){loan.status='COMPLETED';loan.closed_at=now();}
}
const handler=async(req,res)=>{
 const url=new URL(req.url,'http://127.0.0.1');let text='';for await(const chunk of req)text+=chunk;
 const body=text?JSON.parse(text):{};
 if(url.pathname==='/__fixture__'){
  if(body.reset)reset();Object.assign(mode,body);
  if(body.empty){loans=[];payments=[];}
  if(body.historyEur){payments.push({reference:randomUUID(),client_request_id:randomUUID(),meter_id:11,loan_id:null,provider:'MTN_SANDBOX',currency:'EUR',environment:'MTN_SANDBOX',purpose:'PURCHASE',amount:'2.00',billed:'2.00',residual:'0',applied:'0',excess:'0',allocated_kwh:'2.00',allocation_id:null,status:'SETTLED',initiated_at:ago(50),settled_at:ago(40),demo_eligible_at:null,server_time:now(),submission_state:'ACCEPTED',reconciliation_error:'',next_check_at:now()});}

  return result(res,200,{mode,stats});
 }
 const path=url.pathname.replace('/api/v1/','');stats.requests.push(`${req.method} ${path}`); // Never log credentials or bodies.
 if(path==='features/'){if(mode.featuresDelay)await new Promise(resolve=>setTimeout(resolve,mode.featuresDelay));return result(res,200,features);}
 if(path==='auth/get-user-config/'||path==='auth/mobile-account/')return result(res,200,account);
 if(path==='meter/mobile-onboarding/')return result(res,200,{meters:mode.noMeters?[]:meters,sandbox_self_enrollment:true});
 if(path==='auth/mobile-account-details/'){
  if(req.method==='PATCH'){stats.profileUpdates.push(Object.keys(body));Object.assign(profile,body);}
  return result(res,200,{details_available:true,values:profile,choices:{energy_preference:[{value:'SOLAR',label:'Solar'}],payment_method:[{value:'MOBILE_MONEY',label:'Mobile money'}]}});
 }
 if(path==='meter/sandbox-meter-enrollment/'&&req.method==='POST'){
  if(!/^[0-9]{11}$/.test(body.meter_no))return result(res,400,{message:'Use exactly 11 ASCII digits.'});
  let meter=meters.find(row=>row.meter_number===body.meter_no);
  if(!meter){meter={...initialMeters[0],id:13,meter_number:body.meter_no,label:'Prototype meter',ownership_provenance:'SELF_DECLARED',hardware_connection:'PENDING',enrolled_at:now()};meters.push(meter);}
  mode.noMeters=false;return result(res,201,{success:true,status:'SELF_DECLARED',meter,created:true,message:'Meter linked for prototype testing. Ownership and live readings are not verified with the electricity provider.'});
 }
 if(path==='sandbox/summary/'){
  if(mode.unavailable)return result(res,503,{message:'Summary temporarily unavailable.'});
  const relevant=loans.filter(row=>row.status!=='REJECTED');return result(res,200,{owner_id:owner,scope:'OWNER',meter_id:null,currency:'UGX',environment:'UGX_DEMO',loan_count:loans.length,active_loan_count:relevant.filter(row=>row.status==='DISBURSED').length,...Object.fromEntries(['principal','total_due','applied_repayments','outstanding'].map(key=>[key,sum(relevant,key)])),energy:{}});
 }
 if(path==='sandbox/assessment/'){
  const purchase=url.searchParams.get('purpose')==='PURCHASE';
  if(purchase&&mode.purchaseError)return result(res,503,{message:'Fixture purchase pricing unavailable.'});
  if(!purchase&&mode.assessmentError)return result(res,503,{message:'Fixture assessment service unavailable.'});
  const id=Number(url.searchParams.get('meter_id'));if(mode.delay&&id===11)await new Promise(resolve=>setTimeout(resolve,1800));
  return result(res,200,{assessment:purchase?null:assessment(id),policy:purchase?policy:loanPolicy(),purchase_policy:policy,pricing:{available:true,message:'',revision:'fixture-v1'},purchase_pricing:{available:true,message:'',revision:'fixture-v1'}});
 }
 if(/^meter\/mobile-meters\/\d+\/$/.test(path)){
  const meter=meters.find(row=>path.includes(`/${row.id}/`));if(!meter||mode.noMeters)return result(res,404,{});
  return result(res,200,{meter,available_kwh:meter.id===11?'8.95':'2.00',pending_kwh:'5.00',confirmed_kwh:'0.00',meter_reported_remaining_wh:null,simulator_remaining_wh:null,last_meter_contact:null});
 }
 if(path==='sandbox/loans/'&&req.method==='GET')return result(res,200,{loans});
 if(path.startsWith('sandbox/loan-recovery/'))return result(res,200,{loan:loans.find(row=>path.includes(row.client_request_id))||null});
 if(path==='sandbox/quotes/'&&req.method==='POST'){
  const quote={id:randomUUID(),terms_hash:'a'.repeat(64),expires_at:new Date(Date.now()+900000).toISOString(),terms:terms(body.amount,body.meter_id,body.purpose)};quotes.set(quote.id,quote);return result(res,201,quote);
 }
 if(path==='sandbox/loans/'&&req.method==='POST'){
  const existing=loans.find(row=>row.client_request_id===body.client_request_id);if(existing)return result(res,200,{loan:existing});
  stats.applications++;const q=quotes.get(body.quote_id);const loan={id:randomUUID(),client_request_id:body.client_request_id,meter_id:q.terms.meter_id,currency:'UGX',environment:'UGX_DEMO',status:mode.rejectSubmit?'REJECTED':'DISBURSED',principal:q.terms.amount,total_due:q.terms.total_due,applied_repayments:'0',outstanding:mode.rejectSubmit?'0':q.terms.total_due,terms:q.terms,assessment:assessment(q.terms.meter_id),created_at:now(),due_at:dueAt(),closed_at:null,allocation_id:mode.rejectSubmit?null:202,allocated_kwh:mode.rejectSubmit?null:q.terms.energy_kwh,reason:mode.rejectSubmit?'Not approved: controlled server-side eligibility decision.':'Approved using your stored assessment.'};loans.push(loan);return result(res,201,{loan});
 }
 if(path==='sandbox/payments/'&&req.method==='GET')return result(res,200,{payments:payments.map(row=>({...row,server_time:now()})),pending:payments.filter(row=>row.status==='PENDING')});
 if(path==='sandbox/payments/'&&req.method==='POST'){
  const existing=payments.find(row=>row.client_request_id===body.client_request_id);if(existing)return result(res,200,{payment:existing,reused:true});
  stats.initiations++;const q=quotes.get(body.quote_id), started=now();const payment={reference:randomUUID(),client_request_id:body.client_request_id,purpose:body.purpose,provider:'LOCAL_DEMO',currency:'UGX',environment:'UGX_DEMO',status:'PENDING',amount:body.amount||q.terms.amount,meter_id:q?.terms.meter_id||loans.find(row=>row.id===body.loan_id).meter_id,loan_id:body.loan_id||null,billed:'0',residual:'0',applied:'0',excess:'0',allocated_kwh:null,allocation_id:null,initiated_at:started,settled_at:null,demo_eligible_at:new Date(Date.parse(started)+5000).toISOString(),server_time:started,submission_state:'SUBMITTED',reconciliation_error:'',next_check_at:started};if(mapped){payment.provider='MTN_SANDBOX';payment.instruction_id=randomUUID();payment.authorization_policy=authorization.policy;payment.demo_eligible_at=null;payment.provider_receipt={reference:payment.reference,external_id:'fixture-'+payment.reference,transaction_id:null,amount:'1.00',currency:'EUR',environment:'MTN_SANDBOX',status:'PENDING',purpose:'TEST_AUTHORIZATION',no_real_money:true};}payments.unshift(payment);return result(res,202,{payment,reused:false});
 }
 if(path.startsWith('sandbox/payment-recovery/'))return result(res,200,{payment:payments.find(row=>path.includes(row.client_request_id))||null});
 if(/^sandbox\/payments\/.+\/$/.test(path)){
  const payment=payments.find(row=>path.includes(row.reference));if(!payment)return result(res,404,{});if(req.method==='POST')finish(payment);
  return result(res,200,{payment:{...payment,server_time:now()}});
 }
 if(path==='meter/energy-tokens/'){
  const id=Number(url.searchParams.get('allocation_id')), payment=payments.find(row=>row.allocation_id===id);
  const quantity=payment?.allocated_kwh||'5.00';
  return result(res,200,{tokens:[{id:'synthetic-token-'+id,allocation_id:id,token:'000123456789012',meter_number:'00012345678',energy_wh:String(BigInt(quantity.split('.')[0])*1000n),energy_kwh:quantity,environment:mapped?'SANDBOX':'UGX_DEMO',redemption_enabled:false,source:payment?'PURCHASE':'LOAN',source_reference:payment?.reference||loanId,state:'ISSUED',application_environment:'UNCONFIRMED',created_at:now()}]});
 }
 return result(res,404,{message:'No synthetic fixture for this route.'});
};
const server=http.createServer(handler);
if(process.env.CONSUMER_FIXTURE_TLS_CERT && process.env.CONSUMER_FIXTURE_TLS_KEY){
 const tls=https.createServer({cert:readFileSync(process.env.CONSUMER_FIXTURE_TLS_CERT),key:readFileSync(process.env.CONSUMER_FIXTURE_TLS_KEY)},handler);
 tls.listen(19443,'127.0.0.1');
}
server.listen(19081,'127.0.0.1',()=>{writeFileSync('/tmp/parity-fixture.pid',String(process.pid));console.log('Synthetic loopback API ready; no hosted records, providers or devices.');});
