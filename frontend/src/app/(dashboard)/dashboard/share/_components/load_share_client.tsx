"use client";

import { useEffect, useState } from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  Cpu,
  Forward,
  KeyRound,
  Wallet,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import LoadUnitsForm from "./load_units_form";
import ShareForm from "./share_form";
import { useSelectedMeter } from "@/contexts/selected-meter-context";
import { get } from "@/lib/fetch";

type Mode = "choose" | "load" | "share";

export default function LoadShareClient() {
  const [mode, setMode] = useState<Mode>("choose");
  const { meters, refreshWallet } = useSelectedMeter();
  const hasMeters = meters.length > 0;
  const [unitBalance, setUnitBalance] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Function to fetch unit balance
  const fetchUnitBalance = async () => {
    setIsLoading(true);
    try {
      const response = await get<any>("wallet/balance/");
      if (!response.error && response.data?.success) {
        // Get the unit balance from the response
        const balance = Number(response.data.unit_balance?.balance || 0);
        setUnitBalance(balance);
        return balance;
      } else {
        console.error("Failed to fetch unit balance:", response.error);
        setUnitBalance(0);
        return 0;
      }
    } catch (error) {
      console.error("Error fetching unit balance:", error);
      setUnitBalance(0);
      return 0;
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (mode === "choose") {
      void fetchUnitBalance();
      // Also refresh wallet context in the background
      void refreshWallet();
    }
  }, [mode, refreshWallet]);

  // Refresh balance when returning from load/share
  useEffect(() => {
    if (mode === "choose") {
      void fetchUnitBalance();
    }
  }, [mode]);

  if (mode === "load") {
    return <LoadUnitsForm onBack={() => setMode("choose")} />;
  }

  if (mode === "share") {
    return <ShareForm onBack={() => setMode("choose")} />;
  }

  return (
    <div className="mx-auto w-full max-w-5xl px-2 py-4 sm:px-4 sm:py-8">
      <div className="mb-8 text-center sm:mb-10">
        <p className="text-sm font-medium uppercase tracking-wider text-primary">
          Unit wallet
        </p>
        <h2 className="mt-2 text-2xl font-bold tracking-tight sm:text-3xl">
          What would you like to do?
        </h2>
        <p className="mx-auto mt-3 max-w-xl text-sm text-muted-foreground sm:text-base">
          Load kWh onto your own meter, or share from your wallet to someone
          else&apos;s meter.
        </p>
        <div className="mt-5 inline-flex items-center gap-2 rounded-full border bg-muted/40 px-4 py-2 text-sm">
          <Wallet className="h-4 w-4 text-primary" />
          <span className="text-muted-foreground">Available in wallet</span>
          <span className="font-semibold tabular-nums">
            {isLoading ? "..." : (unitBalance !== null ? unitBalance.toFixed(2) : "0.00")} kWh
          </span>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2 md:gap-8">
        <OptionCard
          disabled={!hasMeters}
          accent="sky"
          icon={ArrowDownToLine}
          title="Load Units"
          badge="Your meters"
          description="Move kWh from your wallet onto one of your registered meters. AMI meters update over the network; STS meters receive a keypad token."
          bullets={[
            { icon: Cpu, text: "AMI → direct ThingsBoard top-up" },
            { icon: KeyRound, text: "STS → keypad token for your CIU" },
          ]}
          footerNote={
            hasMeters
              ? `${meters.length} meter${meters.length === 1 ? "" : "s"} on your account`
              : "Register a meter under My Meters first"
          }
          buttonLabel="Load to my meter"
          onSelect={() => setMode("load")}
        />

        <OptionCard
          accent="emerald"
          icon={Forward}
          title="Share Units"
          badge="Send to others"
          description="Transfer kWh from your wallet to another customer's meter. We detect STS vs AMI automatically and deliver the right way."
          bullets={[
            { icon: KeyRound, text: "STS receiver → keypad token by email" },
            { icon: Cpu, text: "AMI receiver → direct device top-up" },
          ]}
          footerNote="Confirm on the next screen to complete the transfer"
          buttonLabel="Share to another meter"
          buttonVariant="outline"
          onSelect={() => setMode("share")}
        />
      </div>
    </div>
  );
}

function OptionCard({
  title,
  description,
  badge,
  bullets,
  footerNote,
  buttonLabel,
  icon: Icon,
  accent,
  disabled,
  buttonVariant = "default",
  onSelect,
}: {
  title: string;
  description: string;
  badge: string;
  bullets: { icon: React.ComponentType<{ className?: string }>; text: string }[];
  footerNote: string;
  buttonLabel: string;
  icon: React.ComponentType<{ className?: string }>;
  accent: "sky" | "emerald";
  disabled?: boolean;
  buttonVariant?: "default" | "outline";
  onSelect: () => void;
}) {
  const accentStyles =
    accent === "sky"
      ? {
          ring: "hover:border-sky-300 hover:shadow-sky-100 dark:hover:border-sky-700 dark:hover:shadow-sky-900/20",
          iconBg: "bg-sky-500/10 text-sky-600 dark:bg-sky-900/30 dark:text-sky-400",
          badge: "bg-sky-500/10 text-sky-700 border-sky-200 dark:bg-sky-900/30 dark:text-sky-400 dark:border-sky-700",
        }
      : {
          ring: "hover:border-emerald-300 hover:shadow-emerald-100 dark:hover:border-emerald-700 dark:hover:shadow-emerald-900/20",
          iconBg: "bg-emerald-500/10 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400",
          badge: "bg-emerald-500/10 text-emerald-700 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-400 dark:border-emerald-700",
        };

  return (
    <Card
      className={cn(
        "relative flex flex-col overflow-hidden border-2 transition-all duration-200",
        disabled
          ? "opacity-60 grayscale-[0.3]"
          : cn("cursor-pointer shadow-md hover:shadow-lg", accentStyles.ring),
        !disabled && "hover:-translate-y-0.5"
      )}
      onClick={disabled ? undefined : onSelect}
      role="button"
      tabIndex={disabled ? -1 : 0}
      onKeyDown={(e) => {
        if (!disabled && (e.key === "Enter" || e.key === " ")) {
          e.preventDefault();
          onSelect();
        }
      }}
    >
      <div
        className={cn(
          "absolute inset-x-0 top-0 h-1",
          accent === "sky" ? "bg-gradient-to-r from-sky-400 to-blue-500" : "bg-gradient-to-r from-emerald-400 to-teal-500"
        )}
      />
      <CardHeader className="pb-3 pt-7">
        <div className="flex items-start justify-between gap-3">
          <div className={cn("rounded-xl p-3", accentStyles.iconBg)}>
            <Icon className="h-7 w-7" />
          </div>
          <Badge variant="outline" className={cn("shrink-0 font-normal", accentStyles.badge)}>
            {badge}
          </Badge>
        </div>
        <CardTitle className="text-xl pt-2">{title}</CardTitle>
        <CardDescription className="text-sm leading-relaxed">{description}</CardDescription>
      </CardHeader>
      <CardContent className="flex-1 space-y-2 pb-4">
        <ul className="space-y-2.5">
          {bullets.map(({ icon: BulletIcon, text }) => (
            <li key={text} className="flex items-start gap-2.5 text-sm text-muted-foreground">
              <BulletIcon className="mt-0.5 h-4 w-4 shrink-0 text-primary/70" />
              <span>{text}</span>
            </li>
          ))}
        </ul>
      </CardContent>
      <CardFooter className="flex flex-col gap-3 border-t bg-muted/20 pt-4">
        <p className="w-full text-center text-xs text-muted-foreground">{footerNote}</p>
        <Button
          type="button"
          variant={buttonVariant}
          className={cn(
            "w-full gap-2",
            buttonVariant === "default" && "gpawa-gradient text-white border-0"
          )}
          disabled={disabled}
          onClick={(e) => {
            e.stopPropagation();
            if (!disabled) onSelect();
          }}
        >
          {buttonLabel}
          <ArrowRight className="h-4 w-4" />
        </Button>
      </CardFooter>
    </Card>
  );
}