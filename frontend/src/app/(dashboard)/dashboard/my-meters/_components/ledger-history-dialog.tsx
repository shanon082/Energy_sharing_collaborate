"use client";

import { useEffect, useState, type KeyboardEvent, type MouseEvent } from "react";
import { Loader2, ScrollText } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { get } from "@/lib/fetch-client";
import { getApiErrorMessage } from "@/lib/api-response";
import type { UserMeter } from "@/interface/meter.interface";

export type MeterLedgerEvent = {
  id: string;
  transaction_type: string;
  label: string;
  amount_kwh: number;
  status: string;
  channel: string;
  source: string;
  destination: string;
  payment_reference: string;
  created_at: string | null;
};

export type MeterLedgerHistory = {
  success?: boolean;
  meter_no?: string;
  units_balance_kwh?: number;
  pending_delivery_kwh?: number;
  events_total_kwh?: number;
  events?: MeterLedgerEvent[];
  note?: string | null;
  error?: string;
};

interface LedgerHistoryDialogProps {
  meter: UserMeter | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export default function LedgerHistoryDialog({
  meter,
  open,
  onOpenChange,
}: LedgerHistoryDialogProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [history, setHistory] = useState<MeterLedgerHistory | null>(null);

  useEffect(() => {
    if (!open || !meter) {
      setHistory(null);
      setError("");
      return;
    }

    let cancelled = false;
    (async () => {
      setLoading(true);
      setError("");
      try {
        const res = await get<MeterLedgerHistory>(
          `meter/ledger-history/?meter_no=${encodeURIComponent(meter.meter_number)}`
        );
        if (cancelled) return;
        if (!res.error && res.data?.success) {
          setHistory(res.data);
        } else {
          setHistory(null);
          setError(getApiErrorMessage(res.error, res.data?.error ?? "Could not load ledger history."));
        }
      } catch {
        if (!cancelled) {
          setError("Network error while loading ledger history.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [open, meter?.meter_number]);

  if (!meter) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ScrollText className="h-5 w-5 text-primary" />
            Ledger history
          </DialogTitle>
          <DialogDescription>
            {meter.label && meter.label !== "Home" ? `${meter.label} · ` : ""}
            <span className="font-mono">{meter.meter_number}</span>
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-12 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin mr-2" />
            Loading ledger events…
          </div>
        ) : error ? (
          <p className="text-sm text-destructive py-4">{error}</p>
        ) : history ? (
          <div className="space-y-4 overflow-y-auto min-h-0 flex-1">
            <div className="grid gap-3 sm:grid-cols-2 rounded-lg border bg-muted/30 p-4 text-sm">
              <div>
                <p className="text-xs text-muted-foreground">Ledger balance</p>
                <p className="font-semibold tabular-nums mt-0.5">
                  {(history.units_balance_kwh ?? meter.units).toFixed(2)} kWh
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Recorded credits</p>
                <p className="font-semibold tabular-nums mt-0.5">
                  {(history.events_total_kwh ?? 0).toFixed(2)} kWh
                </p>
              </div>
            </div>

            {history.note && (
              <p className="text-xs text-amber-800/90 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                {history.note}
              </p>
            )}

            {!history.events?.length ? (
              <p className="text-sm text-muted-foreground text-center py-6">
                No ledger events recorded yet. Loads and shares will appear here.
              </p>
            ) : (
              <ul className="divide-y rounded-lg border overflow-hidden">
                {history.events.map((event) => (
                  <li key={event.id} className="px-4 py-3 text-sm bg-card">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-medium">{event.label}</p>
                        {event.source && (
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {event.transaction_type === "TRANSFER_IN"
                              ? `From meter ${event.source}`
                              : event.source}
                          </p>
                        )}
                        {event.created_at && (
                          <p className="text-xs text-muted-foreground mt-1">
                            {new Date(event.created_at).toLocaleString()}
                          </p>
                        )}
                      </div>
                      <p className="font-semibold tabular-nums text-green-700 shrink-0">
                        +{event.amount_kwh.toFixed(2)} kWh
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

export function LedgerLink({
  className,
  onClick,
}: {
  className?: string;
  onClick: (e: MouseEvent) => void;
}) {
  const handleKeyDown = (e: KeyboardEvent<HTMLSpanElement>) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onClick(e as unknown as MouseEvent);
    }
  };

  return (
    <span
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={handleKeyDown}
      className={
        className ??
        "text-muted-foreground underline-offset-2 hover:underline hover:text-primary focus:outline-none focus-visible:underline"
      }
      title="View ledger history"
    >
      ledger
    </span>
  );
}
