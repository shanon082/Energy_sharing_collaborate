import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError, SessionExpired, type SessionManager } from "./auth/session.ts";
import { LatestRead } from "./api/read-scope.ts";
import { parseAccountDetails, parseAssessment, type AccountDetails, type Assessment, type Choice } from "./api/profile-contracts.ts";
import { dateTime } from "./format.ts";

const names: Record<string, string> = {
  monthly_expenditure: "Monthly electricity expenditure", purchase_frequency: "Purchase frequency",
  payment_consistency: "Payment consistency", disconnection_history: "Disconnection history",
  meter_sharing: "Meter sharing history", monthly_income: "Monthly income",
  income_stability: "Income stability", consumption_level: "Consumption level",
};
const errorText = (cause: unknown) => cause instanceof Error ? cause.message : "Request failed.";
function Options({ choices, value }: { choices: Choice[]; value: string | null }) {
  return <><option value="">Not provided</option>
    {value && !choices.some((choice) => choice.value === value) &&
      <option value={value}>Previously stored value — choose a current option</option>}
    {choices.map((choice) => <option key={choice.value} value={choice.value}>{choice.label}</option>)}</>;
}

export function ProfileEditor({ session, onExpired }: { session: SessionManager; onExpired: () => void }) {
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [details, setDetails] = useState<AccountDetails | null>(null);
  const [errors, setErrors] = useState<{ assessment?: string; details?: string }>({});
  const [blocked, setBlocked] = useState<{ assessment?: boolean; details?: boolean }>({});
  const [fetched, setFetched] = useState<{ assessment?: string; details?: string }>({});
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const reads = useRef(new LatestRead());
  const mounted = useRef(false);

  const load = useCallback(async () => {
    const owner = session.identity, ticket = reads.current.begin();
    setLoading(true); setErrors({}); setNotice(null);
    const results = await Promise.allSettled([
      session.get<unknown>("auth/mobile-profile/").then(parseAssessment),
      session.get<unknown>("auth/mobile-account-details/").then(parseAccountDetails),
    ]);
    if (!mounted.current || owner !== session.identity || !reads.current.current(ticket)) return;
    if (results.some((result) => result.status === "rejected" && result.reason instanceof SessionExpired)) {
      onExpired(); return;
    }
    const [profile, account] = results;
    const now = new Date().toISOString();
    if (profile.status === "fulfilled") { setAssessment(profile.value); setFetched((old) => ({ ...old, assessment: now })); }
    if (account.status === "fulfilled") { setDetails(account.value); setFetched((old) => ({ ...old, details: now })); }
    setErrors({ assessment: profile.status === "rejected" ? errorText(profile.reason) : undefined,
      details: account.status === "rejected" ? errorText(account.reason) : undefined });
    setBlocked({ assessment: profile.status === "rejected", details: account.status === "rejected" });
    setLoading(false);
  }, [session, onExpired]);

  useEffect(() => {
    mounted.current = true; void load();
    return () => { mounted.current = false; reads.current.invalidate(); };
  }, [load]);

  const save = async (kind: "assessment" | "details", event: FormEvent) => {
    event.preventDefault();
    if (loading || busy || blocked[kind] || (kind === "assessment" ? !assessment : !details?.values)) return;
    const owner = session.identity, ticket = reads.current.begin();
    setBusy(true); setNotice(null); setErrors((old) => ({ ...old, [kind]: undefined }));
    try {
      if (kind === "assessment" && assessment) {
        const result = parseAssessment(await session.patch<unknown>("auth/mobile-profile/", assessment.values));
        if (!mounted.current || owner !== session.identity || !reads.current.current(ticket)) return;
        setAssessment(result);
      } else if (details?.values) {
        const { address, energy_preference, payment_method } = details.values;
        const result = parseAccountDetails(await session.patch<unknown>("auth/mobile-account-details/",
          { address, energy_preference, payment_method }));
        if (!mounted.current || owner !== session.identity || !reads.current.current(ticket)) return;
        setDetails(result);
      }
      setFetched((old) => ({ ...old, [kind]: new Date().toISOString() }));
      setNotice(kind === "assessment" ? "Assessment profile saved." : "Account details saved.");
    } catch (cause) {
      if (!mounted.current || owner !== session.identity || !reads.current.current(ticket)) return;
      if (cause instanceof SessionExpired) { onExpired(); return; }
      setErrors((old) => ({ ...old, [kind]: errorText(cause) }));
      setBlocked((old) => ({ ...old, [kind]: !(cause instanceof ApiError) }));
    } finally {
      if (mounted.current && owner === session.identity && reads.current.current(ticket)) setBusy(false);
    }
  };

  const timestamp = (kind: "assessment" | "details") => fetched[kind] &&
    <p className={errors[kind] || loading ? "stale" : "muted"}>
      {errors[kind] || loading ? "Stale — last fetched " : "Fetched "}{dateTime(fetched[kind])}
    </p>;
  return <>
    {loading && <p className="muted" role="status">Loading profile…</p>}
    {notice && <p className="tag" role="status">{notice}</p>}
    <button type="button" className="secondary" disabled={loading || busy} onClick={() => void load()}>Refresh profile</button>
    {errors.assessment && <p className="error" role="alert">Assessment: {errors.assessment}</p>}
    {timestamp("assessment")}
    {assessment && <form className="panel form-panel" onSubmit={(event) => void save("assessment", event)}>
      <h2>Loan assessment profile</h2>
      <p className="muted">These are your own reported details. Django determines eligibility; a missing score is not shown as zero.</p>
      {Object.entries(assessment.choices).map(([key, choices]) =>
        <label key={key}>{names[key] || key}
          <select disabled={busy || loading || Boolean(blocked.assessment)} value={assessment.values[key] || ""}
            onChange={(event) => setAssessment((old) => old && ({ ...old,
              values: { ...old.values, [key]: event.target.value || null } }))}>
            <Options choices={choices} value={assessment.values[key]} />
          </select>
        </label>)}
      <p className="muted">{assessment.complete_for_scoring ? "Saved assessment fields complete" : "Saved assessment fields incomplete"}</p>
      <button type="submit" disabled={busy || loading || Boolean(blocked.assessment)}>Save assessment</button>
    </form>}
    {errors.details && <p className="error" role="alert">Account details: {errors.details}</p>}
    {timestamp("details")}
    {details && !details.details_available && <section className="panel"><h2>Account details unavailable</h2>
      <p className="muted">No account-details record is available. Ask support to review your account.</p></section>}
    {details?.values && <form className="panel form-panel" onSubmit={(event) => void save("details", event)}>
      <h2>Account details</h2>
      <p className="muted">Account number: {details.values.account_number || "Unavailable"}</p>
      <fieldset disabled={busy || loading || Boolean(blocked.details)}>
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
      <button type="submit" disabled={busy || loading || Boolean(blocked.details)}>Save details</button>
    </form>}
  </>;
}
