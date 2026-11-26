"use client";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Activity, ArrowDownLeft, ArrowRight, ArrowUpRight, Check, ChevronRight, CreditCard, Gauge, Home, Leaf, LogOut, Plus, RefreshCw, ShieldCheck, UserRound, Zap } from "lucide-react";
import { AllocationLedgers } from "../allocation-ledgers";
import SandboxConsumer from "../sandbox-consumer";
import { consumerClient, useConsumerRead } from "./read";
import { MeasuredConsumptionPanel } from "../measured-consumption-panel";
import { measuredConsumptionPath, parseMeasuredConsumption, type UsageDays } from "../../lib/measured-consumption";
import { consumerScreen, CONSUMER_PATHS, ConsumerReadScope, defaultConsumerMeter, exactAmount, parseConsumerSummary, record, type ConsumerScreen } from "../../lib/consumer-parity";
import { sandboxCapabilities, parseTestPayment, paymentStatusMessage, type Assessment, type TestMeter } from "../../lib/sandbox";
import { formatEnergy, formatMoney, meterReadEnvironment } from "../../lib/sandbox-presentation";
import { normalizePrototypeMeterNumber, parsePrototypeEnrollment, METER_NUMBER_MESSAGE } from "../../lib/meter-enrollment";
import { parseStoredDemoAssessment } from "../../lib/sandbox";
import { clearPrivateBrowserState } from "../../lib/session-storage";
import logout from "../../app/(dashboard)/dashboard/logout";
import ConsumerAccount from "./account";

type Account = { id: number; first_name: string; last_name: string; email: string; email_verified: boolean };
function accountData(raw: unknown): Account {
  const row = record(raw);
  if (!Number.isSafeInteger(row.id) || Number(row.id) <= 0 || typeof row.email !== "string" || typeof row.first_name !== "string" || typeof row.last_name !== "string" || typeof row.email_verified !== "boolean") throw new Error("Account unavailable.");
  return row as Account;
}
function onboardingData(raw: unknown) {
  const row = record(raw);
  if (!Array.isArray(row.meters)) throw new Error("Meters unavailable.");
  const ids = new Set<number>();
  const meters = row.meters.map(value => {
    const meter = record(value);
    if (!Number.isSafeInteger(meter.id) || Number(meter.id) <= 0 || ids.has(Number(meter.id)) || typeof meter.meter_number !== "string" || !meter.meter_number || typeof meter.label !== "string" || typeof meter.status !== "string") throw new Error("Meter data unavailable.");
    ids.add(Number(meter.id));
    return meter as TestMeter;
  });
  return { meters, enrollment: row.sandbox_self_enrollment === true };
}
function flagsData(raw: unknown) {
  const sandbox = record(raw).sandbox, capabilities = sandboxCapabilities(sandbox);
  if (sandbox && typeof sandbox === 'object' && 'enabled' in sandbox && sandbox.enabled === true && !capabilities.enabled)
    throw new Error('Unsupported sandbox capability contract. Deploy the matching backend and web build; financial actions are blocked.');
  return capabilities;
}
function paymentsData(raw: unknown) {
  const row = record(raw);
  if (!Array.isArray(row.payments)) throw new Error("Activity unavailable.");
  return row.payments.map(parseTestPayment);
}
const icons = { home: Home, meters: Gauge, loans: CreditCard, purchase: Zap, activity: Activity, account: UserRound };
const names = { home: "Home", meters: "Meters", loans: "Loans", apply: "Apply for Loan", purchase: "Buy Units", activity: "Activity", account: "Account" };
const navigation = ["home", "meters", "loans", "purchase", "activity", "account"] as const;

export default function ConsumerRouter({ children }: { children: ReactNode }) {
  const pathname = usePathname(), query = useSearchParams();
  const screen = consumerScreen(pathname.replace(/\/$/, ""), query.get("tab"));
  return screen ? <ConsumerWorkspace screen={screen} /> : children;
}

export function ConsumerWorkspace({ screen }: { screen: ConsumerScreen }) {
  const [attempt, retry] = useState(0);
  const account = useConsumerRead("auth/mobile-account/", accountData, attempt, 0);
  const flags = useConsumerRead("features/", flagsData, attempt, 0);
  const onboarding = useConsumerRead("meter/mobile-onboarding/", onboardingData, attempt, 0);
  const error = account.error || flags.error || onboarding.error;
  if (error || !account.value || !flags.value || !onboarding.value) return <div className="consumer-app consumer-initial"><Leaf size={32} /><h1>EnergyFlex</h1>
    {error ? <><p role="alert">{error}</p><button onClick={() => retry(value => value + 1)}>Try again</button></> : <p role="status">Loading your account…</p>}</div>;
  return <Workspace key={`${account.value.id}:${flags.value.provider ?? "unavailable"}`} account={account.value} capabilities={flags.value} initialMeters={onboarding.value.meters} enrollment={onboarding.value.enrollment} screen={screen} />;
}

function Workspace({ account, capabilities: initialCapabilities, initialMeters, enrollment, screen }: {
  account: Account; capabilities: ReturnType<typeof flagsData>; initialMeters: TestMeter[]; enrollment: boolean; screen: ConsumerScreen;
}) {
  const router = useRouter();
  const [meters, setMeters] = useState(initialMeters);
  const [selected, select] = useState<string | null>(null);
  const meter = defaultConsumerMeter(meters, selected);
  const [revision, setRevision] = useState(0);
  const latestCapabilities = useConsumerRead("features/", flagsData, revision, account.id, true);
  const capabilities = latestCapabilities.value ?? initialCapabilities;
  const capabilitiesReady = latestCapabilities.value !== null && !latestCapabilities.loading && !latestCapabilities.error;
  const refresh = useCallback(() => setRevision(value => value + 1), []);
  const meterReads = useRef(new ConsumerReadScope());
  const [assignmentError, setAssignmentError] = useState<string | null>(null);
  useEffect(() => {
    const scope = meterReads.current;
    const ticket = scope.begin();
    void consumerClient.get<unknown>("meter/mobile-onboarding/").then(onboardingData).then(value => {
      if (!scope.current(ticket)) return;
      setMeters(value.meters); setAssignmentError(null);
    }).catch(() => {
      if (scope.current(ticket)) setAssignmentError("Meter assignments could not be refreshed. The displayed list may be stale; retry before continuing.");
    });
    return () => scope.invalidate();
  }, [account.id, revision]);
  useEffect(() => {
    const focused = () => refresh();
    const timer = window.setInterval(() => { if (document.visibilityState === "visible") refresh(); }, 60000);
    window.addEventListener("focus", focused);
    return () => { window.clearInterval(timer); window.removeEventListener("focus", focused); };
  }, [refresh]);
  const [number, setNumber] = useState("");
  const [enrolling, setEnrolling] = useState(false);
  const [meterError, setMeterError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loggingOut, setLoggingOut] = useState(false);
  const environment = capabilities.environment ?? "MTN_SANDBOX";
  const lendingEnvironment = capabilities.loanEnvironment ?? environment;
  const currency = capabilities.loanCurrency ?? (environment === "UGX_DEMO" ? "UGX" : "EUR");
  const money = (value?: string | null) => formatMoney(value, currency);
  const summaryParser = useCallback((raw: unknown) => parseConsumerSummary(raw, account.id, lendingEnvironment), [account.id, lendingEnvironment]);
  const summary = useConsumerRead(capabilities.enabled ? `sandbox/summary/?environment=${lendingEnvironment}` : null, summaryParser, revision, account.id);
  const assessmentParser = useCallback((raw: unknown): Assessment => {
    const value = record(raw).assessment;
    if (currency === "UGX") return parseStoredDemoAssessment(value, { owner: account.id, meterId: meter?.id ?? null });
    return value as Assessment;
  }, [currency, account.id, meter?.id]);
  const assessment = useConsumerRead(capabilities.enabled && meter ? `sandbox/assessment/?meter_id=${meter.id}${capabilities.loanCurrency === "UGX" && capabilities.provider === "MTN_SANDBOX" ? "&lending=ugx" : ""}` : null, assessmentParser, revision, account.id);
  const energyParser = useCallback((raw: unknown) => {
    const row = record(raw), destination = record(row.meter);
    if (destination.id !== meter?.id || destination.meter_number !== meter?.meter_number) throw new Error("Meter assignment changed. Refresh your meters.");
    return { available: exactAmount(row.available_kwh), pending: exactAmount(row.pending_kwh),
      confirmed: exactAmount(row.confirmed_kwh), physical: row.contact_source === "AC_LAB" };
  }, [meter?.id, meter?.meter_number]);
  const readEnvironment = capabilities.enabled ? meterReadEnvironment(environment, capabilities.energyEnvironment) : "CORE";
  const energy = useConsumerRead(meter ? `meter/mobile-meters/${meter.id}/?environment=${readEnvironment}` : null, energyParser, revision, account.id);
  const [usageDays, setUsageDays] = useState<UsageDays>(7);
  const usageScope = meter ? { id: meter.id, meter_number: meter.meter_number, environment: readEnvironment, days: usageDays } : null;
  const parseUsage = useCallback((raw: unknown) => {
    if (!meter) throw new Error("Choose a meter first.");
    return parseMeasuredConsumption(raw, { id: meter.id, meter_number: meter.meter_number, environment: readEnvironment, days: usageDays });
  }, [meter?.id, meter?.meter_number, readEnvironment, usageDays]);
  const measured = useConsumerRead(usageScope && screen === "meters" ? measuredConsumptionPath(usageScope) : null,
    parseUsage, revision, account.id, true);
  const recent = useConsumerRead(capabilities.enabled ? "sandbox/payments/" : null, paymentsData, revision, account.id);
  const go = useCallback((destination: ConsumerScreen) => router.push(CONSUMER_PATHS[destination]), [router]);
  const signOut = useCallback(async () => {
    setLoggingOut(true); clearPrivateBrowserState(); await logout();
  }, []);
  async function addMeter(event: FormEvent) {
    event.preventDefault(); if (enrolling || !enrollment) return;
    meterReads.current.invalidate();
    setEnrolling(true); setMeterError(null); setNotice(null);
    try {
      const normalized = normalizePrototypeMeterNumber(number);
      const result = parsePrototypeEnrollment(await consumerClient.post("meter/sandbox-meter-enrollment/", { meter_no: normalized }), normalized);
      setMeters(old => [...old.filter(value => value.id !== result.meter.id), result.meter]);
      select(String(result.meter.id)); setNumber(""); setNotice(result.message); refresh();
    } catch (cause) { setMeterError(cause instanceof Error ? cause.message : "Meter could not be linked."); }
    finally { setEnrolling(false); }
  }
  if (loggingOut) return <div className="consumer-app consumer-initial" role="status">Signing out…</div>;
  const selectedScreen = screen === "apply" ? "loans" : screen;
  const selector = <label className="consumer-meter-select"><Gauge size={19} /><span className="sr-only">Selected meter</span>
    <select aria-label="Selected meter" value={meter ? String(meter.id) : ""} onChange={event => select(event.target.value || null)}>
      <option value="">{meters.length ? "Choose a meter" : "No meter linked"}</option>{meters.map(value => <option key={value.id} value={value.id}>{value.label || "Meter"} · {value.meter_number}</option>)}
    </select></label>;
  const score = assessment.value?.assessment_status === "READY" || environment !== "UGX_DEMO" ? assessment.value?.score : null;
  const headlineValue = summary.loading ? "Loading…" : summary.value ? money(summary.value.outstanding) : "Unavailable";
  return <div className="consumer-app">
    <aside className="consumer-sidebar"><Link className="consumer-brand" href="/dashboard"><span><Leaf size={25} /></span>EnergyFlex<span className="brand-period">.</span></Link>
      <p className="nav-caption">YOUR WORKSPACE</p><nav aria-label="Consumer navigation">{navigation.map(key => { const Icon = icons[key]; return <Link key={key} href={CONSUMER_PATHS[key]} aria-current={selectedScreen === key ? "page" : undefined}><Icon size={20} />{names[key]}{selectedScreen === key && <ChevronRight size={16} />}</Link>; })}</nav>
      <div className="sidebar-bottom"><div className="sidebar-help"><ShieldCheck size={22} /><strong>Your energy, simplified.</strong><p>Manage your meters and electricity credit in one place.</p></div><button className="sidebar-logout" onClick={() => void signOut()}><LogOut size={18} />Sign out</button></div>
    </aside>
    <div className="consumer-body"><header className="consumer-header"><Link href="/dashboard" className="mobile-brand"><Leaf size={22} />EnergyFlex</Link><span className="desktop-breadcrumb">Your account <ChevronRight size={14} /> <strong>{names[screen]}</strong></span><div className="header-actions"><Link href="/dashboard/transactions" aria-label="Activity"><Activity size={20} /></Link><span className="header-divider" /><button className="account-avatar" aria-label="Open account" onClick={() => go("account")}>{account.first_name.charAt(0) || "U"}</button><span className="header-name">{account.first_name}<small>Consumer account</small></span></div></header>
      <main className="consumer-main"><div className="consumer-heading"><div><p className="consumer-eyebrow">{screen === "home" ? "YOUR ENERGY, SIMPLIFIED" : "YOUR WORKSPACE"}</p><h1>{screen === "home" ? `Hello, ${account.first_name || "there"}` : names[screen]}{screen === "home" && <span className="greeting-dot">.</span>}</h1><p>{({ home: "A clear view of your electricity and credit.", meters: "Your meters, all in one place.", loans: "Your electricity credit and repayments.", apply: "Choose an amount, then review your terms.", purchase: "Buy electricity for your selected meter.", activity: "Your purchases, loans and repayments.", account: "Manage your account and preferences." })[screen]}</p></div><button className="consumer-refresh" onClick={refresh}><RefreshCw size={16} />Refresh</button></div>
        <div className="consumer-selection">{selector}{meter && screen !== "meters" && <Link href="/dashboard/my-meters">View meter readings</Link>}</div>
        {latestCapabilities.error && <div className="consumer-alert" role="alert">Capabilities request failed: {latestCapabilities.error} <button onClick={refresh}>Retry</button></div>}
        {assignmentError && <div className="consumer-alert" role="alert">{assignmentError} <button onClick={refresh}>Retry</button></div>}
        {!capabilities.enabled && <div className="consumer-alert" role="status">Consumer payments and credit are unavailable in this environment. No financial values have been assumed.</div>}
        {screen === "home" && <>
          <div className="consumer-overview"><section className="consumer-energy"><div className="energy-heading"><Zap size={20} /><span>Cloud energy</span><span className="allocation-label">ALLOCATION</span></div><div className="energy-amount">{energy.loading ? "Loading…" : energy.value ? formatEnergy(energy.value.available) : "Unavailable"}</div><p>{meter ? `Available for ${meter.label || "your meter"}` : "Select a meter to view its entitlement"}</p><div className="energy-foot"><span>Reserved / unresolved <strong>{energy.value ? formatEnergy(energy.value.pending) : "—"}</strong></span><Link href="/dashboard/my-meters">View details <ArrowUpRight size={17} /></Link></div></section>
            <section className="consumer-card credit-card"><div className="card-heading"><h2>Credit overview</h2><ShieldCheck size={21} /></div><div className="credit-numbers"><div><span>Credit score</span><strong>{assessment.loading ? "…" : score ?? "—"}{score != null && <small>%</small>}</strong></div><div><span>Borrowing limit</span><b>{assessment.loading ? "Loading…" : money(assessment.value?.maximum)}</b><span className={`eligibility-chip ${assessment.value?.eligible ? "eligible" : ""}`}>{assessment.value?.eligible ? "Eligible" : score != null ? "Not eligible" : "Not available"}</span></div></div>
              <p className="consumer-muted">{!meter ? "Choose your meter to view its assessment." : assessment.error || assessment.value?.reason || "Assessment is loading."}</p><small className="evidence-label">Demo assessment · simulated account information</small><Link className="consumer-text-link" href={CONSUMER_PATHS.apply}>View borrowing options <ArrowRight size={16} /></Link></section></div>
          {(energy.error || summary.error) && <div className="consumer-alert" role="alert">{energy.error || summary.error} <button onClick={refresh}>Retry</button></div>}
          <div className="consumer-stats"><section className="consumer-card"><span className="stat-icon"><CreditCard size={20} /></span><p>Outstanding loan balance</p><strong data-testid="outstanding-summary">{headlineValue}</strong><small>All your meters · {currency === "UGX" ? "UGX demo" : "EUR test"}</small></section><section className="consumer-card"><span className="stat-icon"><ArrowDownLeft size={20} /></span><p>Repayments applied</p><strong>{summary.loading ? "Loading…" : money(summary.value?.applied_repayments)}</strong><small>Settled amounts applied to loan debt</small></section><section className="consumer-card"><span className="stat-icon"><ShieldCheck size={20} /></span><p>Active loans</p><strong>{summary.loading ? "…" : summary.value?.active_loan_count ?? "Unavailable"}</strong><small>All your meters · server loan status</small></section></div>
          <div className="section-heading"><h2>What would you like to do?</h2></div><div className="consumer-quick-actions">{([["purchase", Zap, "Buy units", "Keep your electricity topped up"], ["apply", Plus, "Apply for a loan", "Explore your borrowing options"], ["loans", CreditCard, "Repay a loan", "View and manage your balance"]] as const).map(([destination, Icon, title, text]) => <Link key={destination} href={CONSUMER_PATHS[destination]}><span className="quick-icon"><Icon size={21} /></span><span><strong>{title}</strong><small>{text}</small></span><ArrowUpRight size={20} /></Link>)}</div>
          <section className="consumer-card recent-activity"><div className="section-heading"><h2>Recent activity</h2><Link href="/dashboard/transactions">View all <ArrowRight size={15} /></Link></div>{recent.loading ? <p role="status">Loading activity…</p> : recent.error ? <p role="alert">Activity unavailable. <button onClick={refresh}>Retry</button></p> : recent.value?.filter(row => row.environment === environment).slice(0, 4).map(row => <Link href="/dashboard/transactions" className="consumer-activity-row" key={row.reference}><span className="activity-icon">{row.purpose === "PURCHASE" ? <Zap size={19} /> : <ArrowDownLeft size={19} />}</span><span><strong>{row.purpose === "PURCHASE" ? "Electricity purchase" : "Loan repayment"}</strong><small>{new Date(row.initiated_at).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })} · {row.checkout?.business_effect === "ADDITIONAL_AUTHORIZATION_REVIEW" ? "Authorization under review" : paymentStatusMessage(row)}</small></span><b>{formatMoney(row.amount, row.currency)}</b><ChevronRight size={16} /></Link>)}{recent.value && !recent.value.some(row => row.environment === environment) && <p className="consumer-muted">No activity yet. Your settled purchases and repayments will appear here.</p>}</section>
        </>}
        {screen === "meters" && <div className="consumer-meter-grid"><section><div className="section-heading"><h2>Your meters</h2><span>{meters.length} linked</span></div>{meters.map(value => <button key={value.id} className={`consumer-meter-card ${meter?.id === value.id ? "selected" : ""}`} onClick={() => select(String(value.id))}><span className="meter-card-icon"><Gauge size={24} /></span><span><strong>{value.label || "Meter"}</strong><b>{value.meter_number}</b><small>{value.status === "ACTIVE" ? "Active" : "Inactive"} · {value.sandbox_inventory ? "Prototype meter" : "Stored meter"}</small></span>{meter?.id === value.id ? <span className="selected-pill"><Check size={14} />Selected</span> : <ChevronRight size={20} />}</button>)}{!meters.length && <section className="consumer-card"><h2>Add your first meter</h2><p>Link a meter to see its assessment and buy electricity.</p></section>}{meter && <section className="consumer-card meter-balances"><h2>Cloud entitlement</h2><p>{meter.meter_number} · {readEnvironment} energy</p><dl><div><dt>Available</dt><dd>{energy.loading ? "Loading…" : formatEnergy(energy.value?.available)}</dd></div><div><dt>Reserved / unresolved</dt><dd>{formatEnergy(energy.value?.pending)}</dd></div><div><dt>Confirmed applied</dt><dd>{formatEnergy(energy.value?.confirmed)}</dd></div></dl><p className="consumer-muted">Cloud allocation, device credit and measured consumption are separate records.</p>{(energy.value?.physical || measured.value?.device_bound || measured.error || (readEnvironment !== "CORE" && meter.sandbox_inventory)) && <MeasuredConsumptionPanel data={measured.value} loading={measured.loading} error={measured.error} days={usageDays} onDays={setUsageDays} onRefresh={refresh} />}<AllocationLedgers client={consumerClient} owner={account.id} meterId={meter.id} />{capabilities.provider === "MTN_SANDBOX" && <p role="status">{capabilities.labEnabled ? "SANDBOX AC lab redemption is configured. Credit is saved after acknowledgement from the matching commissioned device." : "AC lab redemption is disabled on the server. Your cloud allocation is retained; physical credit and relay output are not implied."}</p>}</section>}</section><form className="consumer-card consumer-form add-meter-card" onSubmit={event => void addMeter(event)}><span className="stat-icon"><Plus size={22} /></span><h2>Add your meter</h2><p>Enter your meter number to get started.</p><label>Meter number<input aria-describedby="meter-number-help" value={number} onChange={event => setNumber(event.target.value)} inputMode="numeric" maxLength={11} pattern="[0-9]{11}" required /></label><small id="meter-number-help">{METER_NUMBER_MESSAGE} Leading zeros are preserved.</small><button type="submit" disabled={enrolling || !enrollment}>{enrolling ? "Linking…" : "Add meter"}<ArrowRight size={17} /></button>{meterError && <p className="consumer-error" role="alert">{meterError}</p>}{notice && <p role="status">{notice}</p>}<p className="consumer-muted">Meter linked for prototype testing. Ownership and live readings are not verified with the electricity provider.</p></form></div>}
        {screen === "loans" && <><div className="consumer-loan-overview"><section className="consumer-card"><p>Total outstanding · all your meters</p><strong>{headlineValue}</strong><small>Repayments applied {summary.loading ? "Loading…" : money(summary.value?.applied_repayments)}</small></section><Link className="consumer-primary-link" href={CONSUMER_PATHS.apply}><Plus size={18} />Apply for Loan</Link></div>{summary.error && <p className="consumer-alert" role="alert">Loan summary unavailable: {summary.error} <button onClick={refresh}>Retry summary</button></p>}</>}
        {screen === "account" && <ConsumerAccount account={account} onLogout={signOut} />}
        <div className="consumer-finance-shell" hidden={!(screen === "loans" || screen === "apply" || screen === "purchase" || screen === "activity")}>
          {capabilities.enabled && <SandboxConsumer client={consumerClient} owner={account.id} meters={meters} selectedMeter={meter} capabilities={capabilities} surface="web" mutationsAvailable={capabilitiesReady && !assignmentError} view={screen === "loans" || screen === "apply" || screen === "purchase" || screen === "activity" ? screen : "hidden"} onSelectMeter={select} onAddMeter={() => go("meters")} onNavigate={destination => go(destination)} onChanged={refresh} refreshVersion={revision} />}
        </div>
        <footer className="consumer-footer"><Leaf size={15} />EnergyFlex <span>Electricity, within reach.</span><span>Cloud records and meter evidence</span></footer>
      </main>
    </div><nav className="consumer-bottom-nav" aria-label="Mobile navigation">{navigation.filter(key => key !== "activity").map(key => { const Icon = icons[key]; return <Link key={key} href={CONSUMER_PATHS[key]} aria-current={selectedScreen === key ? "page" : undefined}><Icon size={21} /><span>{names[key]}</span></Link>; })}</nav>
  </div>;
}
