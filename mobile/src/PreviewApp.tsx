import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Brand, Icon, type IconName } from "./ui.tsx";
import { CONSUMER_TABS, previewParent, previewTab, type PreviewScreen } from "./consumer-navigation.ts";
import { isPositiveWholeUgx, wholeUgxWithinDebt } from "./api/payment-guards.ts";
import { useNativeBack } from "./use-native-back.ts";

// Presentation fixtures only. This component has no session or API client and
// never creates a payment, debt, allocation or device command.
const meters = [
  { id: "SAMPLE-M001", name: "Home meter", location: "Main residence", available: "12.40", reserved: "1.50", applied: "8.20" },
  { id: "SAMPLE-M002", name: "Shop meter", location: "Small business", available: "4.60", reserved: "0.00", applied: "3.10" },
];
const receipts = [
  { id: "SAMPLE-P001", label: "Electricity purchase", amount: "5,000", type: "purchase", status: "Settled", date: "09 Oct · 09:30", icon: "bolt" as const },
  { id: "SAMPLE-P002", label: "Loan repayment", amount: "2,500", type: "repayment", status: "Settled", date: "08 Oct · 14:15", icon: "loan" as const },
  { id: "SAMPLE-P003", label: "Electricity purchase", amount: "3,000", type: "purchase", status: "Pending", date: "07 Oct · 11:20", icon: "bolt" as const },
];
const money = (amount: string) => `UGX ${amount.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}`;

function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`panel ${className}`}>{children}</section>;
}
function Heading({ eyebrow, title, text }: { eyebrow?: string; title: string; text?: string }) {
  return <div className="page-heading">{eyebrow && <span className="eyebrow">{eyebrow}</span>}
    <h1>{title}</h1>{text && <p className="muted">{text}</p>}</div>;
}
function SectionTitle({ title, action, onAction }: { title: string; action?: string; onAction?: () => void }) {
  return <div className="section-title"><h2>{title}</h2>{action && <button className="text-button" onClick={onAction}>{action} <Icon name="arrow" /></button>}</div>;
}
function MenuRow({ icon, title, subtitle, onClick }: { icon: IconName; title: string; subtitle?: string; onClick: () => void }) {
  return <button className="menu-row" onClick={onClick}><span className="row-icon"><Icon name={icon} /></span>
    <span><strong>{title}</strong>{subtitle && <small>{subtitle}</small>}</span><Icon name="arrow" /></button>;
}
function UsageChart() {
  const values = [44, 72, 51, 93, 62, 82, 57];
  return <div className="usage-chart" role="img" aria-label="Sample weekly consumption: Monday 0.8, Tuesday 1.3, Wednesday 0.9, Thursday 1.7, Friday 1.1, Saturday 1.5, Sunday 1.0 kWh">
    <div className="chart-grid"><span>2 kWh</span><span>1 kWh</span><span>0</span></div>
    <div className="chart-bars">{values.map((height, index) => <div className="chart-column" key={index}>
      <div className={`chart-bar${index === 5 ? " highlighted" : ""}`} style={{ height: `${height}%` }} />
      <span>{["M", "T", "W", "T", "F", "S", "S"][index]}</span>
    </div>)}</div>
  </div>;
}

export function PreviewApp({ onExit }: { onExit: () => void }) {
  const [screen, setScreen] = useState<PreviewScreen>("dashboard");
  const [meterIndex, setMeterIndex] = useState(0);
  const [scenario, setScenario] = useState<"sample" | "empty" | "offline">("sample");
  const [amount, setAmount] = useState("");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [read, setRead] = useState(false);
  const [receiptIndex, setReceiptIndex] = useState(0);
  const [profile, setProfile] = useState({ first: "Alex", last: "Example", address: "Sample residence" });
  const dialogRef = useRef<HTMLElement>(null);
  const meter = meters[meterIndex];
  const activeTab = previewTab(screen);
  const detail = !CONSUMER_TABS.some((tab) => tab.id === screen);

  const go = (next: PreviewScreen) => {
    setScreen(next); setError(null); window.scrollTo({ top: 0, behavior: "instant" });
  };
  const back = useCallback(() => {
    if (notice) { setNotice(null); return; }
    const parent = previewParent(screen);
    if (parent) { setScreen(parent); setError(null); } else onExit();
  }, [screen, notice, onExit]);
  useNativeBack(back);
  useEffect(() => {
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") back(); };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [back]);
  useEffect(() => {
    if (!notice) return;
    const previous = document.activeElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialogRef.current?.querySelector("button")?.focus();
    return () => {
      document.body.style.overflow = overflow;
      if (previous instanceof HTMLElement) previous.focus();
    };
  }, [notice]);
  const review = (event: FormEvent) => {
    event.preventDefault(); setError(null);
    if (screen === "load") {
      if (!/^(?:0|[1-9]\d*)(?:\.\d{1,2})?$/.test(amount) || !/[1-9]/.test(amount)) {
        setError("Enter positive energy in 0.01 kWh increments."); return;
      }
      const increments = (value: string) => {
        const [whole, fraction = ""] = value.split(".");
        return BigInt(whole) * 100n + BigInt(fraction.padEnd(2, "0"));
      };
      if (increments(amount) > increments(meter.available)) {
        setError("This example request exceeds the selected meter’s available entitlement."); return;
      }
      go("load-review"); return;
    }
    if (!isPositiveWholeUgx(amount)) { setError("Enter a positive whole-UGX amount."); return; }
    if (screen === "repay" && !wholeUgxWithinDebt(amount, "7500.00")) {
      setError("This example loan has UGX 7,500 outstanding."); return;
    }
    go(screen === "purchase" ? "purchase-review" : screen === "apply" ? "apply-review" : "repay-review");
  };
  const unavailable = () => setNotice("This is a design preview. Connect the approved Django workflow to submit this action. No payment, loan or meter request has been sent.");
  const empty = <Card className="empty-card"><span className="empty-icon"><Icon name={activeTab === "loans" ? "loan" : activeTab === "meters" ? "meter" : "activity"} /></span>
    <h2>Nothing here yet</h2><p className="muted">This is the empty-state design. Your records will appear here when account data is available.</p>
    <button className="secondary" onClick={() => setScenario("sample")}>View sample records</button></Card>;

  return <div className="app-shell preview-shell">
    <div className="preview-banner"><span><span className="preview-dot" />Design preview · sample data</span><button onClick={onExit}>Exit preview</button></div>
    <header className="topbar"><Brand /><div className="header-actions">
      <button className="icon-button notification-button" aria-label="Preview notifications" onClick={() => go("notifications")}><Icon name="bell" />{!read && <span />}</button>
      <button className="avatar-button" aria-label="Preview account" onClick={() => go("account")}>{profile.first.charAt(0)}{profile.last.charAt(0)}</button>
    </div></header>
    <main className="content">
      {detail && <button className="text-button back-link" onClick={back}><Icon name="back" />Back</button>}
      {scenario === "offline" && <div className="offline-preview" role="status"><Icon name="phone" /><span>Offline example. Displayed sample values are stale. Requests are not queued.</span><button onClick={() => setScenario("sample")}>Retry</button></div>}
      {screen === "dashboard" && <>
        <Heading eyebrow="YOUR ENERGY AT A GLANCE" title={`Hello, ${profile.first}.`} text="A little clarity for your everyday power." />
        {scenario === "empty" ? empty : <>
          <section className="balance-card"><div className="balance-top"><span><Icon name="bolt" />Available electricity</span><span className="balance-tag">SAMPLE</span></div>
            <div className="balance-amount">{meter.available}<span>kWh</span></div><p>Entitlement available to request for your meter</p>
            <div className="balance-divider" /><div className="balance-split"><div><span>Reserved / unresolved</span><strong>{meter.reserved} kWh</strong></div>
              <div><span>Confirmed applied</span><strong>{meter.applied} kWh</strong></div></div>
          </section>
          <button className="selected-meter" onClick={() => go("meters")}><span className="row-icon"><Icon name="meter" /></span>
            <span><strong>{meter.name}</strong><small>{meter.id} · sample simulator</small></span><span className="text-accent">Change</span></button>
        </>}
        <div className="quick-actions">
          <button onClick={() => { setAmount(""); go("purchase"); }}><span className="quick-icon blue"><Icon name="plus" /></span><strong>Buy electricity</strong></button>
          <button onClick={() => go("loans")}><span className="quick-icon green"><Icon name="loan" /></span><strong>Electricity credit</strong></button>
          <button onClick={() => { setAmount(""); go("load"); }}><span className="quick-icon amber"><Icon name="meter" /></span><strong>Load meter</strong></button>
        </div>
        <Card><SectionTitle title="This week’s usage" action="Details" onAction={() => go("consumption")} />
          <div className="chart-summary"><strong>{scenario === "empty" ? "Unavailable" : "8.30"}<small> kWh</small></strong><span className="status-pill">Sample week</span></div>
          {scenario === "empty" ? <p className="muted">No consumption records available.</p> : <UsageChart />}
        </Card>
        <Card className="credit-promo"><span className="promo-symbol"><Icon name="loan" /></span><div><h2>Power when you need it</h2><p>Explore eligibility and see your electricity-credit options.</p>
          <button className="text-button" onClick={() => go("loans")}>Explore electricity credit <Icon name="arrow" /></button></div></Card>
        <Card><SectionTitle title="Recent activity" action="View all" onAction={() => go("activity")} />
          {scenario === "empty" ? <p className="muted">No activity yet.</p> : receipts.slice(0, 2).map((row, index) => <button className="transaction-row" key={row.id} onClick={() => { setReceiptIndex(index); go("receipt"); }}>
            <span className="row-icon"><Icon name={row.icon} /></span><span><strong>{row.label}</strong><small>{row.date} · Sample</small></span><b>UGX {row.amount}</b>
          </button>)}
        </Card>
      </>}

      {screen === "meters" && <>
        <Heading eyebrow="CONNECTED TO YOUR EVERYDAY" title="Your meters" text="Choose which meter you want to view or load." />
        {scenario === "empty" ? empty : meters.map((row, index) => <button className={`meter-choice${meterIndex === index ? " chosen" : ""}`} key={row.id} onClick={() => setMeterIndex(index)}>
          <span className="meter-card-heading"><span className="row-icon"><Icon name="meter" /></span><span><strong>{row.name}</strong><small>{row.location}</small></span>
            {meterIndex === index ? <span className="selected-tick"><Icon name="check" /></span> : <span className="choice-circle" />}</span>
          <span className="meter-id">{row.id}<span className="status-pill">Sample simulator</span></span>
          <span className="meter-card-bottom"><span>Available <b>{row.available} kWh</b></span><span>Last contact <b>Sample · 10:42</b></span></span>
        </button>)}
        <Card><SectionTitle title="Selected meter delivery" /><div className="metrics two"><div><span>Reserved / unresolved</span><strong>{scenario === "empty" ? "Unavailable" : `${meter.reserved} kWh`}</strong></div>
          <div><span>Confirmed applied</span><strong>{scenario === "empty" ? "Unavailable" : `${meter.applied} kWh`}</strong></div></div>
          <p className="muted small">A queued request is separate from an application acknowledgement.</p>
          <button className="primary-button" onClick={() => { setAmount(""); go("load"); }}>Preview meter loading <Icon name="arrow" /></button></Card>
        <p className="form-hint"><Icon name="shield" />Meter assignment and replacement are managed by authorized staff.</p>
      </>}

      {screen === "consumption" && <>
        <Heading eyebrow="SMALL INSIGHTS, BETTER CONTROL" title="Your energy usage" text={`${meter.name} · ${meter.id}`} />
        {scenario === "empty" ? empty : <>
          <Card><SectionTitle title="Weekly overview" /><div className="chart-summary"><strong>8.30<small> kWh</small></strong><span className="status-pill">Sample week</span></div><UsageChart /></Card>
          <div className="metrics two"><div><span>Example daily average</span><strong>1.19 kWh</strong></div><div><span>Example highest day</span><strong>1.70 kWh</strong></div></div>
          <Card><SectionTitle title="Daily consumption" />{["1.00", "1.50", "1.10", "1.70", "0.90", "1.30", "0.80"].map((value, index) =>
            <div className="list-row" key={index}><span>Sample day {7 - index}<small>Illustrative stored reading</small></span><strong>{value} kWh</strong></div>)}</Card>
          <Card><SectionTitle title="Meter contact" /><div className="contact-row"><span className="contact-dot" /><span>Sample contact · 09 Oct, 10:42</span></div>
            <p className="muted small">Simulator examples demonstrate the interface. Physical accuracy and connectivity have not been verified.</p></Card>
        </>}
      </>}

      {screen === "loans" && <>
        <Heading eyebrow="ELECTRICITY CREDIT" title="A little more power." text="Understand your loan position and explore your options." />
        <Card className="eligibility-card"><div className="section-title"><span className="quick-icon green"><Icon name="shield" /></span><span className="status-pill neutral">Backend required</span></div>
          <h2>Your eligibility, explained</h2><p className="muted">Complete your profile to receive an assessment. Your score and approved terms will come from your account.</p>
          <div className="score-placeholder"><span>Credit score</span><strong>Unavailable</strong></div>
          <button className="secondary" onClick={() => go("profile")}>Complete assessment profile <Icon name="arrow" /></button></Card>
        <button className="primary-button" onClick={() => { setAmount(""); go("apply"); }}>Preview a credit request <Icon name="plus" /></button>
        <SectionTitle title="Your loans" />{scenario === "empty" ? empty : <Card className="loan-card"><div className="section-title"><h2>Sample electricity loan</h2><span className="status-pill">Disbursed · sample</span></div>
          <p className="muted small">SAMPLE-L001 · Home meter</p><span className="muted small">Outstanding amount</span><div className="loan-amount">UGX 7,500</div>
          <div className="repayment-progress"><span /></div><div className="progress-labels"><span>Sample principal: UGX 10,000</span><span>Applied: UGX 2,500</span></div>
          <p className="muted small">Due date and charges need verified backend terms.</p><button className="secondary" onClick={() => go("loan-detail")}>View loan <Icon name="arrow" /></button></Card>}
        <Card className="subtle-card"><Icon name="help" /><h2>Clear before you commit</h2><p className="muted">Review your approved amount, tariff, charges and repayment schedule before submitting a real request.</p></Card>
      </>}

      {screen === "loan-detail" && <>
        <Heading eyebrow="SAMPLE-L001" title="Electricity loan" text="Sample record · no real obligation" />
        <section className="balance-card loan-balance"><span className="balance-tag">SAMPLE OUTSTANDING</span><div className="balance-amount">7,500<span>UGX</span></div>
          <div className="balance-split"><div><span>Example principal</span><strong>UGX 10,000</strong></div><div><span>Applied repayment</span><strong>UGX 2,500</strong></div></div></section>
        <button className="primary-button" onClick={() => { setAmount(""); go("repay"); }}>Preview self-repayment <Icon name="arrow" /></button>
        <Card><SectionTitle title="Loan details" />{[["Intended meter", meters[0].id], ["Interest and fees", "Awaiting backend terms"], ["Due date", "Awaiting backend terms"], ["Tariff", "Awaiting backend terms"]].map(([label, value]) =>
          <div className="review-row" key={label}><span>{label}</span><strong>{value}</strong></div>)}</Card>
        <Card><SectionTitle title="Energy allocation" /><p className="muted">Loan approval, authorized energy and meter application have separate statuses.</p>
          <div className="review-row"><span>Delivery status</span><strong>Awaiting real account data</strong></div></Card>
        <Card><SectionTitle title="Repayment history" /><div className="list-row"><span>Sample self-repayment<small>08 Oct · Settled example</small></span><strong>UGX 2,500</strong></div></Card>
      </>}

      {["purchase", "load", "apply", "repay"].includes(screen) && <>
        <Heading eyebrow="REVIEW BEFORE YOU CONTINUE" title={screen === "purchase" ? "Buy electricity" : screen === "load" ? "Load your meter" : screen === "apply" ? "Request electricity credit" : "Repay your loan"}
          text={screen === "repay" ? "Sample loan SAMPLE-L001 · outstanding UGX 7,500" : "Choose your meter and review the request details."} />
        <form className="panel form-panel transaction-form" onSubmit={review}>
          <label>{screen === "repay" ? "Loan meter" : "Your meter"}<select value={screen === "repay" ? 0 : meterIndex} disabled={screen === "repay"} onChange={(event) => setMeterIndex(Number(event.target.value))}>
            {meters.map((row, index) => <option key={row.id} value={index}>{row.name} · {row.id}</option>)}</select></label>
          {screen === "load" && <div className="form-context"><Icon name="bolt" /><span>Example available entitlement<strong>{meter.available} kWh</strong></span></div>}
          <label>{screen === "load" ? "Energy amount (kWh)" : "Amount (whole UGX)"}<div className="amount-field"><span>{screen === "load" ? "kWh" : "UGX"}</span>
            <input inputMode={screen === "load" ? "decimal" : "numeric"} placeholder={screen === "load" ? "0.00" : "0"} value={amount} maxLength={12} onChange={(event) => setAmount(event.target.value)} required /></div></label>
          {screen === "purchase" && <div className="amount-chips">{["5000", "10000", "20000"].map((value) => <button type="button" className={amount === value ? "active" : ""} key={value} onClick={() => setAmount(value)}>{money(value)}</button>)}</div>}
          {(screen === "purchase" || screen === "repay") && <label>Mobile Money phone<input type="tel" placeholder="+256 …" value={phone} onChange={(event) => setPhone(event.target.value)} required /></label>}
          {screen === "apply" && <div className="form-context"><Icon name="loan" /><span>Interest, fees and repayment term<strong>Awaiting backend quote</strong></span></div>}
          <p className="muted small">{screen === "load" ? "Requests use 0.01 kWh steps. Application requires a matching meter acknowledgement." : screen === "apply" ? "This previews the request form. It does not calculate or approve credit terms." : "No collection is started in preview. Only verified provider settlement can update your real account."}</p>
          {error && <p className="error" role="alert">{error}</p>}<button className="primary-button" type="submit">Review {screen === "load" ? "load" : screen === "repay" ? "repayment" : "request"}<Icon name="arrow" /></button>
        </form>
      </>}

      {["purchase-review", "load-review", "apply-review", "repay-review"].includes(screen) && <>
        <Heading eyebrow="ONE LAST LOOK" title="Review your request" text="Check the selection, amount and purpose." />
        <Card className="review-card"><span className="review-symbol"><Icon name={screen === "load-review" ? "meter" : screen === "apply-review" ? "loan" : "bolt"} /></span>
          <span className="muted small">{screen === "load-review" ? "Energy to reserve" : "Requested amount"}</span><h2 className="review-amount">{screen === "load-review" ? `${amount} kWh` : money(amount)}</h2>
          {[["Purpose", screen === "purchase-review" ? "Electricity purchase" : screen === "load-review" ? "Own-meter loading" : screen === "apply-review" ? "Electricity loan" : "Self-repayment"], ["Meter", screen === "repay-review" ? `${meters[0].name} · ${meters[0].id}` : `${meter.name} · ${meter.id}`],
            ...(screen === "repay-review" ? [["Loan", "SAMPLE-L001"]] : []),
            ...(screen === "purchase-review" || screen === "repay-review" ? [["Mobile Money phone", phone]] : []),
            ...(screen === "purchase-review" ? [["Electricity and residual", "Awaiting tariff quote"]] : []),
            ...(screen === "apply-review" ? [["Rate, charges and term", "Awaiting approved quote"]] : []),
          ].map(([label, value]) => <div className="review-row" key={label}><span>{label}</span><strong>{value}</strong></div>)}
          <div className="integration-notice"><Icon name="shield" /><p>Preview only. Submission will become available after the backend workflow and financial policy are approved.</p></div>
          <button className="primary-button" onClick={unavailable}>About this preview <Icon name="arrow" /></button><button className="text-button" onClick={back}>Edit request</button>
        </Card>
      </>}

      {screen === "activity" && <>
        <Heading eyebrow="EVERYTHING IN ONE PLACE" title="Your activity" text="Payments, receipts and account updates." />
        <button className="alert-shortcut" onClick={() => go("notifications")}><span className="row-icon"><Icon name="bell" /></span><span><strong>Notifications</strong><small>{read ? "All sample alerts read" : "2 sample updates"}</small></span><Icon name="arrow" /></button>
        {scenario === "empty" ? empty : <Card><SectionTitle title="Payment receipts" />{receipts.map((row, index) => <button className="transaction-row" key={row.id} onClick={() => { setReceiptIndex(index); go("receipt"); }}>
          <span className="row-icon"><Icon name={row.icon} /></span><span><strong>{row.label}</strong><small>{row.date}</small><span className={`status-pill${row.status === "Pending" ? " pending" : ""}`}>{row.status} · sample</span></span><b>UGX {row.amount}</b>
        </button>)}</Card>}
        <p className="form-hint"><Icon name="shield" />A pending payment or phone approval is separate from verified settlement.</p>
      </>}
      {screen === "receipt" && <>
        <Heading title="Payment receipt" text="Sample receipt · not proof of a real payment" />
        <Card className="review-card"><span className={`review-symbol${receipts[receiptIndex].status === "Pending" ? " amber" : ""}`}><Icon name={receipts[receiptIndex].status === "Pending" ? "activity" : "check"} /></span>
          <span className="status-pill">{receipts[receiptIndex].status} · sample</span><h2 className="review-amount">UGX {receipts[receiptIndex].amount}</h2>
          {[["Purpose", receipts[receiptIndex].label], ["Reference", receipts[receiptIndex].id], ["Currency", "UGX"], ["Meter", meters[0].id], ["Energy / residual", "Awaiting backend receipt"]].map(([label, value]) =>
            <div className="review-row" key={label}><span>{label}</span><strong>{value}</strong></div>)}
          <p className="muted small">Real receipts will show the full amount received, the amount applied and any residual requiring reconciliation.</p></Card>
      </>}
      {screen === "notifications" && <>
        <Heading title="Notifications" text="Helpful updates about your electricity account." />
        <button className="text-button" disabled={read} onClick={() => setRead(true)}>{read ? "Sample alerts marked read" : "Mark sample alerts as read"}</button>
        <Card>{["Your sample payment receipt is ready to view.", "Your sample meter delivery is awaiting an application acknowledgement."].map((message, index) =>
          <div className="notification-row" key={message}><span className="row-icon"><Icon name={index === 0 ? "activity" : "meter"} /></span><div><strong>{message}</strong><p className="muted small">Sample update · {read ? "Read" : "Unread"}</p></div>{!read && <span className="unread-dot" />}</div>)}</Card>
      </>}

      {screen === "account" && <>
        <Heading eyebrow="MADE FOR YOUR EVERYDAY" title="Your account" />
        <Card className="profile-card"><span className="profile-avatar">{profile.first.charAt(0)}{profile.last.charAt(0)}</span><h2>{profile.first} {profile.last}</h2><p className="muted">alex@example.invalid</p><span className="status-pill neutral">Sample consumer profile</span></Card>
        <Card className="menu-card"><MenuRow icon="user" title="Personal details" subtitle="Your profile and assessment" onClick={() => go("profile")} />
          <MenuRow icon="lock" title="Account security" subtitle="Password and sign-in" onClick={() => go("security")} />
          <MenuRow icon="meter" title="Your meters" subtitle="View assigned meters" onClick={() => go("meters")} />
          <MenuRow icon="help" title="Help and information" subtitle="How electricity credit works" onClick={() => go("help")} /></Card>
        <button className="logout-button" onClick={onExit}><Icon name="logout" />Leave design preview</button>
        <p className="centered muted small">gPawa consumer app · interface preview</p>
      </>}
      {screen === "profile" && <>
        <Heading title="Personal details" text="Edit this sample profile to explore the form." />
        <form className="panel form-panel" onSubmit={(event) => { event.preventDefault(); setNotice("Sample profile updated in this preview only. Your real account has not changed."); }}>
          <div className="field-pair"><label>First name<input value={profile.first} onChange={(event) => setProfile({ ...profile, first: event.target.value })} required /></label>
            <label>Last name<input value={profile.last} onChange={(event) => setProfile({ ...profile, last: event.target.value })} required /></label></div>
          <label>Email<input value="alex@example.invalid" readOnly /></label><label>Address<input value={profile.address} onChange={(event) => setProfile({ ...profile, address: event.target.value })} /></label>
          <button className="primary-button" type="submit">Save sample details <Icon name="check" /></button></form>
        <Card><SectionTitle title="Credit assessment" /><p className="muted">Income, expenditure and energy-use questions will use the backend’s permitted choices. No score is created from this design preview.</p></Card>
      </>}
      {screen === "security" && <>
        <Heading title="Account security" text="Keep access to your account under your control." />
        <Card className="menu-card"><MenuRow icon="lock" title="Change password" subtitle="Available in your signed-in account" onClick={() => setNotice("Leave preview and sign in to change your real password. This preview does not store passwords.")} />
          <MenuRow icon="shield" title="Email verification" subtitle="Verify before account access" onClick={() => setNotice("Use the verification page from Sign in to verify a real email link.")} /></Card>
        <Card className="subtle-card"><Icon name="shield" /><h2>Credentials stay protected</h2><p className="muted">The Android app uses secure storage for refresh credentials. Preview never signs you in or reads your account.</p></Card>
      </>}
      {screen === "help" && <>
        <Heading title="Here to help" text="A few things to know about your electricity account." />
        {[ ["What do the energy balances mean?", "Available energy is entitlement you can request for delivery. Reserved energy is committed to a delivery request. Applied energy has an application acknowledgement."],
          ["When is a payment complete?", "Django must verify a successful provider payment before purchased energy or loan debt can change. Check Activity if a payment is pending."],
          ["Where do credit terms come from?", "Your account assessment and approved backend quote provide the amount, charges, tariff and repayment term. This preview offers no real credit terms."],
          ["Can I share or transfer energy?", "Energy sharing and consumer meter-to-meter transfers are disabled. The app supports viewing and loading your own assigned meter."],
          ["Where is the privacy information?", "Final consumer privacy information and support contact details must be supplied before release. This preview collects no account information."],
        ].map(([title, text]) => <details className="help-item" key={title}><summary>{title}</summary><p>{text}</p></details>)}
      </>}
      <details className="preview-controls"><summary>Preview display states</summary><div>{(["sample", "empty", "offline"] as const).map((value) =>
        <button key={value} className={scenario === value ? "active" : ""} aria-pressed={scenario === value} onClick={() => setScenario(value)}>{value === "sample" ? "Sample records" : value === "empty" ? "Empty account" : "Offline / stale"}</button>)}</div></details>
    </main>
    <nav className="bottom-nav" aria-label="Preview navigation">{CONSUMER_TABS.map((tab) => <button key={tab.id} aria-current={activeTab === tab.id ? "page" : undefined} onClick={() => go(tab.id)}>
      <Icon name={tab.icon} /><span>{tab.label}</span></button>)}</nav>
    {notice && <div className="dialog-backdrop"><section ref={dialogRef} className="preview-dialog" role="dialog" aria-modal="true" aria-labelledby="preview-dialog-title" onKeyDown={(event) => {
      if (event.key === "Tab") event.preventDefault();
    }}><span className="review-symbol"><Icon name="shield" /></span><h2 id="preview-dialog-title">Design preview</h2><p>{notice}</p>
      <button className="primary-button" onClick={() => setNotice(null)}>Got it <Icon name="check" /></button></section></div>}
  </div>;
}
