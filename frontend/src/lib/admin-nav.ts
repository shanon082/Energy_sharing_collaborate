import type { LucideIcon } from "lucide-react";
import {
  Activity,
  ClipboardList,
  FileBarChart,
  FileText,
  Gauge,
  Home,
  Layers,
  Settings,
  Shield,
  Users,
  Zap,
} from "lucide-react";
import { IconMoneybag } from "@tabler/icons-react";

export type AdminNavItem = {
  href: string;
  label: string;
  icon: LucideIcon | typeof IconMoneybag;
  minRole: "CUSTOMER_SERVICE" | "OPERATOR" | "ADMIN";
};

/** Admin sidebar navigation (aligned with reference admin-panel routes). */
export const ADMIN_NAV: AdminNavItem[] = [
  { href: "/admin/dashboard", label: "Dashboard", icon: Home, minRole: "CUSTOMER_SERVICE" },
  { href: "/admin/users", label: "Users", icon: Users, minRole: "CUSTOMER_SERVICE" },
  { href: "/admin/meters", label: "Meters", icon: Zap, minRole: "CUSTOMER_SERVICE" },
  { href: "/admin/transactions", label: "Transactions", icon: FileText, minRole: "CUSTOMER_SERVICE" },
  { href: "/admin/loans", label: "Credit & Loans", icon: IconMoneybag, minRole: "OPERATOR" },
  { href: "/admin/reports", label: "Reports", icon: FileBarChart, minRole: "OPERATOR" },
  { href: "/admin/analytics", label: "Financial Stats", icon: Activity, minRole: "OPERATOR" },
  { href: "/admin/system-health", label: "System Health", icon: Gauge, minRole: "OPERATOR" },
  { href: "/admin/audit-log", label: "Audit Log", icon: ClipboardList, minRole: "ADMIN" },
  { href: "/admin/staff", label: "Staff Accounts", icon: Shield, minRole: "ADMIN" },
  { href: "/admin/loan-tiers", label: "Loan Tiers", icon: Layers, minRole: "ADMIN" },
  { href: "/admin/tariffs", label: "Tariffs", icon: Layers, minRole: "ADMIN" },
  { href: "/admin/myaccount", label: "Settings", icon: Settings, minRole: "CUSTOMER_SERVICE" },
];

const ROLE_LEVEL: Record<string, number> = {
  CUSTOMER_SERVICE: 1,
  OPERATOR: 2,
  ADMIN: 3,
};

export function navItemsForRole(
  userRole?: string | null,
  options?: { isSuperuser?: boolean }
): AdminNavItem[] {
  const level = options?.isSuperuser ? 3 : ROLE_LEVEL[userRole ?? ""] ?? 0;
  return ADMIN_NAV.filter((item) => level >= ROLE_LEVEL[item.minRole]);
}
