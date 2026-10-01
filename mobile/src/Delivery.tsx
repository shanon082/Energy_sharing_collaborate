import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { TransportError, type SessionManager } from "./auth/session.ts";
import type { AllocationStatus } from "./api/contracts.ts";
import { dateTime, energy } from "./format.ts";

type Delivery = { id: number; command_id: string; request_id: string | null;
  amount_kwh: string; status: string; created_at: string; applied_at: string | null };
type History = { meter_no: string; deliveries: Delivery[] };

export function DeliveryPanel({ session, meterNo, allocation, onReserved }: {
  session: SessionManager; meterNo: string; allocation: AllocationStatus | null;
  onReserved: () => void;
}) {
  const [amount, setAmount] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [history, setHistory] = useState<Delivery[] | null>(null);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const inFlight = useRef(false);

  const loadHistory = useCallback(async () => {
    const owner = session.identity;
    try {
      const result = await session.get<History>(`meter/mobile-deliveries/?meter_no=${encodeURIComponent(meterNo)}`);
      if (owner === session.identity && result.meter_no === meterNo) {
        setHistory(result.deliveries);
      }
    } catch (cause) {
      if (owner === session.identity) setError(cause instanceof Error ? cause.message : "Delivery history unavailable.");
    }
  }, [session, meterNo]);
  useEffect(() => { void loadHistory(); }, [loadHistory]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (inFlight.current || !confirmed) return;
    if (!/^(?:0|[1-9]\d*)(?:\.\d{1,2})?$/.test(amount) || !/[1-9]/.test(amount)) {
      setError("Use a positive amount in 0.01 kWh increments."); return;
    }
    const id = requestId || crypto.randomUUID();
    setRequestId(id); inFlight.current = true; setBusy(true); setError(null); setNotice(null);
    try {
      await session.post("meter/deliver/", { meter_no: meterNo, amount, request_id: id });
      setNotice("Energy reserved for simulated delivery. Meter application is not confirmed yet.");
      setConfirmed(false); setAmount(""); setRequestId(null);
      await loadHistory(); onReserved();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Delivery request outcome is unknown.");
      if (cause instanceof TransportError) {
        setNotice("The request outcome is unknown. Check delivery history before a manual retry; it will use the same request ID.");
      } else { setRequestId(null); }
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
    {notice && <p className="tag" role="status">{notice}</p>}
    <h3>Delivery history</h3>
    <button className="secondary" onClick={() => void loadHistory()}>Refresh status</button>
    {history === null && <p className="muted">Loading delivery history…</p>}
    {history?.length === 0 && <p className="muted">No delivery commands for this meter.</p>}
    {history?.map((row) => <div className="list-row" key={row.id}>
      <span>{dateTime(row.created_at)}<small>{row.status === "APPLIED" ?
        `Applied ${dateTime(row.applied_at)}` : row.status === "OUTCOME_UNKNOWN" ?
        "Outcome unknown — reconciliation required" : row.status}</small></span>
      <strong>{energy(row.amount_kwh)}</strong>
    </div>)}
  </section>;
}
