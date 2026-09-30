"use client";

import {
  CircleUser,
  FileTextIcon,
  Smartphone,
  User,
} from "lucide-react";
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
import logout from "../logout";
import { GpawaLogo, LOGO_SIZES } from "@/components/common/gpawa-logo";
import { cn } from "@/lib/utils";
import { usePathname } from "next/navigation";
import { ModeToggle } from "@/components/theme-toggle";
import NotificationBell from "./notification-bell";
import { IconMoneybag } from "@tabler/icons-react";
import DashboardNavLinks from "@/components/dashboard/dashboard-nav-links";
import { Zap, Settings, LogOut, Menu } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useAccount } from "@/hooks/use-account";
import { useFeatures } from "@/contexts/features-context";

interface RightHeaderProps {
  onProfileClick?: () => void;
  onMeterClick?: () => void;
}

export default function RightHeader({ onProfileClick, onMeterClick }: RightHeaderProps) {
  const pathname = usePathname();
  const [isProfileMenuOpen, setIsProfileMenuOpen] = useState(false);
  const { user } = useAccount();
  const { ussd } = useFeatures();
  const [cachedEmail, setCachedEmail] = useState("");

  useEffect(() => {
    if (typeof window === "undefined") return;
    const key = "gpawa:user_email";
    const liveEmail = user?.email?.trim();
    if (liveEmail) {
      window.localStorage.setItem(key, liveEmail);
      setCachedEmail(liveEmail);
      return;
    }
    const saved = window.localStorage.getItem(key) || "";
    setCachedEmail(saved);
  }, [user?.email]);

  const displayEmail = useMemo(() => user?.email?.trim() || cachedEmail, [user?.email, cachedEmail]);

  const handleProfileClick = () => {
    if (onProfileClick) {
      onProfileClick();
      setIsProfileMenuOpen(false);
    }
  };

  const handleMeterClick = () => {
    if (onMeterClick) {
      onMeterClick();
      setIsProfileMenuOpen(false);
    }
  };

  return (
    <header className="flex justify-between sm:justify-end h-14 items-center gap-4 border-b bg-muted/40 px-4 lg:h-[60px] lg:px-6">
      <Sheet>
        <SheetTrigger asChild>
          <Button variant="outline" size="icon" className="shrink-0 md:hidden">
            <Menu className="h-5 w-5" />
            <span className="sr-only">Toggle navigation menu</span>
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="flex w-[88vw] max-w-[360px] flex-col overflow-y-auto">
          <SheetTitle className="sr-only">Navigation menu</SheetTitle>
          <nav className="grid gap-2 text-lg font-medium">
            <GpawaLogo
              href="/"
              textSize={LOGO_SIZES.sidebar.textSize}
              logoSize={LOGO_SIZES.sidebar.logoSize}
            />
            <DashboardNavLinks className="text-base" />
            {ussd && <Link
              href="/ussd-simulator"
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-muted-foreground transition-all hover:text-primary",
                { "bg-muted text-primary": pathname === "/ussd-simulator" }
              )}
            >
              <Smartphone className="h-4 w-4" />
              USSD Simulator
            </Link>}
          </nav>
        </SheetContent>
      </Sheet>

      <div className="flex items-center gap-3">
        <span
          className="hidden text-sm text-muted-foreground md:inline-block max-w-[260px] truncate"
          title={displayEmail}
        >
          {displayEmail}
        </span>
        <NotificationBell />
        <ModeToggle />

        <DropdownMenu open={isProfileMenuOpen} onOpenChange={setIsProfileMenuOpen}>
          <DropdownMenuTrigger asChild>
            <Button variant="secondary" size="icon" className="rounded-full">
              <CircleUser className="h-5 w-5" />
              <span className="sr-only">Toggle user menu</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>My Account</DropdownMenuLabel>
            <DropdownMenuSeparator />

            {onProfileClick && (
              <DropdownMenuItem onClick={handleProfileClick}>
                <User className="h-4 w-4 mr-2" />
                Manage Profile
              </DropdownMenuItem>
            )}

            {onMeterClick && (
              <DropdownMenuItem onClick={handleMeterClick}>
                <Zap className="h-4 w-4 mr-2" />
                Manage Meter
              </DropdownMenuItem>
            )}

            <DropdownMenuItem asChild>
              <Link href="/dashboard/myaccount">
                <Settings className="h-4 w-4 mr-2" />
                Account Settings
              </Link>
            </DropdownMenuItem>

            <DropdownMenuSeparator />

            <DropdownMenuItem asChild>
              <Link href="/dashboard/transactions">
                <FileTextIcon className="h-4 w-4 mr-2" />
                Transaction History
              </Link>
            </DropdownMenuItem>

            <DropdownMenuItem asChild>
              <Link href="/dashboard/myloans">
                <IconMoneybag className="h-4 w-4 mr-2" />
                My Loans
              </Link>
            </DropdownMenuItem>

            {ussd && <DropdownMenuItem asChild>
              <Link href="/ussd-simulator">
                <Smartphone className="h-4 w-4 mr-2" />
                USSD Simulator
              </Link>
            </DropdownMenuItem>}

            <DropdownMenuSeparator />

            <DropdownMenuItem asChild>
              <span
                onClick={async () => {
                  await logout();
                }}
                className="w-full text-left cursor-pointer"
              >
                <LogOut className="h-4 w-4 mr-2" />
                Logout
              </span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
