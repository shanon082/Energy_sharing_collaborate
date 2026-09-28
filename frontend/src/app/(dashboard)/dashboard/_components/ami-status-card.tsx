"use client";

import { useCallback, useEffect, useState } from "react";
import { Wifi, RefreshCw, Circle, Loader2, Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { get } from "@/lib/fetch-client";
import { getApiErrorMessage } from "@/lib/api-response";
import {
  applyWalletUnits,
} from "@/app/(dashboard)/dashboard/share/actions";
import type { UserMeter } from "@/interface/meter.interface";

interface AmiStatusCardProps {
  meter: UserMeter;
  unitBalance: number;  // Changed from walletBalance to unitBalance
  onApplied?: () => void;
}

interface AmiStatus {
  is_online: boolean;
  last_seen: string | null;
  current_balance_kwh: number | null;
}

export default function AmiStatusCard({
  meter,
  unitBalance,  // Changed from walletBalance to unitBalance
  onApplied,
}: AmiStatusCardProps) {
  const [status, setStatus] = useState<AmiStatus | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [amount, setAmount] = useState("");
  const [isApplying, setIsApplying] = useState(false);
  const [applyMessage, setApplyMessage] = useState("");
  const [localUnitBalance, setLocalUnitBalance] = useState(unitBalance);  // Changed from localWalletBalance
  const [localMeterBalance, setLocalMeterBalance] = useState(meter.units);

  useEffect(() => {
    setLocalUnitBalance(unitBalance);  // Changed from localWalletBalance
  }, [unitBalance]);

  useEffect(() => {
    setLocalMeterBalance(meter.units);
  }, [meter.units]);

  const fetchStatus = useCallback(async () => {
    setIsRefreshing(true);
    setError("");
    try {
      const meterQuery = encodeURIComponent(meter.meter_number);
      const [checkRes, statusRes] = await Promise.all([
        get<any>(`meter/check-units/?meter_no=${meterQuery}`),
        get<any>(`meter/ami-status/?meter_no=${meterQuery}`),
      ]);

      if (!checkRes.error && checkRes.data?.success) {
        const liveBalance = checkRes.data.units_kwh ?? meter.units;
        setStatus({
          is_online: true,
          last_seen: checkRes.data.queried_at ?? null,
          current_balance_kwh: liveBalance,
        });
        setLocalMeterBalance(Number(liveBalance) || 0);
      } else if (!statusRes.error && statusRes.data?.success) {
        const balance = statusRes.data.current_balance_kwh ?? meter.units;
        setStatus({
          is_online: statusRes.data.is_online,
          last_seen: statusRes.data.last_seen ?? null,
          current_balance_kwh: balance,
        });
        setLocalMeterBalance(Number(balance) || 0);
        setError(checkRes.data?.message || "");
      } else {
        setStatus({
          is_online: false,
          last_seen: null,
          current_balance_kwh: meter.units,
        });
        setError(
          checkRes.data?.message || statusRes.data?.message || "Could not reach meter."
        );
      }

      if (!statusRes.error && typeof statusRes.data?.unit_balance === "number") {
        setLocalUnitBalance(statusRes.data.unit_balance);  // Changed from wallet_balance
      }
    } catch {
      setStatus({
        is_online: false,
        last_seen: null,
        current_balance_kwh: meter.units,
      });
      setError("Failed to fetch meter status.");
    } finally {
      setIsRefreshing(false);
    }
  }, [meter.meter_number, meter.units]);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  async function handleApply() {
    const amt = parseFloat(amount);
    if (!amount || isNaN(amt) || amt <= 0) {
      setError("Enter a valid kWh amount.");
      return;
    }
    if (amt > localUnitBalance) {  // Changed from localWalletBalance
      setError(`You only have ${localUnitBalance.toFixed(2)} kWh in your wallet.`);  // Changed from localWalletBalance
      return;
    }

    setIsApplying(true);
    setError("");
    setApplyMessage("");

    try {
      const res = await applyWalletUnits({
        amount: amt,
        meter_no: meter.meter_number,
      });

      const data = res.data;
      if (!data?.success) {
        const fallback =
          typeof data?.error === "string" ? data.error : "Failed to apply units.";
        setError(
          getApiErrorMessage(
            typeof res.error === "string" ? res.error : undefined,
            fallback
          )
        );
        return;
      }

      const live = data.live_units_kwh != null ? Number(data.live_units_kwh) : null;
      const walletRem = Number(data.remaining_wallet_balance) || 0;
      const ledger = Number(data.meter_balance) || 0;

      setApplyMessage(data.message || "Units applied to your AMI meter.");
      setLocalUnitBalance(walletRem);  // Changed from localWalletBalance
      setLocalMeterBalance(ledger);

      if (live != null && Number.isFinite(live)) {
        setStatus({
          is_online: true,
          last_seen: data.live_queried_at ?? new Date().toISOString(),
          current_balance_kwh: live,
        });
        setLocalMeterBalance(live);
      } else {
        void fetchStatus();
      }

      setAmount("");
      onApplied?.();
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setIsApplying(false);
    }
  }

  const balance = status?.current_balance_kwh ?? localMeterBalance;

  return (
    <Card className="border-blue-200 dark:border-blue-800 bg-blue-50/40 dark:bg-blue-950/20">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Wifi className="h-5 w-5 text-blue-600" />
            <CardTitle className="text-base">AMI Meter - Load Units from Wallet</CardTitle>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={fetchStatus}
            disabled={isRefreshing}
            className="h-8 px-2"
          >
            <RefreshCw className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} />
          </Button>
        </div>
        <CardDescription>
          Buy units to load your wallet, then apply them here. AMI meters update over the network —
          no token entry required. Use refresh to read live units from ThingsBoard.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-lg border border-blue-200 dark:border-blue-800 bg-white dark:bg-slate-900 px-4 py-3">
            <span className="text-sm text-muted-foreground">Meter balance</span>
            <p className="text-xl font-bold tabular-nums mt-1">{balance.toFixed(2)} kWh</p>
          </div>
          <div className="rounded-lg border border-blue-200 dark:border-blue-800 bg-white dark:bg-slate-900 px-4 py-3">
            <span className="text-sm text-muted-foreground">Unit balance (wallet)</span>
            <p className="text-xl font-bold tabular-nums mt-1">
              {localUnitBalance.toFixed(2)} kWh
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 text-sm">
          <Circle
            className={`h-2.5 w-2.5 fill-current ${
              status?.is_online ? "text-green-500" : "text-amber-500"
            }`}
          />
          <span>{status?.is_online ? "Meter online" : "Meter offline or unreachable"}</span>
          {status?.last_seen && (
            <span className="text-muted-foreground text-xs ml-auto">
              Last seen {new Date(status.last_seen).toLocaleString()}
            </span>
          )}
        </div>

        {meter.static_ip && (
          <p className="text-xs text-muted-foreground font-mono">IP: {meter.static_ip}</p>
        )}

        {localUnitBalance > 0 ? (
          <div className="space-y-2">
            <Label htmlFor="ami-apply-amount">kWh to load from wallet</Label>
            <div className="flex gap-2">
              <Input
                id="ami-apply-amount"
                type="number"
                min="0.01"
                max={localUnitBalance}
                step="0.01"
                placeholder="e.g. 10"
                value={amount}
                onChange={(e) => {
                  setAmount(e.target.value);
                  setError("");
                  setApplyMessage("");
                }}
                disabled={isApplying}
                className="flex-1"
              />
              <Button
                onClick={handleApply}
                disabled={isApplying || !amount}
                className="gpawa-gradient text-white shrink-0"
              >
                {isApplying ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <>
                    <Zap className="h-4 w-4 mr-1.5" />
                    Apply
                  </>
                )}
              </Button>
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground text-center py-2">
            No units in wallet. Buy units first, then apply them to this meter.
          </p>
        )}

        {applyMessage && (
          <p className="text-sm text-green-700 dark:text-green-400">{applyMessage}</p>
        )}
        {error && <p className="text-sm text-destructive">{error}</p>}

        <p className="text-xs text-muted-foreground">
          Balance updates may take a few minutes to reflect on the physical meter.
        </p>
      </CardContent>
    </Card>
  );
}