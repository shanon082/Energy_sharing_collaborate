"use client";

import { useState } from "react";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import EnergyStatusCard from "@/components/dashboard/energy-status-card";
import { useSelectedMeter } from "@/contexts/selected-meter-context";

export default function AllocationLoadClient({ onBack }: { onBack: () => void }) {
  const { meters, isLoading } = useSelectedMeter();
  const [meterNo, setMeterNo] = useState("");
  const selected = meters.find((meter) => meter.meter_number === meterNo);

  return (
    <div className="mx-auto max-w-3xl space-y-4 px-2 py-4">
      <Button type="button" variant="outline" onClick={onBack} className="gap-2">
        <ArrowLeft className="h-4 w-4" /> Back
      </Button>
      <h2 className="text-xl font-semibold">Load your own meter</h2>
      <p className="text-sm text-muted-foreground">
        Choose the intended AMI meter. Only verified purchases and disbursed loans
        linked to that meter can be reserved for simulated delivery.
      </p>
      <label htmlFor="allocation-meter" className="block text-sm font-medium">Meter</label>
      <select id="allocation-meter" value={meterNo} onChange={(event) => setMeterNo(event.target.value)}
        disabled={isLoading} className="w-full rounded-md border border-input bg-background px-3 py-2">
        <option value="">Choose a meter</option>
        {meters.filter((meter) => meter.status === "ACTIVE").map((meter) => (
          <option key={meter.meter_number} value={meter.meter_number}>
            {meter.label} ({meter.meter_number}, {meter.architecture})
          </option>
        ))}
      </select>
      {!isLoading && meters.length === 0 && (
        <p className="text-sm">Register a meter under My Meters first.</p>
      )}
      {selected?.architecture === "AMI" && <EnergyStatusCard meterNo={selected.meter_number} />}
      {selected?.architecture === "STS" && (
        <p className="rounded-md border p-4 text-sm">
          STS keypad loading awaits a validated device protocol. Historical tokens remain available in history.
        </p>
      )}
    </div>
  );
}
