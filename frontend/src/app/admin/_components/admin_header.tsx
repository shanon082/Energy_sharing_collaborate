"use client";

import { CircleUser, Menu } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { GpawaLogo, LOGO_SIZES } from "@/components/common/gpawa-logo";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { ModeToggle } from "@/components/theme-toggle";
import logout from "@/app/(dashboard)/dashboard/logout";
import AdminNavLinks from "./admin-nav-links";
import { Badge } from "@/components/ui/badge";

interface AdminRightHeaderProps {
  userRole?: string | null;
  isSuperuser?: boolean;
}

export default function AdminRightHeader({ userRole, isSuperuser }: AdminRightHeaderProps) {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    setIsOpen(false);
  }, [pathname]);

  return (
    <header className="flex h-14 items-center justify-between gap-4 border-b bg-card px-4 lg:h-[60px] lg:px-6">
      <Sheet open={isOpen} onOpenChange={setIsOpen}>
        <SheetTrigger asChild>
          <Button variant="outline" size="icon" className="shrink-0 md:hidden">
            <Menu className="h-5 w-5" />
            <span className="sr-only">Toggle navigation menu</span>
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="gpawa-sidebar flex w-[88vw] max-w-[360px] flex-col overflow-y-auto border-r p-4">
          <SheetTitle className="sr-only">Admin navigation menu</SheetTitle>
          <div className="mb-4">
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
                className="mt-2 border-[hsl(var(--sidebar-border))] bg-[hsl(var(--sidebar-hover-bg))] text-[hsl(var(--sidebar-text-active))] text-[10px] uppercase"
              >
                {userRole.replace("_", " ")}
              </Badge>
            )}
          </div>
          <AdminNavLinks
            userRole={userRole}
            isSuperuser={isSuperuser}
            onNavigate={() => setIsOpen(false)}
          />
        </SheetContent>
      </Sheet>

      <p className="hidden text-sm text-muted-foreground md:block">
        gPawa management · staff only
      </p>

      <div className="flex items-center gap-2">
        <ModeToggle />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="secondary" size="icon" className="rounded-full">
              <CircleUser className="h-5 w-5" />
              <span className="sr-only">Toggle user menu</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Staff account</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link href="/admin/myaccount">Settings</Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <span
                onClick={async () => {
                  await logout();
                }}
                className="cursor-pointer"
              >
                Logout
              </span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
