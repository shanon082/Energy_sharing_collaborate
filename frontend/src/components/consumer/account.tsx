"use client";
import { useCallback, useState, type FormEvent } from "react";
import Link from "next/link";
import { ArrowRight, LogOut, ShieldCheck, UserRound } from "lucide-react";
import { consumerClient, patchAccount, useConsumerRead } from "./read";
import { record } from "../../lib/consumer-parity";

type Details = { values: { account_number: string | null; address: string | null; energy_preference: string | null; payment_method: string | null } | null;
  choices: Record<"energy_preference" | "payment_method", { value: string; label: string }[]>; details_available: boolean };
function parseDetails(raw: unknown): Details {
  const row = record(raw), choices = record(row.choices);
  if (typeof row.details_available !== "boolean" || !Array.isArray(choices.energy_preference) || !Array.isArray(choices.payment_method)) throw new Error("Account preferences unavailable.");
  if (row.details_available) {
    const values = record(row.values);
    for (const key of ["account_number", "address", "energy_preference", "payment_method"]) if (values[key] !== null && typeof values[key] !== "string") throw new Error("Invalid account preferences.");
  }
  return row as Details;
}
export default function ConsumerAccount({ account, onLogout }: { account: { id: number; first_name: string; last_name: string; email: string; email_verified: boolean }; onLogout: () => Promise<void> }) {
  const [revision, refresh] = useState(0);
  const details = useConsumerRead("auth/mobile-account-details/", parseDetails, revision, account.id);
  const [notice, setNotice] = useState<string | null>(null), [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const save = useCallback(async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); if (busy || !details.value?.details_available) return;
    const fields = new FormData(event.currentTarget);
    setBusy(true); setError(null); setNotice(null);
    try {
      parseDetails(await patchAccount({ address: String(fields.get("address") || ""), energy_preference: fields.get("energy_preference") || null, payment_method: fields.get("payment_method") || null }));
      refresh(value => value + 1); setNotice("Your preferences have been saved.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not save preferences."); }
    finally { setBusy(false); }
  }, [busy, details.value?.details_available]);
  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (busy) return;
    const form = event.currentTarget, fields = new FormData(form);
    setBusy(true); setError(null); setNotice(null);
    try {
      await consumerClient.post("auth/mobile-password/", { current_password: fields.get("current_password"), new_password: fields.get("new_password"), confirm_password: fields.get("confirm_password") });
      form.reset(); await onLogout();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not change your password."); }
    finally { setBusy(false); }
  }
  return <div className="consumer-account-grid"><section className="consumer-card account-summary"><span className="profile-avatar"><UserRound size={30} /></span><h2>{account.first_name} {account.last_name}</h2><p>{account.email}</p><span className="eligibility-chip eligible"><ShieldCheck size={14} />{account.email_verified ? "Email verified" : "Verification pending"}</span><button className="consumer-secondary" onClick={() => void onLogout()} disabled={busy}><LogOut size={17} />Sign out</button></section><div>
    {notice && <p className="consumer-success" role="status">{notice}</p>}{error && <p className="consumer-alert" role="alert">{error}</p>}
    <section className="consumer-card"><h2>Account preferences</h2>{details.loading ? <p role="status">Loading preferences…</p> : details.error ? <p role="alert">{details.error} <button onClick={() => refresh(value => value + 1)}>Retry</button></p> : details.value?.values ? <form key={revision} className="consumer-form" onSubmit={event => void save(event)}><p className="consumer-muted">Account number: {details.value.values.account_number || "Unavailable"}</p><label>Address<input name="address" defaultValue={details.value.values.address || ""} disabled={busy} /></label>{(["energy_preference", "payment_method"] as const).map(key => <label key={key}>{key === "energy_preference" ? "Energy preference" : "Preferred payment method"}<select name={key} defaultValue={details.value?.values?.[key] || ""} disabled={busy}><option value="">Not provided</option>{details.value?.choices[key].map(choice => <option value={choice.value} key={choice.value}>{choice.label}</option>)}</select></label>)}<button disabled={busy} type="submit">{busy ? "Saving…" : "Save preferences"}<ArrowRight size={17} /></button></form> : <p>Preferences are unavailable. Contact support to review your account.</p>}</section>
    <details className="consumer-card account-security"><summary>Security & recovery</summary><p className="consumer-muted">Changing your password signs you out. Your credit assessment is managed automatically.</p><form className="consumer-form" onSubmit={event => void changePassword(event)}><label>Current password<input type="password" name="current_password" autoComplete="current-password" required disabled={busy} /></label><label>New password<input type="password" name="new_password" autoComplete="new-password" required disabled={busy} /></label><label>Confirm new password<input type="password" name="confirm_password" autoComplete="new-password" required disabled={busy} /></label><button type="submit" disabled={busy}>Change password</button></form><Link href="/auth/forgot-password">Recover your account</Link></details>
  </div></div>;
}
