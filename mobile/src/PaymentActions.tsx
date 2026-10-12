import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError, TransportError, type SessionManager } from "./auth/session.ts";
import { isPositiveWholeUgx, wholeUgxWithinDebt } from "./api/payment-guards.ts";
import { clearRequestId, savedRequestId, saveRequestId } from "./api/request-id.ts";
import { energy, ugx } from "./format.ts";
import type { Loan } from "./api/contracts.ts";

import { normalizeUgandanPhone } from "../../frontend/src/lib/ugandan-phone.ts";

import { parsePaymentRecovery } from "./api/payment-recovery.ts";
type Quote = { amount_ugx: string; meter_no: string; estimated_energy_kwh: string;
  estimated_billed_ugx: string; estimated_residual_ugx: string;
  tariff_code: string; binding: false };
type Initiated = { status: string; external_id: string; reused?: boolean };
const describe = (cause: unknown) => cause instanceof Error ? cause.message : "The request failed.";

export function PurchasePanel({ session, meterNo, enabled, onActivity }: {
  session: SessionManager; meterNo: string; enabled: boolean; onActivity: () => void;
}) {
  const [amount, setAmount] = useState("");
  const [phone, setPhone] = useState("");
  const [quote, setQuote] = useState<Quote | null>(null);
  const [pending, setPending] = useState(false);
  const [receiptsChecked, setReceiptsChecked] = useState(false);
  const [requestId, setRequestId] = useState<string | null>(() =>
    savedRequestId(session.identity, "purchase", meterNo));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const inFlight = useRef(false);

  const checkPending = useCallback(async () => {
    const owner = session.identity;
    try {
      const saved = savedRequestId(owner, "purchase", meterNo);
      const query = new URLSearchParams({ purpose: "PURCHASE", meter_no: meterNo });
      if (saved) query.set("client_request_id", saved);
      const data = parsePaymentRecovery(await session.get<unknown>(`transactions/mobile-payment-recovery/?${query}`),
        { purpose: "PURCHASE", binding: meterNo, requestId: saved });
      if (owner === session.identity) {
        if (saved && data.receipt?.client_request_id === saved) {
          clearRequestId(owner, "purchase", meterNo); setRequestId(null);
        }
        setPending(data.pending === true);
        if (data.receipt) setNotice(`Recovered stored request: ${data.receipt.status}. View its receipt in Activity; no new payment was sent.`);
        setReceiptsChecked(true);
      }
    } catch (cause) {
      if (owner === session.identity) { setReceiptsChecked(false); setError(describe(cause)); }
    }
  }, [session, meterNo]);
  useEffect(() => { void checkPending(); }, [checkPending]);

  const review = async (event: FormEvent) => {
    event.preventDefault(); setError(null); setNotice(null); setQuote(null);
    if (!isPositiveWholeUgx(amount)) { setError("Use a positive whole-UGX amount."); return; }
    setBusy(true);
    try {
      const value = await session.post<Quote>("meter/mobile-purchase-quote/", {
        amount, meter_no: meterNo,
      });
      setQuote(value);
    } catch (cause) { setError(describe(cause)); }
    finally { setBusy(false); }
  };
  const initiate = async () => {
    if (inFlight.current || !quote || !phone.trim() || !enabled || pending || !receiptsChecked) return;
    let canonicalPhone: string;
    try { canonicalPhone = normalizeUgandanPhone(phone); }
    catch (cause) { setError(describe(cause)); return; }
    const id = requestId || crypto.randomUUID();
    const owner = session.identity;
    saveRequestId(owner, "purchase", meterNo, id);
    setRequestId(id); inFlight.current = true; setBusy(true); setError(null); setNotice(null);
    try {
      const result = await session.post<Initiated>("meter/mobile-buy-units/", {
        amount: quote.amount_ugx, phone_number: canonicalPhone, payment_source: "PHONE",
        meter_no: quote.meter_no, client_request_id: id,
      });
      setNotice(result.reused ? "Existing payment request found. Check its status in Activity." :
        "Payment request started. Approving on the phone is not settlement; check provider status in Activity.");
      clearRequestId(owner, "purchase", meterNo);
      setQuote(null); setPhone(""); setAmount(""); setRequestId(null);
      await checkPending();
    } catch (cause) {
      setError(describe(cause));
      if (cause instanceof TransportError || cause instanceof ApiError && cause.code === "PAYMENT_INITIATION_UNCONFIRMED") {
        setNotice("The request outcome is unknown. Check Activity before a manual retry with the same request ID.");
      } else { clearRequestId(owner, "purchase", meterNo); setRequestId(null); }
      await checkPending();
    } finally { inFlight.current = false; setBusy(false); }
  };

  return <section className="panel form-panel">
    <h2>Buy electricity</h2>
    <p className="muted">Selected meter: {meterNo}. Purchase money is whole UGX; estimated energy is in exact 0.01 kWh steps.</p>
    {!enabled && <p className="tag">Mobile payment initiation is disabled by Django until the financial policy is approved and a verified provider is configured.</p>}
    {!receiptsChecked && <p className="muted">Pending-payment check unavailable; new requests remain blocked.</p>}
    {requestId && <p className="muted small">An interrupted request ID is saved on this device. Check Activity first; a manual retry must use the same amount and phone. No request is replayed automatically.</p>}
    {pending && <p className="tag">A purchase is pending. Resolve it in Activity before another payment request.</p>}
    <form className="form-panel" onSubmit={(event) => void review(event)}>
      <label>Amount (whole UGX) <input inputMode="numeric" value={amount} onChange={(event) => {
        setAmount(event.target.value); setQuote(null);
      }} maxLength={12} required /></label>
      <button type="submit" className="secondary" disabled={busy}>Review current tariff</button>
    </form>
    {quote && <div className="quote-box"><h3>Review purchase request</h3>
      <p>Purpose: electricity purchase · meter: {quote.meter_no}</p>
      <p>Provider amount: <strong>{ugx(quote.amount_ugx)}</strong></p>
      <p>Estimated energy: {energy(quote.estimated_energy_kwh)} · tariff {quote.tariff_code}</p>
      <p className="muted">Estimated billed {ugx(quote.estimated_billed_ugx)}; estimated residual {ugx(quote.estimated_residual_ugx)} requires reconciliation. Tariff bands can change before settlement; this quote is not binding.</p>
      <label>Mobile Money phone <input type="tel" value={phone}
        onChange={(event) => setPhone(event.target.value)} required /></label>
      <button disabled={busy || !enabled || pending || !receiptsChecked || !phone.trim()}
        onClick={() => void initiate()}>{busy ? "Submitting…" : "Confirm payment request"}</button>
    </div>}
    {error && <p className="error" role="alert">{error}</p>}
    {notice && <p className="tag" role="status">{notice}</p>}
    <button className="secondary" onClick={onActivity}>View payment activity</button>
  </section>;
}

export function RepaymentPanel({ session, loan, enabled, onActivity }: {
  session: SessionManager; loan: Loan; enabled: boolean; onActivity: () => void;
}) {
  const [amount, setAmount] = useState("");
  const [phone, setPhone] = useState("");
  const [reviewed, setReviewed] = useState(false);
  const [pending, setPending] = useState(false);
  const [receiptsChecked, setReceiptsChecked] = useState(false);
  const [requestId, setRequestId] = useState<string | null>(() =>
    savedRequestId(session.identity, "repayment", loan.loan_id));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const inFlight = useRef(false);
  const checkPending = useCallback(async () => {
    const owner = session.identity;
    try {
      const saved = savedRequestId(owner, "repayment", loan.loan_id);
      const query = new URLSearchParams({ purpose: "LOAN_REPAYMENT", loan_id: loan.loan_id });
      if (saved) query.set("client_request_id", saved);
      const data = parsePaymentRecovery(await session.get<unknown>(`transactions/mobile-payment-recovery/?${query}`),
        { purpose: "LOAN_REPAYMENT", binding: loan.loan_id, requestId: saved });
      if (owner === session.identity) {
        if (saved && data.receipt?.client_request_id === saved) {
          clearRequestId(owner, "repayment", loan.loan_id); setRequestId(null);
        }
        setPending(data.pending === true);
        if (data.receipt) setNotice(`Recovered stored repayment: ${data.receipt.status}. Check Activity; no new collection was sent.`);
        setReceiptsChecked(true);
      }
    } catch (cause) {
      if (owner === session.identity) { setReceiptsChecked(false); setError(describe(cause)); }
    }
  }, [session, loan.loan_id]);
  useEffect(() => { void checkPending(); }, [checkPending]);
  const review = (event: FormEvent) => {
    event.preventDefault(); setError(null); setNotice(null);
    if (!wholeUgxWithinDebt(amount, loan.outstanding_ugx)) {
      setError("Use whole UGX no greater than the whole-UGX portion of the latest outstanding debt. Fractional final debt needs an approved policy.");
      return;
    }
    setReviewed(true);
  };
  const initiate = async () => {
    if (inFlight.current || !reviewed || !phone.trim() || !enabled || pending || !receiptsChecked) return;
    let canonicalPhone: string;
    try { canonicalPhone = normalizeUgandanPhone(phone); }
    catch (cause) { setError(describe(cause)); return; }
    const id = requestId || crypto.randomUUID();
    const owner = session.identity;
    saveRequestId(owner, "repayment", loan.loan_id, id);
    setRequestId(id); inFlight.current = true; setBusy(true); setError(null); setNotice(null);
    try {
      const result = await session.post<Initiated>(`loans/mobile-repay/momo/${loan.id}/`, {
        amount, phone_number: canonicalPhone, client_request_id: id,
      });
      setNotice(result.reused ? "Existing repayment request found. Check Activity." :
        "Repayment request started. Debt does not fall until Django verifies provider settlement.");
      clearRequestId(owner, "repayment", loan.loan_id);
      setReviewed(false); setAmount(""); setPhone(""); setRequestId(null);
      await checkPending();
    } catch (cause) {
      setError(describe(cause));
      if (cause instanceof TransportError || cause instanceof ApiError && cause.code === "PAYMENT_INITIATION_UNCONFIRMED") {
        setNotice("The request outcome is unknown. Check Activity before a manual retry with the same request ID.");
      } else { clearRequestId(owner, "repayment", loan.loan_id); setRequestId(null); }
      await checkPending();
    } finally { inFlight.current = false; setBusy(false); }
  };
  if (loan.status !== "DISBURSED" && loan.status !== "DEFAULTED") return null;
  return <section className="panel form-panel"><h2>Repay this loan</h2>
    <p>Loan {loan.loan_id} · outstanding {ugx(loan.outstanding_ugx)}</p>
    {!enabled && <p className="tag">Mobile payment initiation is disabled by Django pending financial-policy approval and provider setup.</p>}
    {pending && <p className="tag">A repayment is pending. Check Activity before another request.</p>}
    <form className="form-panel" onSubmit={review}>
      <label>Amount (whole UGX) <input inputMode="numeric" value={amount}
        onChange={(event) => { setAmount(event.target.value); setReviewed(false); }} maxLength={12} required /></label>
      <button type="submit" className="secondary">Review repayment</button>
    </form>
    {reviewed && <div className="quote-box"><h3>Confirm repayment request</h3>
      <p>Purpose: self-repayment · loan {loan.loan_id} · provider amount {ugx(amount)}</p>
      <label>Mobile Money phone <input type="tel" value={phone}
        onChange={(event) => setPhone(event.target.value)} required /></label>
      <button disabled={busy || !enabled || pending || !receiptsChecked || !phone.trim()}
        onClick={() => void initiate()}>{busy ? "Submitting…" : "Confirm repayment request"}</button>
    </div>}
    {!receiptsChecked && <p className="muted">Pending-payment check unavailable; new requests remain blocked.</p>}
    {requestId && <p className="muted small">An interrupted request ID is saved on this device. Check Activity first; a manual retry must use the same amount and phone. No request is replayed automatically.</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {notice && <p className="tag" role="status">{notice}</p>}
    <button className="secondary" onClick={onActivity}>View payment activity</button>
  </section>;
}
