import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError, SessionExpired, type SessionManager } from "./auth/session.ts";
import { LatestRead } from "./api/read-scope.ts";
import { parseAccountDetails, type AccountDetails, type Choice } from "./api/profile-contracts.ts";
import { dateTime } from "./format.ts";

const errorText = (cause: unknown) => cause instanceof Error ? cause.message : "Request failed.";
function Options({ choices, value }: { choices: Choice[]; value: string | null }) {
  return <><option value="">Not provided</option>
    {value && !choices.some((choice) => choice.value === value) &&
      <option value={value}>Previously stored value — choose a current option</option>}
    {choices.map((choice) => <option key={choice.value} value={choice.value}>{choice.label}</option>)}</>;
}

/** Ordinary account preferences only. Credit assessment is server-owned. */
export function ProfileEditor({ session, onExpired }: { session: SessionManager; onExpired: () => void }) {
  const [details, setDetails] = useState<AccountDetails | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [blocked, setBlocked] = useState(false);
  const [fetched, setFetched] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const reads = useRef(new LatestRead());
  const mounted = useRef(false);

  const load = useCallback(async () => {
    const owner = session.identity, ticket = reads.current.begin();
    setLoading(true); setError(null); setNotice(null);
    try {
      const account = parseAccountDetails(await session.get<unknown>("auth/mobile-account-details/"));
      if (!mounted.current || owner !== session.identity || !reads.current.current(ticket)) return;
      setDetails(account); setFetched(new Date().toISOString()); setBlocked(false);
    } catch (cause) {
      if (!mounted.current || owner !== session.identity || !reads.current.current(ticket)) return;
      if (cause instanceof SessionExpired) { onExpired(); return; }
      setError(errorText(cause)); setBlocked(true);
    } finally {
      if (mounted.current && owner === session.identity && reads.current.current(ticket)) setLoading(false);
    }
  }, [session, onExpired]);

  useEffect(() => {
    mounted.current = true; void load();
    return () => { mounted.current = false; reads.current.invalidate(); };
  }, [load]);

  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (loading || busy || blocked || !details?.values) return;
    const owner = session.identity, ticket = reads.current.begin();
    setBusy(true); setNotice(null); setError(null);
    try {
      const { address, energy_preference, payment_method } = details.values;
      const result = parseAccountDetails(await session.patch<unknown>("auth/mobile-account-details/",
        { address, energy_preference, payment_method }));
      if (!mounted.current || owner !== session.identity || !reads.current.current(ticket)) return;
      setDetails(result); setFetched(new Date().toISOString()); setNotice("Account details saved.");
    } catch (cause) {
      if (!mounted.current || owner !== session.identity || !reads.current.current(ticket)) return;
      if (cause instanceof SessionExpired) { onExpired(); return; }
      setError(errorText(cause)); setBlocked(!(cause instanceof ApiError));
    } finally {
      if (mounted.current && owner === session.identity && reads.current.current(ticket)) setBusy(false);
    }
  };

  return <>
    {loading && <p className="muted" role="status">Loading account details…</p>}
    {notice && <p className="tag" role="status">{notice}</p>}
    <button type="button" className="secondary" disabled={loading || busy} onClick={() => void load()}>Refresh account details</button>
    {error && <p className="error" role="alert">Account details: {error}</p>}
    {fetched && error && <p className="stale">Stale — last fetched {dateTime(fetched)}</p>}
    {details && !details.details_available && <section className="panel"><h2>Account details unavailable</h2>
      <p className="muted">No account-details record is available. Ask support to review your account.</p></section>}
    {details?.values && <form className="panel form-panel" onSubmit={(event) => void save(event)}>
      <h2>Account details</h2>
      <p className="muted">Account number: {details.values.account_number || "Unavailable"}</p>
      <fieldset disabled={busy || loading || blocked}>
        <label>Address <input value={details.values.address || ""} onChange={(event) => setDetails((old) =>
          old?.values ? { ...old, values: { ...old.values, address: event.target.value } } : old)} /></label>
        {(["energy_preference", "payment_method"] as const).map((key) =>
          <label key={key}>{key === "energy_preference" ? "Energy preference" : "Preferred payment method"}
            <select value={details.values?.[key] || ""} onChange={(event) => setDetails((old) =>
              old?.values ? { ...old, values: { ...old.values, [key]: event.target.value || null } } : old)}>
              <Options choices={details.choices[key]} value={details.values?.[key] ?? null} />
            </select>
          </label>)}
      </fieldset>
      <button type="submit" disabled={busy || loading || blocked}>Save details</button>
    </form>}
  </>;
}
