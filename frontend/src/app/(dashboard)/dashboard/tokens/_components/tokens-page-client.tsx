"use client";

import { Suspense, useEffect, useState } from "react";
import TokenList from "./tokenslist";
import EnergyStatusCard from "@/components/dashboard/energy-status-card";
import MeterSelector from "../../_components/meter-selector";
import { useSelectedMeter } from "@/contexts/selected-meter-context";
import { get } from "@/lib/fetch-client";
import { Token } from "@/interface/token.interface";

interface TokensPageClientProps {
  initialTokens: Token[];
}

export default function TokensPageClient({ initialTokens }: TokensPageClientProps) {
  const { selectedMeter, meters, isLoading } = useSelectedMeter();
  const [tokens, setTokens] = useState(initialTokens);

  useEffect(() => {
    async function loadTokens() {
      if (!selectedMeter) return;
      try {
        const res = await get<any>(
          `meter/token/?meter_no=${encodeURIComponent(selectedMeter.meter_number)}`
        );
        if (!res.error) {
          const list = Array.isArray(res.data?.data)
            ? res.data.data
            : res.data?.results ?? [];
          setTokens(list);
        }
      } catch {
        setTokens([]);
      }
    }
    loadTokens();
  }, [selectedMeter?.meter_number]);

  const hasMeter = meters.length > 0;

  return (
    <>
      <div>
        <h1 className="text-lg font-semibold md:text-2xl">Tokens</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {selectedMeter?.architecture === "AMI"
            ? "Review simulated delivery and historical token records"
            : "Historical STS tokens remain visible; new keypad issuance is paused"}
        </p>
      </div>

      {hasMeter && !isLoading && selectedMeter && (
        <div className="space-y-4">
          <MeterSelector />
          {selectedMeter.architecture === "STS" ? (
            <p className="rounded-md border p-4 text-sm">New STS tokens require a validated device protocol. Historical tokens remain listed below.</p>
          ) : (
            <EnergyStatusCard meterNo={selectedMeter.meter_number} />
          )}
        </div>
      )}

      {!hasMeter && !isLoading && (
        <div className="rounded-lg border border-dashed p-8 text-center text-muted-foreground">
          Register a meter to view its delivery status and historical tokens.
        </div>
      )}

      <div className="flex min-w-0 flex-1 justify-center rounded-lg border border-dashed shadow-sm">
        <div className="flex min-w-0 flex-col gap-1 w-full">
          <Suspense fallback={<div className="p-4">Loading tokens...</div>}>
            <TokenList tokens={tokens} />
          </Suspense>
        </div>
      </div>
    </>
  );
}
