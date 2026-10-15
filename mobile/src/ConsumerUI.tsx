import { Icon, type IconName } from "./ui.tsx";
import { energy } from "./format.ts";

export function PageHeading({ title, text, eyebrow }: { title: string; text?: string; eyebrow?: string }) {
  return <div className="page-heading">{eyebrow && <span className="eyebrow">{eyebrow}</span>}<h1>{title}</h1>{text && <p className="muted">{text}</p>}</div>;
}
export function DemoNotice({ local = true }: { local?: boolean }) {
  return <details className="demo-notice"><summary><span className="demo-dot" />Demo mode <Icon name="help" /></summary><div>
    <strong>No real money is deducted.</strong><p>{local ? "Payments and credit assessments use simulated information." : "Payments use the MTN sandbox."} Cloud units do not confirm physical meter delivery.</p>
  </div></details>;
}
export function EmptyState({ icon, title, text, action, onAction }: { icon: IconName; title: string; text: string; action?: string; onAction?: () => void }) {
  return <section className="panel empty-card"><span className="empty-icon"><Icon name={icon} /></span><h2>{title}</h2><p className="muted">{text}</p>{action && <button className="primary-button" onClick={onAction}>{action}<Icon name="arrow" /></button>}</section>;
}
export function MeterSummary({ meter, onChange }: { meter: { label: string; meter_number: string } | null; onChange: () => void }) {
  return <button className="selected-meter" onClick={onChange}><span className="row-icon"><Icon name="meter" /></span><span><small>Selected meter</small><strong>{meter?.label || "Choose your meter"}</strong>{meter && <small className="meter-number">{meter.meter_number}</small>}</span><span className="text-accent">{meter ? "Change" : "Select"}</span><Icon name="arrow" /></button>;
}
export function CloudEnergyCard({ value, pending, loading, onDetails }: { value?: string | null; pending?: string | null; loading?: boolean; onDetails: () => void }) {
  return <section className="energy-hero"><div className="energy-hero-heading"><span><Icon name="bolt" />Cloud energy</span><span className="hero-pill">Allocation</span></div><div className="energy-hero-value">{value == null ? (loading ? "Loading…" : "Unavailable") : energy(value)}</div><p>Available for your selected meter</p><div className="energy-hero-footer"><span>Reserved <strong>{energy(pending)}</strong></span><button onClick={onDetails}>Details <Icon name="arrow" /></button></div></section>;
}
export function MenuRow({ icon, title, text, onClick, expanded }: { icon: IconName; title: string; text: string; onClick: () => void; expanded?: boolean }) {
  return <button className="menu-row" onClick={onClick} aria-expanded={expanded}><span className="row-icon"><Icon name={icon} /></span><span><strong>{title}</strong><small>{text}</small></span><Icon name="arrow" /></button>;
}
