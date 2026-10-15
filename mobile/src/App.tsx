import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Capacitor } from "@capacitor/core";
import { App as NativeApp } from "@capacitor/app";
import { API_BASE_URL } from "./api/config.ts";
import { DISABLED_MOBILE_ACTIONS, parseMobileActions, type MobileActions } from "./api/mobile-actions.ts";
import type { ConsumerFinanceView, FinanceDestination } from "../../frontend/src/components/sandbox-mobile-view.tsx";
import SandboxConsumer from "../../frontend/src/components/sandbox-consumer.tsx";
import { sandboxCapabilities, NO_SANDBOX, type SandboxCapabilities } from "../../frontend/src/lib/sandbox.ts";
import { MeterOnboarding } from "./Onboarding.tsx";
import { ForegroundPoller } from "./api/polling.ts";
import { Access } from "./Access.tsx";
import { ProfileEditor } from "./Profile.tsx";
import { DeliveryPanel } from "./Delivery.tsx";
import { Activity } from "./Activity.tsx";
import { LoanQuote } from "./LoanQuote.tsx";
import { PurchasePanel, RepaymentPanel } from "./PaymentActions.tsx";
import { Brand, Icon } from "./ui.tsx";
import { CONSUMER_TABS, activeConsumerTab, type ConsumerTab } from "./consumer-navigation.ts";
import { LatestRead } from "./api/read-scope.ts";
import { parseMeterDashboard, selectedMeterStillAssigned, parseConsumption, parseLoans, parseMeters,
  type AllocationStatus, type ConsumptionHistory, type Loan, type MeterInfo } from "./api/contracts.ts";
import { ApiError, SessionExpired, SessionManager, TransportError, type ConsumerIdentity } from "./auth/session.ts";
import { AndroidSecureStore } from "./auth/secure-store.ts";
import { dateTime, energy, ugx } from "./format.ts";
import { CreditSummary } from "./CreditSummary.tsx";
import { PageHeading, MeterSummary, CloudEnergyCard, EmptyState, MenuRow } from "./ConsumerUI.tsx";

const session = new SessionManager(API_BASE_URL, new AndroidSecureStore());
type Tab = ConsumerTab | "activity" | "consumption" | "apply";
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
  if (data.error || (data.fetchedAt && (offline || data.loading))) return <>
    {data.error && <p className="error" role="alert">{data.error}</p>}
    {data.fetchedAt && <p className="stale">Stale — updated {dateTime(data.fetchedAt)}.</p>}
  </>;
  if (offline && data.value === null) return <p className="muted">Connection unavailable. Tap Refresh to try again.</p>;
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
  const [showProfile, setShowProfile] = useState(false);
  const [showAddMeter, setShowAddMeter] = useState(false);
  const [creditRevision, setCreditRevision] = useState(0);
  const [meters, setMeters] = useState<Resource<MeterInfo[]>>(empty);
  const [loans, setLoans] = useState<Resource<Loan[]>>(empty);
  const [selectedMeter, setSelectedMeter] = useState<string | null>(null);
  const [allocation, setAllocation] = useState<Resource<AllocationStatus>>(empty);
  const [consumption, setConsumption] = useState<Resource<ConsumptionHistory>>(empty);
  const [capabilitiesReady, setCapabilitiesReady] = useState(false);
  const [sandbox, setSandbox] = useState<SandboxCapabilities>(NO_SANDBOX);
  const [mobileActions, setMobileActions] = useState<MobileActions>(DISABLED_MOBILE_ACTIONS);
  const booted = useRef(false);
  const selectedRef = useRef<MeterInfo | null>(null);
  const meterReads = useRef(new LatestRead());
  const selectedReads = useRef(new LatestRead());
  const capabilityReads = useRef(new LatestRead());
  const financeBack = useRef<(() => boolean) | null>(null);
  const registerFinanceBack = useCallback((handler: (() => boolean) | null) => { financeBack.current = handler; }, []);
  const [meterNotice, setMeterNotice] = useState<string | null>(null);

  const clearView = useCallback(() => {
    setAccount(null); setMeters(empty()); setLoans(empty()); setAllocation(empty());
    setConsumption(empty()); setSelectedMeter(null); selectedRef.current = null;
    meterReads.current.invalidate(); selectedReads.current.invalidate(); setMeterNotice(null);
    setChangingPassword(false); setShowProfile(false); setShowAddMeter(false); setSandbox(NO_SANDBOX);
    setTab("dashboard"); setCapabilitiesReady(false); setMobileActions(DISABLED_MOBILE_ACTIONS);
    capabilityReads.current.invalidate(); financeBack.current = null;
  }, []);

  const expire = useCallback(() => {
    clearView(); setAuthError("Session expired. Please sign in again."); setPhase("signed_out");
  }, [clearView]);

  const loadFeatures = useCallback(async () => {
    const owner = session.identity, ticket = capabilityReads.current.begin();
    try {
      const data = await session.publicGet<{ features?: unknown; mobile_actions?: unknown; sandbox?: unknown }>("features/");
      if (owner !== session.identity || !capabilityReads.current.current(ticket)) return;
      setOffline(false);
      setMobileActions(parseMobileActions(data.mobile_actions));
      setSandbox(sandboxCapabilities(data.sandbox)); setCapabilitiesReady(true);
    } catch (error) {
      if (owner !== session.identity || !capabilityReads.current.current(ticket)) return;
      if (error instanceof TransportError) setOffline(true);
      // Keep the known controller mounted for pending recovery; disable new mutations.
      setMobileActions(DISABLED_MOBILE_ACTIONS); setCapabilitiesReady(false);
    }
  }, []);

  const loadMeters = useCallback(async () => {
    const owner = session.identity;
    const ticket = meterReads.current.begin();
    setMeters((old) => ({ ...old, loading: true, error: null }));
    try {
      let value: MeterInfo[];
      try {
        const onboarding = await session.get<{ meters: unknown[] }>("meter/mobile-onboarding/");
        value = parseMeters({ success: true, data: { has_meter: onboarding.meters.length > 0, meters: onboarding.meters } });
      } catch (cause) {
        if (!(cause instanceof ApiError && cause.status === 404)) throw cause;
        // Keep existing authorized reads usable during the staged backend upload.
        value = parseMeters(await session.get<unknown>("meter/mobile-meters/"));
      }
      if (owner !== session.identity || !meterReads.current.current(ticket)) return;
      setOffline(false);
      if (selectedRef.current && !selectedMeterStillAssigned(selectedRef.current, value)) {
        selectedRef.current = null; setSelectedMeter(null); selectedReads.current.invalidate();
        setAllocation(empty()); setConsumption(empty());
        setMeterNotice("Your meter assignment changed. Select an assigned meter again.");
      }
      setMeters({ value, loading: false, error: null, fetchedAt: new Date().toISOString() });
    } catch (error) {
      if (owner !== session.identity || !meterReads.current.current(ticket)) return;
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

  const loadSelected = useCallback(async (selected: MeterInfo) => {
    const meterNo = selected.meter_number;
    const owner = session.identity;
    const ticket = selectedReads.current.begin();
    setAllocation((old) => ({ ...old, loading: true, error: null }));
    setConsumption((old) => ({ ...old, loading: true, error: null }));
    const path = encodeURIComponent(meterNo);
    const [allocationResult, consumptionResult] = await Promise.allSettled([
      session.get<unknown>(`meter/mobile-meters/${selected.id}/`).then((data) => parseMeterDashboard(data, selected)),
      session.get<unknown>(`meter/mobile-consumption/?meter_id=${selected.id}&meter_no=${path}`)
        .then((data) => parseConsumption(data, selected)),
    ]);
    if (owner !== session.identity || selectedRef.current?.id !== selected.id ||
        selectedRef.current.meter_number !== meterNo || !selectedReads.current.current(ticket)) return false;
    if (allocationResult.status === "rejected" && allocationResult.reason instanceof ApiError &&
        allocationResult.reason.status === 404) {
      selectedRef.current = null; setSelectedMeter(null); selectedReads.current.invalidate();
      setAllocation(empty()); setConsumption(empty());
      setMeterNotice("This meter is no longer assigned to your account. Refresh and select a meter again.");
      return false;
    }
    if (allocationResult.status === "fulfilled") {
      setOffline(false);
      setAllocation({ value: allocationResult.value, loading: false, error: null, fetchedAt: new Date().toISOString() });
    } else if (allocationResult.reason instanceof SessionExpired) { expire(); return false; }
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
    return allocationResult.status === "fulfilled" && consumptionResult.status === "fulfilled";
  }, [expire]);

  const chooseMeter = (selected: MeterInfo) => {
    selectedRef.current = selected; setSelectedMeter(selected.meter_number); setMeterNotice(null);
    setAllocation(empty()); setConsumption(empty());
    void loadSelected(selected);
  };

  const enrolledMeter = (linked: MeterInfo) => {
    meterReads.current.invalidate();
    setMeters(old => ({ value: [...(old.value ?? []).filter(item => item.id !== linked.id), linked],
      loading: false, error: null, fetchedAt: new Date().toISOString() }));
    chooseMeter(linked); setShowAddMeter(false); setCreditRevision(value => value + 1);
  };

  const refresh = useCallback(() => {
    if (phase !== "signed_in") return;
    setCreditRevision(value => value + 1);
    void loadFeatures(); void loadMeters(); void loadLoans();
    if (selectedRef.current) void loadSelected(selectedRef.current);
  }, [phase, loadFeatures, loadMeters, loadLoans, loadSelected]);

  useEffect(() => {
    if (phase !== "signed_in") return;
    if (!selectedRef.current && !meterNotice && meters.value?.length === 1) chooseMeter(meters.value[0]);
  }, [phase, meters.value, meterNotice]);

  useEffect(() => {
    if (phase !== "signed_in") return;
    const poller = new ForegroundPoller(async () => {
      const selected = selectedRef.current;
      if (selected) return await loadSelected(selected);
      await loadMeters();
      return false;
    });
    let nativeActive = true;
    const visibility = () => poller.setActive(nativeActive && document.visibilityState !== "hidden");
    visibility();
    document.addEventListener("visibilitychange", visibility);
    let removed = false;
    let handle: { remove: () => Promise<void> } | undefined;
    if (Capacitor.isNativePlatform()) void NativeApp.addListener("appStateChange", ({ isActive }) => {
      nativeActive = isActive; visibility();
    }).then((listener) => { if (removed) void listener.remove(); else handle = listener; });
    return () => { removed = true; poller.dispose(); document.removeEventListener("visibilitychange", visibility); if (handle) void handle.remove(); };
  }, [phase, loadSelected, loadMeters]);

  useEffect(() => {
    if (booted.current) return;
    booted.current = true;
    void (async () => {
      let restoreStage: "refresh" | "account" = "refresh";
      try {
        const restored = await session.restore();
        if (!restored) { setPhase("signed_out"); return; }
        restoreStage = "account";
        const user = await session.getAccount();
        setOffline(false);
        setAccount(user); setPhase(user.must_change_password ? "password_required" : "signed_in");
        if (!user.must_change_password) { void loadFeatures(); void loadMeters(); void loadLoans(); }
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
    if (!Capacitor.isNativePlatform() || phase === "signed_out") return;
    let removed = false;
    let listener: { remove: () => Promise<void> } | undefined;
    void NativeApp.addListener("backButton", () => {
      if (phase === "signed_in" && showAddMeter) setShowAddMeter(false);
      else if (phase === "signed_in" && showProfile) setShowProfile(false);
      else if (phase === "signed_in" && changingPassword) setChangingPassword(false);
      else if (phase === "signed_in" && financeBack.current?.()) return;
      else if (phase === "signed_in" && tab === "consumption") setTab("meters");
      else if (phase === "signed_in" && tab === "apply") setTab("loans");
      else if (phase === "signed_in" && tab !== "dashboard") setTab("dashboard");
      else void NativeApp.minimizeApp();
    }).then((handle) => { if (removed) void handle.remove(); else listener = handle; });
    return () => { removed = true; if (listener) void listener.remove(); };
  }, [phase, tab, changingPassword, showProfile, showAddMeter]);

  const financeError = useCallback((cause: unknown) => {
    if (cause instanceof SessionExpired) expire();
    else if (cause instanceof TransportError) setOffline(true);
  }, [expire]);

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
          ? `Sign-in succeeded, but the account check failed. ${error.message}`
          : `Sign-in could not complete. ${error.message}`
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

  if (phase === "checking") return <main className="loading" role="status"><Brand /><span className="loading-spinner" /><p>Opening your energy account…</p></main>;
  if (phase === "signed_out") return <Access session={session} onLogin={login} loginBusy={busy} loginError={authError} />;
  if (phase === "password_required") return <PasswordChange required onDone={() => void logout()} />;
  if (changingPassword) return <PasswordChange required={false} onDone={() => void logout()}
    onCancel={() => setChangingPassword(false)} />;

  const meter = meters.value?.find((item) => item.meter_number === selectedMeter) ?? null;
  const title = { dashboard: "Home", meters: "My Meters", loans: "Loans", purchase: "Buy Units", account: "Account", activity: "Activity", consumption: "Usage", apply: "Apply for Loan" }[tab];
  const navigate = (next: Tab) => { setTab(next); setShowProfile(false); setShowAddMeter(false); window.scrollTo({ top: 0, behavior: "instant" }); };
  const financeView: ConsumerFinanceView = tab === "dashboard" ? "home" : (tab === "loans" || tab === "apply" || tab === "purchase" || tab === "activity") ? tab : "hidden";
  const navigateFinance = (next: FinanceDestination) => navigate(next);
  return <div className="app-shell consumer-redesign">
    <header className="topbar"><div className="topbar-identity"><Brand /><span className="topbar-page">{title}</span></div><div className="header-actions">
      <button className="icon-button" aria-label="Refresh account" onClick={refresh}><Icon name="refresh" /></button>
      <button className="icon-button" aria-label="Activity and notifications" onClick={() => navigate("activity")}><Icon name="bell" /></button>
      <button className="avatar-button" aria-label="Your account" onClick={() => navigate("account")}>{account?.first_name?.charAt(0) || "U"}</button>
    </div></header>
    <main className="content" id="main-content">
      {offline && <div className="offline" role="status">Connection interrupted. Some values may be out of date. <button className="text-button" onClick={refresh}>Retry</button></div>}
      {meterNotice && <p className="tag" role="status">{meterNotice}</p>}
      {tab === "dashboard" && <>
        <PageHeading eyebrow="YOUR ENERGY, SIMPLIFIED" title={`Hello, ${account?.first_name || "there"}`} text="Everything you need to keep going." />
        <MeterSummary meter={meter} onChange={() => navigate("meters")} />
        <StateLine data={meters} offline={offline} />
        {meter ? <><CloudEnergyCard value={allocation.value?.available_kwh} pending={allocation.value?.pending_kwh} loading={allocation.loading} onDetails={() => navigate("meters")} />
          <StateLine data={allocation} offline={offline} /></> : <EmptyState icon="meter" title="Start with your meter" text="Link your meter number to get started." action="Add your meter" onAction={() => { navigate("meters"); setShowAddMeter(true); }} />}
        <div className="home-actions">
          <button className="action-tile" onClick={() => navigate("apply")}><span className="action-symbol"><Icon name="loan" /></span><strong>Apply for Loan</strong><span>Electricity when you need it</span><Icon name="arrow" /></button>
          <button className="action-tile" onClick={() => navigate("purchase")}><span className="action-symbol"><Icon name="bolt" /></span><strong>Buy Units</strong><span>Top up your cloud energy</span><Icon name="arrow" /></button>
        </div>
        {!capabilitiesReady ? <section className="panel"><h2>Credit overview</h2><p className="muted">Refresh to load your account capabilities.</p></section> : sandbox.enabled ? null : <CreditSummary session={session} meterId={meter?.id ?? null} revision={creditRevision} onExpired={expire} onLoans={() => navigate("loans")} demo={false} />}

      </>}

      {tab === "meters" && <>
        <PageHeading title="My Meters" text="Select a meter or link a new one." />
        <div className="section-title"><p className="muted">{meters.value ? `${meters.value.length} meter${meters.value.length === 1 ? "" : "s"} on your account` : "Your registered meters"}</p></div>
        <button className="primary-button" aria-expanded={showAddMeter} onClick={() => setShowAddMeter(value => !value)}><Icon name={showAddMeter ? "back" : "plus"} />{showAddMeter ? "Back to meters" : "Add new meter"}</button>
        {(showAddMeter || meters.value?.length === 0) && <MeterOnboarding session={session} hasMeter={Boolean(meters.value?.length)} onRefresh={refresh} onLinked={enrolledMeter} />}
        <StateLine data={meters} offline={offline} />
        {meters.value?.map(item => <button className={`meter-choice ${selectedMeter === item.meter_number ? "chosen" : ""}`} key={item.id} onClick={() => chooseMeter(item)} aria-pressed={selectedMeter === item.meter_number}>
          <span className="meter-card-heading"><span className="row-icon"><Icon name="meter" /></span><span><strong>{item.label || "My meter"}</strong><small className="meter-number">{item.meter_number}</small></span><span className={selectedMeter === item.meter_number ? "selected-tick" : "choice-circle"}>{selectedMeter === item.meter_number && <Icon name="check" />}</span></span>
          <span className="meter-id"><span>{item.status.replaceAll("_", " ")}</span><span className="status-pill neutral">{selectedMeter === item.meter_number ? "Selected" : "Tap to select"}</span></span>
        </button>)}
        {meter && <><Panel title={meter.label || "Meter details"}>
          <p className="meter-number muted">{meter.meter_number}</p><StateLine data={allocation} offline={offline} />
          <div className="detail-grid"><div><span>Cloud energy available</span><strong>{energy(allocation.value?.available_kwh)}</strong></div><div><span>Reserved energy</span><strong>{energy(allocation.value?.pending_kwh)}</strong></div><div><span>{allocation.value?.contact_source === "SIMULATOR" ? "Simulator remaining credit" : "Physical meter balance"}</span><strong>{allocation.value?.meter_reported_remaining_wh == null ? "Unavailable" : `${allocation.value.meter_reported_remaining_wh} Wh`}</strong></div></div>
          <div className="button-pair"><button onClick={() => navigate("purchase")}>Buy Units</button><button className="secondary" onClick={() => navigate("consumption")}>View usage</button></div>
          <details className="info-disclosure"><summary>Meter information</summary><p>Cloud allocations are separate from electricity applied to the physical meter.</p>
            {meter.ownership_provenance === "SELF_DECLARED" && <p>Linked using the number you provided. Ownership has not been checked with the utility.</p>}
            <p>Last contact: {dateTime(allocation.value?.last_meter_contact)}.</p>
            <p>Recorded application: {allocation.value?.contact_source === "UNAVAILABLE" ? "Unavailable" : energy(allocation.value?.confirmed_kwh)}.</p>
            {allocation.value?.contact_source === "SIMULATOR" && <p>Contact and delivery readings are simulated.</p>}
          </details>
        </Panel><details className="info-disclosure panel"><summary>Delivery history & loading</summary><DeliveryPanel key={meter.id} session={session} meter={meter} allocation={allocation.value} onReserved={() => void loadSelected(meter)} /></details></>}
      </>}

      {tab === "consumption" && <>
        <button className="text-button" onClick={() => navigate("meters")}><Icon name="back" />My Meters</button>
        <PageHeading title="Energy usage" text={meter ? `${meter.label} · ${meter.meter_number}` : "Select a meter to see its readings."} />
        {!meter ? <EmptyState icon="meter" title="Choose your meter" text="Usage belongs to the selected meter." action="Select meter" onAction={() => navigate("meters")} /> : <>
          <StateLine data={consumption} offline={offline} />
          <Panel title="Stored daily usage">{consumption.value?.daily_usage.length ? <>
            {!consumption.value.consumer_attribution_available && <p className="muted small">Meter history; previous consumer attribution is unavailable.</p>}
            {consumption.value.daily_usage.map(row => <div className="list-row" key={row.date}><span>{row.date}<small>{row.source === "STUB" ? "Sample reading" : row.source}</small></span><strong>{energy(row.kwh)}</strong></div>)}
          </> : <div className="empty-inline"><Icon name="chart" /><h3>No readings yet</h3><p className="muted">Actual consumption appears when meter readings become available.</p></div>}</Panel>
          {!!consumption.value?.simulator_telemetry.length && <details className="panel info-disclosure"><summary>Simulated readings</summary>{consumption.value.simulator_telemetry.map(row => <div className="list-row" key={row.event_id}><span>{dateTime(row.measured_at)}<small>{row.classification}</small></span><strong>{row.cumulative_wh} Wh</strong></div>)}</details>}
        </>}
      </>}

      {(tab === "loans" || tab === "apply" || tab === "purchase") && <>
        <PageHeading title={tab !== "purchase" ? "Loans" : "Buy Units"} text={tab !== "purchase" ? "Apply for electricity credit or manage your repayments." : "Choose an amount and review your electricity purchase."} />
        <MeterSummary meter={meter} onChange={() => navigate("meters")} />
        {capabilitiesReady && !sandbox.enabled && (tab === "loans" || tab === "apply") && <>
          <LoanQuote session={session} meters={meters.value} selectedMeter={selectedMeter} />
        </>}
        {tab === "loans" && <details className="panel info-disclosure" open={!sandbox.enabled}><summary>{sandbox.enabled ? "Earlier loan records" : "Loan records & repayments"}</summary>
          <StateLine data={loans} offline={offline} />
          {loans.value?.length === 0 && <p className="muted">No records in this loan history.</p>}
          {loans.value?.map(loan => <Panel key={loan.id} title={loan.loan_id}><span className="status-pill neutral">{loan.status}</span><p className="muted">Outstanding</p><strong className="loan-amount">{ugx(loan.outstanding_ugx)}</strong><p className="muted">Due {dateTime(loan.due_at)}</p><RepaymentPanel session={session} loan={loan} enabled={mobileActions.repayment} onActivity={() => navigate("activity")} /><details className="info-disclosure"><summary>Repayment history</summary>{loan.repayments.map(row => <div className="list-row" key={row.id}><span>{dateTime(row.paid_at)}<small>{row.status} · Applied {ugx(row.applied_ugx)}{row.excess_ugx && <> · Excess {ugx(row.excess_ugx)}</>}</small></span><strong>{ugx(row.received_ugx)}</strong></div>)}</details></Panel>)}
        </details>}
        {capabilitiesReady && !sandbox.enabled && tab === "purchase" && (meter ? <PurchasePanel key={meter.id} session={session} meterNo={meter.meter_number} enabled={mobileActions.purchase} onActivity={() => navigate("activity")} /> : <EmptyState icon="meter" title="Select a meter first" text="Your units will be allocated to this meter." action="Choose meter" onAction={() => navigate("meters")} />)}
      </>}
      {/* One controller across all tabs; only its presentation changes. */}
      {sandbox.enabled && account && <section className="finance-workspace" aria-label="Loans and payments" hidden={financeView === "hidden"}>
        <SandboxConsumer key={`${account.id}:${sandbox.provider ?? "MTN_SANDBOX"}`} client={session} owner={account.id}
          meters={meters.value ?? []} selectedMeter={meter} capabilities={sandbox} onChanged={refresh}
          view={financeView} onNavigate={navigateFinance} refreshVersion={creditRevision}
          mutationsAvailable={capabilitiesReady && !offline} onError={financeError} registerBackHandler={registerFinanceBack} />
      </section>}
      {tab === "dashboard" && <>
        <section className="panel menu-card"><MenuRow icon="loan" title="My loans & repayments" text="Check your balance, due date and loan history" onClick={() => navigate("loans")} />
          <MenuRow icon="activity" title="Activity & receipts" text="Review payments and account updates" onClick={() => navigate("activity")} /></section>
        <div className="connection-note"><Icon name="meter" /><div><strong>{allocation.value?.contact_source === "SIMULATOR" ? "Simulator readings available" : allocation.value?.last_meter_contact ? "Stored meter readings" : "Hardware contact unavailable"}</strong><p>{allocation.value?.last_meter_contact ? `Last contact ${dateTime(allocation.value.last_meter_contact)}` : "Live balance and usage will appear after hardware connection."}</p></div><button className="text-button" onClick={() => navigate("consumption")}>Usage</button></div>
      </>}
      {tab === "activity" && <>
        <button className="text-button" onClick={() => navigate("dashboard")}><Icon name="back" />Home</button>

        <Activity session={session} />
      </>}
      {tab === "account" && <>
        <PageHeading title="Account" text="Your details, preferences and security." />
        <section className="panel profile-card"><span className="profile-avatar">{account?.first_name?.charAt(0) || "U"}{account?.last_name?.charAt(0)}</span><h2>{account?.first_name} {account?.last_name}</h2><p className="muted">{account?.email}</p><span className="status-pill neutral">{account?.email_verified ? "Email verified" : "Email verification pending"}</span></section>
        <section className="panel menu-card"><MenuRow icon="user" title="Personal details" text="Address and account preferences" onClick={() => setShowProfile(value => !value)} expanded={showProfile} />
          <MenuRow icon="lock" title="Change password" text="Keep your account secure" onClick={() => setChangingPassword(true)} />
          <MenuRow icon="meter" title="My meters" text="Manage and select your meter" onClick={() => navigate("meters")} />
          <MenuRow icon="activity" title="Activity & receipts" text="Payment records and notifications" onClick={() => navigate("activity")} /></section>
        {showProfile && <ProfileEditor session={session} onExpired={expire} />}
        <details className="panel info-disclosure"><summary>Help & information</summary><h3>Where is my credit score?</h3><p>Open Credit overview on Home to view the stored assessment. You do not need to fill in a loan questionnaire.</p><h3>Where are my units?</h3><p>Cloud energy shows your allocation. Physical meter balance requires a hardware connection.</p><h3>What if a payment is pending?</h3><p>Check its receipt in Loans or Buy Units before starting another payment.</p></details>
        <button className="logout-button" onClick={() => void logout()}><Icon name="logout" />Log out</button>
        <p className="muted small centered">Offline logout clears this device. Server revocation needs a connection.</p>
      </>}
    </main>
    <nav className="bottom-nav" aria-label="Main navigation">{CONSUMER_TABS.map(item => <button key={item.id} aria-current={activeConsumerTab(tab) === item.id ? "page" : undefined} onClick={() => navigate(item.id)}><Icon name={item.icon} /><span>{item.label}</span></button>)}</nav>
  </div>;
}
