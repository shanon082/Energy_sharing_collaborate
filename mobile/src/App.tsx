import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Capacitor } from "@capacitor/core";
import { App as NativeApp } from "@capacitor/app";
import { DISABLED_FEATURES, parseFeatureAvailability, type FeatureAvailability } from "../../frontend/src/lib/features.ts";
import { API_BASE_URL } from "./api/config.ts";
import { Access } from "./Access.tsx";
import { ProfileEditor } from "./Profile.tsx";
import { DeliveryPanel } from "./Delivery.tsx";
import { Activity } from "./Activity.tsx";
import { LoanQuote } from "./LoanQuote.tsx";
import { parseAllocation, parseConsumption, parseLoans, parseMeters,
  type AllocationStatus, type ConsumptionHistory, type Loan, type MeterInfo } from "./api/contracts.ts";
import { SessionExpired, SessionManager, TransportError, type ConsumerIdentity } from "./auth/session.ts";
import { AndroidSecureStore } from "./auth/secure-store.ts";
import { dateTime, energy, ugx } from "./format.ts";

const session = new SessionManager(API_BASE_URL, new AndroidSecureStore());
type Tab = "dashboard" | "meters" | "consumption" | "loans" | "activity" | "account";
type Resource<T> = { value: T | null; loading: boolean; error: string | null; fetchedAt: string | null };
const empty = <T,>(): Resource<T> => ({ value: null, loading: false, error: null, fetchedAt: null });

function message(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "This information is unavailable. Please try again.";
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return <section className="panel"><h2>{title}</h2>{children}</section>;
}

function StateLine<T>({ data, offline }: { data: Resource<T>; offline: boolean }) {
  if (data.loading && data.value === null) return <p className="muted" role="status">Loading…</p>;
  if (data.error || data.fetchedAt) return <>
    {data.error && <p className="error" role="alert">{data.error}</p>}
    {data.fetchedAt && <p className={data.error ? "stale" : "muted"}>
      {data.error ? "Stale — " : "Fetched "}{dateTime(data.fetchedAt)}
    </p>}
  </>;
  if (offline && data.value === null) return <p className="muted">The API could not be reached. No account data is stored on this device.</p>;
  return null;
}

function PasswordChange({ required, onDone, onCancel }: {
  required: boolean; onDone: () => void; onCancel?: () => void;
}) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError(null);
    try {
      await session.post("auth/mobile-password/", {
        current_password: current, new_password: next, confirm_password: confirm,
      });
      setCurrent(""); setNext(""); setConfirm(""); setDone(true);
    } catch (cause) { setError(message(cause)); }
    finally { setBusy(false); }
  };
  return <main className="login-shell"><div className="brand">gPawa <span>consumer prototype</span></div>
    <form className="panel login-card" onSubmit={(event) => void submit(event)}>
      <h1>{required ? "Change required password" : "Change password"}</h1>
      {required && <p className="muted">Set a new password before using your account.</p>}
      {done ? <><p className="tag" role="status">Password changed. Please sign in again.</p>
        <button type="button" onClick={onDone}>Continue to sign in</button></> : <>
        <label>Current password <input type="password" autoComplete="current-password" value={current}
          onChange={(event) => setCurrent(event.target.value)} required /></label>
        <label>New password <input type="password" autoComplete="new-password" value={next}
          onChange={(event) => setNext(event.target.value)} required /></label>
        <label>Confirm new password <input type="password" autoComplete="new-password" value={confirm}
          onChange={(event) => setConfirm(event.target.value)} required /></label>
        {error && <p className="error" role="alert">{error}</p>}
        <button type="submit" disabled={busy}>{busy ? "Changing…" : "Change password"}</button>
        {!required && <button type="button" className="secondary" onClick={onCancel}>Back to account</button>}
      </>}
    </form>
  </main>;
}

export default function App() {
  const [phase, setPhase] = useState<"checking" | "signed_out" | "password_required" | "signed_in">("checking");
  const [account, setAccount] = useState<ConsumerIdentity | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [offline, setOffline] = useState(false);
  const [tab, setTab] = useState<Tab>("dashboard");
  const [changingPassword, setChangingPassword] = useState(false);
  const [meters, setMeters] = useState<Resource<MeterInfo[]>>(empty);
  const [loans, setLoans] = useState<Resource<Loan[]>>(empty);
  const [selectedMeter, setSelectedMeter] = useState<string | null>(null);
  const [allocation, setAllocation] = useState<Resource<AllocationStatus>>(empty);
  const [consumption, setConsumption] = useState<Resource<ConsumptionHistory>>(empty);
  const [features, setFeatures] = useState<FeatureAvailability>(DISABLED_FEATURES);
  const [featuresVerified, setFeaturesVerified] = useState(false);
  const booted = useRef(false);
  const selectedRef = useRef<string | null>(null);

  const clearView = useCallback(() => {
    setAccount(null); setMeters(empty()); setLoans(empty()); setAllocation(empty());
    setConsumption(empty()); setSelectedMeter(null); selectedRef.current = null;
    setChangingPassword(false);
    setTab("dashboard");
  }, []);

  const expire = useCallback(() => {
    clearView(); setAuthError("Session expired. Please sign in again."); setPhase("signed_out");
  }, [clearView]);

  const loadFeatures = useCallback(async () => {
    try {
      const data = await session.publicGet<{ features?: unknown }>("features/");
      setOffline(false);
      setFeatures(parseFeatureAvailability(data.features)); setFeaturesVerified(true);
    } catch (error) {
      if (error instanceof TransportError) setOffline(true);
      setFeatures(DISABLED_FEATURES); setFeaturesVerified(false);
    }
  }, []);

  const loadMeters = useCallback(async () => {
    const owner = session.identity;
    setMeters((old) => ({ ...old, loading: true, error: null }));
    try {
      const value = parseMeters(await session.get<unknown>("meter/my-meter/"));
      setOffline(false);
      if (owner === session.identity) setMeters({ value, loading: false, error: null, fetchedAt: new Date().toISOString() });
    } catch (error) {
      if (error instanceof SessionExpired) { expire(); return; }
      if (error instanceof TransportError) setOffline(true);
      if (owner === session.identity) setMeters((old) => ({ ...old, loading: false, error: message(error) }));
    }
  }, [expire]);

  const loadLoans = useCallback(async () => {
    const owner = session.identity;
    setLoans((old) => ({ ...old, loading: true, error: null }));
    try {
      const value = parseLoans(await session.get<unknown>("loans/mobile-overview/"));
      setOffline(false);
      if (owner === session.identity) setLoans({ value, loading: false, error: null, fetchedAt: new Date().toISOString() });
    } catch (error) {
      if (error instanceof SessionExpired) { expire(); return; }
      if (error instanceof TransportError) setOffline(true);
      if (owner === session.identity) setLoans((old) => ({ ...old, loading: false, error: message(error) }));
    }
  }, [expire]);

  const loadSelected = useCallback(async (meterNo: string) => {
    const owner = session.identity;
    setAllocation((old) => ({ ...old, loading: true, error: null }));
    setConsumption((old) => ({ ...old, loading: true, error: null }));
    const path = encodeURIComponent(meterNo);
    const [allocationResult, consumptionResult] = await Promise.allSettled([
      session.get<unknown>(`meter/allocation-status/?meter_no=${path}`).then(parseAllocation),
      session.get<unknown>(`meter/mobile-consumption/?meter_no=${path}`).then(parseConsumption),
    ]);
    if (owner !== session.identity || selectedRef.current !== meterNo) return;
    if (allocationResult.status === "fulfilled") {
      setOffline(false);
      setAllocation({ value: allocationResult.value, loading: false, error: null, fetchedAt: new Date().toISOString() });
    } else if (allocationResult.reason instanceof SessionExpired) { expire(); return; }
    else {
      if (allocationResult.reason instanceof TransportError) setOffline(true);
      setAllocation((old) => ({ ...old, loading: false, error: message(allocationResult.reason) }));
    }
    if (consumptionResult.status === "fulfilled") {
      setOffline(false);
      setConsumption({ value: consumptionResult.value, loading: false, error: null, fetchedAt: new Date().toISOString() });
    } else if (consumptionResult.reason instanceof SessionExpired) { expire(); }
    else {
      if (consumptionResult.reason instanceof TransportError) setOffline(true);
      setConsumption((old) => ({ ...old, loading: false, error: message(consumptionResult.reason) }));
    }
  }, [expire]);

  const chooseMeter = (meterNo: string) => {
    selectedRef.current = meterNo; setSelectedMeter(meterNo);
    setAllocation(empty()); setConsumption(empty());
    void loadSelected(meterNo);
  };

  const refresh = () => {
    if (phase !== "signed_in") return;
    void loadFeatures(); void loadMeters(); void loadLoans();
    if (selectedRef.current) void loadSelected(selectedRef.current);
  };

  useEffect(() => {
    if (booted.current) return;
    booted.current = true;
    void loadFeatures();
    void (async () => {
      let restoreStage: "refresh" | "account" = "refresh";
      try {
        const restored = await session.restore();
        if (!restored) { setPhase("signed_out"); return; }
        restoreStage = "account";
        const user = await session.getAccount();
        setOffline(false);
        setAccount(user); setPhase(user.must_change_password ? "password_required" : "signed_in");
        if (!user.must_change_password) { void loadMeters(); void loadLoans(); }
      } catch (error) {
        if (error instanceof TransportError) setOffline(true);
        setAuthError(error instanceof TransportError
          ? restoreStage === "refresh"
            ? "Saved session refresh did not return a readable response. You can sign in again."
            : "Saved session account check did not return a readable response. You can sign in again."
          : message(error));
        setPhase("signed_out");
      }
    })();
  }, [loadFeatures, loadMeters, loadLoans]);

  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return;
    let removed = false;
    let listener: { remove: () => Promise<void> } | undefined;
    void NativeApp.addListener("backButton", () => {
      if (phase === "signed_in" && changingPassword) setChangingPassword(false);
      else if (phase === "signed_in" && tab !== "dashboard") setTab("dashboard");
      else void NativeApp.minimizeApp();
    }).then((handle) => { if (removed) void handle.remove(); else listener = handle; });
    return () => { removed = true; if (listener) void listener.remove(); };
  }, [phase, tab, changingPassword]);

  const login = async (email: string, password: string) => {
    setBusy(true); setAuthError(null);
    let loginCompleted = false;
    try {
      await session.login(email, password);
      loginCompleted = true;
      const user = await session.getAccount();
      setOffline(false);
      clearView(); setAccount(user); setPhase(user.must_change_password ? "password_required" : "signed_in");
      if (!user.must_change_password) { void loadFeatures(); void loadMeters(); void loadLoans(); }
    } catch (error) {
      if (error instanceof TransportError) setOffline(true);
      setAuthError(error instanceof TransportError
        ? loginCompleted
          ? "Sign-in succeeded, but the account check did not return a readable response. Check the account request."
          : "The sign-in request did not return a readable response. Check the login request."
        : message(error));
    }
    finally { setBusy(false); }
  };

  const logout = async () => {
    clearView(); setPhase("signed_out"); setAuthError(null);
    setBusy(true);
    try { await session.logout(); }
    finally { setBusy(false); }
  };

  if (phase === "checking") return <main className="loading" role="status">Opening gPawa…</main>;
  if (phase === "signed_out") return <Access session={session} onLogin={login} loginBusy={busy} loginError={authError} />;
  if (phase === "password_required") return <PasswordChange required onDone={() => void logout()} />;
  if (changingPassword) return <PasswordChange required={false} onDone={() => void logout()}
    onCancel={() => setChangingPassword(false)} />;

  const meter = meters.value?.find((item) => item.meter_number === selectedMeter) ?? null;
  return <div className="app-shell">
    <header className="topbar"><div><strong>gPawa</strong><span>Consumer prototype</span></div>
      <button className="quiet" onClick={refresh}>Refresh</button></header>
    {offline && <div className="offline" role="status">A request could not reach the API. Displayed values may be stale; tap Refresh to retry.</div>}
    <main className="content">
      {tab === "dashboard" && <>
        <h1>Dashboard</h1>
        <p className="muted">Hello, {account?.first_name || account?.email || "consumer"}.</p>
        <Panel title="Selected meter">
          {meter ? <p><strong>{meter.label}</strong><br /><span className="muted">{meter.meter_number} · {meter.architecture}</span></p>
            : <p className="muted">Choose a meter on the Meters tab to view its entitlement.</p>}
          <button className="secondary" onClick={() => setTab("meters")}>Choose meter</button>
        </Panel>
        {meter && <Panel title="Energy entitlement">
          <StateLine data={allocation} offline={offline} />
          {allocation.value && <>
            <div className="metrics">
              <div><span>Available to request</span><strong>{energy(allocation.value.available_kwh)}</strong></div>
              <div><span>Reserved / unresolved</span><strong>{energy(allocation.value.pending_kwh)}</strong></div>
              <div><span>Confirmed applied</span><strong>{energy(allocation.value.confirmed_kwh)}</strong></div>
            </div>
            <p className="muted">Last meter contact: {dateTime(allocation.value.last_meter_contact)}</p>
            {allocation.value.delivery_environment === "SIMULATOR" &&
              <p className="tag">Simulation only — no physical meter accuracy is established.</p>}
            {allocation.value.delivery_environment === "UNAVAILABLE" &&
              <p className="muted">Physical delivery status is unavailable.</p>}
          </>}
        </Panel>}
        {meter && <DeliveryPanel key={meter.meter_number} session={session} meterNo={meter.meter_number}
          allocation={allocation.value} onReserved={() => void loadSelected(meter.meter_number)} />}
        <Panel title="Loan position"><StateLine data={loans} offline={offline} />
          {loans.value && (loans.value.length ? loans.value.map((loan) =>
            <div className="list-row" key={loan.id}><span>{loan.loan_id} · {loan.status}</span>
              <strong>{ugx(loan.outstanding_ugx)}</strong></div>) : <p className="muted">No loan records.</p>)}
        </Panel>
      </>}

      {tab === "meters" && <><h1>Meters</h1><p className="muted">Select the meter whose records you want to view.</p>
        <StateLine data={meters} offline={offline} />
        {meters.value && (meters.value.length ? meters.value.map((item) =>
          <button className={`meter-choice ${selectedMeter === item.meter_number ? "chosen" : ""}`}
            key={item.meter_number} onClick={() => chooseMeter(item.meter_number)}>
            <strong>{item.label}</strong><span>{item.meter_number} · {item.architecture} · {item.status}</span>
            <small>{selectedMeter === item.meter_number ? "Selected" : "Tap to select"}</small>
          </button>) : <Panel title="No meters"><p className="muted">No meter is assigned to this account.</p></Panel>)}
      </>}

      {tab === "consumption" && <><h1>Consumption history</h1>
        {!meter ? <Panel title="Choose a meter"><p className="muted">Select a meter first.</p><button onClick={() => setTab("meters")}>Select meter</button></Panel>
          : <><p className="muted">{meter.label} · {meter.meter_number}</p><StateLine data={consumption} offline={offline} />
            {consumption.value && <>
              <Panel title="Stored daily usage">
                {consumption.value.daily_usage.length ? consumption.value.daily_usage.map((row) =>
                  <div className="list-row" key={row.date}><span>{row.date}<small>{row.source === "STUB" ? "Development stub" : row.source}</small></span>
                    <strong>{energy(row.kwh)}</strong></div>) : <p className="muted">No stored daily usage is available.</p>}
              </Panel>
              <Panel title="Simulator counter readings">
                <p className="tag">Simulated cumulative Wh; resets and reordered events are labelled. These are not physical accuracy results.</p>
                {consumption.value.simulator_telemetry.length ? consumption.value.simulator_telemetry.map((row) =>
                  <div className="list-row" key={row.event_id}><span>{dateTime(row.measured_at)}<small>{row.classification}</small></span>
                    <strong>{row.cumulative_wh} Wh</strong></div>) : <p className="muted">No simulator readings.</p>}
              </Panel>
            </>}
          </>}
      </>}

      {tab === "loans" && <><h1>Loans and repayments</h1><StateLine data={loans} offline={offline} />
        <LoanQuote session={session} meters={meters.value} selectedMeter={selectedMeter} />
        {loans.value && (loans.value.length ? loans.value.map((loan) => <Panel key={loan.id} title={loan.loan_id}>
          <div className="metrics two"><div><span>Status</span><strong>{loan.status}</strong></div>
            <div><span>Outstanding</span><strong>{ugx(loan.outstanding_ugx)}</strong></div></div>
          <p className="muted">Approved: {ugx(loan.amount_approved_ugx)} · Due: {dateTime(loan.due_at)}</p>
          <h3>Repayment history</h3>
          {loan.repayments.length ? loan.repayments.map((row) =>
            <div className="list-row" key={row.id}><span>{dateTime(row.paid_at)}<small>{row.status} · Applied {ugx(row.applied_ugx)}
              {row.excess_ugx && <> · Excess {ugx(row.excess_ugx)}</>}</small></span><strong>{ugx(row.received_ugx)}</strong></div>)
            : <p className="muted">No repayments recorded.</p>}
        </Panel>) : <Panel title="No loans"><p className="muted">No loan records are available.</p></Panel>)}
      </>}

      {tab === "activity" && <Activity session={session} />}

      {tab === "account" && <><h1>Account</h1><Panel title="Consumer profile">
        <p><strong>{account?.first_name} {account?.last_name}</strong><br />{account?.email}</p>
        <p className="muted">Role: {account?.user_role}</p>
        <p className="muted">Email: {account?.email_verified ? "Verified" : "Verification status unavailable"}</p>
      </Panel><ProfileEditor session={session} /><Panel title="Security">
        <button className="secondary" onClick={() => setChangingPassword(true)}>Change password</button>
      </Panel><Panel title="Feature availability">
        <p className="muted">{featuresVerified ? "Supplied by Django" : "Could not verify; deferred features remain hidden."}</p>
        <p className="muted">{Object.values(features).filter(Boolean).length} optional features enabled on the server; this read-only app offers none of their actions.</p>
      </Panel><Panel title="Session"><button className="danger" onClick={() => void logout()}>Log out</button>
        <p className="muted small">Offline logout clears this device; server revocation needs a connection.</p></Panel></>}
    </main>
    <nav className="bottom-nav" aria-label="Main navigation">
      {(["dashboard", "meters", "consumption", "loans", "activity", "account"] as const).map((item) =>
        <button key={item} aria-current={tab === item ? "page" : undefined} onClick={() => setTab(item)}>
          {item[0].toUpperCase() + item.slice(1)}</button>)}
    </nav>
  </div>;
}
