"use client";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { parseStoredDemoAssessment, parseTestQuote, assertTestPaymentBinding, mergePayments, parseTestLoan, parseTestPayment, readRetry, writeRetry, testAmount, testDemoAmount, testMoney, demoCountdown, paymentStatusMethod, canClearRecoveredRetry, testPhone,
  paymentConflictReason, checkoutRetryId, type Assessment, type SandboxCapabilities, type SandboxClient, type TestLoan, type TestMeter, type TestPayment, type TestPolicy, type TestQuote, type PricingStatus } from "../lib/sandbox";

import { EnergyTokenCard } from "./energy-token-card";
import { TariffDetails } from "./tariff-details";
import { readFinanceSetup } from "../lib/finance-setup";
import { withRequestDeadline } from "../lib/request-deadline";
import { assessmentContextKey, loanProgressionReason } from "../lib/meter-credit";
import SandboxMobileView, { type ConsumerFinanceView, type FinanceDestination } from "./sandbox-mobile-view";

const describe = (error: unknown) => error instanceof Error ? error.message : "Sandbox request failed. Refresh to recover stored status.";
const when = (time: string | null) => time ? new Date(time).toLocaleString() : "Unavailable";
const DEMO_PENDING = "Demo payment: simulating phone authorization. No PIN or real money is required.";
const DEMO_SUCCESS = "Demo payment successful — no real money was deducted.";

/** Shared UI; transport is injected. No Next server/cookie or mobile token imports. */
export default function SandboxConsumer({ client, owner, meters, selectedMeter, capabilities, onChanged, view = "all", onNavigate, onSelectMeter, onAddMeter, surface = "mobile", refreshVersion = 0, mutationsAvailable = true, onError, registerBackHandler }: {
  client: SandboxClient; owner: number; meters: TestMeter[]; selectedMeter: TestMeter | null;
  capabilities: SandboxCapabilities; onChanged?: () => void;
  view?: ConsumerFinanceView | "all"; onNavigate?: (view: FinanceDestination) => void; refreshVersion?: number;
  onSelectMeter?: (id: string) => void; onAddMeter?: () => void;
  surface?: "web" | "mobile";
  mutationsAvailable?: boolean; onError?: (error: unknown) => void; registerBackHandler?: (handler: (() => boolean) | null) => void;
}) {
  const demo = capabilities.provider === "LOCAL_DEMO";
  const paymentEnvironment = capabilities.environment ?? (demo ? "UGX_DEMO" : "MTN_SANDBOX");
  const paymentCurrency = capabilities.currency ?? (demo ? "UGX" : "EUR");
  const loanEnvironment = capabilities.loanEnvironment ?? paymentEnvironment;
  const loanCurrency = capabilities.loanCurrency ?? paymentCurrency;
  const validPaymentAmount = paymentCurrency === "UGX" ? testDemoAmount : testAmount;
  const [clock, setClock] = useState(Date.now);
  const formVersion = useRef(0);
  const nextAttempt = useRef(new Map<string, number>());
  const [assessmentError, setAssessmentError] = useState<string | null>(null);
  const [purchaseError, setPurchaseError] = useState<string | null>(null);
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const pricingContext = useRef("");
  const readMeter = useRef<number | undefined>(undefined);
  const [loanPolicy, setLoanPolicy] = useState<TestPolicy | null>(null);
  const [purchasePolicy, setPurchasePolicy] = useState<TestPolicy | null>(null);
  const [loanPricing, setLoanPricing] = useState<PricingStatus>({available:false,message:'Checking tariff…'});
  const [purchasePricing, setPurchasePricing] = useState<PricingStatus>({available:false,message:'Checking pricing…'});
  const [loans, setLoans] = useState<TestLoan[]>([]);
  const [payments, setPayments] = useState<TestPayment[]>([]);
  const [purpose, setPurpose] = useState<"LOAN" | "PURCHASE">("LOAN");
  const currency = purpose === "LOAN" ? loanCurrency : paymentCurrency;
  const environment = purpose === "LOAN" ? loanEnvironment : paymentEnvironment;
  const validAmount = currency === "UGX" ? testDemoAmount : testAmount;
  const money = (value: string | null | undefined) => testMoney(value, currency);
  const policy = purpose === "LOAN" ? loanPolicy : purchasePolicy;
  const pricingStatus = purpose === "LOAN" ? loanPricing : purchasePricing;
  const [amount, setAmount] = useState(loanCurrency === "UGX" ? "1000" : "2.00");
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
  const [unresolvedLoan, setUnresolvedLoan] = useState(false);
  const [unresolvedPayment, setUnresolvedPayment] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [loansError, setLoansError] = useState<string | null>(null);
  const [paymentsError, setPaymentsError] = useState<string | null>(null);
  const unresolved = purpose === "LOAN" ? unresolvedLoan : unresolvedPayment;
  const [offline, setOffline] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const epoch = useRef(0);
  const active = useRef(true);
  const token = useRef(0);
  const inFlight = useRef(false);
  const reading = useRef(false);
  const polling = useRef(false);
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
    const meterId = selectedMeter?.id;
    if (inFlight.current || (reading.current && readMeter.current === meterId)) return;
    readMeter.current = meterId;
    reading.current = true; setRefreshing(true);
    const run = ++token.current; const identity = epoch.current;
    try {
      const [setupResult, loanResult, paymentResult] = await Promise.allSettled([
        withRequestDeadline(() => readFinanceSetup(client, meterId, capabilities.loanCurrency === "UGX" && !demo,
          {currency: paymentCurrency, environment: paymentEnvironment}, {currency: loanCurrency, environment: loanEnvironment})),
        withRequestDeadline(() => client.get<{ loans: unknown[] }>("sandbox/loans/")),
        withRequestDeadline(() => client.get<{ payments: unknown[]; pending: unknown[] }>("sandbox/payments/")),
      ]);
      const recoveredLoans: TestLoan[] = []; const recoveredPayments: TestPayment[] = [];
      let unknownLoan = false; let unknownPayment = paymentResult.status === "rejected";
      const recoveryErrors: string[] = [];
      await Promise.all((["UGX_DEMO", "MTN_SANDBOX"] as const).flatMap(recoveryEnvironment =>
        (["LOAN", "PURCHASE", "LOAN_REPAYMENT"] as const).map(async kind => {
          const id = readRetry(owner, kind, recoveryEnvironment);
          if (!id) return;
          try {
          if (kind === "LOAN") {
            const recovery = await withRequestDeadline(() => client.get<{ loan: unknown }>(`sandbox/loan-recovery/${id}/`));
            if (recovery.loan) {
              const loan = parseTestLoan(recovery.loan);
              if (loan.client_request_id !== id || loan.environment !== recoveryEnvironment) throw new Error("Loan recovery belongs to a different request or test environment.");
              recoveredLoans.push(loan);
              if (canClearRecoveredRetry(loan) && current(identity) && token.current === run) writeRetry(owner, kind, null, recoveryEnvironment);
            }
          } else {
            const recovery = await withRequestDeadline(() => client.get<{ payment: unknown }>(`sandbox/payment-recovery/${id}/`));
            if (recovery.payment) {
              const record = parseTestPayment(recovery.payment);
              if (record.client_request_id !== id || record.environment !== recoveryEnvironment) throw new Error("Payment recovery belongs to a different request or test environment.");
              recoveredPayments.push(record);
              if (canClearRecoveredRetry(record) && current(identity) && token.current === run) writeRetry(owner, kind, null, recoveryEnvironment);
            }
          }
          } catch (cause) {
            recoveryErrors.push(describe(cause));
          }
          const matched = [...recoveredLoans, ...recoveredPayments].some(row => row.client_request_id === id);
          if (!matched) { if (kind === "LOAN") unknownLoan = true; else unknownPayment = true; }
        })));
      const setup = setupResult.status === "fulfilled" ? setupResult.value : {
        lending: {status: "rejected", reason: setupResult.reason} as PromiseRejectedResult,
        purchase: {status: "rejected", reason: setupResult.reason} as PromiseRejectedResult,
      };
      if (!current(identity) || token.current !== run || destination.current !== meterId) return;
      let parsed: Assessment | null = null;
      let loanFailure: string | null = null;
      if (setup.lending.status === 'fulfilled') {
        try {
          parsed = loanCurrency === "UGX" ? parseStoredDemoAssessment(setup.lending.value.assessment, {owner, meterId: meterId ?? null}) : setup.lending.value.assessment;
        } catch (cause) { loanFailure = `Loan assessment unavailable: ${describe(cause)}`; }
      } else loanFailure = `Loan assessment request failed: ${describe(setup.lending.reason)}`;
      const a = setup.lending.status === 'fulfilled' && !loanFailure ? setup.lending.value : null;
      const purchase = setup.purchase.status === 'fulfilled' ? setup.purchase.value : null;
      const purchaseFailure = setup.purchase.status === 'rejected' ? `Purchase terms request failed: ${describe(setup.purchase.reason)}` : null;
      const context = (parsed && a ? assessmentContextKey(parsed, a.policy, a.pricing) : loanFailure) + JSON.stringify(purchase);
      if (pricingContext.current !== context) {
        formVersion.current++; setQuote(null); setAccepted(false); pricingContext.current = context;
      }
      setAssessment(parsed); setAssessmentError(loanFailure); setPurchaseError(purchaseFailure);
      setLoanPolicy(a?.policy ?? null); setPurchasePolicy(purchase?.policy ?? null);
      setLoanPricing(a?.pricing ?? {available: false, message: loanFailure ?? 'Loan assessment unavailable.'});
      setPurchasePricing(purchase?.pricing ?? {available: false, message: purchaseFailure ?? 'Purchase terms unavailable.'});
      let loanFailureRead = loanResult.status === 'rejected' ? `Loans unavailable: ${describe(loanResult.reason)}` : null;
      let paymentFailureRead = paymentResult.status === 'rejected' ? `Payments unavailable: ${describe(paymentResult.reason)}` : null;
      if (loanResult.status === 'fulfilled') {
        try { setLoans([...new Map([...loanResult.value.loans.map(parseTestLoan), ...recoveredLoans].map(row => [row.id, row])).values()]); }
        catch (cause) { loanFailureRead = `Loans unavailable: ${describe(cause)}`; }
      }
      if (paymentResult.status === 'fulfilled') {
        try { setPayments([...new Map([...mergePayments(paymentResult.value.payments, paymentResult.value.pending), ...recoveredPayments].map(row => [row.reference, row])).values()]); }
        catch (cause) { paymentFailureRead = `Payments unavailable: ${describe(cause)}`; unknownPayment = true; }
      }
      setLoansError(loanFailureRead); setPaymentsError(paymentFailureRead);
      setUnresolvedLoan(unknownLoan); setUnresolvedPayment(unknownPayment); setOffline(false);
      if (!loanFailureRead && !paymentFailureRead) setFetched(new Date().toISOString());
      setError([loanFailureRead, paymentFailureRead, ...recoveryErrors].filter(Boolean).join(' ') || null);
    } catch (cause) {
      if (!current(identity) || token.current !== run) return;
      setError(describe(cause)); setUnresolvedPayment(true); onError?.(cause);
    } finally {
      if (current(identity) && token.current === run) {
        reading.current = false; setRefreshing(false); setLoaded(true);
      }
    }
  }, [client, owner, demo, loanCurrency, capabilities.loanCurrency, paymentCurrency, paymentEnvironment, loanEnvironment, onError, selectedMeter?.id]);
  useEffect(() => { if (!busy) void refresh(); }, [refresh, selectedMeter?.id, refreshVersion, busy]);
  useEffect(() => {
    const changed = () => { formVersion.current++; setQuote(null); setAccepted(false); setAssessment(null); };
    changed();
  }, [selectedMeter?.id]);
  useEffect(() => {
    const onOffline = () => setOffline(true);
    const onOnline = () => { setOffline(false); void refresh(); };
    window.addEventListener("offline", onOffline); window.addEventListener("online", onOnline);
    const interval = window.setInterval(() => { if (document.visibilityState === "visible") void refresh(); }, 30000);
    return () => { window.clearInterval(interval); window.removeEventListener("offline", onOffline); window.removeEventListener("online", onOnline); };
  }, [refresh]);
  // A single mounted controller serves the mobile tabs; navigation never initiates a payment.
  useEffect(() => {
    const next = view === "purchase" ? "PURCHASE" : view === "apply" || view === "loans" ? "LOAN" : null;
    if (next && next !== purpose) { formVersion.current++; setPurpose(next); setAmount((next === "LOAN" ? loanCurrency : paymentCurrency) === "UGX" ? "1000" : "2.00"); setQuote(null); setAccepted(false); }
  }, [view, purpose, loanCurrency, paymentCurrency]);
  useEffect(() => {
    // Capability/domain updates invalidate old quotes and consent, not recovery handles.
    formVersion.current++; setQuote(null); setAccepted(false); setRepayAccepted(false);
  }, [loanCurrency, loanEnvironment, paymentCurrency, paymentEnvironment, capabilities.loans, capabilities.purchases, capabilities.repayments]);
  useEffect(() => {
    if (!quote) return;
    setClock(Date.now());
    const timer = window.setInterval(() => setClock(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [quote]);

  const perform = async (work: () => Promise<void>, recovery = false, uncertainFinancialEffect = true, operation = purpose === "LOAN" ? "LOAN" : "PAYMENT") => {
    if (inFlight.current || reading.current || offline || (!recovery && (!mutationsAvailable || (operation === "LOAN" ? unresolvedLoan : unresolvedPayment)))) return;
    inFlight.current = true;
    const identity = epoch.current;
    setBusy(true); setError(null); setNotice(null);
    try { await work(); }
    catch (cause) { if (current(identity)) { setError(describe(cause)); if (uncertainFinancialEffect) { if (operation === "LOAN") setUnresolvedLoan(true); else setUnresolvedPayment(true); } onError?.(cause); } }
    finally { inFlight.current = false; if (current(identity)) setBusy(false); }
  };
  const getQuote = (event: FormEvent) => {
    event.preventDefault();
    if (!(purpose === "LOAN" ? capabilities.loans : capabilities.purchases)) { setError((purpose === "LOAN" ? capabilities.loanMessage : capabilities.purchaseMessage) || capabilities.paymentMessage || "This operation is disabled by the server."); return; }
    if (!pricingStatus.available || (purpose === "LOAN" && loanReason)) { setError(purpose === "LOAN" && loanReason ? loanReason : pricingStatus.message); return; }
    if (!selectedMeter?.sandbox_inventory || !validAmount(amount)) { setError("Add or select a linked prototype meter and enter a positive matching test amount."); return; }
    const meterId = selectedMeter.id; const identity = epoch.current; const revision = formVersion.current; const intent = purpose;
    void perform(async () => {
      const q = parseTestQuote(await client.post<unknown>("sandbox/quotes/", { meter_id: meterId, amount, purpose, ...(purpose === "LOAN" && capabilities.loanCurrency === "UGX" && !demo ? {loan_contract: "UGX-PROTOTYPE-SANDBOX-v1"} : {}) }),
        { owner, meterId, amount, purpose: intent, currency, environment, ...(purpose === "LOAN" && capabilities.loanCurrency === "UGX" && !demo ? {loanContract: "UGX-PROTOTYPE-SANDBOX-v1"} : {}) });
      if (current(identity) && destination.current === meterId && formVersion.current === revision && q.terms.purpose === intent) { setQuote(q); setAccepted(false); }
    }, false, false);
  };
  const submit = () => {
    if (!(purpose === "LOAN" ? capabilities.loans : capabilities.purchases) || !quote || !accepted || quote.terms.purpose !== purpose || quote.terms.meter_id !== destination.current || Date.parse(quote.expires_at) <= Date.now() ||
      (purpose === "PURCHASE" && !demo && !testPhone(phone))) return;
    const meterId = quote.terms.meter_id;
    if (typeof meterId !== "number") return;
    const terms = quote; const kind = purpose; const identity = epoch.current;
    void perform(async () => {
      const key = readRetry(owner, kind, environment) || crypto.randomUUID(); writeRetry(owner, kind, key, environment);
      if (kind === "LOAN") {
        const result = await client.post<{ loan: unknown }>("sandbox/loans/", { quote_id: terms.id, terms_hash: terms.terms_hash,
          client_request_id: key, accept_test_terms: true });
        const decision = parseTestLoan(result.loan);
        if (current(identity)) setNotice(`${decision.status === "DISBURSED" ? "Approved" : decision.status === "REJECTED" ? "Not approved" : decision.status}: ${decision.reason}`);
      } else {
        const result = await client.post<{ payment: unknown }>("sandbox/payments/", { purpose: kind, quote_id: terms.id,
          terms_hash: terms.terms_hash, client_request_id: key, ...(demo ? {} : { msisdn: phone }), accept_test_terms: true });
        const payment = parseTestPayment(result.payment);
        assertTestPaymentBinding(payment, { client_request_id: key, purpose: kind, amount: terms.terms.amount,
          meter_id: meterId, loan_id: null, currency, environment });
        if (current(identity)) {
          setPayments(previous => [payment, ...previous.filter(row => row.reference !== payment.reference)]);
          setNotice(demo ? payment.status === "SETTLED" ? DEMO_SUCCESS : DEMO_PENDING : `Purchase ${payment.status}. Only verified settlement allocates test energy.`);
        }
      }
      if (!current(identity)) return;
      setQuote(null); setAccepted(false); inFlight.current = false; await refresh(); onChanged?.();
      if (kind === "LOAN" && view !== "all" && current(identity)) onNavigate?.("loans");
    });
  };
  const repay = (event: FormEvent) => {
    event.preventDefault();
    if (!capabilities.repayments) { setError(capabilities.repaymentMessage || capabilities.paymentMessage || "Repayments are disabled by the server."); return; }
    if (!loanId || !validPaymentAmount(repayment) || (!demo && !testPhone(phone)) || !repayAccepted) { setError("Choose your test loan, a positive matching test amount; accept the terms."); return; }
    const loan = loans.find(row => row.id === loanId && row.environment === paymentEnvironment && row.currency === paymentCurrency && row.repayment_available !== false && row.status === "DISBURSED");
    if (!loan) { setError("Choose an active loan in the current test currency."); return; }
    const identity = epoch.current;
    void perform(async () => {
      const key = readRetry(owner, "LOAN_REPAYMENT", paymentEnvironment) || crypto.randomUUID(); writeRetry(owner, "LOAN_REPAYMENT", key, paymentEnvironment);
      const result = await client.post<{ payment: unknown }>("sandbox/payments/", { purpose: "LOAN_REPAYMENT", loan_id: loanId,
        amount: repayment, ...(demo ? {} : { msisdn: phone }), accept_test_terms: true, client_request_id: key });
      const payment = parseTestPayment(result.payment);
      assertTestPaymentBinding(payment, { client_request_id: key, purpose: "LOAN_REPAYMENT", amount: repayment,
        meter_id: loan.meter_id, loan_id: loanId, currency: paymentCurrency, environment: paymentEnvironment });
      if (!current(identity)) return;
      setPayments(previous => [payment, ...previous.filter(row => row.reference !== payment.reference)]);
      setNotice(demo ? payment.status === "SETTLED" ? DEMO_SUCCESS : DEMO_PENDING : `Repayment ${payment.status}. Pending requests do not reduce debt.`); setRepayAccepted(false); inFlight.current = false; await refresh();
    }, false, true, "PAYMENT");
  };
  const pending = payments.some(row => row.status === "PENDING");
  useEffect(() => {
    if (!pending) return;
    let disposed = false; const identity = epoch.current;
    const tick = async () => {
      const now = Date.now(); setClock(now);
      if (disposed || offline || inFlight.current || polling.current || reading.current || document.visibilityState !== "visible") return;
      const row = payments.find(item => item.status === "PENDING" && now >= (nextAttempt.current.get(item.reference) ?? 0));
      if (!row || now < (nextAttempt.current.get(row.reference) ?? 0)) return;
      polling.current = true; nextAttempt.current.set(row.reference, now + 2000);
      try {
        const result = paymentStatusMethod(row, now) === "GET"
          ? await client.get<{ payment: unknown }>(`sandbox/payments/${row.reference}/`)
          : await client.post<{ payment: unknown }>(`sandbox/payments/${row.reference}/`, {});
        const record = parseTestPayment(result.payment);
        assertTestPaymentBinding(record, row);
        if (disposed || !current(identity)) return;
        setPayments(previous => previous.map(item => item.reference === record.reference ? record : item));
        if (record.status !== "PENDING") {
          setNotice(record.status === "FAILED" ? "Sandbox payment failed. No financial effect was applied." : record.provider === "LOCAL_DEMO" ? DEMO_SUCCESS : "Sandbox payment confirmed by Django. No real money was collected."); setError(null);
          const kind = record.purpose === "PURCHASE" ? "PURCHASE" : "LOAN_REPAYMENT";
          if (readRetry(owner, kind, record.environment) === record.client_request_id) writeRetry(owner, kind, null, record.environment);
          await refresh(); onChanged?.();
        }
      } catch (cause) {
        nextAttempt.current.set(row.reference, Date.now() + 15000);
        if (!disposed && current(identity)) { setError(describe(cause)); onError?.(cause); }
      } finally { polling.current = false; }
    };
    const interval = window.setInterval(() => { void tick(); }, 500);
    return () => { disposed = true; window.clearInterval(interval); };
  }, [client, demo, environment, offline, owner, payments, pending, refresh, onChanged, onError]);
  const blocked = busy || refreshing || offline || unresolved || !mutationsAvailable;
  const purchaseBlockReason = paymentsError || paymentConflictReason(payments, "PURCHASE", selectedMeter?.id);
  const repaymentBlockReason = paymentsError || paymentConflictReason(payments, "LOAN_REPAYMENT", undefined, loanId);
  const retryPayment = (row: TestPayment) => void perform(async () => {
    const key = checkoutRetryId(owner, row.reference);
    writeRetry(owner, row.purpose === "PURCHASE" ? "PURCHASE" : "LOAN_REPAYMENT", key, row.environment);
    const response = await client.post<{payment: unknown}>(`sandbox/payments/${row.reference}/retry/`, {client_request_id: key, accept_test_terms: true});
    const replacement = parseTestPayment(response.payment);
    assertTestPaymentBinding(replacement, {...row, reference: undefined, client_request_id: key});
    if (replacement.checkout?.replaces_reference !== row.reference || replacement.checkout.operation_reference !== row.checkout?.operation_reference)
      throw new Error("Replacement checkout is not bound to the original operation.");
    setPayments(previous => [replacement, ...previous.filter(item => item.reference !== replacement.reference)]);
    inFlight.current = false; await refresh();
  }, true, true, "PAYMENT");
  const meterAssessment = loanCurrency !== "UGX" || assessment?.meter_id === (selectedMeter?.id ?? null) ? assessment : null;
  const loanReason = assessmentError || loanProgressionReason(meterAssessment, selectedMeter?.id ?? null, amount);
  const selectedLoan = loans.find(row => row.id === loanId && row.environment === paymentEnvironment && row.status === "DISBURSED");
  const eligibleMeters = meters.filter(row => row.sandbox_inventory);
  const stale = !!error || offline;
  if (view !== "all") return <SandboxMobileView
    client={client} owner={owner} view={view} surface={surface} navigate={onNavigate ?? (() => {})} registerBackHandler={registerBackHandler} demo={demo} currency={currency} environment={environment} loanCurrency={loanCurrency} loanEnvironment={loanEnvironment} paymentCurrency={paymentCurrency} paymentEnvironment={paymentEnvironment} validPaymentAmount={validPaymentAmount}
    capabilities={capabilities} setupError={purpose === "LOAN" ? assessmentError : purchaseError} assessment={meterAssessment} assessmentPolicy={loanPolicy} policy={policy} pricingStatus={pricingStatus} loanReason={loanReason} loans={loans} payments={payments}
    meters={meters} selectedMeter={selectedMeter} setSelectedMeter={onSelectMeter ?? (() => {})} onAddMeter={onAddMeter} purpose={purpose} amount={amount}
    setAmount={value => { formVersion.current++; setAmount(value); setQuote(null); setAccepted(false); }}
    quote={quote} clearQuote={() => { formVersion.current++; setQuote(null); setAccepted(false); }}
    accepted={accepted} setAccepted={setAccepted} phone={phone} setPhone={setPhone}
    loanId={loanId} selectLoan={id => { setLoanId(id); setRepayment(""); setRepayAccepted(false); }}
    repayment={repayment} setRepayment={setRepayment} repayAccepted={repayAccepted} setRepayAccepted={setRepayAccepted}
    blocked={blocked} busy={busy} refreshing={refreshing} offline={offline} unresolved={unresolved} pending={pending}
    loaded={loaded} loansError={loansError} paymentsError={paymentsError} purchaseBlockReason={purchaseBlockReason} repaymentBlockReason={repaymentBlockReason} retryPayment={retryPayment}
    error={error} notice={notice} fetched={fetched} clock={clock} validAmount={validAmount} validPhone={testPhone(phone)}
    initializeAssessment={selectedMeter && loanCurrency === 'UGX' ? () => { void perform(async () => {
      await client.post('sandbox/assessment/', {meter_id: selectedMeter.id}); inFlight.current = false; await refresh();
    }, false, false); } : undefined}
    refresh={() => void refresh()} getQuote={getQuote} submit={submit} repay={repay}
    checkPayment={row => void perform(async () => { await client.post(`sandbox/payments/${row.reference}/`, {}); inFlight.current = false; await refresh(); onChanged?.(); }, true, false)}
  />;

  return <section className="sandbox-consumer panel">
    <h2>{paymentCurrency === "UGX" ? "UGX TEST / NO REAL MONEY" : "EUR TEST / MTN SANDBOX"}</h2>
    <p>{capabilities.authorizationPolicy ? "UGX prototype testing. No real money is collected. Provider authorization details remain in receipts." : demo ? "Local simulator. No real money or actual phone authorization. You may apply for one UGX demo loan alongside an existing EUR loan, without converting or closing it." : capabilities.loanCurrency === "UGX" ? "UGX prototype loans and EUR MTN payments are separate. No repayment conversion is approved." : "EUR test currency only."} Core UGX debt, wallets and real scores remain separate. Cloud allocation is not confirmed meter delivery.</p>
    <button type="button" className="secondary" disabled={busy} onClick={() => void refresh()}>Refresh & recover stored requests</button>
    {fetched && <p className={stale ? "stale" : "muted"}>{stale ? "Stale — " : "Fetched "}{when(fetched)}</p>}
    {offline && <p role="status">Offline — no financial requests will be initiated.</p>}
    {capabilities.paymentMessage && <p role="status">{capabilities.paymentMessage}</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {notice && <p className="tag" role="status">{notice}</p>}
    {unresolved && <p>Refresh to resolve the previous attempt before submitting another request. Never retry by creating a new payment identity.</p>}
    {pending && <p>There is a pending test payment. Scheduled reconciliation continues when the app is closed. Its checkout expires after five minutes; provider reconciliation continues independently.</p>}
    {assessment && loanPolicy && <section><h3>{loanCurrency === "UGX" ? "Demo assessment — simulated account information" : "Test credit assessment"}</h3>
      <p>{loanCurrency === "UGX" && assessment.assessment_status !== "READY" ? `Score unavailable — ${assessment.assessment_status?.toLowerCase() ?? "pending"}` : assessment.starter ? "Starter allowance — no established credit score" : `Credit score: ${assessment.score}% (base ${assessment.profile_score}, purchase contribution ${assessment.purchase_points})`}</p>
      <p>{loanReason || assessment.reason} Maximum: {testMoney(assessment.maximum, loanCurrency)}.</p>
      {assessment.factors && <p>{Object.entries(assessment.factors).map(([key, value]) => `${key.replaceAll("_", " ")}: ${value} (${assessment.categories?.[key] ?? "recorded"})`).join(" · ")}</p>}
      {loanCurrency === "UGX" && <p>These payment, consumption and financial categories are fixed synthetic test inputs, not utility, bank, telecom or credit-bureau records. No questionnaire is required. Assessment {when(assessment.assessed_at ?? null)} · {assessment.scoring_policy_version} · {assessment.provider}.</p>}
      <p>Settled billed test purchases: {testMoney(assessment.qualifying_billed_test ?? assessment.qualifying_billed_eur, loanCurrency)}. One point per {testMoney(loanPolicy.purchase_per_point, loanCurrency)}, capped at {loanPolicy.purchase_score_cap}. Refreshing does not earn points.</p>
      <p>Policy {loanPolicy.id}; threshold {loanPolicy.score_threshold}; flat interest {loanPolicy.interest_percent}%; fee {testMoney(loanPolicy.fee, loanCurrency)}; due {loanPolicy.due_days} days; overdue charge {loanPolicy.penalty_percent}%.</p>
      <p>{loanPolicy.rounding}. Full repayment closes new test loans permanently.</p>
    </section>}
    <form onSubmit={getQuote}>
      <h3>Apply for test credit or buy test electricity</h3>
      {!selectedMeter?.sandbox_inventory ? <p>Add or select a linked prototype meter in Meters. {eligibleMeters.length ? `${eligibleMeters.length} test meter(s) linked.` : "No prototype meter is linked."}</p> : <p>Explicit destination: {selectedMeter.meter_number} · cloud test inventory. Hardware connection is pending; actual usage and physical meter balance are unavailable without device evidence.</p>}
      <label>Activity<select value={purpose} onChange={event => { formVersion.current++; setPurpose(event.target.value === "PURCHASE" ? "PURCHASE" : "LOAN"); setQuote(null); setAccepted(false); }}>
        <option value="LOAN">Test electricity loan</option><option value="PURCHASE" disabled={capabilities.newPaymentsPaused}>{demo ? "Demo purchase" : "MTN sandbox purchase"}</option>
      </select></label>
      <label>Principal / payment ({currency === "UGX" ? "whole UGX" : "EUR TEST"})<input inputMode={currency === "UGX" ? "numeric" : "decimal"} value={amount} onChange={event => { formVersion.current++; setAmount(event.target.value); setQuote(null); setAccepted(false); }} required /></label>
      <p>Quote range {money(policy?.minimum ?? null)} – {money(policy?.maximum ?? null)}. Approval uses your limit and existing obligations at submission.</p>
      {(purpose === "LOAN" && loanReason) && <p role="status">{loanReason}</p>}
      {!pricingStatus.available && <p role="status">{pricingStatus.message}</p>}
      <button type="submit" disabled={blocked || !selectedMeter?.sandbox_inventory || !pricingStatus.available || !(purpose === "LOAN" ? capabilities.loans && !loanReason : capabilities.purchases)}>Review server quote</button>
    </form>
    {quote && <section><h3>Review {quote.terms.policy.id}</h3>
      <p>Principal/payment {money(quote.terms.amount)} · test energy {quote.terms.energy_kwh} kWh · interest {money(quote.terms.interest)} · fee {money(quote.terms.fee)} · loan total {money(quote.terms.total_due)}.</p>
      <TariffDetails pricing={quote.terms.pricing} currency={currency} />
      <p>{quote.terms.pricing ? "Configured tariff;" : `Original test price ${money(quote.terms.policy.rate_per_kwh)}/kWh;`} billed {money(quote.terms.billed)}; energy-rounding remainder {money(quote.terms.residual)} retained for reconciliation. No automatic refund or energy conversion.</p>
      <p>Expires {when(quote.expires_at)}. Allocations are not physical meter receipts.</p>
      <label><input type="checkbox" checked={accepted} onChange={event => setAccepted(event.target.checked)} /> I accept these SANDBOX TEST terms.</label>
      <button type="button" onClick={submit} disabled={blocked || !accepted || Date.parse(quote.expires_at) <= Date.now() || (purpose === "PURCHASE" && !demo && !testPhone(phone))}>{purpose === "LOAN" ? "Submit actual test application" : (demo ? "Start demo purchase" : "Initiate MTN sandbox purchase")}</button>
    </section>}
    {!demo && <section><h3>MTN sandbox number</h3>
      <label>Test MSISDN (10–15 digits; no +)<input inputMode="numeric" autoComplete="off" value={phone} onChange={event => setPhone(event.target.value)} /></label>
      <p>Use a sandbox scenario, never your real account number or PIN. Example test-only 46733123499: ordinary success scenario; 46733123450: failure; 46733123453: ongoing; 46733123454: delayed. Provider evidence, not this label, decides the outcome.</p>
      {(!capabilities.purchases || !capabilities.repayments) && <p>Sandbox payments unavailable. Check the server capability message; no local-demo fallback is used.</p>}
    </section>}
    <section><h3>Test loans & decisions</h3>{!loaded ? <p>Loading…</p> : !loans.length ? <p>No test applications.</p> : loans.map(loan => <article className="panel" key={loan.id}>
      <strong>{loan.status} · {testMoney(loan.outstanding, loan.currency)} outstanding</strong><p>{loan.reason}</p>
      <p>Reference {loan.id} · meter ID {loan.meter_id} · accepted policy {loan.terms.policy.id}</p>
      <p>Principal {testMoney(loan.principal, loan.currency)} · frozen total {testMoney(loan.total_due, loan.currency)} · due {when(loan.due_at)} · closed {when(loan.closed_at)}.</p>
      {loan.allocation_id && <EnergyTokenCard client={client} owner={owner} allocationId={loan.allocation_id} />}
      <p>Test allocation {loan.allocated_kwh === null ? "None" : `${loan.allocated_kwh} kWh`} · confirmed physical application unavailable.</p>
      {payments.filter(payment => payment.loan_id === loan.id).map(payment => <p key={payment.reference}>Repayment {payment.status}: received {testMoney(payment.amount, payment.currency)}, applied {testMoney(payment.applied, payment.currency)}, excess {testMoney(payment.excess, payment.currency)}.</p>)}
    </article>)}</section>
    <form onSubmit={repay} hidden={capabilities.newPaymentsPaused}><h3>Self-repayment ({demo ? "UGX DEMO" : "MTN sandbox"})</h3>
      <label>Your test loan<select value={loanId} onChange={event => { setLoanId(event.target.value); setRepayment(""); setRepayAccepted(false); }}><option value="">Choose explicitly</option>
        {loans.filter(row => row.status === "DISBURSED" && row.environment === paymentEnvironment).map(row => <option key={row.id} value={row.id}>{row.id} · {testMoney(row.outstanding, row.currency)}</option>)}
      </select></label>
      {selectedLoan && <p>Policy {selectedLoan.terms.policy.id}; outstanding {testMoney(selectedLoan.outstanding, paymentCurrency)}. Repayment reduces only this loan; it creates no energy.</p>}
      <label>Amount ({paymentCurrency === "UGX" ? "whole UGX" : "EUR TEST cents"})<input inputMode={paymentCurrency === "UGX" ? "numeric" : "decimal"} value={repayment} onChange={event => setRepayment(event.target.value)} required /></label>
      <label><input type="checkbox" checked={repayAccepted} onChange={event => setRepayAccepted(event.target.checked)} /> I accept test repayment terms: any late excess is preserved for reconciliation; no automatic refund or credit.</label>
      <button type="submit" disabled={blocked || !capabilities.repayments || !repayAccepted || !selectedLoan || !validPaymentAmount(repayment) || (!demo && !testPhone(phone))}>{demo ? "Start demo self-repayment" : "Initiate sandbox self-repayment"}</button>
    </form>
    <section><h3>Sandbox receipts & pending recovery</h3>{!loaded ? <p>Loading…</p> : !payments.length ? <p>No sandbox payments.</p> : payments.map(row => <article className="panel" key={row.reference}>
      <strong>{row.purpose} · {row.status} · {testMoney(row.amount, row.currency)}</strong><p>Reference {row.reference} · {when(row.initiated_at)}</p>
      <p>Environment: {row.environment}. Submission: {row.submission_state}. {row.reconciliation_error && `Reconciliation: ${row.reconciliation_error}.`} {row.provider === "LOCAL_DEMO" ? "No external provider or phone prompt." : `Next provider check ${when(row.next_check_at)}.`}</p>
      {row.status === "SETTLED" && row.purpose === "PURCHASE" && <EnergyTokenCard client={client} owner={owner} allocationId={row.allocation_id} />}
      {row.status === "SETTLED" && <p>{row.provider === "LOCAL_DEMO" ? DEMO_SUCCESS : "Provider verified."} {when(row.settled_at)}. Billed {testMoney(row.billed, row.currency)}; remainder {testMoney(row.residual, row.currency)}; debt applied {testMoney(row.applied, row.currency)}; excess {testMoney(row.excess, row.currency)}. Allocation {row.allocated_kwh ?? "None"} kWh; physical delivery unconfirmed.</p>}
      {row.status === "PENDING" && row.provider === "LOCAL_DEMO" && <p role="status">{DEMO_PENDING} Processing: {demoCountdown(row, clock) ?? "Unavailable"} seconds. {demoCountdown(row, clock) === 0 && "Awaiting server confirmation — not yet successful."}</p>}
      {row.provider_receipt && <details><summary>Provider test authorization</summary><p>EUR {row.provider_receipt.amount} · {row.authorization_policy}. Test evidence only, not a currency conversion or real UGX collection.</p></details>}
      {row.status === "PENDING" && row.environment !== environment && <p>This earlier request retains its original provider and currency. Scheduled reconciliation continues; it is not converted.</p>}
      {row.status === "PENDING" && <button type="button" className="secondary" disabled={busy || offline || (row.provider === "LOCAL_DEMO" && demoCountdown(row, clock) !== 0)} onClick={() => void perform(async () => { await client.post(`sandbox/payments/${row.reference}/`, {}); inFlight.current = false; await refresh(); onChanged?.(); })}>{demo ? "Request server demo completion" : "Check with MTN (server backoff applies)"}</button>}
    </article>)}</section>
  </section>;
}
