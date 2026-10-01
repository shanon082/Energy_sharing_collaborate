import { useState, type FormEvent } from "react";
import type { SessionManager } from "./auth/session.ts";
import { accountTokenQuery, parseAccountLink } from "./auth/account-links.ts";
import { API_BASE_URL } from "./api/config.ts";
import { probeConnection, type ConnectionProbe } from "./api/diagnostics.ts";

type Mode = "login" | "register" | "verify" | "forgot" | "reset";
type Props = { session: SessionManager; onLogin: (email: string, password: string) => Promise<void>;
  loginBusy: boolean; loginError: string | null; };

function describe(error: unknown): string {
  return error instanceof Error ? error.message : "The request failed. Please try again.";
}

export function Access({ session, onLogin, loginBusy, loginError }: Props) {
  const [mode, setMode] = useState<Mode>("login");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [first, setFirst] = useState("");
  const [last, setLast] = useState("");
  const [phone, setPhone] = useState("");
  const [gender, setGender] = useState("MALE");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [link, setLink] = useState("");
  const [checkingApi, setCheckingApi] = useState(false);
  const [connection, setConnection] = useState<ConnectionProbe | null>(null);

  const change = (next: Mode) => {
    setMode(next); setError(null); setSuccess(null); setPassword(""); setConfirm(""); setLink("");
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setError(null); setSuccess(null);
    if (mode === "login") { await onLogin(email.trim(), password); return; }
    setBusy(true);
    try {
      if (mode === "register") {
        if (password !== confirm) throw new Error("Passwords do not match.");
        await session.publicPost("auth/register/", {
          first_name: first.trim(), last_name: last.trim(), email: email.trim(),
          phone_number: phone.trim(), gender, password, confirm_password: confirm,
        });
        setPassword(""); setConfirm("");
        setSuccess("Account created. Check your email, then verify before signing in.");
        setMode("verify");
      } else if (mode === "forgot") {
        await session.publicPost("auth/forgot-password/", { email: email.trim() });
        setSuccess("If this email has an account, reset instructions will be sent.");
        setMode("reset");
      } else if (mode === "verify") {
        const parsed = parseAccountLink(link);
        if (parsed.kind !== "verify") throw new Error("Paste an email verification link.");
        await session.publicGet(`auth/verify-email/?${accountTokenQuery(parsed)}`);
        setLink(""); setSuccess("Email verified. You can sign in now."); setMode("login");
      } else {
        const parsed = parseAccountLink(link);
        if (parsed.kind !== "reset") throw new Error("Paste a password reset link.");
        if (password !== confirm) throw new Error("Passwords do not match.");
        const query = accountTokenQuery(parsed);
        await session.publicGet(`auth/reset-password/?${query}`);
        await session.publicPatch(`auth/reset-password/?${query}`, { password, confirm_password: confirm });
        setPassword(""); setConfirm(""); setLink("");
        setSuccess("Password reset. Sign in with your new password."); setMode("login");
      }
    } catch (cause) { setError(describe(cause)); }
    finally { setBusy(false); }
  };
  const resend = async () => {
    setBusy(true); setError(null); setSuccess(null);
    try {
      await session.publicGet(`auth/resend-email-link/?email=${encodeURIComponent(email.trim())}`);
      setSuccess("If verification is still needed, a new email has been requested.");
    } catch (cause) { setError(describe(cause)); }
    finally { setBusy(false); }
  };

  return <main className="login-shell">
    <div className="brand">gPawa <span>consumer prototype</span></div>
    <form className="panel login-card" onSubmit={(event) => void submit(event)}>
      <h1>{({ login: "Sign in", register: "Create account", verify: "Verify email",
        forgot: "Forgot password", reset: "Reset password" } as const)[mode]}</h1>
      {(mode === "login" || mode === "register" || mode === "forgot" || mode === "verify") &&
        <label>Email <input type="email" autoComplete="email" value={email}
          onChange={(event) => setEmail(event.target.value)} required={mode !== "verify"} /></label>}
      {mode === "register" && <>
        <label>First name <input value={first} onChange={(event) => setFirst(event.target.value)} required /></label>
        <label>Last name <input value={last} onChange={(event) => setLast(event.target.value)} required /></label>
        <label>Phone number <input type="tel" value={phone} onChange={(event) => setPhone(event.target.value)} required /></label>
        <label>Gender <select value={gender} onChange={(event) => setGender(event.target.value)}>
          <option value="MALE">Male</option><option value="FEMALE">Female</option></select></label>
      </>}
      {(mode === "verify" || mode === "reset") && <>
        <p className="muted small">For local testing, copy the complete link from the email and paste it here. Django validates its token and expiry.</p>
        <label>Email link <input type="url" value={link} onChange={(event) => setLink(event.target.value)} required /></label>
      </>}
      {(mode === "login" || mode === "register" || mode === "reset") &&
        <label>{mode === "reset" ? "New password" : "Password"}
          <input type="password" autoComplete={mode === "login" ? "current-password" : "new-password"}
            value={password} onChange={(event) => setPassword(event.target.value)} required /></label>}
      {(mode === "register" || mode === "reset") &&
        <label>Confirm password <input type="password" autoComplete="new-password"
          value={confirm} onChange={(event) => setConfirm(event.target.value)} required /></label>}
      {(error || (mode === "login" && loginError)) &&
        <p className="error" role="alert">{error || loginError}</p>}
      {success && <p className="tag" role="status">{success}</p>}
      <button type="submit" disabled={busy || loginBusy}>
        {busy || loginBusy ? "Please wait…" : ({ login: "Sign in", register: "Register",
          verify: "Verify link", forgot: "Send reset email", reset: "Reset password" } as const)[mode]}</button>
      {mode === "verify" && <button type="button" className="secondary" disabled={busy || !email.trim()}
        onClick={() => void resend()}>Resend verification email</button>}
      <div className="access-links">
        {mode !== "login" && <button type="button" className="secondary" onClick={() => change("login")}>Sign in</button>}
        {mode !== "register" && <button type="button" className="secondary" onClick={() => change("register")}>Register</button>}
        {mode !== "forgot" && <button type="button" className="secondary" onClick={() => change("forgot")}>Forgot password</button>}
        {mode !== "verify" && <button type="button" className="secondary" onClick={() => change("verify")}>Verify email</button>}
        {mode !== "reset" && <button type="button" className="secondary" onClick={() => change("reset")}>Reset from link</button>}
      </div>
      {mode === "login" && import.meta.env.MODE === "android-debug" && <>
        <button type="button" className="secondary" disabled={checkingApi} onClick={() => {
          setCheckingApi(true);
          void probeConnection(API_BASE_URL, window.location.origin)
            .then(setConnection).finally(() => setCheckingApi(false));
        }}>{checkingApi ? "Checking API…" : "Test API connection"}</button>
        {connection && <div className="muted small" role="status">
          <div>App origin: {connection.origin}</div><div>API: {connection.api}</div>
          <div>Simple GET: {connection.simpleGet}</div><div>JSON GET: {connection.jsonGet}</div>
          <div>Empty login POST: {connection.loginPreflight}</div>
          <div>Account GET with invalid test token: {connection.accountGet}</div>
          <div>No-CORS GET: {connection.opaqueGet}</div>
        </div>}
      </>}
    </form>
  </main>;
}
