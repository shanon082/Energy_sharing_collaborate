"use client";

import { useCallback, useEffect, useState } from "react";
import { get } from "@/lib/fetch-client";
import { applyWalletUnits } from "@/app/(dashboard)/dashboard/share/actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getApiErrorMessage, toApiError } from "@/lib/api-response";

type EnergyStatus = {
  available_kwh: string;
  pending_kwh: string;
  confirmed_kwh: string;
  last_meter_contact: string | null;
  delivery_environment: "SIMULATOR" | "UNAVAILABLE";
};

export default function EnergyStatusCard({ meterNo }: { meterNo: string }) {
  const [status, setStatus] = useState<EnergyStatus | null>(null);
  const [amount, setAmount] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  const refresh = useCallback(async () => {
    const result = await get<EnergyStatus>(
      `meter/allocation-status/?meter_no=${encodeURIComponent(meterNo)}`
    );
    if (result.data) setStatus(result.data);
    else setError("Could not load allocation status.");
  }, [meterNo]);

  useEffect(() => { void refresh(); }, [refresh]);

  async function reserve() {
    const requested = Number(amount);
    if (!Number.isFinite(requested) || requested <= 0 ||
        !/^\d+(?:\.\d{1,2})?$/.test(amount)) {
      setError("Enter kWh in 0.01 increments.");
      return;
    }
    setPending(true);
    setError("");
    setMessage("");
    try {
      const result = await applyWalletUnits({ meter_no: meterNo, amount });
      if (result.data?.status === "QUEUED") {
        setMessage("Energy reserved for simulated delivery. Meter application is awaiting acknowledgement.");
        setAmount("");
        await refresh();
      } else {
        setError(getApiErrorMessage(toApiError(
          result.error, result.data?.message ?? "Delivery could not be queued."
        )));
      }
    } catch {
      setError("Delivery request could not be submitted.");
    } finally {
      setPending(false);
    }
  }

  const rows = [
    ["Available entitlement", status?.available_kwh],
    ["Reserved (pending or unresolved)", status?.pending_kwh],
    ["Confirmed applied", status?.confirmed_kwh],
  ];

  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Electricity allocation · {meterNo}</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-3">
          {rows.map(([label, value]) => (
            <div key={label} className="rounded-md border p-3">
              <p className="text-xs text-muted-foreground">{label}</p>
              <p className="text-lg font-semibold">{value ?? "—"} kWh</p>
            </div>
          ))}
        </div>
        <p className="text-sm text-muted-foreground">
          Last simulated meter contact: {status?.last_meter_contact
            ? new Date(status.last_meter_contact).toLocaleString() : "No contact yet"}
        </p>
        {status?.delivery_environment === "SIMULATOR" ? (
          <div className="flex flex-wrap items-center gap-2">
            <Input aria-label="kWh to reserve" type="number" step="0.01" min="0.01"
              value={amount} onChange={(event) => setAmount(event.target.value)}
              className="w-36" placeholder="kWh" />
            <Button type="button" disabled={pending} onClick={reserve}>Reserve for simulator</Button>
            <Button type="button" variant="outline" onClick={() => void refresh()}>Refresh</Button>
          </div>
        ) : (
          <p className="text-sm">Meter delivery is unavailable until an authenticated device protocol is approved.</p>
        )}
        {message && <p role="status" className="text-sm text-blue-700">{message}</p>}
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      </CardContent>
    </Card>
  );
}
