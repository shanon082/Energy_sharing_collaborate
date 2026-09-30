"use client";

import Link from "next/link";
import { ArrowUpRight, FileTextIcon, Forward, Home, PlusCircleIcon, Smartphone } from "lucide-react";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { GpawaLogo, LOGO_SIZES } from "@/components/common/gpawa-logo";
import DashboardNavLinks from "@/components/dashboard/dashboard-nav-links";
import { IconMoneybag } from "@tabler/icons-react";
import { PersonIcon } from "@radix-ui/react-icons";
import { useFeatures } from "@/contexts/features-context";

export default function DesktopSidebar() {
  const pathname = usePathname();
  const { peer_sharing, ussd } = useFeatures();

  return (
    <div className="hidden border-r bg-muted/40 md:block">
      <div className="flex h-full max-h-screen flex-col gap-2">
        <div className="flex h-14 items-center border-b px-4 lg:h-[60px] lg:px-6">
          <GpawaLogo
            href="/"
            textSize={LOGO_SIZES.sidebar.textSize}
            logoSize={LOGO_SIZES.sidebar.logoSize}
          />
        </div>
        <div className="flex-1">
          <nav className="grid items-start px-2 text-sm font-medium lg:px-4">
            <Link
              href="/dashboard"
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-muted-foreground transition-all hover:text-primary",
                { "bg-muted text-primary": pathname === "/dashboard" }
              )}
            >
              <Home className="h-4 w-4" />
              Dashboard
            </Link>
            <Link
              href="/dashboard/buy-units"
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-muted-foreground transition-all hover:text-primary",
                { "bg-muted text-primary": pathname === "/dashboard/deposit" }
              )}
            >
              <PlusCircleIcon className="h-4 w-4" />
              Buy Units
            </Link>
            <Link
              href="/dashboard/share"
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-muted-foreground transition-all hover:text-primary",
                { "bg-muted text-primary": pathname === "/dashboard/share" }
              )}
            >
              <Forward className="h-4 w-4" />
              {peer_sharing ? "Load / Share Units" : "Load My Meter"}
            </Link>            
            {/* <Link
              href="/dashboard/transfering"
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-muted-foreground transition-all hover:text-primary",
                { "bg-muted text-primary": pathname === "/dashboard/transfering" }
              )}
            >
              <ArrowRight className="h-4 w-4" />
              Transfer Units
            </Link> */}
            <Link
              href="/dashboard/tokens"
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-muted-foreground transition-all hover:text-primary",
                { "bg-muted text-primary": pathname === "/dashboard/withdraw" }
              )}
            >
              <ArrowUpRight className="h-4 w-4" />
              Tokens
            </Link>
            {/* <Link
            href="/dashboard/buy-airtime"
            className={cn("flex items-center gap-3 rounded-lg px-3 py-2 text-muted-foreground transition-all hover:text-primary", {"bg-muted text-primary": pathname === "/dashboard/buy-airtime"})}
          >
            <LineChart className="h-4 w-4" />
            Buy airtime &amp; data
          </Link> */}
            {/* {loading ? <Skeleton /> : <>
          {user?.package !== "NONE" && <Link
            href={`/dashboard/network/${user?.id}`}
            className={cn("flex items-center gap-3 rounded-lg px-3 py-2 text-muted-foreground transition-all hover:text-primary", {"bg-muted text-primary": pathname === "/dashboard/network"})}
          >
            <Users className="h-4 w-4" />
            My team
          </Link>}
          </>} */}
            <Link
              href="/dashboard/request-loan"
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-muted-foreground transition-all hover:text-primary",
                {
                  "bg-muted text-primary":
                    pathname === "/dashboard/request-loan",
                }
              )}
            >
              <IconMoneybag className="h-4 w-4" />
              Request Loan
            </Link>

            <Link
              href="/dashboard/myloans"
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-muted-foreground transition-all hover:text-primary",
                { "bg-muted text-primary": pathname === "/dashboard/myloans" }
              )}
            >
              <FileTextIcon className="h-4 w-4" />
              My Loans
            </Link>
            <Link
              href={`/dashboard/transactions`}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-muted-foreground transition-all hover:text-primary",
                { "bg-muted text-primary": pathname === "/dashboard/network" }
              )}
            >
              <Forward className="h-4 w-4" />
              Transactions
            </Link>
            <Link
              href={`/dashboard/wallet`}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-muted-foreground transition-all hover:text-primary",
                { "bg-muted text-primary": pathname === "/dashboard/wallet" }
              )}
            >
              <IconMoneybag className="h-4 w-4" />
              Wallet
            </Link>
            <Link
              href={`/dashboard/myaccount`}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-muted-foreground transition-all hover:text-primary",
                { "bg-muted text-primary": pathname === "/dashboard/myaccount" }
              )}
            >
              <PersonIcon className="h-4 w-4" />
              My Account
            </Link>
            {ussd && <Link
              href="/ussd-simulator"
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-all hover:text-primary",
                { "bg-muted text-primary": pathname === "/ussd-simulator" }
              )}
            >
              <Smartphone className="h-4 w-4" />
              USSD Simulator
            </Link>}
          </nav>
        </div>
      </div>
    </div>
  );
}
