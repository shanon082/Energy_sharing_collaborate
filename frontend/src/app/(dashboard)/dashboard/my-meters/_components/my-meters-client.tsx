"use client";

import { useEffect, useState, type ReactNode } from "react";
import {
  Activity,
  Gauge,
  KeyRound,
  Loader2,
  Plus,
  RefreshCw,
  Trash2,
  Wifi,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { getApiErrorMessage } from "@/lib/api-response";
import { get } from "@/lib/fetch-client";
import { useSelectedMeter } from "@/contexts/selected-meter-context";
import { deleteMeter } from "../actions";
import AddMeterDialog from "./add-meter-dialog";
import EnergyStatusCard from "@/components/dashboard/energy-status-card";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import type { UserMeter } from "@/interface/meter.interface";

export default function MyMetersClient() {
  const { meters, isLoading, refreshMeters } = useSelectedMeter();
  const [selectedNo, setSelectedNo] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [checkingUnits, setCheckingUnits] = useState(false);
  const [liveUnits, setLiveUnits] = useState<number | null>(null);
  const [liveQueriedAt, setLiveQueriedAt] = useState<string | null>(null);
  const [checkError, setCheckError] = useState("");
  const [actionMessage, setActionMessage] = useState("");

  const selected = meters.find((m) => m.meter_number === selectedNo) ?? meters[0] ?? null;

  useEffect(() => {
    if (meters.length && !selectedNo) {
      setSelectedNo(meters[0].meter_number);
    }
  }, [meters, selectedNo]);

  useEffect(() => {
    setLiveUnits(null);
    setLiveQueriedAt(null);
    setCheckError("");
    setActionMessage("");
  }, [selected?.meter_number]);

  const handleCheckUnits = async () => {
    if (!selected || selected.architecture !== "AMI") return;
    setCheckingUnits(true);
    setCheckError("");
    setActionMessage("");
    try {
      const res = await get<{
        success?: boolean;
        units_kwh?: number | string;
        queried_at?: string;
        message?: string;
      }>(`meter/check-units/?meter_no=${encodeURIComponent(selected.meter_number)}`);

      if (!res.error && res.data?.success) {
        const units = Number(res.data.units_kwh);
        if (!Number.isFinite(units)) {
          setCheckError("ThingsBoard returned an invalid balance.");
          setLiveUnits(null);
          return;
        }
        setLiveUnits(units);
        setLiveQueriedAt(res.data.queried_at ?? new Date().toISOString());
        setActionMessage(
          `Live balance: ${units.toFixed(2)} kWh (from ThingsBoard).`
        );
      } else {
        setLiveUnits(null);
        setCheckError(
          getApiErrorMessage(res.error, res.data?.message ?? "Could not read meter balance.")
        );
      }
    } catch {
      setLiveUnits(null);
      setCheckError("Network error while checking units.");
    } finally {
      setCheckingUnits(false);
    }
  };

  const handleMeterAdded = async () => {
    await refreshMeters();
    setAddOpen(false);
  };

  const handleDeleteMeter = async () => {
    if (!selected) return;
    setDeleting(true);
    setCheckError("");
    setActionMessage("");
    try {
      const res = await deleteMeter(selected.meter_number);
      if (res.data?.success) {
        setDeleteOpen(false);
        setSelectedNo(null);
        setActionMessage(res.data.message ?? "Meter removed.");
        await refreshMeters();
      } else {
        setCheckError(getApiErrorMessage(res.error, res.data?.error ?? "Failed to remove meter."));
      }
    } catch {
      setCheckError("Failed to remove meter.");
    } finally {
      setDeleting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20 text-muted-foreground">
        <Loader2 className="h-6 w-6 animate-spin mr-2" />
        Loading your meters…
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-6xl">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm text-muted-foreground">
            {meters.length} meter{meters.length === 1 ? "" : "s"} on your account
          </p>
        </div>
        <Button onClick={() => setAddOpen(true)} className="gpawa-gradient text-white gap-2">
          <Plus className="h-4 w-4" />
          Add new meter
        </Button>
      </div>

      {meters.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <Gauge className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold">No meters yet</h3>
            <p className="text-sm text-muted-foreground mt-2 max-w-md">
              Register your STS or AMI meter to load units, check live balance, and manage
              electricity on your account.
            </p>
            <Button onClick={() => setAddOpen(true)} className="mt-6 gpawa-gradient text-white">
              <Plus className="h-4 w-4 mr-2" />
              Add your first meter
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,340px)_1fr]">
          <div className="space-y-3">
            {meters.map((meter) => (
              <button
                key={meter.meter_number}
                type="button"
                onClick={() => setSelectedNo(meter.meter_number)}
                className={cn(
                  "w-full rounded-xl border p-4 text-left transition-all hover:shadow-md",
                  selected?.meter_number === meter.meter_number
                    ? "border-primary bg-primary/5 shadow-sm ring-1 ring-primary/20"
                    : "bg-card hover:border-primary/30"
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-semibold">{meter.label || "Home"}</p>
                    <p className="font-mono text-sm text-muted-foreground mt-0.5">
                      {meter.meter_number}
                    </p>
                  </div>
                  <Badge variant="outline" className={meter.architecture === "AMI" ? "border-sky-300 text-sky-700 dark:border-sky-700 dark:text-sky-400" : "dark:border-muted"}>
                    {meter.architecture}
                  </Badge>
                </div>
                <p className="mt-3 text-sm">
                  <span className="font-semibold tabular-nums">{meter.units.toFixed(2)}</span>
                  <span className="text-muted-foreground ml-1">kWh legacy snapshot</span>
                </p>
              </button>
            ))}
          </div>

          {selected && (
            <>
            <Card>
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <CardTitle>{selected.label || "Home"}</CardTitle>
                    <CardDescription className="font-mono mt-1">
                      {selected.meter_number}
                    </CardDescription>
                  </div>
                  <Badge
                    className={
                      selected.architecture === "AMI"
                        ? "bg-sky-500/10 text-sky-700 border-sky-200 dark:bg-sky-900/30 dark:text-sky-400 dark:border-sky-700"
                        : "bg-amber-500/10 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-400 dark:border-amber-700"
                    }
                  >
                    {selected.architecture === "AMI" ? (
                      <span className="flex items-center gap-1">
                        <Wifi className="h-3 w-3" /> AMI
                      </span>
                    ) : (
                      <span className="flex items-center gap-1">
                        <KeyRound className="h-3 w-3" /> STS
                      </span>
                    )}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid gap-3 sm:grid-cols-2">
                  <InfoTile
                    label="Legacy meter snapshot"
                    value={`${selected.units.toFixed(2)} kWh`}
                  />
                  <InfoTile
                    label={
                      selected.architecture === "AMI"
                        ? "Legacy pending snapshot"
                        : "Legacy pending units"
                    }
                    value={`${selected.pending_units.toFixed(2)} kWh`}
                  />
                  <InfoTile label="Status" value={selected.status} />
                  {selected.architecture === "AMI" && (
                    <InfoTile
                      label="Device token"
                      value={selected.has_iot_token ? "Configured" : "Not set"}
                    />
                  )}
                  {selected.static_ip && (
                    <InfoTile label="Static IP" value={selected.static_ip} mono />
                  )}
                  {selected.architecture === "AMI" && (
                    <InfoTile
                      label="Live balance (ThingsBoard)"
                      value={
                        checkingUnits
                          ? "Checking…"
                          : liveUnits != null
                          ? `${liveUnits.toFixed(2)} kWh`
                          : "—"
                      }
                      highlight
                      muted={liveUnits == null && !checkingUnits}
                    />
                  )}
                </div>

                {selected.architecture === "AMI" && selected.pending_units > 0 && (
                  <div className="rounded-lg border border-sky-200 bg-sky-50/80 px-4 py-3 text-sm text-sky-900 dark:border-sky-800 dark:bg-sky-900/20 dark:text-sky-200">
                    {selected.pending_units.toFixed(2)} kWh are queued for your meter. Delivery
                    retries automatically every few minutes and when you tap Check Units.
                  </div>
                )}

                {liveQueriedAt && (
                  <p className="text-xs text-muted-foreground">
                    Last checked: {new Date(liveQueriedAt).toLocaleString()}
                  </p>
                )}

                {selected.architecture === "STS" && (
                  <div className="rounded-lg border border-amber-200 bg-amber-50/80 px-4 py-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-200">
                    STS meters do not support remote balance checks. Read your remaining units
                    directly from the Customer Interface Unit (CIU) on your wall.
                  </div>
                )}

                {checkError && (
                  <p className="text-sm text-destructive">{checkError}</p>
                )}
                {actionMessage && (
                  <p className="text-sm text-green-700 dark:text-green-400">{actionMessage}</p>
                )}

                <div className="flex flex-wrap gap-3 pt-2">
                  <Button
                    variant="outline"
                    onClick={handleCheckUnits}
                    disabled={selected.architecture !== "AMI" || checkingUnits || !selected.has_iot_token}
                    className="gap-2"
                    title={
                      selected.architecture !== "AMI"
                        ? "Only available for AMI meters"
                        : !selected.has_iot_token
                        ? "Configure a ThingsBoard device token first"
                        : undefined
                    }
                  >
                    {checkingUnits ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Activity className="h-4 w-4" />
                    )}
                    Check Units
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => refreshMeters()}
                    title="Refresh meter list"
                  >
                    <RefreshCw className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    className="gap-2 text-destructive border-destructive/30 hover:bg-destructive/5"
                    onClick={() => setDeleteOpen(true)}
                  >
                    <Trash2 className="h-4 w-4" />
                    Remove meter
                  </Button>
                </div>

                <p className="text-xs text-muted-foreground">
                  New energy allocations and confirmed delivery are shown separately below.
                  Historical balances require reconciliation before delivery.
                </p>
              </CardContent>
            </Card>
            {selected.architecture === "AMI" ? (
              <EnergyStatusCard meterNo={selected.meter_number} />
            ) : (
              <p className="rounded-md border p-4 text-sm">STS keypad loading awaits a validated device protocol.</p>
            )}
            </>
          )}
        </div>
      )}

      <AddMeterDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        onSuccess={handleMeterAdded}
      />

      <AlertDialog open={deleteOpen} onOpenChange={(o) => !deleting && setDeleteOpen(o)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove meter from your account?</AlertDialogTitle>
            <AlertDialogDescription>
              {selected && (
                <>
                  Meter <span className="font-mono font-medium">{selected.meter_number}</span> will
                  be unlinked from your account. The meter number can be registered again later
                  (by you or another customer). A record is kept for audit purposes.
                </>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault();
                void handleDeleteMeter();
              }}
              disabled={deleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleting ? "Removing…" : "Remove meter"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function InfoTile({
  label,
  value,
  mono,
  highlight,
  muted,
}: {
  label: ReactNode;
  value: string;
  mono?: boolean;
  highlight?: boolean;
  muted?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border px-4 py-3 dark:border-white/10",
        highlight && "border-sky-200 bg-sky-50/50 dark:border-sky-800 dark:bg-sky-900/20"
      )}
    >
      <p className="text-xs text-muted-foreground">{label}</p>
      <p
        className={cn(
          "font-semibold mt-1 tabular-nums",
          mono && "font-mono text-sm",
          muted && "text-muted-foreground font-normal"
        )}
      >
        {value}
      </p>
    </div>
  );
}
