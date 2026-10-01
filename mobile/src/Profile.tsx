import { useEffect, useState, type FormEvent } from "react";
import type { SessionManager } from "./auth/session.ts";

type Choice = { value: string; label: string };
type Assessment = { values: Record<string, string | null>;
  choices: Record<string, Choice[]>; complete_for_scoring: boolean };
type Details = { account_number: string | null; address: string | null;
  energy_preference: string | null; payment_method: string | null };

const names: Record<string, string> = {
  monthly_expenditure: "Monthly electricity expenditure", purchase_frequency: "Purchase frequency",
  payment_consistency: "Payment consistency", disconnection_history: "Disconnection history",
  meter_sharing: "Meter sharing history", monthly_income: "Monthly income",
  income_stability: "Income stability", consumption_level: "Consumption level",
};
const errorText = (cause: unknown) => cause instanceof Error ? cause.message : "Request failed.";

export function ProfileEditor({ session }: { session: SessionManager }) {
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [details, setDetails] = useState<Details | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const owner = session.identity;
    let mounted = true;
    void Promise.allSettled([
      session.get<Assessment>("auth/mobile-profile/"),
      session.get<Details>("auth/account-details/"),
    ]).then(([profile, account]) => {
      if (!mounted || owner !== session.identity) return;
      if (profile.status === "fulfilled") setAssessment(profile.value);
      else setError(errorText(profile.reason));
      if (account.status === "fulfilled") setDetails(account.value);
      else setError(errorText(account.reason));
    });
    return () => { mounted = false; };
  }, [session]);

  const saveAssessment = async (event: FormEvent) => {
    event.preventDefault(); if (!assessment) return;
    setBusy(true); setError(null); setNotice(null);
    try {
      const updated = await session.patch<Assessment>("auth/mobile-profile/", assessment.values);
      setAssessment(updated); setNotice("Assessment profile saved.");
    } catch (cause) { setError(errorText(cause)); }
    finally { setBusy(false); }
  };
  const saveDetails = async (event: FormEvent) => {
    event.preventDefault(); if (!details) return;
    setBusy(true); setError(null); setNotice(null);
    try {
      await session.patch("auth/update-account-details/", {
        address: details.address || "", energy_preference: details.energy_preference || null,
        payment_method: details.payment_method || null,
      });
      setNotice("Account details saved.");
    } catch (cause) { setError(errorText(cause)); }
    finally { setBusy(false); }
  };

  return <>
    {error && <p className="error" role="alert">{error}</p>}
    {notice && <p className="tag" role="status">{notice}</p>}
    {!assessment && !details && !error && <p className="muted" role="status">Loading profile…</p>}
    {assessment && <form className="panel form-panel" onSubmit={(event) => void saveAssessment(event)}>
      <h2>Loan assessment profile</h2>
      <p className="muted">These are your own reported details. Django determines eligibility; a missing score is not shown as zero.</p>
      {Object.entries(assessment.choices).map(([key, choices]) =>
        <label key={key}>{names[key] || key}
          <select value={assessment.values[key] || ""} onChange={(event) => setAssessment((old) => old && ({
            ...old, values: { ...old.values, [key]: event.target.value },
          }))}>
            <option value="">Not provided</option>
            {choices.map((choice) => <option key={choice.value} value={choice.value}>{choice.label}</option>)}
          </select>
        </label>)}
      <p className="muted">{assessment.complete_for_scoring ? "Assessment fields complete" : "Assessment fields incomplete"}</p>
      <button type="submit" disabled={busy}>Save assessment</button>
    </form>}
    {details && <form className="panel form-panel" onSubmit={(event) => void saveDetails(event)}>
      <h2>Account details</h2>
      <p className="muted">Account number: {details.account_number || "Unavailable"}</p>
      <label>Address <input value={details.address || ""} onChange={(event) => setDetails((old) => old &&
        ({ ...old, address: event.target.value }))} /></label>
      <label>Energy preference <select value={details.energy_preference || ""}
        onChange={(event) => setDetails((old) => old && ({ ...old, energy_preference: event.target.value }))}>
        <option value="">Not set</option><option value="SOLAR">Solar</option><option value="HYDRO">Hydro</option>
        <option value="THERMAL">Thermal</option><option value="OTHER">Other</option></select></label>
      <label>Preferred payment method <select value={details.payment_method || ""}
        onChange={(event) => setDetails((old) => old && ({ ...old, payment_method: event.target.value }))}>
        <option value="">Not set</option><option value="MOBILE_MONEY">Mobile Money</option>
        <option value="CREDIT_CARD">Credit card</option><option value="BANK_TRANSFER">Bank transfer</option></select></label>
      <button type="submit" disabled={busy}>Save details</button>
    </form>}
  </>;
}
