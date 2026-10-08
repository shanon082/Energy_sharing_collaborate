import type { IconName } from "./ui.tsx";

export const CONSUMER_TABS = [
  { id: "dashboard", label: "Home", icon: "home" },
  { id: "meters", label: "Meters", icon: "meter" },
  { id: "consumption", label: "Usage", icon: "chart" },
  { id: "loans", label: "Credit", icon: "loan" },
  { id: "activity", label: "Activity", icon: "activity" },
  { id: "account", label: "Account", icon: "user" },
] as const satisfies ReadonlyArray<{ id: string; label: string; icon: IconName }>;
export type ConsumerTab = typeof CONSUMER_TABS[number]["id"];
export type PreviewScreen = ConsumerTab | "purchase" | "purchase-review" | "load" |
  "load-review" | "apply" | "apply-review" | "loan-detail" | "repay" |
  "repay-review" | "profile" | "security" | "help" | "notifications" | "receipt";

export function previewParent(screen: PreviewScreen): PreviewScreen | null {
  const parents: Partial<Record<PreviewScreen, PreviewScreen>> = {
    purchase: "dashboard", "purchase-review": "purchase", load: "meters", "load-review": "load",
    apply: "loans", "apply-review": "apply", "loan-detail": "loans", repay: "loan-detail",
    "repay-review": "repay", profile: "account", security: "account", help: "account",
    notifications: "activity", receipt: "activity",
  };
  return parents[screen] ?? (screen === "dashboard" ? null : "dashboard");
}

export function previewTab(screen: PreviewScreen): ConsumerTab {
  if (screen.startsWith("purchase")) return "dashboard";
  if (screen.startsWith("load")) return "meters";
  if (["apply", "apply-review", "loan-detail", "repay", "repay-review"].includes(screen)) return "loans";
  if (["profile", "security", "help"].includes(screen)) return "account";
  if (["notifications", "receipt"].includes(screen)) return "activity";
  return screen as ConsumerTab;
}
