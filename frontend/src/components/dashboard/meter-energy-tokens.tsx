"use client";
import { useEffect, useState } from "react";
import { get } from "@/lib/fetch-client";
import type { SandboxClient } from "../../lib/sandbox";
import { EnergyTokenCard } from "../energy-token-card";

const client: SandboxClient = {
  async get<T>(path: string): Promise<T> {
    const result = await get<T>(path);
    if (!result.data) throw new Error("Token service unavailable.");
    return result.data;
  },
  async post(): Promise<never> { throw new Error("Read-only token history."); },
};
export function MeterEnergyTokens({ meterNo }: { meterNo: string }) {
  const [selection, setSelection] = useState<{ number: string; owner: number; meter: number } | null>(null);
  useEffect(() => {
    let active = true;
    void Promise.all([client.get<{ id: number }>("auth/mobile-account/"),
      client.get<{ data: { meters: { id: number; meter_number: string }[] } }>("meter/mobile-meters/")])
      .then(([account, result]) => { const meter = result.data.meters.find(row => row.meter_number === meterNo);
        if (active && meter) setSelection({ number: meterNo, owner: account.id, meter: meter.id }); })
      .catch(() => { if (active) setSelection(null); });
    return () => { active = false; };
  }, [meterNo]);
  return selection?.number === meterNo ? <EnergyTokenCard client={client} owner={selection.owner} meterId={selection.meter} /> : null;
}
