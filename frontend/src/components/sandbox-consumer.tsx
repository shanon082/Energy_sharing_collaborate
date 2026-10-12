"use client";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { mergePayments, parseTestLoan, parseTestPayment, readRetry, writeRetry, testAmount, testPhone,
  type Assessment, type SandboxCapabilities, type SandboxClient, type TestLoan, type TestMeter, type TestPayment, type TestPolicy, type TestQuote } from "../lib/sandbox";

const describe = (error: unknown) => error instanceof Error ? error.message : "Sandbox request failed. Refresh to recover stored status.";
const when = (time: string | null) => time ? new Date(time).toLocaleString() : "Unavailable";
const eur = (value: string | null) => value === null ? "Unavailable" : `EUR TEST ${value}`;

/** Shared UI; transport is injected. No Next server/cookie or mobile token imports. */
export default function SandboxConsumer({ client, owner, meters, selectedMeter, capabilities, onChanged }: {
  client: SandboxClient; owner: number; meters: TestMeter[]; selectedMeter: TestMeter | null;
  capabilities: SandboxCapabilities; onChanged?: () => void;
}) {
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [policy, setPolicy] = useState<TestPolicy | null>(null);
  const [loans, setLoans] = useState<TestLoan[]>([]);
  const [payments, setPayments] = useState<TestPayment[]>([]);
  const [purpose, setPurpose] = useState<"LOAN" | "PURCHASE">("LOAN");
  const [amount, setAmount] = useState("2.00");
  const [phone, setPhone] = useState("");
  const [quote, setQuote] = useState<TestQuote | null>(null);
  const [accepted, setAccepted] = useState(false);
  const [repayment, setRepayment] = useState("");
  const [loanId, setLoanId] = useState("");
  const [repayAccepted, setRepayAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [fetched, setFetched] = useState<string | null>(null);
  const [unresolved, setUnresolved] = useState(false);
  const [offline, setOffline] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const epoch = useRef(0);
  const active = useRef(true);
  const token = useRef(0);
  const inFlight = useRef(false);
  const reading = useRef(false);
  const destination = useRef(selectedMeter?.id);
  destination.current = selectedMeter?.id;
  // Parents key this component by account; late responses cannot repopulate a new account.
  useEffect(() => {
    active.current = true;
    const scope = epoch.current;
    const initialRead = token.current;
    return () => { active.current = false; epoch.current = scope + 1; reading.current = false; token.current = initialRead + 1; };
  }, []);
  const current = (run: number) => active.current && epoch.current === run;
  const refresh = useCallback(async () => {
    if (inFlight.current || reading.current) return;
    reading.current = true; setRefreshing(true);
    const run = ++token.current; const identity = epoch.current;
    try {
      const [a, l, p] = await Promise.all([
        client.get<{ assessment: Assessment; policy: TestPolicy }>("sandbox/assessment/"),
        client.get<{ loans: unknown[] }>("sandbox/loans/"),
        client.get<{ payments: unknown[]; pending: unknown[] }>("sandbox/payments/"),
      ]);
      const recoveredLoans: TestLoan[] = []; const recoveredPayments: TestPayment[] = [];
      let unknown = false;
      for (const kind of ["LOAN", "PURCHASE", "LOAN_REPAYMENT"] as const) {
        const id = readRetry(owner, kind);
        if (!id) continue;
        if (kind === "LOAN") {
          const recovery = await client.get<{ loan: unknown }>(`sandbox/loan-recovery/${id}/`);
          if (recovery.loan) {
            recoveredLoans.push(parseTestLoan(recovery.loan));
            if (current(identity) && token.current === run) writeRetry(owner, kind, null);
          }
          else if (current(identity) && token.current === run) writeRetry(owner, kind, null);
        } else {
          const recovery = await client.get<{ payment: unknown }>(`sandbox/payment-recovery/${id}/`);
          if (recovery.payment) {
            const record = parseTestPayment(recovery.payment); recoveredPayments.push(record);
            if (record.status !== "PENDING" && current(identity) && token.current === run) writeRetry(owner, kind, null);
          }
          else if (current(identity) && token.current === run) writeRetry(owner, kind, null);
        }
      }
      // If any lookup fails, catch retains the handles and blocks another initiation.
      unknown = ["LOAN", "PURCHASE", "LOAN_REPAYMENT"].some(kind => !!readRetry(owner, kind as "LOAN" | "PURCHASE" | "LOAN_REPAYMENT") &&
        ![...recoveredLoans, ...recoveredPayments].some(row => row.client_request_id === readRetry(owner, kind as "LOAN" | "PURCHASE" | "LOAN_REPAYMENT")));
      if (!current(identity) || token.current !== run) return;
      setAssessment(a.assessment); setPolicy(a.policy);
      setLoans([...new Map([...l.loans.map(parseTestLoan), ...recoveredLoans].map(row => [row.id, row])).values()]);
      setPayments([...new Map([...mergePayments(p.payments, p.pending), ...recoveredPayments].map(row => [row.reference, row])).values()]);
      setUnresolved(unknown); setOffline(false); setFetched(new Date().toISOString()); setError(null);
    } catch (cause) {
      if (!current(identity) || token.current !== run) return;
      setError(describe(cause)); setUnresolved(true);
    } finally {
      if (current(identity) && token.current === run) {
        reading.current = false; setRefreshing(false);
      }
    }
  }, [client, owner]);
  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    const changed = () => { setQuote(null); setAccepted(false); };
    changed();
  }, [selectedMeter?.id]);
  useEffect(() => {
    const onOffline = () => setOffline(true);
    const onOnline = () => { setOffline(false); void refresh(); };
    window.addEventListener("offline", onOffline); window.addEventListener("online", onOnline);
    const interval = window.setInterval(() => { if (document.visibilityState === "visible") void refresh(); }, 30000);
    return () => { window.clearInterval(interval); window.removeEventListener("offline", onOffline); window.removeEventListener("online", onOnline); };
  }, [refresh]);
  const perform = async (work: () => Promise<void>) => {
    if (inFlight.current || reading.current || offline) return;
    inFlight.current = true;
    const identity = epoch.current;
    setBusy(true); setError(null); setNotice(null);
    try { await work(); }
    catch (cause) { if (current(identity)) { setError(describe(cause)); setUnresolved(true); } }
    finally { inFlight.current = false; if (current(identity)) setBusy(false); }
  };
  const getQuote = (event: FormEvent) => {
    event.preventDefault();
    if (!selectedMeter?.sandbox_inventory || !testAmount(amount)) { setError("Add or select a linked prototype meter and enter positive EUR cents."); return; }
    const meterId = selectedMeter.id; const identity = epoch.current;
    void perform(async () => {
      const q = await client.post<TestQuote>("sandbox/quotes/", { meter_id: meterId, amount, purpose });
      if (current(identity) && destination.current === meterId) { setQuote(q); setAccepted(false); }
    });
  };
  const submit = () => {
    if (!quote || !accepted || (purpose === "PURCHASE" && !testPhone(phone))) return;
    const terms = quote; const kind = purpose; const identity = epoch.current;
    void perform(async () => {
      const key = readRetry(owner, kind) || crypto.randomUUID(); writeRetry(owner, kind, key);
      if (kind === "LOAN") {
        const result = await client.post<{ loan: unknown }>("sandbox/loans/", { quote_id: terms.id, terms_hash: terms.terms_hash,
          client_request_id: key, accept_test_terms: true });
        const decision = parseTestLoan(result.loan);
        if (current(identity)) setNotice(`${decision.status}: ${decision.reason}`);
      } else {
        const result = await client.post<{ payment: unknown }>("sandbox/payments/", { purpose: kind, quote_id: terms.id,
          terms_hash: terms.terms_hash, client_request_id: key, msisdn: phone, accept_test_terms: true });
        const payment = parseTestPayment(result.payment);
        if (current(identity)) setNotice(`Purchase ${payment.status}. Only verified settlement allocates test energy.`);
      }
      if (!current(identity)) return;
      setQuote(null); setAccepted(false); inFlight.current = false; await refresh(); onChanged?.();
    });
  };
  const repay = (event: FormEvent) => {
    event.preventDefault();
    if (!loanId || !testAmount(repayment) || !testPhone(phone) || !repayAccepted) { setError("Choose your test loan, positive EUR cents and an MTN test number; accept the terms."); return; }
    const identity = epoch.current;
    void perform(async () => {
      const key = readRetry(owner, "LOAN_REPAYMENT") || crypto.randomUUID(); writeRetry(owner, "LOAN_REPAYMENT", key);
      const result = await client.post<{ payment: unknown }>("sandbox/payments/", { purpose: "LOAN_REPAYMENT", loan_id: loanId,
        amount: repayment, msisdn: phone, accept_test_terms: true, client_request_id: key });
      const payment = parseTestPayment(result.payment);
      if (!current(identity)) return;
      setNotice(`Repayment ${payment.status}. Pending requests do not reduce debt.`); setRepayAccepted(false); inFlight.current = false; await refresh();
    });
  };
  const pending = payments.some(row => row.status === "PENDING");
  const blocked = busy || refreshing || offline || unresolved || pending;
  const selectedLoan = loans.find(row => row.id === loanId);
  const eligibleMeters = meters.filter(row => row.sandbox_inventory);
  const stale = !!error || offline;
  return <section className="sandbox-consumer panel">
    <h2>SANDBOX / NO REAL MONEY</h2>
    <p>EUR test currency only. Historical UGX debt, wallets and real scores remain separate. Test allocation is not confirmed meter delivery.</p>
    <button type="button" className="secondary" disabled={busy} onClick={() => void refresh()}>Refresh & recover stored requests</button>
    {fetched && <p className={stale ? "stale" : "muted"}>{stale ? "Stale — " : "Fetched "}{when(fetched)}</p>}
    {offline && <p role="status">Offline — no financial requests will be initiated.</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {notice && <p className="tag" role="status">{notice}</p>}
    {unresolved && <p>Refresh to resolve the previous attempt before submitting another request. Never retry by creating a new payment identity.</p>}
    {pending && <p>There is a pending test payment. Scheduled reconciliation continues when the app is closed. Another payment is blocked until its outcome is known.</p>}
    {assessment && policy && <section><h3>Test credit assessment</h3>
      <p>{assessment.starter ? "Starter allowance — no established credit score" : `Test score ${assessment.score}/100 (profile ${assessment.profile_score}, purchase contribution ${assessment.purchase_points})`}</p>
      <p>{assessment.reason} Maximum: {eur(assessment.maximum)}.</p>
      {assessment.factors && <p>{Object.entries(assessment.factors).map(([key, value]) => `${key}: ${value}`).join(" · ")}</p>}
      <p>Settled billed test purchases: {eur(assessment.qualifying_billed_eur)}. One point per {eur(policy.purchase_per_point)}, capped at {policy.purchase_score_cap}. Refreshing does not earn points.</p>
      <p>Policy {policy.id}; threshold {policy.score_threshold}; flat interest {policy.interest_percent}%; fee {eur(policy.fee)}; due {policy.due_days} days; overdue charge {policy.penalty_percent}%.</p>
      <p>{policy.rounding}. Full repayment closes new test loans permanently.</p>
    </section>}
    <form onSubmit={getQuote}>
      <h3>Apply for test credit or buy test electricity</h3>
      {!selectedMeter?.sandbox_inventory ? <p>Add or select a linked prototype meter in Meters. {eligibleMeters.length ? `${eligibleMeters.length} test meter(s) linked.` : "No prototype meter is linked."}</p> : <p>Explicit destination: {selectedMeter.meter_number} · cloud test inventory. Hardware connection is pending; actual usage and physical meter balance are unavailable without device evidence.</p>}
      <label>Activity<select value={purpose} onChange={event => { setPurpose(event.target.value === "PURCHASE" ? "PURCHASE" : "LOAN"); setQuote(null); setAccepted(false); }}>
        <option value="LOAN">Test electricity loan</option><option value="PURCHASE">MTN sandbox purchase</option>
      </select></label>
      <label>Principal / payment (EUR TEST)<input inputMode="decimal" value={amount} onChange={event => { setAmount(event.target.value); setQuote(null); setAccepted(false); }} required /></label>
      <p>Quote range {eur(policy?.minimum ?? null)} – {eur(policy?.maximum ?? null)}. Approval uses your limit and existing obligations at submission.</p>
      <button type="submit" disabled={blocked || !selectedMeter?.sandbox_inventory || !(purpose === "LOAN" ? capabilities.loans : capabilities.purchases)}>Review server quote</button>
    </form>
    {quote && <section><h3>Review {quote.terms.policy.id}</h3>
      <p>Principal/payment {eur(quote.terms.amount)} · test energy {quote.terms.energy_kwh} kWh · interest {eur(quote.terms.interest)} · fee {eur(quote.terms.fee)} · loan total {eur(quote.terms.total_due)}.</p>
      <p>Test price {eur(quote.terms.policy.rate_per_kwh)}/kWh; billed {eur(quote.terms.billed)}; energy-rounding remainder {eur(quote.terms.residual)} retained for reconciliation. No automatic refund or energy conversion.</p>
      <p>Expires {when(quote.expires_at)}. Allocations are not physical meter receipts.</p>
      <label><input type="checkbox" checked={accepted} onChange={event => setAccepted(event.target.checked)} /> I accept these SANDBOX TEST terms.</label>
      <button type="button" onClick={submit} disabled={blocked || !accepted || Date.parse(quote.expires_at) <= Date.now() || (purpose === "PURCHASE" && !testPhone(phone))}>{purpose === "LOAN" ? "Submit actual test application" : "Initiate MTN sandbox purchase"}</button>
    </section>}
    <section><h3>MTN sandbox number</h3>
      <label>Test MSISDN (10–15 digits; no +)<input inputMode="numeric" autoComplete="off" value={phone} onChange={event => setPhone(event.target.value)} /></label>
      <p>Use a sandbox scenario, never your real account number or PIN. Example test-only 46733123499: ordinary success scenario; 46733123450: failure; 46733123453: ongoing; 46733123454: delayed. Provider evidence, not this label, decides the outcome.</p>
      {(!capabilities.purchases || !capabilities.repayments) && <p>MTN sandbox credentials are not configured on the server. Test loan submission remains available; payment initiation will become available after private operator setup.</p>}
    </section>
    <section><h3>Test loans & decisions</h3>{!fetched ? <p>Loading…</p> : !loans.length ? <p>No test applications.</p> : loans.map(loan => <article className="panel" key={loan.id}>
      <strong>{loan.status} · {eur(loan.outstanding)} outstanding</strong><p>{loan.reason}</p>
      <p>Reference {loan.id} · meter ID {loan.meter_id} · accepted policy {loan.terms.policy.id}</p>
      <p>Principal {eur(loan.principal)} · frozen total {eur(loan.total_due)} · due {when(loan.due_at)} · closed {when(loan.closed_at)}.</p>
      <p>Test allocation {loan.allocated_kwh === null ? "None" : `${loan.allocated_kwh} kWh`} · confirmed physical application unavailable.</p>
      {payments.filter(payment => payment.loan_id === loan.id).map(payment => <p key={payment.reference}>Repayment {payment.status}: received {eur(payment.amount)}, applied {eur(payment.applied)}, excess {eur(payment.excess)}.</p>)}
    </article>)}</section>
    <form onSubmit={repay}><h3>Self-repayment (MTN sandbox)</h3>
      <label>Your test loan<select value={loanId} onChange={event => { setLoanId(event.target.value); setRepayment(""); setRepayAccepted(false); }}><option value="">Choose explicitly</option>
        {loans.filter(row => row.status === "DISBURSED").map(row => <option key={row.id} value={row.id}>{row.id} · EUR {row.outstanding}</option>)}
      </select></label>
      {selectedLoan && <p>Policy {selectedLoan.terms.policy.id}; outstanding {eur(selectedLoan.outstanding)}. Repayment reduces only this loan; it creates no energy.</p>}
      <label>Amount (EUR TEST cents)<input inputMode="decimal" value={repayment} onChange={event => setRepayment(event.target.value)} required /></label>
      <label><input type="checkbox" checked={repayAccepted} onChange={event => setRepayAccepted(event.target.checked)} /> I accept test repayment terms: any late excess is preserved for reconciliation; no automatic refund or credit.</label>
      <button type="submit" disabled={blocked || !capabilities.repayments || !repayAccepted || !selectedLoan || !testAmount(repayment) || !testPhone(phone)}>Initiate sandbox self-repayment</button>
    </form>
    <section><h3>Sandbox receipts & pending recovery</h3>{!fetched ? <p>Loading…</p> : !payments.length ? <p>No sandbox payments.</p> : payments.map(row => <article className="panel" key={row.reference}>
      <strong>{row.purpose} · {row.status} · {eur(row.amount)}</strong><p>Reference {row.reference} · {when(row.initiated_at)}</p>
      <p>Submission: {row.submission_state}. {row.reconciliation_error && `Reconciliation: ${row.reconciliation_error}.`} Next provider check {when(row.next_check_at)}.</p>
      {row.status === "SETTLED" && <p>Verified {when(row.settled_at)}. Billed {eur(row.billed)}; remainder {eur(row.residual)}; debt applied {eur(row.applied)}; excess {eur(row.excess)}. Allocation {row.allocated_kwh ?? "None"} kWh; physical delivery unconfirmed.</p>}
      {row.status === "PENDING" && <button type="button" className="secondary" disabled={busy || offline} onClick={() => void perform(async () => { await client.post(`sandbox/payments/${row.reference}/`, {}); inFlight.current = false; await refresh(); onChanged?.(); })}>Check with MTN (server backoff applies)</button>}
    </article>)}</section>
  </section>;
}
