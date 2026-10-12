import { useCallback, useEffect, useRef, useState } from "react";
import type { SessionManager } from "./auth/session.ts";
import { dateTime, energy, ugx } from "./format.ts";
import { LatestRead } from "./api/read-scope.ts";
import { parseReceipts, parseReceipt, parseNotices, parseHistory, type Page, type Receipt } from "./api/activity-contracts.ts";

const failure = (cause: unknown) => cause instanceof Error ? cause.message : "Activity is unavailable.";
function useFeed<T>(session: SessionManager, path: string, parse: (data: unknown) => Page<T>) {
  const [data, setData] = useState<Page<T> | null>(null);
  const [fetchedAt, setFetchedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const scope = useRef(new LatestRead());
  const load = useCallback(async (before?: number | null) => {
    const owner = session.identity, ticket = scope.current.begin();
    setBusy(true); setError(null);
    try {
      const page = parse(await session.get<unknown>(`${path}${before ? `?before_id=${before}` : ""}`));
      if (owner !== session.identity || !scope.current.current(ticket)) return;
      setData((old) => ({ ...page, rows: before ? [...(old?.rows ?? []), ...page.rows] : page.rows }));
      if (!before) setFetchedAt(new Date().toISOString());
    } catch (cause) {
      if (owner === session.identity && scope.current.current(ticket)) setError(failure(cause));
    } finally { if (owner === session.identity && scope.current.current(ticket)) setBusy(false); }
  }, [session, path, parse]);
  useEffect(() => { void load(); const reads = scope.current; return () => reads.invalidate(); }, [load]);
  return { data, fetchedAt, error, busy, load };
}
function Freshness({ feed }: { feed: { fetchedAt: string | null; error: string | null } }) {
  return <>{feed.error && <p className="error" role="alert">{feed.error} {feed.fetchedAt && "Displayed records are stale."}</p>}
    {feed.fetchedAt && <p className="muted small">Fetched {dateTime(feed.fetchedAt)}</p>}</>;
}

export function Activity({ session }: { session: SessionManager }) {
  const receipts = useFeed(session, "transactions/mobile-receipts/", parseReceipts);
  const notices = useFeed(session, "meter/mobile-notifications/", parseNotices);
  const history = useFeed(session, "transactions/mobile-history/", parseHistory);
  const [error, setError] = useState<string | null>(null);
  const [marking, setMarking] = useState(false);
  const [detail, setDetail] = useState<Receipt | null>(null);
  const detailReads = useRef(new LatestRead());
  useEffect(() => { const reads = detailReads.current; return () => reads.invalidate(); }, []);
  const busy = receipts.busy || notices.busy || history.busy || marking;
  const reload = () => {
    detailReads.current.invalidate(); setDetail(null); setError(null);
    void receipts.load(); void notices.load(); void history.load();
  };
  const markRead = async () => {
    const owner = session.identity;
    const ids = notices.data?.rows.filter((row) => !row.is_read).slice(0, 50).map((row) => row.id) ?? [];
    if (!ids.length) return;
    setMarking(true); setError(null);
    try { await session.patch("meter/mobile-notifications/", { ids }); if (owner === session.identity) await notices.load(); }
    catch (cause) { if (owner === session.identity) setError(failure(cause)); }
    finally { if (owner === session.identity) setMarking(false); }
  };
  const showReceipt = async (receipt: Receipt) => {
    const owner = session.identity, ticket = detailReads.current.begin();
    setDetail(null); setError(null);
    try {
      const data = await session.get<{ receipt: unknown }>(`transactions/mobile-receipts/${encodeURIComponent(receipt.external_id)}/`);
      const parsed = parseReceipt(data.receipt);
      if (parsed.external_id !== receipt.external_id) throw new Error("Receipt identity changed.");
      if (owner === session.identity && detailReads.current.current(ticket)) setDetail(parsed);
    } catch (cause) { if (owner === session.identity && detailReads.current.current(ticket)) setError(failure(cause)); }
  };
  return <>
    <h1>Activity</h1><p className="muted">Stored payment records, alerts and historical events.</p>
    <button className="secondary" disabled={busy} onClick={reload}>{busy ? "Refreshing…" : "Refresh activity"}</button>
    {error && <p className="error" role="alert">{error}</p>}
    {detail && <section className="panel"><h2>Receipt details</h2>
      <p>{detail.purpose} · {detail.status}</p><p>Recorded amount: {ugx(detail.amount_ugx)}</p>
      <p>{detail.environment === "SIMULATOR" ? "Simulation only" : "Stored payment record"} ·
        {detail.settlement_recorded ? ` Settlement recorded ${dateTime(detail.settled_at)}` : " Settlement not confirmed"}</p>
      {detail.purpose === "PURCHASE" && <>
        <p>Source-linked energy allocated: {detail.allocated_energy_kwh === null ? "Not recorded" : energy(detail.allocated_energy_kwh)}</p>
        <p>Meter application acknowledged: {detail.delivery_confirmed_kwh === null ? "Not recorded" : energy(detail.delivery_confirmed_kwh)}</p>
        <p className="muted small">Payment verification does not prove meter delivery. Simulator acknowledgement is not evidence of physical hardware application.</p>
      </>}
      {detail.purchase_billed_ugx !== null && <p>Billed {ugx(detail.purchase_billed_ugx)} · Residual {ugx(detail.purchase_residual_ugx)}</p>}
      {detail.repayment_applied_ugx !== null && <p>Applied to debt {ugx(detail.repayment_applied_ugx)} · Excess {ugx(detail.repayment_excess_ugx)}</p>}
      <p className="muted small">Residuals and excess remain recorded for reconciliation. This read does not contact a provider.</p>
      <button className="secondary" onClick={() => { detailReads.current.invalidate(); setDetail(null); }}>Close receipt</button>
    </section>}
    <section className="panel"><h2>Payment requests and receipts</h2><Freshness feed={receipts} />
      {!receipts.data ? <p className="muted">{receipts.busy ? "Loading receipts…" : "Receipts unavailable."}</p> : !receipts.data.rows.length ?
        <p className="muted">No payment intents recorded.</p> : receipts.data.rows.map((row) =>
          <div className="list-row" key={row.external_id}><span>
            {row.purpose === "PURCHASE" ? `Purchase · ${row.meter_no || "meter unavailable"}` : `Loan repayment · ${row.loan_id || "loan unavailable"}`}
            <small>{row.status} · {dateTime(row.initiated_at)}{row.environment === "SIMULATOR" && " · Simulation only"}</small>
            <button className="secondary" onClick={() => void showReceipt(row)}>View receipt</button>
          </span><strong>{ugx(row.amount_ugx)}</strong></div>)}
      {receipts.data?.next && <button disabled={receipts.busy} onClick={() => void receipts.load(receipts.data?.next)}>More receipts</button>}
      <p className="muted small">Pending requests are not paid electricity. Refresh reads stored status; verified settlement runs independently of this screen.</p>
    </section>
    <section className="panel"><h2>Alerts</h2><Freshness feed={notices} />
      {notices.data?.rows.some((row) => !row.is_read) && <button className="secondary" disabled={notices.busy || marking || Boolean(notices.error)}
        onClick={() => void markRead()}>Mark displayed alerts read</button>}
      {!notices.data ? <p className="muted">{notices.busy ? "Loading alerts…" : "Alerts unavailable."}</p> : !notices.data.rows.length ?
        <p className="muted">No alerts.</p> : notices.data.rows.map((row) =>
          <div className="list-row" key={row.id}><span>{row.message}<small>{dateTime(row.occurred_at)} · {row.is_read ? "Read" : "Unread"}</small></span></div>)}
      {notices.data?.next && <button disabled={notices.busy} onClick={() => void notices.load(notices.data?.next)}>More alerts</button>}
    </section>
    <section className="panel"><h2>Historical event log</h2><Freshness feed={history} />
      {!history.data ? <p className="muted">{history.busy ? "Loading history…" : "History unavailable."}</p> : !history.data.rows.length ?
        <p className="muted">No logged events.</p> : history.data.rows.map((row) =>
          <div className="list-row" key={row.id}><span>{row.transaction_type_display}<small>{row.status} · {dateTime(row.created_at)}</small>
            {row.recorded_units !== null && <small>Recorded units: {row.recorded_units}</small>}</span>
            <strong>{row.recorded_amount === null ? "Amount unavailable" : `Recorded amount: ${row.recorded_amount}`}</strong></div>)}
      {history.data?.next && <button disabled={history.busy} onClick={() => void history.load(history.data?.next)}>More events</button>}
      <p className="muted small">Legacy log units are unconfirmed. Values are shown as recorded, without interpreting them as UGX or kWh. This log does not include every legacy table.</p>
    </section>
  </>;
}
