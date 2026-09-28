"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { navItemsForRole, type AdminNavItem } from "@/lib/admin-nav";

interface AdminNavLinksProps {
  userRole?: string | null;
  isSuperuser?: boolean;
  className?: string;
  onNavigate?: () => void;
}

function NavLinkItem({
  item,
  pathname,
  onNavigate,
}: {
  item: AdminNavItem;
  pathname: string;
  onNavigate?: () => void;
}) {
  const Icon = item.icon;
  const active =
    item.href === "/admin/dashboard"
      ? pathname === "/admin/dashboard"
      : pathname.startsWith(item.href);

  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      className={cn("gpawa-sidebar-link", active && "active")}
    >
      <Icon className="h-4 w-4 shrink-0" />
      <span className="truncate">{item.label}</span>
    </Link>
  );
}

export default function AdminNavLinks({
  userRole,
  isSuperuser,
  className,
  onNavigate,
}: AdminNavLinksProps) {
  const pathname = usePathname();
  const items = navItemsForRole(userRole, { isSuperuser });

  return (
    <nav className={cn("grid items-start gap-0.5", className)}>
      {items.map((item) => (
        <NavLinkItem
          key={item.href}
          item={item}
          pathname={pathname}
          onNavigate={onNavigate}
        />
      ))}
    </nav>
  );
}
