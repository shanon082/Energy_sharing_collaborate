import { useCallback, useEffect, useState } from "react";
import type { SessionManager } from "./auth/session.ts";
import { dateTime, ugx } from "./format.ts";

type Receipt = { external_id: string; purpose: string; status: string; amount_ugx: string;
  currency: string; meter_no: string | null; loan_id: string | null;
  purchase_billed_ugx: string | null; purchase_residual_ugx: string | null;
  initiated_at: string; settled_at: string | null };
type Notice = { id: number; message: string; occurred_at: string; is_read: boolean; meter_no: string | null };
type HistoryRow = { id: string; transaction_type_display: string; status: string;
  amount: number | null; created_at: string | null };
const failure = (cause: unknown) => cause instanceof Error ? cause.message : "Activity is unavailable.";

export function Activity({ session }: { session: SessionManager }) {
  const [receipts, setReceipts] = useState<Receipt[] | null>(null);
  const [notices, setNotices] = useState<Notice[] | null>(null);
  const [history, setHistory] = useState<HistoryRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    const owner = session.identity;
    setBusy(true); setError(null);
    const results = await Promise.allSettled([
      session.get<{ receipts: Receipt[] }>("transactions/mobile-receipts/"),
      session.get<{ notifications: Notice[] }>("meter/notifications/"),
      session.get<{ transactions: HistoryRow[] }>("transactions/history/?page=1&page_size=30"),
    ]);
    if (owner !== session.identity) return;
    const [payments, alerts, activity] = results;
    if (payments.status === "fulfilled") setReceipts(payments.value.receipts);
    if (alerts.status === "fulfilled") setNotices(alerts.value.notifications);
    if (activity.status === "fulfilled") setHistory(activity.value.transactions);
    const failed = results.find((result) => result.status === "rejected");
    if (failed?.status === "rejected") setError(failure(failed.reason));
    setBusy(false);
  }, [session]);
  useEffect(() => { void reload(); }, [reload]);

  const markRead = async () => {
    setBusy(true); setError(null);
    try {
      await session.patch("meter/notifications/", { all: true });
      await reload();
    } catch (cause) { setError(failure(cause)); }
    finally { setBusy(false); }
  };

  return <>
    <h1>Activity</h1>
    <p className="muted">Your payment receipts, alerts and historical transactions.</p>
    <button className="secondary" disabled={busy} onClick={() => void reload()}>
      {busy ? "Refreshing…" : "Refresh activity"}</button>
    {error && <p className="error" role="alert">{error} Previously shown records may be stale.</p>}
    <section className="panel"><h2>Verified payment intents</h2>
      {receipts === null ? <p className="muted">Loading receipts…</p> : receipts.length === 0 ?
        <p className="muted">No payment intents recorded.</p> : receipts.map((row) =>
          <div className="list-row" key={row.external_id}><span>
            {row.purpose === "PURCHASE" ? `Purchase · ${row.meter_no || "meter unavailable"}` :
              `Loan repayment · ${row.loan_id || "loan unavailable"}`}
            <small>{row.status} · {dateTime(row.initiated_at)}</small>
            {row.status === "SETTLED" && row.purchase_residual_ugx !== null &&
              row.purchase_residual_ugx !== "0.00" &&
              <small>Residual {ugx(row.purchase_residual_ugx)} requires reconciliation</small>}
          </span><strong>{ugx(row.amount_ugx)}</strong></div>)}
      <p className="muted small">Only Django provider verification establishes settlement. Pending requests are not paid electricity.</p>
    </section>
    <section className="panel"><h2>Alerts</h2>
      {notices?.some((row) => !row.is_read) && <button className="secondary" disabled={busy}
        onClick={() => void markRead()}>Mark all read</button>}
      {notices === null ? <p className="muted">Loading alerts…</p> : notices.length === 0 ?
        <p className="muted">No alerts.</p> : notices.map((row) =>
          <div className="list-row" key={row.id}><span>{row.message}
            <small>{dateTime(row.occurred_at)} · {row.is_read ? "Read" : "Unread"}</small>
          </span></div>)}
    </section>
    <section className="panel"><h2>Transaction history</h2>
      {history === null ? <p className="muted">Loading history…</p> : history.length === 0 ?
        <p className="muted">No transactions.</p> : history.map((row) =>
          <div className="list-row" key={row.id}><span>{row.transaction_type_display}
            <small>{row.status} · {row.created_at || "Date unavailable"}</small></span>
            <strong>{row.amount == null ? "Amount unavailable" : ugx(String(row.amount))}</strong></div>)}
      <p className="muted small">Historical entries may combine legacy sources. Receipts above show exact recorded UGX for new payment intents.</p>
    </section>
  </>;
}
