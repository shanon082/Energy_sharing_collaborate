// Actual authenticated production Next routes; loopback synthetic HTTPS API only.
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const {chromium}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE||'/tmp/gpawa-browser/node_modules/playwright/index.mjs'));
const base='http://localhost:3100';
const directory=new URL('../../docs/review/payment-checkout/',import.meta.url).pathname;
await mkdir(directory,{recursive:true});
const control=async body=>(await fetch('http://127.0.0.1:19081/__fixture__',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json();
const browser=await chromium.launch({headless:true,args:['--no-sandbox','--host-resolver-rules=MAP localhost 127.0.0.1']});
const context=await browser.newContext({viewport:{width:1440,height:1100}});
await context.addCookies([{name:'Authentication',value:'synthetic-browser-fixture-only',url:base,httpOnly:true,sameSite:'Lax'}]);
const page=await context.newPage();page.setDefaultTimeout(45000);page.setDefaultNavigationTimeout(120000);
await page.route('**/*',route=>['127.0.0.1','localhost'].includes(new URL(route.request().url()).hostname)?route.continue():route.abort());
const errors=[];page.on('pageerror',error=>errors.push(error.message));
const shot=async name=>page.screenshot({path:directory+name+'.png',fullPage:true,mask:[page.getByRole('textbox',{name:'15-digit electricity token'})]});
const select=async()=>page.getByRole('combobox',{name:'Selected meter',exact:true}).selectOption('11');
const review=()=>page.getByRole('button',{name:/^Review terms/});
const waitReview=()=>page.waitForFunction(()=>[...document.querySelectorAll('button')].some(button=>button.textContent.startsWith('Review terms')&&!button.disabled));
const results=[];
try {
 await control({reset:true,empty:true,seedPendingPurchase:true,hold:true,statusDelay:1200});
 await page.goto(base+'/dashboard/buy-units/');await select();
 await page.getByRole('complementary',{name:'Pending payment status'}).waitFor();
 await page.getByRole('textbox',{name:'Amount (UGX)',exact:true}).fill('10000');
 assert.equal(await review().isDisabled(),true);
 await shot('buy-units-pending-form');
 await page.goto(base+'/dashboard/request-loan/');await select();await waitReview();
 await shot('loan-available-during-pending-purchase');
 await review().click();await page.getByRole('heading',{name:'Review loan terms'}).waitFor();
 results.push('Open purchase has its own status panel; both forms stay visible and unrelated loan terms remain available.');

 await control({expirePending:true,statusDelay:0});await page.goto(base+'/dashboard/buy-units/');await select();
 await page.getByText('Request timed out; payment confirmation is still being checked.',{exact:true}).first().waitFor();
 await shot('expired-checkout-explicit-retry');
 const retry=page.locator('.checkout-retry');
 assert.equal(await retry.getByRole('button',{name:'Start a new sandbox attempt'}).isDisabled(),true);
 await retry.getByRole('checkbox').check();
 await retry.getByRole('button',{name:'Start a new sandbox attempt'}).dblclick();
 await page.waitForFunction(()=>document.querySelectorAll('.payment-card').length===2);
 let state=await control({});assert.equal(state.stats.initiations,1);
 await page.reload();await select();
 await page.waitForFunction(()=>document.querySelectorAll('.payment-card').length===2);
 assert.equal((await control({})).stats.initiations,1);
 await control({hold:false,confirmPayments:true});
 await page.getByText('Additional successful test authorization retained for review; this operation was already fulfilled. No second financial effect.',{exact:true}).first().waitFor();
 state=await control({});assert.equal(state.stats.completions,1);assert.equal(state.stats.providerConfirmations,2);
 assert.equal(await page.getByRole('textbox',{name:'15-digit electricity token'}).count(),1);
 await shot('late-success-review-one-token');
 results.push('Server-expired checkout needs consent; double-click and reload keep one replacement; two successes show one synthetic token and extra evidence under review.');

 await control({reset:true,empty:true,unavailable:true,loansError:true,paymentsError:true});
 await page.goto(base+'/dashboard/loans/');await select();
 await page.getByText(/Loan summary unavailable/).first().waitFor();
 await page.getByText(/Loans unavailable/).first().waitFor();
 await page.waitForFunction(()=>![...document.querySelectorAll('strong')].some(element=>element.textContent.includes('Loading')));
 assert.equal(await page.getByText('Loading loans…',{exact:true}).count(),0);
 await shot('loan-errors-end-loading');
 // Failed payment history/recovery is deliberately not a loan-origination gate.
 await page.goto(base+'/dashboard/request-loan/');await select();await waitReview();
 await shot('loan-independent-of-payment-read-error');
 results.push('Summary, loan and payment HTTP503 end loading with visible errors; payment read failure does not block an otherwise eligible loan quote.');

 await control({reset:true,empty:true,summaryHang:true});await page.goto(base+'/dashboard/loans/');await select();
 await page.getByText(/Loan summary unavailable.*timed out/).first().waitFor();
 assert.equal(await page.getByText('Loading…',{exact:true}).count(),0);await shot('stalled-summary-timeout');
 results.push('A stalled summary request ends in a bounded timeout error, never a permanent Loading card.');

 await control({reset:true,empty:true,seedPendingPurchase:true,hold:true,expirePending:true});
 await page.setViewportSize({width:390,height:844});await page.goto(base+'/dashboard/buy-units/');await select();
 await page.getByRole('textbox',{name:'Amount (UGX)',exact:true}).waitFor();
 await shot('phone-expired-checkout-form');
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1));
 assert.deepEqual(errors,[]);results.push('Phone-width form, status and retry controls remain usable with no browser runtime errors.');
 await writeFile(directory+'results.json',JSON.stringify({environment:'LOCAL production Next.js + SYNTHETIC HTTPS API',hosted:false,provider_tested:false,phone_tested:false,board_tested:false,results,errors},null,2));
 console.log(JSON.stringify({passed:results.length,results,screenshots:directory},null,2));
} catch(error) {
 await shot('failure-diagnostic');
 console.error('VISIBLE_ALERTS', await page.locator('[role="alert"]').allTextContents());
 const state=await control({}); console.error('SYNTHETIC_COUNTS', JSON.stringify({initiations:state.stats.initiations,completions:state.stats.completions,requests:state.stats.requests.slice(-16)}));
 throw error;
} finally {await browser.close();}
