'use client';

import { GpawaLogo, LOGO_SIZES } from "@/components/common/gpawa-logo";
import AdminNavLinks from "./admin-nav-links";
import { Badge } from "@/components/ui/badge";

interface AdminDesktopSidebarProps {
  userRole?: string | null;
  isSuperuser?: boolean;
}

export default function AdminDesktopSidebar({ userRole, isSuperuser }: AdminDesktopSidebarProps) {
  return (
    <div className="gpawa-sidebar hidden h-full border-r md:flex md:flex-col">
      <div className="flex h-14 flex-col justify-center border-b border-[hsl(var(--sidebar-border))] px-4 lg:h-[60px] lg:px-6">
        <GpawaLogo
          href="/admin/dashboard"
          showText={false}
          suffix="Admin Panel"
          suffixVariant="sidebar"
          textSize={LOGO_SIZES.sidebar.textSize}
          logoSize={LOGO_SIZES.sidebar.logoSize}
        />
        {userRole && (
          <Badge
            variant="outline"
            className="mt-2 w-fit border-[hsl(var(--sidebar-border))] bg-[hsl(var(--sidebar-hover-bg))] text-[hsl(var(--sidebar-text-active))] text-[10px] uppercase tracking-wide"
          >
            {userRole.replace("_", " ")}
          </Badge>
        )}
      </div>
      <div className="flex-1 overflow-y-auto py-3">
        <AdminNavLinks
          userRole={userRole}
          isSuperuser={isSuperuser}
          className="px-2 lg:px-3"
        />
      </div>
      <p className="gpawa-sidebar-footer border-t border-[hsl(var(--sidebar-border))] px-4 py-3 text-[11px]">
        Management console — not the customer portal.
      </p>
    </div>
  );
}
