import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { TransportError, type SessionManager } from "./auth/session.ts";
import { clearRequestId, savedRequestId, saveRequestId } from "./api/request-id.ts";
import type { AllocationStatus, MeterInfo } from "./api/contracts.ts";
import { dateTime, energy } from "./format.ts";

import { parseDeliveries, type Delivery } from "./api/activity-contracts.ts";
import { LatestRead } from "./api/read-scope.ts";

export function DeliveryPanel({ session, meter, allocation, onReserved }: {
  session: SessionManager; meter: MeterInfo; allocation: AllocationStatus | null;
  onReserved: () => void;
}) {
  const meterNo = meter.meter_number;
  const reads = useRef(new LatestRead());
  const [fetchedAt, setFetchedAt] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [historyBusy, setHistoryBusy] = useState(false);
  const [next, setNext] = useState<number | null>(null);
  const [amount, setAmount] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [history, setHistory] = useState<Delivery[] | null>(null);
  const [requestId, setRequestId] = useState<string | null>(() =>
    savedRequestId(session.identity, "delivery", meterNo));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const inFlight = useRef(false);

  const loadHistory = useCallback(async (before?: number) => {
    const owner = session.identity, ticket = reads.current.begin();
    setHistoryBusy(true); setHistoryError(null);
    try {
      const result = parseDeliveries(await session.get<unknown>(`meter/mobile-deliveries/?meter_id=${meter.id}&meter_no=${encodeURIComponent(meterNo)}${before ? `&before_id=${before}` : ""}`), meter);
      if (owner === session.identity && reads.current.current(ticket)) {
        setHistory((old) => before ? [...(old ?? []), ...result.rows] : result.rows);
        setNext(result.next); if (!before) setFetchedAt(new Date().toISOString());
        const saved = savedRequestId(owner, "delivery", meterNo);
        if (saved && result.rows.some((row) => row.request_id === saved)) {
          clearRequestId(owner, "delivery", meterNo); setRequestId(null);
        }
      }
    } catch (cause) {
      if (owner === session.identity && reads.current.current(ticket)) setHistoryError(cause instanceof Error ? cause.message : "Delivery history unavailable.");
    } finally { if (owner === session.identity && reads.current.current(ticket)) setHistoryBusy(false); }
  }, [session, meter, meterNo]);
  useEffect(() => { void loadHistory(); const scope = reads.current; return () => scope.invalidate(); }, [loadHistory]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (inFlight.current || !confirmed) return;
    if (!/^(?:0|[1-9]\d*)(?:\.\d{1,2})?$/.test(amount) || !/[1-9]/.test(amount)) {
      setError("Use a positive amount in 0.01 kWh increments."); return;
    }
    const id = requestId || crypto.randomUUID();
    const owner = session.identity;
    saveRequestId(owner, "delivery", meterNo, id);
    setRequestId(id); inFlight.current = true; setBusy(true); setError(null); setNotice(null);
    try {
      await session.post("meter/deliver/", { meter_no: meterNo, amount, request_id: id });
      setNotice("Energy reserved for simulated delivery. Meter application is not confirmed yet.");
      clearRequestId(owner, "delivery", meterNo);
      setConfirmed(false); setAmount(""); setRequestId(null);
      await loadHistory(); onReserved();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Delivery request outcome is unknown.");
      if (cause instanceof TransportError) {
        setNotice("The request outcome is unknown. Check delivery history before a manual retry; it will use the same request ID.");
      } else { clearRequestId(owner, "delivery", meterNo); setRequestId(null); }
      await loadHistory();
    } finally { inFlight.current = false; setBusy(false); }
  };

  return <section className="panel form-panel">
    <h2>Load your selected meter</h2>
    {allocation?.delivery_environment !== "SIMULATOR" ?
      <p className="muted">Meter loading is unavailable until a reviewed physical device protocol is connected.</p> : <>
      <p className="tag">Simulation only. A queued command or gateway receipt is not proof of meter application.</p>
      <p>Available attributable entitlement: <strong>{energy(allocation.available_kwh)}</strong></p>
      <form className="form-panel" onSubmit={(event) => void submit(event)}>
        <label>Energy to reserve (kWh, 0.01 increments)
          <input inputMode="decimal" value={amount} onChange={(event) => {
            setAmount(event.target.value); setConfirmed(false);
          }} required /></label>
        <label className="check-row"><input type="checkbox" checked={confirmed}
          onChange={(event) => setConfirmed(event.target.checked)} />
          Reserve {amount || "the entered amount"} kWh for simulated meter {meterNo}</label>
        <button type="submit" disabled={busy || !confirmed}>{busy ? "Requesting…" : "Confirm load request"}</button>
      </form>
    </>}
    {error && <p className="error" role="alert">{error}</p>}
    {historyError && <p className="error" role="alert">{historyError}</p>}
    {notice && <p className="tag" role="status">{notice}</p>}
    {requestId && <p className="muted small">A request ID is saved for manual retry after checking history. Use the same meter and amount; nothing is replayed automatically.</p>}
    <h3>Delivery history</h3>
    <button className="secondary" disabled={historyBusy || busy} onClick={() => void loadHistory()}>Refresh status</button>
    {fetchedAt && <p className="muted small">Fetched {dateTime(fetchedAt)}{historyError && " · Displayed history is stale"}</p>}
    {history === null && <p className="muted">{historyBusy ? "Loading delivery history…" : "Delivery history unavailable."}</p>}
    {history?.length === 0 && <p className="muted">No delivery commands for this meter.</p>}
    {history?.map((row) => <div className="list-row" key={row.id}>
      <span>{dateTime(row.created_at)}<small>{row.application_confirmed ?
        `Applied ${dateTime(row.applied_at)}` : row.status === "OUTCOME_UNKNOWN" ?
        "Outcome unknown — reconciliation required" : row.status === "APPLIED" ? "Application evidence incomplete" : row.status}</small></span>
      <strong>{energy(row.amount_kwh)}</strong>
      <small>{row.source} · {row.environment === "SOFTWARE_BENCH" ? "Software bench only" : row.environment === "SIMULATOR" ? "Simulation only" : "Environment unconfirmed"}</small>
    </div>)}
    {next && <button disabled={historyBusy || busy} onClick={() => void loadHistory(next)}>More deliveries</button>}
  </section>;
}
