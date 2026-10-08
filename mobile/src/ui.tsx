import type { ReactNode } from "react";

export type IconName = "bolt" | "home" | "meter" | "chart" | "loan" | "user" | "activity" |
  "arrow" | "back" | "check" | "shield" | "mail" | "lock" | "eye" | "eye-off" |
  "plus" | "bell" | "help" | "logout" | "refresh" | "phone" | "settings";

const paths: Record<IconName, ReactNode> = {
  bolt: <path d="m13 2-9 12h7l-1 8 10-13h-7l1-7Z" />,
  home: <><path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1Z" /><path d="M9 21v-8h6v8" /></>,
  meter: <><rect x="5" y="2" width="14" height="20" rx="3" /><path d="M8 6h8v6H8zM9 16h.01M15 16h.01M12 19h.01" /></>,
  chart: <><path d="M4 3v17h17M8 15v-4M13 15V6M18 15v-7" /></>,
  loan: <><rect x="3" y="5" width="18" height="14" rx="3" /><path d="M3 10h18M7 15h3M17 15h.01" /></>,
  user: <><circle cx="12" cy="7" r="4" /><path d="M4 21v-2a8 8 0 0 1 16 0v2" /></>,
  activity: <><path d="M6 3h12v18l-3-2-3 2-3-2-3 2ZM9 7h6M9 11h6M9 15h3" /></>,
  arrow: <path d="M4 12h16m-6-6 6 6-6 6" />,
  back: <path d="M20 12H4m6-6-6 6 6 6" />,
  check: <path d="m5 12 4 4L19 6" />,
  shield: <><path d="m12 2 8 4v6c0 5-8 10-8 10S4 17 4 12V6Z" /><path d="m8 12 3 3 5-6" /></>,
  mail: <><rect x="3" y="5" width="18" height="14" rx="3" /><path d="m4 7 8 6 8-6" /></>,
  lock: <><rect x="5" y="10" width="14" height="11" rx="3" /><path d="M8 10V6a4 4 0 0 1 8 0v4M12 14v3" /></>,
  eye: <><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" /></>,
  "eye-off": <><path d="m3 3 18 18M10 5h2c6 0 10 7 10 7s-1 2-3 4M6 6c-3 2-4 6-4 6s4 7 10 7c2 0 4-1 5-2M10 10l4 4" /></>,
  plus: <path d="M12 5v14M5 12h14" />,
  bell: <><path d="M5 17h14l-2-4V8a5 5 0 0 0-10 0v5ZM10 21h4" /></>,
  help: <><circle cx="12" cy="12" r="9" /><path d="M9 9a3 3 0 0 1 6 0c0 2-3 2-3 5M12 17h.01" /></>,
  logout: <><path d="M9 3H4v18h5M9 12h12m-4-4 4 4-4 4" /></>,
  refresh: <><path d="M20 7v5h-5M4 17v-5h5M5 7a8 8 0 0 1 14-1l1 1M4 17l1 1a8 8 0 0 0 14-1" /></>,
  phone: <><rect x="6" y="2" width="12" height="20" rx="3" /><path d="M10 5h4M12 18h.01" /></>,
  settings: <><circle cx="12" cy="12" r="3" /><path d="m10 2-1 3-3 1-3-1-2 4 2 2v3l-2 2 2 4 3-1 3 1 1 3h4l1-3 3-1 3 1 2-4-2-2v-3l2-2-2-4-3 1-3-1-1-3Z" /></>,
};

export function Icon({ name, className = "" }: { name: IconName; className?: string }) {
  return <svg className={`icon ${className}`} viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"
    aria-hidden="true">{paths[name]}</svg>;
}

export function Brand({ light = false }: { light?: boolean }) {
  return <div className={`brand-lockup${light ? " brand-light" : ""}`}>
    <img src="./gpawa-mark.png" width="34" height="34" alt="" />
    <span>gPawa<span className="brand-dot">.</span></span>
  </div>;
}

export function EnergyArtwork() {
  return <div className="energy-art" aria-hidden="true">
    <div className="art-orbit orbit-one" /><div className="art-orbit orbit-two" />
    <div className="art-spark spark-one"><Icon name="bolt" /></div>
    <div className="art-spark spark-two"><Icon name="home" /></div>
    <div className="art-meter">
      <div className="art-meter-top"><span>gPawa</span><span className="art-led" /></div>
      <div className="art-display"><Icon name="bolt" /><span>Power for<br /><strong>your everyday.</strong></span></div>
      <div className="art-wave"><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /></div>
      <div className="art-meter-bottom"><span>SMART ENERGY</span><span>kWh</span></div>
    </div>
    <div className="art-label"><Icon name="shield" /><span>Your energy. In your hands.</span></div>
  </div>;
}
