"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ArrowUpRight,
  Activity,
  Forward,
  Gauge,
  Home,
  PlusCircleIcon,
} from "lucide-react";
import { PersonIcon } from "@radix-ui/react-icons";
import { IconMoneybag } from "@tabler/icons-react";
import { cn } from "@/lib/utils";
import { useSelectedMeter } from "@/contexts/selected-meter-context";
import { useFeatures } from "@/contexts/features-context";

export default function DashboardNavLinks({ className }: { className?: string }) {
  const pathname = usePathname();
  const { meters, selectedMeter } = useSelectedMeter();
  const { peer_sharing } = useFeatures();

  const hasStsMeter = meters.some((m) => m.architecture === "STS");
  const hasAmiMeter = meters.some((m) => m.architecture === "AMI");
  const selectedIsSts = selectedMeter?.architecture === "STS";
  const showTokensNav = hasStsMeter && (meters.length < 2 || selectedIsSts);

  const linkClass = (active: boolean) =>
    cn(
      "flex items-center gap-3 rounded-lg px-3 py-2 text-muted-foreground transition-all hover:text-primary",
      { "bg-muted text-primary": active }
    );

  return (
    <nav className={cn("grid items-start px-2 text-sm font-medium lg:px-4", className)}>
      <Link href="/dashboard" className={linkClass(pathname === "/dashboard")}>
        <Home className="h-4 w-4" />
        Dashboard
      </Link>
      <Link
        href="/dashboard/my-meters"
        className={linkClass(pathname.startsWith("/dashboard/my-meters"))}
      >
        <Gauge className="h-4 w-4" />
        My Meters
      </Link>
      <Link href="/dashboard/buy-units" className={linkClass(pathname === "/dashboard/buy-units")}>
        <PlusCircleIcon className="h-4 w-4" />
        TopUp Wallet
      </Link>
      <Link href="/dashboard/share" className={linkClass(pathname === "/dashboard/share")}>
        <Forward className="h-4 w-4" />
        {peer_sharing ? "Load / Share Units" : "Load My Meter"}
      </Link>
      {showTokensNav && (
        <Link href="/dashboard/tokens" className={linkClass(pathname === "/dashboard/tokens")}>
          <ArrowUpRight className="h-4 w-4" />
          STS Tokens
        </Link>
      )}
      {hasAmiMeter && (
        <Link
          href="/dashboard/power-usage"
          className={linkClass(pathname === "/dashboard/power-usage")}
        >
          <Activity className="h-4 w-4" />
          Energy Usage
        </Link>
      )}
      <Link
        href="/dashboard/loans"
        className={linkClass(pathname.startsWith("/dashboard/loans") || pathname.startsWith("/dashboard/request-loan") || pathname.startsWith("/dashboard/myloans"))}
      >
        <IconMoneybag className="h-4 w-4" />
        Loans
      </Link>
      <Link
        href="/dashboard/transactions"
        className={linkClass(pathname === "/dashboard/transactions")}
      >
        <Forward className="h-4 w-4" />
        Transactions
      </Link>
      <Link href="/dashboard/myaccount" className={linkClass(pathname === "/dashboard/myaccount")}>
        <PersonIcon className="h-4 w-4" />
        My Account
      </Link>
    </nav>
  );
}
