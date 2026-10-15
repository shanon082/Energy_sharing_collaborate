import type { IconName } from "./ui.tsx";

export const CONSUMER_TABS = [
  { id: "dashboard", label: "Home", icon: "home" },
  { id: "meters", label: "Meters", icon: "meter" },
  { id: "loans", label: "Loans", icon: "loan" },
  { id: "purchase", label: "Buy Units", icon: "bolt" },
  { id: "account", label: "Account", icon: "user" },
] as const satisfies ReadonlyArray<{ id: string; label: string; icon: IconName }>;
export type ConsumerTab = typeof CONSUMER_TABS[number]["id"];
export type PreviewScreen = ConsumerTab | "consumption" | "activity" | "purchase-review" | "load" |
  "load-review" | "apply" | "apply-review" | "apply-confirm" | "loan-detail" | "repay" |
  "repay-review" | "profile" | "security" | "help" | "notifications" | "receipt";
export function activeConsumerTab(screen: string): ConsumerTab {
  if (screen.startsWith("purchase")) return "purchase";
  if (["meters", "consumption", "load", "load-review"].includes(screen)) return "meters";
  if (["loans", "apply", "apply-review", "apply-confirm", "loan-detail", "repay", "repay-review"].includes(screen)) return "loans";
  if (["account", "profile", "security", "help"].includes(screen)) return "account";
  return "dashboard";
}
export function previewParent(screen: PreviewScreen): PreviewScreen | null {
  const parents: Partial<Record<PreviewScreen, PreviewScreen>> = {
    "purchase-review": "purchase", load: "meters", "load-review": "load", consumption: "meters",
    apply: "loans", "apply-review": "apply", "apply-confirm": "apply-review", "loan-detail": "loans", repay: "loan-detail",
    "repay-review": "repay", profile: "account", security: "account", help: "account",
    notifications: "activity", receipt: "activity",
  };
  return parents[screen] ?? (screen === "dashboard" ? null : "dashboard");
}
export const previewTab = (screen: PreviewScreen): ConsumerTab => activeConsumerTab(screen);
