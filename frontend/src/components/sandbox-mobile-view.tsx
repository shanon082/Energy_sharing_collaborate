"use client";

import { useEffect, useState, type FormEvent } from "react";
import { demoCountdown, type Assessment, type SandboxCapabilities, type TestCurrency, type TestEnvironment,
  type TestLoan, type TestMeter, type TestPayment, type TestPolicy, type TestQuote, type PricingStatus } from "../lib/sandbox";

import { TariffDetails } from "./tariff-details";
import { financeBackAction } from "../lib/finance-navigation";

export type ConsumerFinanceView = "home" | "loans" | "apply" | "purchase" | "activity" | "hidden";
export type FinanceDestination = "loans" | "apply" | "purchase" | "activity" | "meters";
export type MobileFinanceProps = {
  view: ConsumerFinanceView; navigate: (view: FinanceDestination) => void;
  registerBackHandler?: (handler: (() => boolean) | null) => void;
  demo: boolean; currency: TestCurrency; environment: TestEnvironment; capabilities: SandboxCapabilities;
  pricingStatus: PricingStatus; loanReason: string | null;
  assessment: Assessment | null; policy: TestPolicy | null; loans: TestLoan[]; payments: TestPayment[];
  meters: TestMeter[]; selectedMeter: TestMeter | null; purpose: "LOAN" | "PURCHASE";
  amount: string; setAmount: (value: string) => void; quote: TestQuote | null; clearQuote: () => void;
  accepted: boolean; setAccepted: (value: boolean) => void; phone: string; setPhone: (value: string) => void;
  loanId: string; selectLoan: (id: string) => void; repayment: string; setRepayment: (value: string) => void;
  repayAccepted: boolean; setRepayAccepted: (value: boolean) => void;
  blocked: boolean; busy: boolean; refreshing: boolean; offline: boolean; unresolved: boolean; pending: boolean;
  error: string | null; notice: string | null; fetched: string | null; clock: number;
  validAmount: (value: string) => boolean; validPhone: boolean;
  refresh: () => void; getQuote: (event: FormEvent) => void; submit: () => void; repay: (event: FormEvent) => void;
  checkPayment: (row: TestPayment) => void;
};

/** Display exact strings; no lending calculation or currency conversion occurs here. */
function money(value: string | null | undefined, currency: TestCurrency): string {
  if (value == null || !/^\d+(?:\.\d+)?$/.test(value)) return "Unavailable";
  const [whole, fraction] = value.split(".");
  return `${currency === "EUR" ? "EUR TEST" : "UGX"} ${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}${fraction && /[1-9]/.test(fraction) ? `.${fraction}` : ""}`;
}
const when = (value: string | null | undefined) => value && Number.isFinite(Date.parse(value)) ? new Date(value).toLocaleString() : "Unavailable";
const label = (status: string) => ({ DISBURSED: "Active", COMPLETED: "Repaid", REJECTED: "Not approved", SETTLED: "Completed", PENDING: "Pending", FAILED: "Failed" }[status] ?? status);
function InfoRow({ title, value }: { title: string; value: string }) { return <div className="review-row"><span>{title}</span><strong>{value}</strong></div>; }

export default function SandboxMobileView(p: MobileFinanceProps) {
  const [repaymentContext, setRepaymentContext] = useState<{ loan: string; receipt: string | null } | null>(null);
  const [reviewRepayment, setReviewRepayment] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [filter, setFilter] = useState<"all" | "PURCHASE" | "LOAN_REPAYMENT">("all");
  const currentLoans = p.loans.filter(loan => loan.environment === p.environment);
  const oldLoans = p.loans.filter(loan => loan.environment !== p.environment);
  const currentLoan = currentLoans.find(loan => loan.status === "DISBURSED");
  const selectedLoan = currentLoans.find(loan => loan.id === p.loanId && loan.status === "DISBURSED");
  const ready = p.assessment && (!p.demo || p.assessment.assessment_status === "READY");
  const score = ready && !p.assessment?.starter ? p.assessment?.score : null;
  const allowed = p.purpose === "LOAN" ? p.capabilities.loans : p.capabilities.purchases;
  const activeQuote = p.quote?.terms.purpose === p.purpose ? p.quote : null;
  const expired = activeQuote ? Date.parse(activeQuote.expires_at) <= p.clock : false;
  const lastRepayment = (id: string) => p.payments.find(row => row.loan_id === id)?.reference ?? null;
  const showRepayment = !!repaymentContext && !!selectedLoan && repaymentContext.loan === p.loanId &&
    repaymentContext.receipt === lastRepayment(p.loanId);
  const chooseRepayment = (loan: TestLoan) => {
    p.selectLoan(loan.id); setRepaymentContext({ loan: loan.id, receipt: lastRepayment(loan.id) }); setReviewRepayment(false); p.navigate("loans");
  };
  useEffect(() => {
    if (!p.registerBackHandler) return;
    const handle = () => {
      const action = financeBackAction({ view: p.view, busy: p.busy, pending: p.pending,
        hasQuote: !!activeQuote, confirming, repaying: showRepayment, reviewingRepayment: reviewRepayment });
      if (action === "none") return false;
      if (action === "terms") setConfirming(false);
      if (action === "amount") { p.clearQuote(); setConfirming(false); }
      if (action === "repayment") { setReviewRepayment(false); p.setRepayAccepted(false); }
      if (action === "loans") { setRepaymentContext(null); p.navigate("loans"); }
      return true;
    };
    p.registerBackHandler(handle);
    return () => p.registerBackHandler?.(null);
  }, [p, activeQuote, confirming, showRepayment, reviewRepayment]);
  const disclosure = p.demo ? "Demo payment: no real money is deducted and no phone PIN is required." : "MTN sandbox payment in EUR TEST. No real money is collected.";
  const phoneField = !p.demo && <label>MTN sandbox number<input inputMode="numeric" autoComplete="off" value={p.phone} onChange={e => p.setPhone(e.target.value)} required /><small className="muted">Use your configured test scenario number, 10–15 digits. Never enter a PIN.</small></label>;
  const assessmentCard = <section className="panel credit-summary" aria-label="Credit overview">
    <div className="section-title"><h2>Credit overview</h2>{ready && <span className={`status-pill ${p.assessment?.eligible ? "" : "pending"}`}>{p.assessment?.eligible ? "Eligible" : "Not eligible"}</span>}</div>
    <div className="credit-summary-grid"><div><span className="muted">Credit score</span><strong className="credit-score">{!p.fetched ? "…" : score ?? "—"}{score != null && <small>%</small>}</strong></div><div><span className="muted">Borrowing limit</span><strong className="credit-limit">{money(p.assessment?.maximum, p.currency)}</strong><button type="button" className="text-button" onClick={() => p.navigate("apply")}>View loan options →</button></div></div>
    {p.assessment?.reason && <p className="muted small">{p.assessment.reason}</p>}
    {!ready && p.fetched && <p className="muted">Assessment {p.assessment?.assessment_status?.toLowerCase() || "unavailable"}. Link your meter and refresh.</p>}
    {p.assessment?.starter && <p className="muted small">Starter allowance; no established credit score yet.</p>}
    <details className="info-disclosure"><summary>How your score is calculated</summary>
      <p>{p.demo ? "Demo assessment — simulated account information." : "Sandbox assessment."} No questionnaire is needed.</p>
      {Object.entries(p.assessment?.factors ?? {}).map(([key, value]) => <InfoRow key={key} title={key.replaceAll("_", " ")} value={`${value}${p.assessment?.categories?.[key] ? ` · ${p.assessment.categories[key]}` : ""}`} />)}
      <InfoRow title="Purchase contribution" value={p.assessment?.purchase_points == null ? "Unavailable" : `${p.assessment.purchase_points} points`} />
      <p className="small">Assessed {when(p.assessment?.assessed_at)} · {p.assessment?.scoring_policy_version || p.assessment?.policy_id}</p>
      {p.policy && <p className="small">Settled billed purchases: {money(p.assessment?.qualifying_billed_test ?? p.assessment?.qualifying_billed_eur, p.currency)}. One point per {money(p.policy.purchase_per_point, p.currency)}, capped at {p.policy.purchase_score_cap}. Refreshing does not award points.</p>}
    </details>
  </section>;

  const paymentCard = (row: TestPayment) => <article className="panel payment-card" key={row.reference}>
    <div className="section-title"><h3>{row.purpose === "PURCHASE" ? "Electricity purchase" : "Loan repayment"}</h3><span className={`status-pill ${row.status === "PENDING" ? "pending" : row.status === "FAILED" ? "neutral" : ""}`}>{label(row.status)}</span></div>
    <strong className="payment-amount">{money(row.amount, row.currency)}</strong><p className="muted small">{when(row.initiated_at)} · {row.currency === "UGX" ? "UGX demo" : "EUR test"}</p>
    {row.status === "PENDING" && row.environment === "UGX_DEMO" && <div className="payment-progress" role="status"><span className="loading-spinner" /><div><strong>Processing payment</strong><p>{(demoCountdown(row, p.clock) ?? 0) > 0 ? `Please wait · ${demoCountdown(row, p.clock)} seconds` : "Waiting for server confirmation"}</p><small>No real money or phone PIN is required.</small></div></div>}
    {row.status === "SETTLED" && <p className="small">{row.environment === "UGX_DEMO" ? "Demo payment successful. No real money was deducted." : "Sandbox payment verified."}</p>}
    {row.status === "FAILED" && <p className="muted">Payment failed. Review the receipt before trying again.</p>}
    {row.status === "PENDING" && row.environment !== p.environment && <p className="muted small">This earlier payment belongs to a different test environment. It has not been cancelled or converted.</p>}
    <details className="info-disclosure"><summary>Receipt details</summary><p className="reference">Reference: {row.reference}</p><InfoRow title="Meter" value={p.meters.find(meter => meter.id === row.meter_id)?.meter_number ?? `Meter ID ${row.meter_id}`} />
      {row.purpose === "PURCHASE" ? <><InfoRow title="Billed amount" value={money(row.billed, row.currency)} /><InfoRow title="Rounding remainder" value={money(row.residual, row.currency)} /><InfoRow title="Cloud energy allocated" value={row.allocated_kwh == null ? "Unavailable" : `${row.allocated_kwh} kWh`} /></> : <><InfoRow title="Applied to debt" value={money(row.applied, row.currency)} /><InfoRow title="Excess received" value={money(row.excess, row.currency)} /></>}
      <TariffDetails pricing={row.pricing} currency={row.currency} />
      <p className="muted small">Remainders and excess are recorded for reconciliation. Cloud allocation does not confirm physical delivery.</p><InfoRow title="Settled" value={when(row.settled_at)} /><p className="small">{row.environment} · {row.submission_state}</p>{row.reconciliation_error && <p className="error">{row.reconciliation_error}</p>}
    </details>
    {row.status === "PENDING" && row.environment === p.environment && <button type="button" className="secondary" disabled={p.busy || p.refreshing || p.offline || (p.demo && demoCountdown(row, p.clock) !== 0)} onClick={() => p.checkPayment(row)}>Check payment status</button>}
  </article>;

  const loanCard = (loan: TestLoan, historical = false) => <article className="panel loan-card" key={loan.id}>
    <div className="section-title"><h3>Electricity loan</h3><span className={`status-pill ${loan.status === "REJECTED" ? "pending" : "neutral"}`}>{label(loan.status)}</span></div>
    <p className="muted small">Meter {p.meters.find(meter => meter.id === loan.meter_id)?.meter_number ?? loan.meter_id}{historical ? ` · ${loan.currency} test history` : ""}</p>
    <span className="muted small">Outstanding balance</span><strong className="loan-balance">{money(loan.outstanding, loan.currency)}</strong>
    <InfoRow title="Principal" value={money(loan.principal, loan.currency)} /><InfoRow title="Total repayment" value={money(loan.total_due, loan.currency)} /><InfoRow title="Due" value={when(loan.due_at)} />
    <p className="muted small">{loan.reason}</p>
    {!historical && loan.status === "DISBURSED" && <button type="button" className="primary-button" disabled={!p.capabilities.repayments} onClick={() => chooseRepayment(loan)}>Pay Loan →</button>}
    <details className="info-disclosure"><summary>Loan details & repayments</summary><p className="reference">Reference: {loan.id}</p><InfoRow title="Accepted policy" value={loan.terms.policy.id} /><TariffDetails pricing={loan.terms.pricing} currency={loan.currency} /><InfoRow title="Cloud allocation" value={loan.allocated_kwh == null ? "None" : `${loan.allocated_kwh} kWh`} /><InfoRow title="Closed" value={when(loan.closed_at)} />
      {p.payments.filter(row => row.loan_id === loan.id).map(row => <div className="list-row" key={row.reference}><span>{label(row.status)}<small>Applied {money(row.applied, row.currency)} · excess {money(row.excess, row.currency)}</small></span><strong>{money(row.amount, row.currency)}</strong></div>)}
      <p className="muted small">Cloud allocation is separate from physical meter delivery.</p>
    </details>
  </article>;

  if (p.view === "hidden") return null;
  return <section className="mobile-finance" aria-label="Energy finance">
    <div className="finance-toolbar"><span className="muted small">{p.refreshing ? "Updating…" : p.fetched ? `Updated ${new Date(p.fetched).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : "Loading your account…"}</span><button type="button" className="text-button" disabled={p.busy || p.refreshing} onClick={p.refresh}>Refresh</button></div>
    {(p.offline || (p.error && p.fetched)) && <p className="stale" role="status">Displayed records may be out of date. Last updated {when(p.fetched)}.</p>}
    {p.error && <p className="error" role="alert">{p.error}</p>}{p.notice && !(p.pending && p.notice.startsWith("Demo payment:")) && <p className="tag" role="status">{p.notice}</p>}
    {p.unresolved && <p className="muted small">A previous request needs checking. Refresh before starting another.</p>}
    {p.pending && <div className="pending-summary"><strong>Payment pending</strong><p>We’re waiting for its confirmed outcome before allowing another payment.</p>{p.view === "home" && <button className="text-button" onClick={() => p.navigate("activity")}>View payment →</button>}</div>}

    {p.view === "home" && <>{assessmentCard}{currentLoan ? loanCard(currentLoan) : p.fetched && <section className="panel"><h2>No active loan</h2><p className="muted">Review your options when you need electricity credit.</p><button className="secondary" onClick={() => p.navigate("apply")}>Apply for Loan →</button></section>}
      <div className="section-title"><h2>Recent activity</h2><button className="text-button" onClick={() => p.navigate("activity")}>View all</button></div>{p.payments.length ? p.payments.slice(0, 2).map(paymentCard) : <p className="muted">{p.fetched ? "No payments yet." : "Loading payments…"}</p>}
    </>}

    {(p.view === "loans" || p.view === "apply") && <div className="segmented-control" aria-label="Loan section"><button aria-pressed={p.view === "loans"} onClick={() => { setRepaymentContext(null); p.navigate("loans"); }}>My Loans</button><button aria-pressed={p.view === "apply"} onClick={() => { setConfirming(false); p.navigate("apply"); }}>Apply for Loan</button></div>}
    {p.view === "loans" && <>
      {showRepayment && !p.pending ? <section className="panel"><button type="button" className="text-button" onClick={() => setRepaymentContext(null)}>← My Loans</button><h2>Pay Loan</h2>
        <form className="form-panel" onSubmit={event => { if (!reviewRepayment) { event.preventDefault(); setReviewRepayment(true); } else p.repay(event); }}>
          {!reviewRepayment ? <><label>Your loan<select value={p.loanId} onChange={event => { p.selectLoan(event.target.value); setRepaymentContext({ loan: event.target.value, receipt: lastRepayment(event.target.value) }); setReviewRepayment(false); }} required><option value="">Choose a loan</option>{currentLoans.filter(loan => loan.status === "DISBURSED").map(loan => <option key={loan.id} value={loan.id}>{money(loan.outstanding, loan.currency)} · {loan.id}</option>)}</select></label>{selectedLoan && <InfoRow title="Outstanding" value={money(selectedLoan.outstanding, p.currency)} />}<label>Repayment amount ({p.currency})<input inputMode={p.demo ? "numeric" : "decimal"} value={p.repayment} onChange={event => { p.setRepayment(event.target.value); p.setRepayAccepted(false); }} required /></label><button type="submit" disabled={p.blocked || !p.capabilities.repayments || !selectedLoan || !p.validAmount(p.repayment)}>Review repayment →</button></> : <>
            <InfoRow title="Repayment amount" value={money(p.repayment, p.currency)} /><InfoRow title="Outstanding" value={money(selectedLoan?.outstanding, p.currency)} /><p className="muted small">Repayment reduces this loan only. Any excess is recorded for reconciliation, with no automatic refund or energy credit.</p>{phoneField}<p className="payment-disclosure">{disclosure}</p><label className="check-row"><input type="checkbox" checked={p.repayAccepted} onChange={event => p.setRepayAccepted(event.target.checked)} />I accept these test repayment terms.</label><button type="submit" disabled={p.blocked || !p.capabilities.repayments || !selectedLoan || !p.validAmount(p.repayment) || !p.repayAccepted || (!p.demo && !p.validPhone)}>{p.busy ? "Submitting…" : "Confirm repayment"}</button><button type="button" className="secondary" disabled={p.busy} onClick={() => { setReviewRepayment(false); p.setRepayAccepted(false); }}>Edit amount</button>
          </>}
        </form>
      </section> : <>{!p.fetched ? <p role="status">Loading loans…</p> : currentLoans.length ? currentLoans.map(loan => loanCard(loan)) : <section className="panel empty-card"><h2>No loan applications yet</h2><p className="muted">See your borrowing options and review the terms.</p><button onClick={() => p.navigate("apply")}>Apply for Loan →</button></section>}</>}
      {p.payments.filter(row => row.purpose === "LOAN_REPAYMENT" && row.environment === p.environment).slice(0, 5).map(paymentCard)}
      {oldLoans.length > 0 && <details className="panel info-disclosure"><summary>Earlier test-currency loans</summary>{oldLoans.map(loan => loanCard(loan, true))}</details>}
    </>}

    {(p.view === "apply" || p.view === "purchase") && <>
      {p.view === "apply" && <ol className="loan-stepper">{["Amount", "Terms", "Confirm"].map((name, index) => { const step = !activeQuote ? 0 : confirming ? 2 : 1; return <li key={name} className={index === step ? "current" : index < step ? "done" : ""} aria-current={index === step ? "step" : undefined}><span>{index + 1}</span>{name}</li>; })}</ol>}
      {!p.selectedMeter?.sandbox_inventory ? <section className="panel empty-card"><h2>Select your meter</h2><p className="muted">Link or select a meter before continuing.</p><button onClick={() => p.navigate("meters")}>Choose meter →</button></section> : <>
        {p.view === "apply" && assessmentCard}
        {!allowed && <p className="muted" role="status">{p.view === "apply" ? "Loan applications" : "Purchases"} are currently unavailable. Refresh to check again.</p>}
        {!p.pricingStatus.available && <p className="error" role="status">{p.pricingStatus.message}</p>}
        {p.view === "apply" && p.loanReason && <p className="muted" role="status" id="loan-eligibility-reason">{p.loanReason}</p>}
        {!activeQuote ? !p.pending && <form className="panel form-panel" onSubmit={event => { setConfirming(false); p.getQuote(event); }}><h2>{p.view === "apply" ? "How much do you need?" : "How much would you like to buy?"}</h2><label>Amount ({p.currency})<input inputMode={p.demo ? "numeric" : "decimal"} value={p.amount} onChange={event => p.setAmount(event.target.value)} required /></label><p className="muted small">{p.demo ? "Enter whole shillings." : "Use EUR test amounts."} Range {money(p.policy?.minimum, p.currency)}–{money(p.policy?.maximum, p.currency)}.</p>{p.view === "apply" && <p className="muted small">Your limit: {money(p.assessment?.maximum, p.currency)}. Eligibility is checked when you submit.</p>}<button type="submit" aria-describedby={p.view === "apply" && p.loanReason ? "loan-eligibility-reason" : undefined} disabled={p.blocked || !p.policy || !allowed || !p.pricingStatus.available || !p.validAmount(p.amount) || (p.view === "apply" && (!ready || !!p.loanReason))}>{p.busy ? "Getting quote…" : "Review terms →"}</button></form> : <section className="panel form-panel"><h2>{p.view === "apply" ? confirming ? "Confirm your application" : "Review loan terms" : "Review your purchase"}</h2>
          <div className="quote-summary"><InfoRow title={p.view === "apply" ? "Loan principal" : "Payment amount"} value={money(activeQuote.terms.amount, p.currency)} /><InfoRow title="Cloud energy" value={`${activeQuote.terms.energy_kwh} kWh`} />{p.view === "apply" && <><InfoRow title={`Interest (${activeQuote.terms.policy.interest_percent}%)`} value={money(activeQuote.terms.interest, p.currency)} /><InfoRow title="Fee" value={money(activeQuote.terms.fee, p.currency)} /><InfoRow title="Loan term" value={`${activeQuote.terms.policy.due_days} days`} /><div className="quote-total"><span>Total repayment</span><strong>{money(activeQuote.terms.total_due, p.currency)}</strong></div></>}</div>
          <details className="info-disclosure"><summary>Pricing & policy details</summary>{activeQuote.terms.pricing ? <TariffDetails pricing={activeQuote.terms.pricing} currency={p.currency} /> : <InfoRow title="Original fixed price per kWh" value={money(activeQuote.terms.policy.rate_per_kwh, p.currency)} />}<InfoRow title="Billed" value={money(activeQuote.terms.billed, p.currency)} /><InfoRow title="Rounding remainder" value={money(activeQuote.terms.residual, p.currency)} /><p>Remainder retained for reconciliation; no automatic refund or energy conversion.</p><p>{activeQuote.terms.policy.rounding} · {activeQuote.terms.policy.id}</p><p>Overdue charge {activeQuote.terms.policy.penalty_percent}%. Cloud allocation does not confirm physical delivery.</p></details>
          <p className={expired ? "error" : "muted small"}>{expired ? "This quote expired. Get a fresh quote." : `Quote valid until ${when(activeQuote.expires_at)}`}</p>
          {p.view === "purchase" && phoneField}<p className="payment-disclosure">{p.view === "apply" ? "Demo loan: these are test obligations and cloud units, not real-money credit or physical meter delivery." : disclosure}</p>
          {!confirming && <label className="check-row"><input type="checkbox" checked={p.accepted} onChange={event => p.setAccepted(event.target.checked)} />I accept these test terms.</label>}
          <button type="button" disabled={p.blocked || !allowed || !p.accepted || expired || (p.view === "purchase" && !p.demo && !p.validPhone)} onClick={() => { if (p.view === "apply" && !confirming) setConfirming(true); else p.submit(); }}>{p.busy ? "Submitting…" : p.view === "apply" ? confirming ? "Submit application" : "Continue →" : "Confirm purchase"}</button>
          <button type="button" className="secondary" disabled={p.busy} onClick={() => { p.clearQuote(); setConfirming(false); }}>Edit amount</button>
        </section>}
      </>}
      {p.view === "purchase" && p.payments.filter(row => row.purpose === "PURCHASE" && row.environment === p.environment).slice(0, 5).map(paymentCard)}
      {p.view === "apply" && p.notice && <button className="secondary" onClick={() => p.navigate("loans")}>View loan decision →</button>}
    </>}

    {p.view === "activity" && <><h2>Payments & receipts</h2><div className="receipt-filters" aria-label="Receipt filters">{([['all', 'All'], ['PURCHASE', 'Purchases'], ['LOAN_REPAYMENT', 'Repayments']] as const).map(([value, name]) => <button key={value} className="secondary" aria-pressed={filter === value} onClick={() => setFilter(value)}>{name}</button>)}</div>{p.payments.filter(row => filter === "all" || row.purpose === filter).map(paymentCard)}{p.fetched && !p.payments.some(row => filter === "all" || row.purpose === filter) && <p className="muted">No matching payments yet.</p>}</>}
  </section>;
}
