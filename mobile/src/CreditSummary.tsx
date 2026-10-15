import { useEffect, useRef, useState } from "react";
import { SessionExpired, type SessionManager } from "./auth/session.ts";
import { LatestRead } from "./api/read-scope.ts";
import { Icon } from "./ui.tsx";
import { dateTime, ugx } from "./format.ts";

import { parseCreditSummary, type Credit } from "./api/credit-summary.ts";
export { parseCreditSummary } from "./api/credit-summary.ts";

export function CreditSummary({ session, revision, onExpired, onLoans, demo }: { session: SessionManager; revision: number; onExpired: () => void; onLoans: () => void; demo: boolean }) {
  const [data, setData] = useState<Credit | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const reads = useRef(new LatestRead());
  useEffect(() => {
    const scope = reads.current, ticket = scope.begin(), owner = session.identity;
    setLoading(true); setError(null);
    void session.get<unknown>("loans/mobile-eligibility/").then(result => {
      if (owner === session.identity && scope.current(ticket)) setData(parseCreditSummary(result));
    }).catch(cause => {
      if (owner !== session.identity || !scope.current(ticket)) return;
      if (cause instanceof SessionExpired) { onExpired(); return; }
      setData(null); setError(cause instanceof Error ? cause.message : "Assessment unavailable.");
    }).finally(() => { if (owner === session.identity && scope.current(ticket)) setLoading(false); });
    return () => scope.invalidate();
  }, [session, revision, retry, onExpired]);
  return <section className="panel credit-summary"><div className="section-title"><h2>Credit overview</h2><span className="row-icon"><Icon name="shield" /></span></div>
    {error ? <><p className="error" role="alert">{error}</p><button className="text-button" onClick={() => setRetry(value => value + 1)}>Retry assessment</button></> : <>
      <div className="credit-summary-grid"><div><span className="muted">Your score</span><strong className="credit-score">{loading ? "…" : data?.score ?? "—"}{data?.score != null && !loading && <small>/100</small>}</strong></div><div><span className="muted">Borrowing limit</span><strong className="credit-limit">{loading ? "Loading…" : ugx(data?.limit)}</strong><button className="text-button" onClick={onLoans}>View loans <Icon name="arrow" /></button></div></div>
      {!loading && data?.score == null && <p className="muted">Your assessment is not ready. Link a meter, then check again.</p>}
      <details className="info-disclosure"><summary>How your score is calculated</summary>{(demo || data?.simulated) && <p className="small">Simulated assessment · no external account verification.</p>}{data?.reason && <p>{data.reason}</p>}{Object.entries(data?.factors ?? {}).map(([factor, value]) => <div className="list-row" key={factor}><span>{factor.replaceAll("_", " ")}</span><strong>{value}</strong></div>)}<p className="muted small">Assessed {dateTime(data?.calculatedAt)}. Final eligibility is checked when you apply.</p></details>
    </>}
  </section>;
}
