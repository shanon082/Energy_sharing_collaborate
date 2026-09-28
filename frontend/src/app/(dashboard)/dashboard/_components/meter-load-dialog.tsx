"use client";

import { useEffect, useState } from "react";
import {
  Check,
  CheckCircle2,
  Copy,
  Cpu,
  Hash,
  KeyRound,
  Loader2,
  Wallet,
  Wifi,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { FormError } from "@/components/common/form-error";
import { getApiErrorMessage } from "@/lib/api-response";
import {
  applyWalletUnits,
  type AmiLoadSuccessResult,
} from "@/app/(dashboard)/dashboard/share/actions";
import { generateTokenFromWallet } from "@/app/(dashboard)/dashboard/my-meters/actions";
import type { UserMeter } from "@/interface/meter.interface";

interface MeterLoadDialogProps {
  meter: UserMeter | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  unitBalance: number;
  initialAmount?: number;
  onunitBalanceChange?: (balance: number) => void;
  onSuccess?: (result?: AmiLoadSuccessResult) => void;
}

export default function MeterLoadDialog({
  meter,
  open,
  onOpenChange,
  unitBalance,
  initialAmount,
  onunitBalanceChange,
  onSuccess,
}: MeterLoadDialogProps) {
  const [amount, setAmount] = useState("1");
  const [step, setStep] = useState<"form" | "confirm" | "token" | "ami-success">("form");
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState("");
  const [tokenResult, setTokenResult] = useState<{
    token: string;
    units: number;
    remaining: number;
  } | null>(null);
  const [amiResult, setAmiResult] = useState<AmiLoadSuccessResult | null>(null);
  const [copied, setCopied] = useState(false);

  const isAmi = meter?.architecture === "AMI";
  const parsedAmount = parseFloat(amount) || 0;

  useEffect(() => {
    if (!open) {
      setStep("form");
      setAmount("1");
      setError("");
      setTokenResult(null);
      setAmiResult(null);
      setCopied(false);
    } else if (initialAmount != null && initialAmount > 0) {
      setAmount(String(initialAmount));
      setStep("confirm");
    }
  }, [open, meter?.meter_number, initialAmount]);

  const handleReview = () => {
    setError("");
    if (!meter) return;
    if (parsedAmount <= 0) {
      setError("Enter a valid kWh amount.");
      return;
    }
    if (parsedAmount > unitBalance) {
      setError(`Insufficient wallet balance. Available: ${unitBalance.toFixed(2)} kWh.`);
      return;
    }
    setStep("confirm");
  };

  const handleConfirm = async () => {
    if (!meter) return;
    setIsPending(true);
    setError("");
    try {
      if (isAmi) {
        const res = await applyWalletUnits({
          meter_no: meter.meter_number,
          amount: parsedAmount,
        });
        if (res.data?.success) {
          const result: AmiLoadSuccessResult = {
            units_applied: Number(res.data.units_applied) || parsedAmount,
            meter_balance: Number(res.data.meter_balance) || 0,
            pending_delivery_kwh: Number(res.data.pending_delivery_kwh) || 0,
            remaining_wallet_balance: Number(res.data.remaining_wallet_balance) || 0,
            live_units_kwh:
              res.data.live_units_kwh != null ? Number(res.data.live_units_kwh) : null,
            live_queried_at: res.data.live_queried_at ?? null,
            delivery_status:
              res.data.delivery_status === "pending" ? "pending" : "delivered",
            message: res.data.message ?? "Units loaded successfully.",
          };
          onunitBalanceChange?.(result.remaining_wallet_balance);
          setAmiResult(result);
          setStep("ami-success");
          onSuccess?.(result);
        } else {
          const fallback =
            typeof res.data?.error === "string"
              ? res.data.error
              : "Failed to load units to meter.";
          setError(
            getApiErrorMessage(
              typeof res.error === "string" ? res.error : undefined,
              fallback
            )
          );
        }
      } else {
        const res = await generateTokenFromWallet({
          meter_no: meter.meter_number,
          amount: parsedAmount,
        });
        if (res.data?.success && res.data.token) {
          setTokenResult({
            token: res.data.token,
            units: Number(res.data.units) || parsedAmount,
            remaining: Number(res.data.remaining_balance) || 0,
          });
          onunitBalanceChange?.(Number(res.data.remaining_balance) || 0);
          setStep("token");
          onSuccess?.();
        } else {
          const fallback =
            typeof res.data?.error === "string"
              ? res.data.error
              : "Failed to generate STS token.";
          setError(
            getApiErrorMessage(
              typeof res.error === "string" ? res.error : undefined,
              fallback
            )
          );
        }
      }
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setIsPending(false);
    }
  };

  async function copyToken() {
    if (!tokenResult) return;
    await navigator.clipboard.writeText(tokenResult.token);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (!meter) return null;

  return (
    <Dialog open={open} onOpenChange={(o) => !isPending && onOpenChange(o)}>
      <DialogContent className="sm:max-w-md">
        {step === "ami-success" && amiResult ? (
          <>
            <DialogHeader>
              <div className="flex items-center gap-2 text-green-700">
                <CheckCircle2 className="h-5 w-5" />
                <DialogTitle>
                  {amiResult.delivery_status === "pending"
                    ? "Units queued for delivery"
                    : "Units loaded successfully"}
                </DialogTitle>
              </div>
              <DialogDescription>{amiResult.message}</DialogDescription>
            </DialogHeader>
            <div className="rounded-xl border bg-green-50/60 dark:bg-green-950/20 divide-y text-sm overflow-hidden">
              <SuccessRow
                icon={<Zap className="h-4 w-4" />}
                label="Units loaded"
                value={`${amiResult.units_applied.toFixed(2)} kWh`}
              />
              {amiResult.live_units_kwh != null && (
                <SuccessRow
                  icon={<Wifi className="h-4 w-4" />}
                  label="Live meter reading (ThingsBoard)"
                  value={`${amiResult.live_units_kwh.toFixed(2)} kWh`}
                  highlight
                />
              )}
              <SuccessRow
                icon={<Cpu className="h-4 w-4" />}
                label="Meter ledger"
                value={`${amiResult.meter_balance.toFixed(2)} kWh`}
              />
              {amiResult.pending_delivery_kwh > 0 && (
                <SuccessRow
                  icon={<Loader2 className="h-4 w-4" />}
                  label="Pending delivery"
                  value={`${amiResult.pending_delivery_kwh.toFixed(2)} kWh`}
                />
              )}
              <SuccessRow
                icon={<Wallet className="h-4 w-4" />}
                label="Wallet remaining"
                value={`${amiResult.remaining_wallet_balance.toFixed(2)} kWh`}
              />
            </div>
            <DialogFooter>
              <Button onClick={() => onOpenChange(false)} className="w-full">
                Done
              </Button>
            </DialogFooter>
          </>
        ) : step === "token" && tokenResult ? (
          <>
            <DialogHeader>
              <DialogTitle>STS token generated</DialogTitle>
              <DialogDescription>
                Enter this token on your meter keypad (CIU) to load{" "}
                {tokenResult.units.toFixed(2)} kWh onto meter {meter.meter_number}.
              </DialogDescription>
            </DialogHeader>
            <div className="rounded-xl border bg-muted/30 p-4 text-center">
              <p className="text-xs text-muted-foreground mb-2">Your token</p>
              <p className="font-mono text-2xl font-bold tracking-widest">{tokenResult.token}</p>
            </div>
            <Button type="button" variant="outline" className="w-full gap-2" onClick={copyToken}>
              {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              {copied ? "Copied" : "Copy token"}
            </Button>
            <DialogFooter>
              <Button onClick={() => onOpenChange(false)}>Done</Button>
            </DialogFooter>
          </>
        ) : step === "confirm" ? (
          <>
            <DialogHeader>
              <DialogTitle>
                {isAmi ? "Confirm load to AMI meter" : "Confirm STS token generation"}
              </DialogTitle>
              <DialogDescription>
                {isAmi
                  ? "Units will be deducted from your wallet and pushed to ThingsBoard for this device."
                  : "Units will be deducted from your wallet and converted into a keypad token."}
              </DialogDescription>
            </DialogHeader>
            <div className="rounded-xl border bg-muted/20 divide-y text-sm overflow-hidden">
              <DetailRow icon={<Hash className="h-4 w-4" />} label="Meter" value={meter.meter_number} />
              <DetailRow
                icon={isAmi ? <Cpu className="h-4 w-4" /> : <KeyRound className="h-4 w-4" />}
                label="Type"
                value={isAmi ? "AMI (networked)" : "STS (keypad token)"}
              />
              <DetailRow
                icon={<Zap className="h-4 w-4" />}
                label="Load amount"
                value={`${parsedAmount.toFixed(2)} kWh`}
              />
              <DetailRow
                icon={<Wallet className="h-4 w-4" />}
                label="Wallet after"
                value={`${Math.max(0, unitBalance - parsedAmount).toFixed(2)} kWh`}
              />
            </div>
            <FormError message={error} />
            <DialogFooter>
              <Button variant="outline" onClick={() => setStep("form")} disabled={isPending}>
                Back
              </Button>
              <Button onClick={handleConfirm} disabled={isPending} className="gpawa-gradient text-white">
                {isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Loading to meter…
                  </>
                ) : isAmi ? (
                  "Confirm load"
                ) : (
                  "Generate token"
                )}
              </Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>Load units to meter</DialogTitle>
              <DialogDescription>
                {meter.label && meter.label !== "Home" ? `${meter.label} · ` : ""}
                {meter.meter_number} ({isAmi ? "AMI" : "STS"})
              </DialogDescription>
            </DialogHeader>
            <div className="flex items-center justify-between rounded-lg border bg-muted/30 px-4 py-3 text-sm">
              <span className="text-muted-foreground">Wallet balance</span>
              <span className="font-semibold tabular-nums">{unitBalance.toFixed(2)} kWh</span>
            </div>
            <div className="space-y-2">
              <label htmlFor="load-amount" className="text-sm font-medium">
                kWh to load
              </label>
              <Input
                id="load-amount"
                type="number"
                min="0.01"
                step="0.01"
                max={unitBalance}
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
              />
            </div>
            <FormError message={error} />
            <DialogFooter>
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleReview}
                disabled={unitBalance <= 0}
                className="gpawa-gradient text-white"
              >
                Review
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function DetailRow({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-3 px-4 py-3">
      <span className="text-muted-foreground">{icon}</span>
      <div>
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="font-medium">{value}</p>
      </div>
    </div>
  );
}

function SuccessRow({
  icon,
  label,
  value,
  highlight,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={`flex items-center gap-3 px-4 py-3 ${
        highlight ? "bg-sky-50/80 dark:bg-sky-950/30" : ""
      }`}
    >
      <span className="text-muted-foreground">{icon}</span>
      <div>
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className={`font-semibold tabular-nums ${highlight ? "text-sky-800 dark:text-sky-200" : ""}`}>
          {value}
        </p>
      </div>
    </div>
  );
}
