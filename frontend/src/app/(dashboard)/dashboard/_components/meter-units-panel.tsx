"use client";

import { useSelectedMeter } from "@/contexts/selected-meter-context";
import MeterSelector from "./meter-selector";
import EnergyStatusCard from "@/components/dashboard/energy-status-card";

export default function MeterUnitsPanel() {
  const { selectedMeter, meters, isLoading } = useSelectedMeter();

  if (isLoading) {
    return (
      <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
        Loading meter details...
      </div>
    );
  }

  if (!selectedMeter || meters.length === 0) {
    return null;
  }

  return (
    <div className="space-y-4">
      <MeterSelector />
      {selectedMeter.architecture === "STS" ? (
        <p className="rounded-md border p-4 text-sm">STS keypad loading awaits an authenticated, validated device protocol.</p>
      ) : (
        <EnergyStatusCard meterNo={selectedMeter.meter_number} />
      )}
    </div>
  );
}
