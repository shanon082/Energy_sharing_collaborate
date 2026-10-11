import { useCallback, useState, type FormEvent } from "react";
import { App as NativeApp } from "@capacitor/app";
import type { SessionManager } from "./auth/session.ts";
import { accountTokenQuery, parseAccountLink } from "./auth/account-links.ts";
import { API_BASE_URL } from "./api/config.ts";
import { probeConnection, type ConnectionProbe } from "./api/diagnostics.ts";
import { Brand, EnergyArtwork, Icon } from "./ui.tsx";
import { useNativeBack } from "./use-native-back.ts";

type Mode = "welcome" | "login" | "register" | "verify" | "forgot" | "reset";
type Props = { session: SessionManager; onLogin: (email: string, password: string) => Promise<void>;
  loginBusy: boolean; loginError: string | null; onPreview: () => void; };

function describe(error: unknown): string {
  return error instanceof Error ? error.message : "The request failed. Please try again.";
}

export function Access({ session, onLogin, loginBusy, loginError, onPreview }: Props) {
  const [mode, setMode] = useState<Mode>("welcome");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [first, setFirst] = useState("");
  const [last, setLast] = useState("");
  const [phone, setPhone] = useState("");
  const [gender, setGender] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [link, setLink] = useState("");
  const [checkingApi, setCheckingApi] = useState(false);
  const [connection, setConnection] = useState<ConnectionProbe | null>(null);

  const change = (next: Mode) => {
    setMode(next); setError(null); setSuccess(null); setPassword(""); setConfirm(""); setLink("");
    setShowPassword(false);
  };
  useNativeBack(useCallback(() => {
    if (busy || loginBusy) return;
    if (mode !== "welcome") {
      setMode("welcome"); setPassword(""); setConfirm(""); setLink(""); setError(null); setSuccess(null);
    } else void NativeApp.minimizeApp();
  }, [mode, busy, loginBusy]));
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy || loginBusy) return;
    setError(null); setSuccess(null);
    if (mode === "login") { await onLogin(email.trim(), password); return; }
    setBusy(true);
    try {
      if (mode === "register") {
        if (password !== confirm) throw new Error("Passwords do not match.");
        const response = await session.publicPost<{ message?: unknown }>("auth/register/", {
          first_name: first.trim(), last_name: last.trim(), email: email.trim(),
          phone_number: phone.trim(), gender, password, confirm_password: confirm,
        });
        setPassword(""); setConfirm("");
        setSuccess(typeof response?.message === "string" ? response.message : "Account created. Verification email requested; verify before signing in.");
        setMode("verify");
      } else if (mode === "forgot") {
        const response = await session.publicPost<{ message?: unknown }>("auth/forgot-password/", { email: email.trim() });
        setSuccess(typeof response?.message === "string" ? response.message : "If this email has an account, reset instructions have been requested.");
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
      const response = await session.publicGet<{ message?: unknown }>(`auth/resend-email-link/?email=${encodeURIComponent(email.trim())}`);
      setSuccess(typeof response?.message === "string" ? response.message : "If verification is still needed, a new email has been requested.");
    } catch (cause) { setError(describe(cause)); }
    finally { setBusy(false); }
  };

  if (mode === "welcome") return <main className="welcome-shell">
    <header className="welcome-top"><Brand light /><span className="edition-label">ELECTRICITY CREDIT</span></header>
    <EnergyArtwork />
    <div className="welcome-copy"><span className="eyebrow">A BRIGHTER EVERYDAY</span>
      <h1>Your power.<br /><em>Your possibilities.</em></h1>
      <p>Manage your electricity, keep an eye on your meter, and explore energy credit. All in one place.</p>
      <div className="welcome-pillars"><span><Icon name="meter" />Your meter</span>
        <span><Icon name="chart" />Your usage</span><span><Icon name="loan" />Your credit</span></div>
    </div>
    <div className="welcome-actions"><button className="primary-button" onClick={() => change("register")}>Get started <Icon name="arrow" /></button>
      <button className="welcome-signin" onClick={() => change("login")}>Already have an account? <strong>Sign in</strong></button>
      <button className="preview-link" onClick={onPreview}>Explore the app preview <Icon name="arrow" /></button>
      <p className="welcome-footnote">Preview uses sample data. No account needed.</p>
    </div>
  </main>;

  const titles = { login: "Welcome back.", register: "A brighter start.", verify: "Check your inbox.",
    forgot: "Let’s get you back in.", reset: "A fresh start." };
  const subtitles = { login: "Sign in to see your energy, meters and account.",
    register: "Create your account and take charge of your electricity.",
    verify: "Verify your email to finish setting up your account.",
    forgot: "Enter your email and we’ll help you reset your password.",
    reset: "Use your reset link to choose a new password." };
  return <main className="access-shell">
    <header className="access-top"><button type="button" className="icon-button" aria-label="Back to welcome"
      disabled={busy || loginBusy} onClick={() => change("welcome")}><Icon name="back" /></button><Brand /></header>
    <div className="access-heading"><span className="access-symbol"><Icon name={mode === "verify" ? "mail" : mode === "forgot" || mode === "reset" ? "lock" : "bolt"} /></span>
      <span className="eyebrow">{mode === "register" ? "JOIN GPAWA" : "YOUR ENERGY ACCOUNT"}</span>
      <h1>{titles[mode]}</h1><p>{subtitles[mode]}</p>
    </div>
    {mode === "login" || mode === "register" ? <div className="auth-tabs" aria-label="Account access">
      <button type="button" aria-pressed={mode === "login"} disabled={busy || loginBusy} onClick={() => change("login")}>Sign in</button>
      <button type="button" aria-pressed={mode === "register"} disabled={busy || loginBusy} onClick={() => change("register")}>Create account</button>
    </div> : null}
    <form className="login-card auth-form" onSubmit={(event) => void submit(event)}>
      {mode === "register" && <div className="field-pair">
        <label>First name <input autoComplete="given-name" placeholder="First name" value={first} onChange={(event) => setFirst(event.target.value)} required /></label>
        <label>Last name <input autoComplete="family-name" placeholder="Last name" value={last} onChange={(event) => setLast(event.target.value)} required /></label>
      </div>}
      {(mode === "login" || mode === "register" || mode === "forgot" || mode === "verify") &&
        <label>Email address <span className="input-wrap"><Icon name="mail" /><input type="email" autoComplete="email" placeholder="you@example.com" value={email}
          onChange={(event) => setEmail(event.target.value)} required={mode !== "verify"} /></span></label>}
      {mode === "register" && <>
        <label>Phone number <span className="input-wrap"><Icon name="phone" /><input type="tel" autoComplete="tel" placeholder="+256 …" value={phone} onChange={(event) => setPhone(event.target.value)} required /></span></label>
        <label>Gender <select value={gender} onChange={(event) => setGender(event.target.value)} required>
          <option value="" disabled>Select gender</option>
          <option value="MALE">Male</option><option value="FEMALE">Female</option></select></label>
      </>}
      {(mode === "verify" || mode === "reset") && <>
        <p className="muted small">For local testing, copy the complete link from the email and paste it here. Django validates its token and expiry.</p>
        <label>Email link <input type="url" value={link} onChange={(event) => setLink(event.target.value)} required /></label>
      </>}
      {(mode === "login" || mode === "register" || mode === "reset") &&
        <label>{mode === "reset" ? "New password" : "Password"}
          <span className="input-wrap"><Icon name="lock" /><input type={showPassword ? "text" : "password"} autoComplete={mode === "login" ? "current-password" : "new-password"}
            placeholder={mode === "login" ? "Enter your password" : "Create a password"}
            value={password} onChange={(event) => setPassword(event.target.value)} required />
          <button type="button" className="password-toggle" aria-label={showPassword ? "Hide password" : "Show password"}
            aria-pressed={showPassword} onClick={() => setShowPassword((value) => !value)}><Icon name={showPassword ? "eye-off" : "eye"} /></button></span></label>}
      {(mode === "register" || mode === "reset") &&
        <label>Confirm password <span className="input-wrap"><Icon name="lock" /><input type={showPassword ? "text" : "password"} autoComplete="new-password" placeholder="Re-enter your password"
          value={confirm} onChange={(event) => setConfirm(event.target.value)} required /></span></label>}
      {mode === "login" && <button type="button" className="text-button forgot-link" disabled={loginBusy} onClick={() => change("forgot")}>Forgot password?</button>}
      {(error || (mode === "login" && loginError)) &&
        <p className="error" role="alert">{error || loginError}</p>}
      {success && <p className="tag" role="status">{success}</p>}
      <button type="submit" className="primary-button" disabled={busy || loginBusy}>
        {busy || loginBusy ? "Please wait…" : ({ login: "Sign in", register: "Register",
          verify: "Verify link", forgot: "Send reset email", reset: "Reset password" } as const)[mode]}<Icon name="arrow" /></button>
      {mode === "register" && <p className="form-hint"><Icon name="shield" />We’ll send you an email to verify your account before you sign in.</p>}
      {mode === "verify" && <button type="button" className="secondary" disabled={busy || !email.trim()}
        onClick={() => void resend()}>Resend verification email</button>}
      <div className="access-links">
        {mode !== "login" && mode !== "register" && <button type="button" className="text-button" disabled={busy} onClick={() => change("login")}>Back to sign in</button>}
        {mode === "login" && <button type="button" className="text-button" disabled={loginBusy} onClick={() => change("verify")}>Have a verification link?</button>}
        {mode === "forgot" && <button type="button" className="text-button" disabled={busy} onClick={() => change("reset")}>Already have a reset link?</button>}
      </div>
      {mode === "login" && import.meta.env.MODE === "android-debug" && <details className="connection-details"><summary>Development connection tools</summary>
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
      </details>}
    </form>
    <footer className="access-footer"><Icon name="shield" /><span>Your account. Your electricity. Your control.</span></footer>
  </main>;
}
