"use client";

import { Suspense, useEffect, useState } from "react";
import TokenList from "./tokenslist";
import GenerateTokenCard from "./generate-token-card";
import AmiStatusCard from "../../_components/ami-status-card";
import MeterSelector from "../../_components/meter-selector";
import { useSelectedMeter } from "@/contexts/selected-meter-context";
import { get } from "@/lib/fetch-client";
import { Token } from "@/interface/token.interface";

interface TokensPageClientProps {
  initialTokens: Token[];
}

export default function TokensPageClient({ initialTokens }: TokensPageClientProps) {
  const { selectedMeter, meters, isLoading } = useSelectedMeter();
  const [unitBalance, setUnitBalance] = useState(0);
  const [tokens, setTokens] = useState(initialTokens);

  useEffect(() => {
    async function loadWallet() {
      try {
        const res = await get<any>("wallet/balance");
        if (!res.error && res.data?.success) {
          // Get unit_balance.balance for units (kWh)
          const bal = parseFloat(
            res.data?.unit_balance?.balance ?? res.data?.unit_balance ?? "0"
          );
          setUnitBalance(Number.isFinite(bal) ? bal : 0);
        }
      } catch {
        setUnitBalance(0);
      }
    }
    loadWallet();
  }, [selectedMeter?.meter_number]);

  async function refreshWallet() {
    try {
      const res = await get<any>("wallet/balance");
      if (!res.error && res.data?.success) {
        // Get unit_balance.balance for units (kWh)
        const bal = parseFloat(
          res.data?.unit_balance?.balance ?? res.data?.unit_balance ?? "0"
        );
        setUnitBalance(Number.isFinite(bal) ? bal : 0);
      }
    } catch {
      /* keep current balance */
    }
  }

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
            ? "AMI meters sync balance over the network — no tokens required"
            : "Generate and manage STS meter tokens"}
        </p>
      </div>

      {hasMeter && !isLoading && selectedMeter && (
        <div className="space-y-4">
          <MeterSelector />
          {selectedMeter.architecture === "STS" ? (
            <GenerateTokenCard
              architecture="STS"
              unitBalance={unitBalance}
              meterNo={selectedMeter.meter_number}
              stsMeters={meters.filter((m) => m.architecture === "STS")}
              onTokenGenerated={refreshWallet}
            />
          ) : (
            <AmiStatusCard
              meter={selectedMeter}
              unitBalance={unitBalance}
              onApplied={refreshWallet}
            />
          )}
        </div>
      )}

      {!hasMeter && !isLoading && (
        <div className="rounded-lg border border-dashed p-8 text-center text-muted-foreground">
          Register a meter first to generate tokens.
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