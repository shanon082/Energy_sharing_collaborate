import { useEffect, useState, type FormEvent } from "react";
import type { SessionManager } from "./auth/session.ts";
import { dateTime } from "./format.ts";
import { enrollmentLabel, type MeterRequest } from "./api/enrollment.ts";
import { normalizePrototypeMeterNumber, parsePrototypeEnrollment, PROTOTYPE_OWNERSHIP_NOTICE } from "../../frontend/src/lib/meter-enrollment.ts";
import type { MeterInfo } from "./api/contracts.ts";

export function MeterOnboarding({ session, hasMeter, onRefresh, onLinked }: {
  session: SessionManager; hasMeter: boolean; onRefresh: () => void; onLinked: (meter: MeterInfo) => void;
}) {
  const [number, setNumber] = useState("");
  const [requests, setRequests] = useState<MeterRequest[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [selfEnrollment, setSelfEnrollment] = useState<boolean | null>(null);
  const load = async () => {
    const owner = session.identity;
    try {
      const result = await session.get<{ requests: MeterRequest[]; sandbox_self_enrollment?: boolean }>("meter/mobile-onboarding/");
      if (owner === session.identity) { setRequests(result.requests); setSelfEnrollment(result.sandbox_self_enrollment === true); }
    } catch (cause) {
      if (owner === session.identity) setError(cause instanceof Error ? cause.message : "Onboarding is unavailable.");
    }
  };
  useEffect(() => { void load(); }, [session]);
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setError(null); setNotice(null);
    if (selfEnrollment === null || busy) return;
    let normalized: string;
    try { normalized = normalizePrototypeMeterNumber(number); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Enter a meter number."); return; }
    const owner = session.identity;
    setBusy(true);
    try {
      const response = await session.post<{ message: string }>(selfEnrollment ? "meter/sandbox-meter-enrollment/" : "meter/mobile-meter-requests/", { meter_no: normalized });
      if (owner !== session.identity) return;
      if (selfEnrollment) onLinked(parsePrototypeEnrollment(response, normalized).meter);
      setNotice(response.message); setNumber(""); await load(); if (owner === session.identity) onRefresh();
    } catch (cause) {
      if (owner === session.identity) setError(cause instanceof Error ? cause.message : "Request could not be confirmed. Retrying the same meter number will not create another request.");
    } finally { if (owner === session.identity) setBusy(false); }
  };
  return <section className="panel form-panel"><h2>{hasMeter ? "Add another meter" : "Add your meter"}</h2>
    <p className="muted">{selfEnrollment ? "For this prototype, we assume the number you enter belongs to you. Linking enables cloud test allocations; hardware connection is pending." : "Physical enrollment records a request; staff must verify your right to use the meter before assignment."}</p>
    {selfEnrollment && <p className="muted">{PROTOTYPE_OWNERSHIP_NOTICE}</p>}
    <form className="form-panel" onSubmit={(event) => void submit(event)}>
      <label>Meter number <input value={number} maxLength={100} required autoComplete="off"
        onChange={(event) => setNumber(event.target.value)} /></label>
      <button disabled={busy || selfEnrollment === null}>{busy ? "Recording…" : selfEnrollment ? "Add your meter" : "Request meter verification"}</button>
    </form>
    {error && <p className="error" role="alert">{error}</p>}
    {notice && <p className="tag" role="status">{notice}</p>}
    {requests?.map((row) => <div className="list-row" key={row.id}>
      <span>{row.meter_number}<small>{dateTime(row.requested_at)}</small></span>
      <span><strong>{enrollmentLabel(row.status)}</strong>
        {row.decision_reason && <small>{row.decision_reason}</small>}</span>
      {selfEnrollment && row.status === "PENDING" && <button type="button" className="secondary" disabled={busy}
        onClick={() => { setNumber(row.meter_number); setNotice("Review the number and tap Add your meter to explicitly retry using the prototype ownership assumption."); }}>Retry as prototype meter</button>}
    </div>)}
    <button className="secondary" onClick={() => { void load(); onRefresh(); }}>Refresh meters</button>
  </section>;
}
