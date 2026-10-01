import { useEffect, useState, type FormEvent } from "react";
import type { SessionManager } from "./auth/session.ts";
import type { MeterInfo } from "./api/contracts.ts";
import { energy, ugx } from "./format.ts";

type Eligibility = { score: number | null; eligible: boolean; can_apply: boolean;
  reason: string | null; source: string | null; tier?: string;
  min_loan_ugx?: string; max_loan_ugx?: string; interest_rate_percent?: string | null };
type Quote = { requested_ugx: string; estimated_approved_ugx: string; estimated_interest_ugx: string;
  estimated_total_due_ugx: string; estimated_energy_kwh: string; unallocated_ugx: string;
  interest_rate_percent: string; tenure_months: number; meter_no: string; tariff_code: string;
  binding: false; application_available: false; application_blocker: string };

export function LoanQuote({ session, meters, selectedMeter }: {
  session: SessionManager; meters: MeterInfo[] | null; selectedMeter: string | null;
}) {
  const [eligibility, setEligibility] = useState<Eligibility | null>(null);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [amount, setAmount] = useState("");
  const [tenure, setTenure] = useState("6");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const owner = session.identity;
    void session.get<Eligibility>("loans/mobile-eligibility/").then((value) => {
      if (owner === session.identity) setEligibility(value);
    }).catch((cause) => {
      if (owner === session.identity) setError(cause instanceof Error ? cause.message : "Eligibility unavailable.");
    });
  }, [session]);
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setError(null); setQuote(null);
    if (!selectedMeter || !/^\d+$/.test(amount) || amount === "0") {
      setError("Select your meter and enter a whole-UGX amount."); return;
    }
    setBusy(true);
    try {
      const result = await session.post<Quote>("loans/mobile-quote/", {
        amount_requested: amount, tenure_months: Number(tenure), meter_no: selectedMeter,
      });
      setQuote(result);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Quote unavailable."); }
    finally { setBusy(false); }
  };
  return <section className="panel form-panel">
    <h2>Loan eligibility and quotation</h2>
    {error && <p className="error" role="alert">{error}</p>}
    {!eligibility && !error && <p className="muted" role="status">Loading eligibility…</p>}
    {eligibility && <>
      <p>Score: <strong>{eligibility.score === null ? "Unavailable" :
        `${eligibility.score} (self-reported profile estimate)`}</strong></p>
      <p className="muted">{eligibility.reason || `Tier ${eligibility.tier || "unavailable"}; current cap ${ugx(eligibility.max_loan_ugx)}.`}</p>
      {eligibility.can_apply && <form className="form-panel" onSubmit={(event) => void submit(event)}>
        <label>Requested amount (whole UGX) <input inputMode="numeric" value={amount}
          onChange={(event) => { setAmount(event.target.value); setQuote(null); }} required /></label>
        <label>Repayment term <select value={tenure} onChange={(event) => { setTenure(event.target.value); setQuote(null); }}>
          {Array.from({ length: 12 }, (_, index) => index + 1).map((months) =>
            <option key={months} value={months}>{months} month{months === 1 ? "" : "s"}</option>)}
        </select></label>
        <p className="muted">Selected meter: {meters?.find((meter) => meter.meter_number === selectedMeter)?.label || "None"}</p>
        <button type="submit" disabled={busy || !selectedMeter}>{busy ? "Quoting…" : "Get provisional quote"}</button>
      </form>}
    </>}
    {quote && <div className="quote-box">
      <h3>Provisional terms</h3>
      <p>Meter {quote.meter_no} · tariff {quote.tariff_code} · {quote.tenure_months} months</p>
      <p>Requested {ugx(quote.requested_ugx)} · estimated approved {ugx(quote.estimated_approved_ugx)}</p>
      <p>Estimated energy {energy(quote.estimated_energy_kwh)}</p>
      <p>Rate {quote.interest_rate_percent}% · estimated interest {ugx(quote.estimated_interest_ugx)} ·
        estimated total due {ugx(quote.estimated_total_due_ugx)}</p>
      <p className="muted">Potential UGX residual after energy rounding: {ugx(quote.unallocated_ugx)}. This is not a binding loan offer.</p>
      <p className="error">{quote.application_blocker}</p>
    </div>}
  </section>;
}
