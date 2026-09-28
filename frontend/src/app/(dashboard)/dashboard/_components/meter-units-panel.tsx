"use client";

import { useSelectedMeter } from "@/contexts/selected-meter-context";
import MeterSelector from "./meter-selector";
import GenerateTokenCard from "../tokens/_components/generate-token-card";
import AmiStatusCard from "./ami-status-card";

export default function MeterUnitsPanel() {
  const { selectedMeter, meters, isLoading, walletBalance, refreshWallet } = useSelectedMeter();

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
        <GenerateTokenCard
          architecture="STS"
          walletBalance={walletBalance}
          meterNo={selectedMeter.meter_number}
          stsMeters={meters.filter((m) => m.architecture === "STS")}
          onTokenGenerated={() => {
            /* wallet balance will refresh on next navigation; optional future hook */
          }}
        />
      ) : (
        <AmiStatusCard
          meter={selectedMeter}
          walletBalance={walletBalance}
          onApplied={refreshWallet}
        />
      )}
    </div>
  );
}
