"use client";

import { useEffect, useState, type FormEvent } from "react";
import { demoCountdown, type Assessment, type SandboxCapabilities, type TestCurrency, type TestEnvironment,
  testMoney, type TestLoan, type TestMeter, type TestPayment, type TestPolicy, type TestQuote, type PricingStatus } from "../lib/sandbox";

import { EnergyTokenCard } from "./energy-token-card";
import type { SandboxClient } from "../lib/sandbox";
import { TariffDetails } from "./tariff-details";
import { financeBackAction } from "../lib/finance-navigation";
import { exactDifference, formatEnergy, formatMoney } from "../lib/sandbox-presentation";
import { quoteAvailabilityReason } from "../lib/quote-availability";

export type ConsumerFinanceView = "home" | "loans" | "apply" | "purchase" | "activity" | "hidden";
export type FinanceDestination = "loans" | "apply" | "purchase" | "activity" | "meters";
export type MobileFinanceProps = {
  client: SandboxClient; owner: number;
  view: ConsumerFinanceView; navigate: (view: FinanceDestination) => void;
  surface?: "web" | "mobile";
  registerBackHandler?: (handler: (() => boolean) | null) => void;
  loanCurrency?: TestCurrency; loanEnvironment?: TestEnvironment; paymentCurrency?: TestCurrency; paymentEnvironment?: TestEnvironment;
  validPaymentAmount?: (value: string) => boolean; initializeAssessment?: () => void;
  demo: boolean; currency: TestCurrency; environment: TestEnvironment; capabilities: SandboxCapabilities;
  pricingStatus: PricingStatus; loanReason: string | null; setupError?: string | null;
  assessment: Assessment | null; assessmentPolicy?: TestPolicy | null; policy: TestPolicy | null; loans: TestLoan[]; payments: TestPayment[];
  meters: TestMeter[]; selectedMeter: TestMeter | null; setSelectedMeter: (id: string) => void;
  onAddMeter?: () => void; purpose: "LOAN" | "PURCHASE";
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
const when = (value: string | null | undefined) => value && Number.isFinite(Date.parse(value)) ? new Date(value).toLocaleString() : "Unavailable";
const label = (status: string) => ({ DISBURSED: "Active", COMPLETED: "Repaid", REJECTED: "Not approved", SETTLED: "Completed", PENDING: "Pending", FAILED: "Failed" }[status] ?? status.toLowerCase().replaceAll("_", " ").replace(/\b\w/g, value => value.toUpperCase()));
function InfoRow({ title, value }: { title: string; value: string }) { return <div className="review-row"><span>{title}</span><strong>{value}</strong></div>; }
function CopyReference({ value }: { value: string }) {
  const [notice, setNotice] = useState("");
  return <div className="reference"><p>Reference: {value}</p><button type="button" className="secondary" onClick={() => {
    if (!navigator.clipboard?.writeText) { setNotice("Select the reference to copy it."); return; }
    void navigator.clipboard.writeText(value).then(() => setNotice("Reference copied.")).catch(() => setNotice("Select the reference to copy it."));
  }}>Copy reference</button>{notice && <small role="status">{notice}</small>}</div>;
}

export default function SandboxMobileView(p: MobileFinanceProps) {
  const web = p.surface === "web";
  const money = (value: string | null | undefined, currency: TestCurrency) => web ? formatMoney(value, currency) : testMoney(value, currency);
  const energy = (value: string | null | undefined) => web ? formatEnergy(value) : value == null ? "Unavailable" : `${value} kWh`;
  const [repaymentContext, setRepaymentContext] = useState<{ loan: string; receipt: string | null } | null>(null);
  const [reviewRepayment, setReviewRepayment] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [filter, setFilter] = useState<"all" | "PURCHASE" | "LOAN" | "LOAN_REPAYMENT">("all");
  const [activityPage, setActivityPage] = useState(1);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [printing, setPrinting] = useState(false);
  const eligibleMeters = p.meters.filter(meter => meter.sandbox_inventory);
  const loanEnvironment = p.loanEnvironment ?? p.capabilities.loanEnvironment ?? p.environment;
  const loanCurrency = p.loanCurrency ?? p.capabilities.loanCurrency ?? p.currency;
  const assessmentPolicy = p.assessmentPolicy ?? p.policy;
  const paymentEnvironment = p.paymentEnvironment ?? p.environment;
  const paymentCurrency = p.paymentCurrency ?? p.currency;
  const validPaymentAmount = p.validPaymentAmount ?? p.validAmount;
  const repaymentAllowed = (loan: TestLoan) => loan.currency === paymentCurrency && loan.environment === paymentEnvironment && loan.repayment_available !== false && p.capabilities.repayments;
  const currentLoans = p.loans.filter(loan => loan.environment === loanEnvironment);
  const oldLoans = p.loans.filter(loan => loan.environment !== loanEnvironment);
  const currentLoan = currentLoans.find(loan => loan.status === "DISBURSED");
  const selectedLoan = p.loans.find(loan => loan.id === p.loanId && loan.status === "DISBURSED" && repaymentAllowed(loan));
  const ready = p.assessment && p.assessment.score !== null && (!p.assessment.assessment_status || p.assessment.assessment_status === "READY");
  const score = ready && !p.assessment?.starter ? p.assessment?.score : null;
  const allowed = p.purpose === "LOAN" ? p.capabilities.loans : p.capabilities.purchases;
  const reviewReason = quoteAvailabilityReason({ busy: p.busy, refreshing: p.refreshing, offline: p.offline, unresolved: p.unresolved,
    pending: p.pending, blocked: p.blocked, policy: p.policy !== null, allowed, pricing: p.pricingStatus, validAmount: p.validAmount(p.amount),
    purpose: p.purpose, assessmentReady: Boolean(ready), loanReason: p.loanReason, setupError: p.setupError,
    capabilityReason: (p.purpose === "LOAN" ? p.capabilities.loanMessage : p.capabilities.purchaseMessage) || p.capabilities.paymentMessage });
  const activeQuote = p.quote?.terms.purpose === p.purpose ? p.quote : null;
  const expired = activeQuote ? Date.parse(activeQuote.expires_at) <= p.clock : false;
  const confirmationReason = reviewReason || (expired ? "This quote expired. Get fresh terms." : !p.accepted ? "Accept the displayed terms to continue." :
    p.view === 'purchase' && !p.demo && !p.validPhone ? "Enter the MTN sandbox test number (10–15 digits)." : null);
  const repaymentReviewReason = p.busy ? "A request is in progress." : p.offline ? "Reconnect to repay." : p.unresolved ? "Refresh to reconcile the previous request." :
    p.pending ? "Wait for the pending payment’s confirmed outcome." : p.refreshing ? "Refreshing loan balances…" :
    !p.capabilities.repayments ? p.capabilities.repaymentMessage || p.capabilities.paymentMessage || "Repayments are disabled by the server." :
    !selectedLoan ? "Choose an active loan in the payment currency. EUR receipts cannot repay UGX debt." :
    !validPaymentAmount(p.repayment) ? "Enter a positive repayment in the displayed currency and precision." :
    p.blocked ? "Account capabilities are unavailable. Refresh to retry." : null;
  const repaymentConfirmationReason = repaymentReviewReason || (!p.repayAccepted ? "Accept the repayment terms to continue." :
    !p.demo && !p.validPhone ? "Enter the MTN sandbox test number (10–15 digits)." : null);
  const lastRepayment = (id: string) => p.payments.find(row => row.loan_id === id)?.reference ?? null;
  const showRepayment = !!repaymentContext && !!selectedLoan && repaymentContext.loan === p.loanId &&
    repaymentContext.receipt === lastRepayment(p.loanId);
  const activityRows = [
    ...currentLoans.filter(loan => web || loan.status === "DISBURSED" || loan.status === "COMPLETED")
      .map(loan => ({ kind: "LOAN" as const, id: loan.id, date: loan.created_at ?? loan.due_at, loan })),
    ...p.payments.filter(payment => payment.environment === paymentEnvironment)
      .map(payment => ({ kind: payment.purpose as "PURCHASE" | "LOAN_REPAYMENT", id: payment.reference, date: payment.initiated_at, payment })),
  ].sort((a, b) => Date.parse(b.date) - Date.parse(a.date));
  const filteredActivity = activityRows.filter(row => {
    const date = Number.isFinite(Date.parse(row.date)) ? new Date(row.date).toISOString().slice(0, 10) : "";
    return (filter === "all" || row.kind === filter) && (!startDate || date >= startDate) && (!endDate || date <= endDate);
  });
  const activityPageSize = 10;
  const activityPages = Math.max(1, Math.ceil(filteredActivity.length / activityPageSize));
  const visibleActivity = filteredActivity.slice((activityPage - 1) * activityPageSize, activityPage * activityPageSize);
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
  const disclosure = p.demo ? (web ? "Demo payment — no real money will be deducted." : "Demo payment: no real money is deducted and no phone PIN is required.") : "MTN sandbox payment in EUR TEST. No real money is collected.";
  const phoneField = !p.demo && <label>MTN sandbox number<input inputMode="numeric" autoComplete="off" value={p.phone} onChange={e => p.setPhone(e.target.value)} required /><small className="muted">Use your configured test scenario number, 10–15 digits. Never enter a PIN.</small></label>;
  const assessmentCard = <section className="panel credit-summary" aria-label="Credit overview">
    <div className="section-title"><h2>Credit overview</h2>{ready && <span className={`status-pill ${p.assessment?.eligible ? "" : "pending"}`}>{p.assessment?.eligible ? "Eligible" : "Not eligible"}</span>}</div>
    <div className="credit-summary-grid"><div><span className="muted">Credit score</span><strong className="credit-score">{!p.fetched ? "…" : score ?? "—"}{score != null && <small>%</small>}</strong></div><div><span className="muted">Borrowing limit</span><strong className="credit-limit">{money(p.assessment?.maximum, loanCurrency)}</strong><button type="button" className="text-button" onClick={() => p.navigate("apply")}>View loan options →</button></div></div>
    {p.assessment?.reason && <p className="muted small">{p.assessment.reason}</p>}
    {!ready && p.fetched && <p className="muted">Assessment {p.assessment?.assessment_status?.toLowerCase() || "unavailable"}. Link your meter and refresh.</p>}
    {!ready && p.selectedMeter && p.initializeAssessment && <button type="button" className="secondary" disabled={p.busy || p.offline} onClick={p.initializeAssessment}>Initialize automatic assessment</button>}
    {p.assessment?.starter && <p className="muted small">Starter allowance; no established credit score yet.</p>}
    <details className="info-disclosure"><summary>How your score is calculated</summary>
      <p>{loanCurrency === "UGX" ? "Demo assessment — simulated account information." : "Sandbox assessment."} No questionnaire is needed.</p>
      {Object.entries(p.assessment?.factors ?? {}).map(([key, value]) => <InfoRow key={key} title={key.replaceAll("_", " ")} value={`${value}${p.assessment?.categories?.[key] ? ` · ${p.assessment.categories[key]}` : ""}`} />)}
      <InfoRow title="Purchase contribution" value={p.assessment?.purchase_points == null ? "Unavailable" : `${p.assessment.purchase_points} points`} />
      <p className="small">Assessed {when(p.assessment?.assessed_at)} · {p.assessment?.scoring_policy_version || p.assessment?.policy_id}</p>
      {assessmentPolicy && <p className="small">Settled billed purchases: {money(p.assessment?.qualifying_billed_test ?? p.assessment?.qualifying_billed_eur, loanCurrency)}. One point per {money(assessmentPolicy.purchase_per_point, loanCurrency)}, capped at {assessmentPolicy.purchase_score_cap}. Refreshing does not award points.</p>}
    </details>
  </section>;

  const paymentCard = (row: TestPayment) => <article className="panel payment-card" key={row.reference}>
    <div className="section-title"><h3>{row.purpose === "PURCHASE" ? "Electricity purchase" : "Loan repayment"}</h3><span className={`status-pill ${row.status === "PENDING" ? "pending" : row.status === "FAILED" ? "neutral" : ""}`}>{label(row.status)}</span></div>
    <strong className="payment-amount">{money(row.amount, row.currency)}</strong><p className="muted small">{when(row.initiated_at)} · {row.currency === "UGX" ? "UGX demo" : "EUR test"}</p>
    {row.status === "PENDING" && row.environment === "UGX_DEMO" && <div className="payment-progress" role="status"><span className="loading-spinner" /><div><strong>Processing payment</strong><p>{(demoCountdown(row, p.clock) ?? 0) > 0 ? `Please wait · ${demoCountdown(row, p.clock)} seconds` : "Waiting for server confirmation"}</p><small>No real money or phone PIN is required.</small></div></div>}
    {row.status === "PENDING" && row.environment === "MTN_SANDBOX" && <p role="status">Waiting for MTN sandbox confirmation. Closing this app will not start another charge.</p>}
    {row.status === "SETTLED" && <p className="small">{row.environment === "UGX_DEMO" ? "Demo payment successful. No real money was deducted." : "Sandbox payment verified."}</p>}
    {row.status === "SETTLED" && row.purpose === "PURCHASE" && row.environment === "MTN_SANDBOX" && <p className="muted small">Payment confirmed; cloud allocation recorded. Saving credit requires a commissioned SANDBOX/GPAWA_PZEM_V2 device and its application acknowledgement.</p>}
    {row.status === "SETTLED" && row.purpose === "PURCHASE" && <EnergyTokenCard compact={web} client={p.client} owner={p.owner} allocationId={row.allocation_id} />}
    {row.status === "FAILED" && <p className="muted">Payment failed. Review the receipt before trying again.</p>}
    {row.status === "PENDING" && row.environment !== p.environment && <p className="muted small">This earlier payment belongs to a different test environment. It has not been cancelled or converted.</p>}
    <details className="info-disclosure"><summary>Receipt details</summary>{web ? <CopyReference value={row.reference} /> : <p className="reference">Reference: {row.reference}</p>}<InfoRow title="Meter" value={p.meters.find(meter => meter.id === row.meter_id)?.meter_number ?? `Meter ID ${row.meter_id}`} />
      {row.purpose === "PURCHASE" ? <><InfoRow title="Billed amount" value={money(row.billed, row.currency)} /><InfoRow title="Rounding remainder" value={money(row.residual, row.currency)} /><InfoRow title="Cloud energy allocated" value={row.allocated_kwh == null ? "Unavailable" : `${row.allocated_kwh} kWh`} /></> : <><InfoRow title="Applied to debt" value={money(row.applied, row.currency)} /><InfoRow title="Excess received" value={money(row.excess, row.currency)} /></>}
      <TariffDetails pricing={row.pricing} currency={row.currency} />
      <p className="muted small">Remainders and excess are recorded for reconciliation. Cloud allocation does not confirm physical delivery.</p><InfoRow title="Settled" value={when(row.settled_at)} /><p className="small">{row.environment} · {label(row.submission_state)}</p>{row.reconciliation_error && <p className="error">{row.reconciliation_error}</p>}
    </details>
    {row.status === "PENDING" && <button type="button" className="secondary" disabled={p.busy || p.refreshing || p.offline || (row.environment === "UGX_DEMO" && demoCountdown(row, p.clock) !== 0)} onClick={() => p.checkPayment(row)}>Check payment status</button>}
  </article>;

  const loanCard = (loan: TestLoan, historical = false) => <article className="panel loan-card" key={loan.id}>
    <div className="section-title"><h3>Electricity loan</h3><span className={`status-pill ${loan.status === "REJECTED" ? "pending" : "neutral"}`}>{label(loan.status)}</span></div>
    <p className="muted small">Meter {p.meters.find(meter => meter.id === loan.meter_id)?.meter_number ?? loan.meter_id}{historical ? ` · ${loan.currency} test history` : ""}</p>
    <span className="muted small">Outstanding balance</span><strong className="loan-balance">{money(loan.outstanding, loan.currency)}</strong>
    <InfoRow title={web && loan.status === "REJECTED" ? "Requested principal" : "Principal"} value={money(loan.principal, loan.currency)} />
    {web ? <>
      <InfoRow title={loan.status === "REJECTED" ? "Quoted total (not owed)" : "Total due"} value={money(loan.total_due, loan.currency)} />
      <InfoRow title="Repayments applied" value={money(loan.applied_repayments ?? exactDifference(loan.total_due, loan.outstanding), loan.currency)} />
      <InfoRow title="Due date" value={when(loan.due_at)} />
    </> : <><InfoRow title="Total repayment" value={money(loan.total_due, loan.currency)} /><InfoRow title="Due" value={when(loan.due_at)} /></>}
    {(!web || loan.status === "REJECTED") && <p className="muted small">{loan.reason}</p>}
    {web && loan.status !== "REJECTED" && !loan.allocation_id && <p className="muted small">Token unavailable for this historical transaction.</p>}
    {loan.allocation_id && <EnergyTokenCard compact={web} client={p.client} owner={p.owner} allocationId={loan.allocation_id} />}
    {loan.status === "DISBURSED" && !repaymentAllowed(loan) && <p role="status">{loan.repayment_message || `${loan.currency} debt cannot be repaid with ${paymentCurrency} payments. Same-currency servicing is unavailable in this mode; your existing obligation is preserved.`}</p>}
    {repaymentAllowed(loan) && loan.status === "DISBURSED" && <button type="button" className="primary-button" disabled={!p.capabilities.repayments || (web && Number(loan.outstanding) <= 0)} onClick={() => chooseRepayment(loan)}>{web ? "Make a repayment" : "Pay Loan →"}</button>}
    <details className="info-disclosure"><summary>Loan details & repayments</summary>{web ? <CopyReference value={loan.id} /> : <p className="reference">Reference: {loan.id}</p>}{web && <p>{loan.reason}</p>}<InfoRow title="Accepted policy" value={loan.terms.policy.id} /><TariffDetails pricing={loan.terms.pricing} currency={loan.currency} /><InfoRow title="Cloud allocation" value={loan.allocated_kwh == null ? (web ? "Unavailable" : "None") : web ? energy(loan.allocated_kwh) : `${loan.allocated_kwh} kWh`} /><InfoRow title="Closed" value={when(loan.closed_at)} />
      {p.payments.filter(row => row.loan_id === loan.id).map(row => <div className="list-row" key={row.reference}><span>{label(row.status)}<small>Applied {money(row.applied, row.currency)} · excess {money(row.excess, row.currency)}</small></span><strong>{money(row.amount, row.currency)}</strong></div>)}
      <p className="muted small">Cloud allocation is separate from physical meter delivery.</p>
    </details>
  </article>;

  if (p.view === "hidden") return null;
  return <section className="mobile-finance" aria-label="Energy finance">
    {(!web || p.view !== "purchase") && <div className="finance-toolbar"><span className="muted small">{p.refreshing ? "Updating…" : p.fetched ? `Updated ${new Date(p.fetched).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : "Loading your account…"}</span><button type="button" className="text-button" disabled={p.busy || p.refreshing} onClick={p.refresh}>Refresh</button></div>}
    {(p.offline || (p.error && p.fetched)) && <p className="stale" role="status">Displayed records may be out of date. Last updated {when(p.fetched)}.</p>}
    {p.error && (web && p.view === "activity"
      ? <div className="error" role="alert"><p>Couldn’t load transactions.</p><button className="secondary" type="button" onClick={p.refresh}>Retry</button></div>
      : <p className="error" role="alert">{p.error}</p>)}{p.notice && !(p.pending && p.notice.startsWith("Demo payment:")) && <p className="tag" role="status">{p.notice}</p>}
    {p.unresolved && <p className="muted small">A previous request needs checking. Refresh before starting another.</p>}
    {p.capabilities.paymentMessage && <p role="status">{p.capabilities.paymentMessage}</p>}
    {p.pending && <div className="pending-summary"><strong>Payment pending</strong><p>We’re waiting for its confirmed outcome before allowing another payment.</p>{p.view === "home" && <button className="text-button" onClick={() => p.navigate("activity")}>View payment →</button>}</div>}

    {p.view === "home" && <>{assessmentCard}{currentLoan ? loanCard(currentLoan) : p.fetched && <section className="panel"><h2>No active loan</h2><p className="muted">Review your options when you need electricity credit.</p><button className="secondary" onClick={() => p.navigate("apply")}>Apply for Loan →</button></section>}
      <div className="section-title"><h2>Recent activity</h2><button className="text-button" onClick={() => p.navigate("activity")}>View all</button></div>{p.payments.length ? p.payments.slice(0, 2).map(paymentCard) : <p className="muted">{p.fetched ? "No payments yet." : "Loading payments…"}</p>}
    </>}

    {(p.view === "loans" || p.view === "apply") && <div className="segmented-control" aria-label="Loan section"><button aria-pressed={p.view === "loans"} onClick={() => { setRepaymentContext(null); p.navigate("loans"); }}>My Loans</button><button aria-pressed={p.view === "apply"} onClick={() => { setConfirming(false); p.navigate("apply"); }}>Apply for Loan</button></div>}
    {p.view === "loans" && <>
      {showRepayment && !p.pending ? <section className="panel"><button type="button" className="text-button" onClick={() => setRepaymentContext(null)}>← My Loans</button><h2>Pay Loan</h2>
        {(reviewRepayment ? repaymentConfirmationReason : repaymentReviewReason) && <p role="status">{reviewRepayment ? repaymentConfirmationReason : repaymentReviewReason}</p>}
        <form className="form-panel" onSubmit={event => { if (!reviewRepayment) { event.preventDefault(); setReviewRepayment(true); } else p.repay(event); }}>
          {!reviewRepayment ? <><label>Your loan<select value={p.loanId} onChange={event => { p.selectLoan(event.target.value); setRepaymentContext({ loan: event.target.value, receipt: lastRepayment(event.target.value) }); setReviewRepayment(false); }} required><option value="">Choose a loan</option>{p.loans.filter(loan => loan.status === "DISBURSED" && repaymentAllowed(loan)).map(loan => <option key={loan.id} value={loan.id}>{money(loan.outstanding, loan.currency)} · {loan.id}</option>)}</select></label>{selectedLoan && <InfoRow title="Outstanding" value={money(selectedLoan.outstanding, paymentCurrency)} />}<label>Repayment amount ({paymentCurrency})<input inputMode={p.demo ? "numeric" : "decimal"} value={p.repayment} onChange={event => { p.setRepayment(event.target.value); p.setRepayAccepted(false); }} required /></label><button type="submit" disabled={repaymentReviewReason !== null}>Review repayment →</button></> : <>
            <InfoRow title="Repayment amount" value={money(p.repayment, paymentCurrency)} /><InfoRow title="Outstanding" value={money(selectedLoan?.outstanding, paymentCurrency)} /><p className="muted small">Repayment reduces this loan only. Any excess is recorded for reconciliation, with no automatic refund or energy credit.</p>{phoneField}<p className="payment-disclosure">{disclosure}</p><label className="check-row"><input type="checkbox" checked={p.repayAccepted} onChange={event => p.setRepayAccepted(event.target.checked)} />I accept these test repayment terms.</label><button type="submit" disabled={repaymentConfirmationReason !== null}>{p.busy ? "Submitting…" : "Confirm repayment"}</button><button type="button" className="secondary" disabled={p.busy} onClick={() => { setReviewRepayment(false); p.setRepayAccepted(false); }}>Edit amount</button>
          </>}
        </form>
      </section> : <>{!p.fetched ? <p role="status">Loading loans…</p> : currentLoans.length ? web ? <>
        {currentLoans.filter(loan => loan.status === "DISBURSED").map(loan => loanCard(loan))}
        {currentLoans.some(loan => loan.status !== "DISBURSED") && <section className="panel"><h2>Completed and declined</h2>
          {currentLoans.filter(loan => loan.status !== "DISBURSED").map(loan => loanCard(loan))}</section>}
      </> : currentLoans.map(loan => loanCard(loan)) : <section className="panel empty-card"><h2>No loan applications yet</h2><p className="muted">See your borrowing options and review the terms.</p><button onClick={() => p.navigate("apply")}>Apply for Loan</button></section>}</>}
      {p.payments.filter(row => row.purpose === "LOAN_REPAYMENT" && row.environment === p.environment).slice(0, 5).map(paymentCard)}
      {oldLoans.length > 0 && <details className="panel info-disclosure"><summary>Earlier test-currency loans</summary>{oldLoans.map(loan => loanCard(loan, true))}</details>}
    </>}

    {(p.view === "apply" || p.view === "purchase") && <>
      {p.view === "apply" && p.capabilities.loans && <ol className="loan-stepper">{["Amount", "Terms", "Confirm"].map((name, index) => { const step = !activeQuote ? 0 : confirming ? 2 : 1; return <li key={name} className={index === step ? "current" : index < step ? "done" : ""} aria-current={index === step ? "step" : undefined}><span>{index + 1}</span>{name}</li>; })}</ol>}
      {p.view === "apply" && !p.capabilities.loans && <section className="panel" role="status"><h2>Loan applications unavailable</h2><p>{p.capabilities.loanMessage || p.loanReason || "The server has not enabled loan applications in this mode."}</p><p>Existing loans remain in My Loans. No questionnaire, currency conversion or fallback approval is available.</p><button type="button" className="secondary" onClick={() => p.navigate("loans")}>My Loans</button></section>}
      {!web && p.view === "apply" && p.loanReason && p.capabilities.loans && <p className="muted" role="status" id="loan-eligibility-reason">{p.loanReason}</p>}
      {web && p.view === "apply" && <label>Meter<select value={p.selectedMeter?.sandbox_inventory ? String(p.selectedMeter.id) : ""} onChange={event => p.setSelectedMeter(event.target.value)} required>
        <option value="">{eligibleMeters.length ? "Choose a meter" : "No meter linked"}</option>
        {eligibleMeters.map(meter => <option key={meter.id} value={meter.id}>{meter.meter_number}</option>)}
      </select></label>}
      {p.view === "purchase" && p.capabilities.newPaymentsPaused ? <section className="panel" role="status"><h2>UGX purchases unavailable</h2><p>New payments are paused while MTN Sandbox accepts EUR only. A compatible UGX payment provider is required.</p><p>Existing receipts and pending payments remain below. No new charge will be started.</p></section> : p.view === "apply" && !p.capabilities.loans ? null : !p.selectedMeter?.sandbox_inventory ? web ? <section className="panel empty-card">
        {p.view === "purchase" && eligibleMeters.length > 0 && <label>Meter<select value="" onChange={event => p.setSelectedMeter(event.target.value)} required>
          <option value="">Choose a meter</option>{eligibleMeters.map(meter => <option key={meter.id} value={meter.id}>{meter.meter_number}</option>)}
        </select></label>}
        <p className="muted">{eligibleMeters.length ? "Choose a meter to continue." : "Add a meter to buy units or request a loan."}</p>
        {eligibleMeters.length === 0 && p.onAddMeter && <button type="button" onClick={p.onAddMeter}>Add a meter</button>}
      </section> : <section className="panel empty-card"><h2>Select your meter</h2><p className="muted">Link or select a meter before continuing.</p><button onClick={() => p.navigate("meters")}>Choose meter →</button></section> : <>
        {p.view === "apply" && assessmentCard}
        {!allowed && <p className="muted" role="status">{(p.view === "apply" ? p.capabilities.loanMessage : p.capabilities.purchaseMessage) || p.capabilities.paymentMessage || "This action is disabled by the server. Refresh to check again."}</p>}
        {!p.pricingStatus.available && <p className="error" role="status">{p.pricingStatus.message}</p>}
        {!activeQuote && reviewReason && <p id="quote-availability-reason" role="status">{reviewReason}</p>}
        {!activeQuote ? !p.pending &&         <form className="panel form-panel" onSubmit={event => { setConfirming(false); p.getQuote(event); }}><h2>{web ? p.view === "apply" ? "Request a loan" : "Buy Units" : p.view === "apply" ? "How much do you need?" : "How much would you like to buy?"}</h2>{web && p.view === "purchase" && <label>Meter<select value={String(p.selectedMeter.id)} onChange={event => p.setSelectedMeter(event.target.value)} required>{eligibleMeters.map(meter => <option key={meter.id} value={meter.id}>{meter.meter_number}</option>)}</select></label>}<label>Amount ({p.currency})<input aria-label={p.currency === "UGX" ? "Amount (UGX)" : "Amount (EUR TEST)"} inputMode={p.currency === "UGX" ? "numeric" : "decimal"} value={p.amount} onChange={event => p.setAmount(event.target.value)} required /></label>{!web && <p className="muted small">{p.currency === "UGX" ? "Enter whole shillings." : "Use EUR test amounts."} Range {money(p.policy?.minimum, p.currency)}–{money(p.policy?.maximum, p.currency)}.</p>}{p.view === "apply" && web && <p className="muted small">Borrowing limit: {money(p.assessment?.maximum, loanCurrency)}.</p>}{p.view === "apply" && !web && <p className="muted small">Your limit: {money(p.assessment?.maximum, loanCurrency)}. Eligibility is checked when you submit.</p>}{web && p.view === "apply" && p.loanReason && <p id="loan-eligibility-reason" className="eligibility-reason" role="status">{p.loanReason}</p>}<button type="submit" aria-describedby={web && p.view === "apply" && p.loanReason ? "loan-eligibility-reason" : undefined} disabled={reviewReason !== null}>{p.busy ? "Getting quote…" : web ? p.view === "apply" ? "Review terms" : "Review terms" : "Review terms →"}</button></form> : <section className="panel form-panel"><h2>{p.view === "apply" ? confirming ? "Confirm your application" : "Review loan terms" : "Review your purchase"}</h2>
          <div className="quote-summary"><InfoRow title={p.view === "apply" ? "Loan principal" : "Payment amount"} value={money(activeQuote.terms.amount, p.currency)} /><InfoRow title={web ? "Estimated energy" : "Cloud energy"} value={energy(activeQuote.terms.energy_kwh)} />{web && p.view === "purchase" && <InfoRow title="Quoted total" value={money(activeQuote.terms.pricing?.breakdown.total ?? activeQuote.terms.billed, p.currency)} />}{p.view === "apply" && <><InfoRow title={`Interest (${activeQuote.terms.policy.interest_percent}%)`} value={money(activeQuote.terms.interest, p.currency)} /><InfoRow title="Fee" value={money(activeQuote.terms.fee, p.currency)} />{web ? <InfoRow title="Due date" value={when(activeQuote.terms.due_at ?? null)} /> : <InfoRow title="Loan term" value={`${activeQuote.terms.policy.due_days} days`} />}<div className="quote-total"><span>{web ? "Total due" : "Total repayment"}</span><strong>{money(activeQuote.terms.total_due, p.currency)}</strong></div></>}</div>
          {p.view === 'apply' && activeQuote.terms.policy.repayment_message && <p role="status">{activeQuote.terms.policy.repayment_message} This is prototype lending with simulated assessment evidence.</p>}
          <details className="info-disclosure"><summary>Pricing & policy details</summary>{activeQuote.terms.pricing ? <TariffDetails pricing={activeQuote.terms.pricing} currency={p.currency} /> : <InfoRow title="Original fixed price per kWh" value={money(activeQuote.terms.policy.rate_per_kwh, p.currency)} />}<InfoRow title="Billed" value={money(activeQuote.terms.billed, p.currency)} /><InfoRow title="Rounding remainder" value={money(activeQuote.terms.residual, p.currency)} /><p>Remainder retained for reconciliation; no automatic refund or energy conversion.</p><p>{activeQuote.terms.policy.rounding} · {activeQuote.terms.policy.id}</p><p>Overdue charge {activeQuote.terms.policy.penalty_percent}%. Cloud allocation does not confirm physical delivery.</p></details>
          <p className={expired ? "error" : "muted small"}>{expired ? "This quote expired. Get a fresh quote." : `Quote valid until ${when(activeQuote.expires_at)}`}</p>
          {p.view === "purchase" && phoneField}<p className="payment-disclosure">{p.view === "apply" ? "Test loan — cloud allocation only; no physical meter delivery." : disclosure}</p>
          {!confirming && <label className="check-row"><input type="checkbox" checked={p.accepted} onChange={event => p.setAccepted(event.target.checked)} />I accept these test terms.</label>}
          {confirmationReason && <p role="status">{confirmationReason}</p>}
          <button type="button" disabled={confirmationReason !== null} onClick={() => { if (p.view === "apply" && !confirming) setConfirming(true); else p.submit(); }}>{p.busy ? "Submitting…" : p.view === "apply" ? confirming ? "Submit application" : "Continue →" : "Confirm purchase"}</button>
          <button type="button" className="secondary" disabled={p.busy} onClick={() => { p.clearQuote(); setConfirming(false); }}>Edit amount</button>
        </section>}
      </>}
      {p.view === "purchase" && p.payments.filter(row => row.purpose === "PURCHASE" && row.environment === paymentEnvironment).slice(0, 5).map(paymentCard)}
      {p.view === "apply" && p.notice && <button className="secondary" onClick={() => p.navigate("loans")}>View loan decision →</button>}
    </>}

    {web && p.view === "activity" && <><h2>History</h2>
      {p.fetched && <div className="finance-summary" aria-label="Records in this loaded history">
        <div><span>Purchases</span><strong>{filteredActivity.filter(row => row.kind === "PURCHASE").length}</strong></div>
        <div><span>Loan disbursements</span><strong>{filteredActivity.filter(row => row.kind === "LOAN").length}</strong></div>
        <div><span>Repayments</span><strong>{filteredActivity.filter(row => row.kind === "LOAN_REPAYMENT").length}</strong></div>
      </div>}
      <div className="receipt-filters" aria-label="Transaction filters">{([["all", "All"], ["PURCHASE", "Purchases"], ["LOAN", "Loan decisions"], ["LOAN_REPAYMENT", "Repayments"]] as const).map(([value, name]) => <button key={value} className="secondary" aria-pressed={filter === value} onClick={() => { setFilter(value); setActivityPage(1); }}>{name}</button>)}</div>
      <div className="activity-filters"><label>From<input type="date" value={startDate} onChange={event => { setStartDate(event.target.value); setActivityPage(1); }} /></label>
        <label>To<input type="date" value={endDate} onChange={event => { setEndDate(event.target.value); setActivityPage(1); }} /></label>
        <button type="button" className="secondary" onClick={() => { setFilter("all"); setStartDate(""); setEndDate(""); setActivityPage(1); }}>Reset filters</button>
        <button type="button" className="secondary" onClick={() => { setPrinting(true); window.setTimeout(() => { window.print(); setPrinting(false); }, 100); }}>Print statement</button>
      </div>
      {!p.fetched && !p.error ? <p role="status">Loading transactions…</p> : p.fetched ? <>
        {visibleActivity.map(row => row.kind === "LOAN" ? <article className="panel transaction-card" key={row.id}>
          <div className="section-title"><h3>Loan decision · electricity</h3><span className="status-pill">{label(row.loan.status)}</span></div>
          <p className="muted small">{when(row.loan.created_at)} · Meter {p.meters.find(meter => meter.id === row.loan.meter_id)?.meter_number ?? row.loan.meter_id}</p>
          <strong>{money(row.loan.principal, row.loan.currency)}</strong>
          <p>{row.loan.status === "REJECTED" ? "No energy allocated." : `${energy(row.loan.allocated_kwh)} allocated to cloud entitlement; this is not cash.`}</p>
          <details className="info-disclosure"><summary>View details</summary><CopyReference value={row.loan.id} /><InfoRow title="Total due" value={money(row.loan.total_due, row.loan.currency)} /><InfoRow title="Outstanding" value={money(row.loan.outstanding, row.loan.currency)} /><p>{row.loan.reason}</p></details>
        </article> : <article className="panel transaction-card" key={row.id}>
          <div className="section-title"><h3>{row.kind === "PURCHASE" ? "Electricity purchase" : "Loan repayment"}</h3><span className={`status-pill ${row.payment.status === "PENDING" ? "pending" : ""}`}>{label(row.payment.status)}</span></div>
          <p className="muted small">{when(row.payment.initiated_at)} · Meter {p.meters.find(meter => meter.id === row.payment.meter_id)?.meter_number ?? row.payment.meter_id}</p>
          <strong>{money(row.payment.amount, row.payment.currency)}</strong>
          {row.kind === "PURCHASE" ? <p>{row.payment.status === "SETTLED" ? energy(row.payment.allocated_kwh) : "Energy pending settlement"} · Purchase</p>
            : <p>{row.payment.status === "SETTLED" ? `Applied to debt ${money(row.payment.applied, row.payment.currency)} · no energy created` : "No debt reduction until settled"}</p>}
          <details className="info-disclosure"><summary>View receipt</summary><CopyReference value={row.payment.reference} />
            {row.kind === "PURCHASE" && row.payment.status === "SETTLED" && row.payment.allocation_id == null && <p>Token unavailable for this historical transaction.</p>}{row.kind === "PURCHASE" && row.payment.status === "SETTLED" && <EnergyTokenCard compact={web} client={p.client} owner={p.owner} allocationId={row.payment.allocation_id} />}
            {row.kind === "LOAN_REPAYMENT" && <><InfoRow title="Loan" value={row.payment.loan_id ?? "Unavailable"} /><InfoRow title="Applied" value={money(row.payment.applied, row.payment.currency)} /></>}
          </details>
        </article>)}
        {p.payments.some(row => row.environment !== paymentEnvironment) && <details className="panel info-disclosure"><summary>Earlier test-currency receipts</summary>{p.payments.filter(row => row.environment !== paymentEnvironment).map(paymentCard)}</details>}
        {!filteredActivity.length && <p className="muted">No transactions yet.</p>}
        <p className="muted small">Showing the latest 100 loans and payments, plus older active loans and pending payments. History counts are not account totals.</p>
        {activityPages > 1 && <div className="activity-pagination"><button className="secondary" disabled={activityPage <= 1} onClick={() => setActivityPage(page => page - 1)}>Previous</button><span>Page {activityPage} of {activityPages}</span><button className="secondary" disabled={activityPage >= activityPages} onClick={() => setActivityPage(page => page + 1)}>Next</button></div>}
      </> : null}</>}
    {p.view === "activity" && printing && <div className="statement-print">
      <h1>EnergyFlex transaction statement</h1><p>{p.environment} · {startDate || "All time"} to {endDate || "Now"}</p>
      <table><thead><tr><th>Date</th><th>Transaction</th><th>Meter</th><th>Amount / Energy</th><th>Status</th></tr></thead><tbody>
        {filteredActivity.map(row => row.kind === "LOAN" ? <tr key={row.id}><td>{when(row.date)}</td><td>Loan decision</td><td>{p.meters.find(meter => meter.id === row.loan.meter_id)?.meter_number ?? row.loan.meter_id}</td><td>{money(row.loan.principal, row.loan.currency)} · {energy(row.loan.allocated_kwh)}</td><td>{label(row.loan.status)}</td></tr>
          : <tr key={row.id}><td>{when(row.date)}</td><td>{row.kind === "PURCHASE" ? "Electricity purchase" : "Loan repayment"}</td><td>{p.meters.find(meter => meter.id === row.payment.meter_id)?.meter_number ?? row.payment.meter_id}</td><td>{money(row.payment.amount, row.payment.currency)} · {row.kind === "PURCHASE" ? energy(row.payment.allocated_kwh) : money(row.payment.applied, row.payment.currency)}</td><td>{label(row.payment.status)}</td></tr>)}
      </tbody></table>
    </div>}
    {!web && p.view === "activity" && <><h2>Payments &amp; receipts</h2>
      <div className="receipt-filters" aria-label="Receipt filters">{([["all", "All"], ["PURCHASE", "Purchases"], ["LOAN_REPAYMENT", "Repayments"]] as const).map(([value, name]) => <button key={value} className="secondary" aria-pressed={filter === value} onClick={() => setFilter(value)}>{name}</button>)}</div>
      {p.payments.filter(row => filter === "all" || row.purpose === filter).map(paymentCard)}
      {p.fetched && !p.payments.some(row => filter === "all" || row.purpose === filter) && <p className="muted">No matching payments yet.</p>}
    </>}
  </section>;
}
