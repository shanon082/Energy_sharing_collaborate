"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatEnergy, formatMoney, exactSum, meterReadEnvironment } from "@/lib/sandbox-presentation";
import type { SandboxClient, TestEnvironment, TestMeter } from "@/lib/sandbox";

type Environment = TestEnvironment | "CORE";
type Read<T> = { value: T | null; error: string | null; loading: boolean };
type MeterEnergy = {
  available: string;
  pending: string;
  confirmed: string;
  physicalWh: string | null;
  simulatorWh: string | null;
};

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Unexpected account response.");
  return value as Record<string, unknown>;
}

function decimal(value: unknown): string {
  if (typeof value !== "string" || !/^\d+(?:\.\d{1,6})?$/.test(value)) throw new Error("The balance is unavailable.");
  return value;
}

function userError(cause: unknown): string {
  return cause instanceof Error ? cause.message : "Couldn’t load this balance.";
}

export default function ConsumerWallet({ client, meters, environment }: {
  client: SandboxClient;
  meters: TestMeter[];
  environment: Environment;
}) {
  const [selectedId, setSelectedId] = useState("");
  const [cash, setCash] = useState<Read<string>>({ value: null, error: null, loading: true });
  const [debt, setDebt] = useState<Read<string>>({ value: null, error: null, loading: true });
  const [energy, setEnergy] = useState<Read<MeterEnergy>>({ value: null, error: null, loading: false });
  const meterRead = useRef(0);

  useEffect(() => {
    setSelectedId(previous => meters.some(meter => String(meter.id) === previous)
      ? previous : String(meters[0]?.id ?? ""));
  }, [meters]);

  const loadCash = useCallback(async () => {
    setCash(current => ({ ...current, loading: true, error: null }));
    try {
      const response = object(await client.get("wallet/balance/"));
      if (response.success !== true) throw new Error("Cash wallet is unavailable.");
      const wallet = object(response.wallet);
      if (wallet.currency !== "UGX") throw new Error("Cash wallet currency is unavailable.");
      setCash({ value: decimal(wallet.balance), error: null, loading: false });
    } catch (cause) {
      setCash({ value: null, error: userError(cause), loading: false });
    }
  }, [client]);

  const loadDebt = useCallback(async () => {
    setDebt(current => ({ ...current, loading: true, error: null }));
    try {
      const payload = object(await client.get(environment === "CORE" ? "loans/mobile-overview/" : "sandbox/loans/"));
      if (!Array.isArray(payload.loans)) throw new Error("Loan balance is unavailable.");
      const activeStatuses = new Set(["DISBURSED", "DEFAULTED"]);
      const rows = payload.loans.filter(value => {
        const row = object(value);
        return row.environment === undefined || row.environment === environment;
      });
      const balances = rows.flatMap(value => {
        const row = object(value);
        if (!activeStatuses.has(String(row.status))) return [];
        const balance = environment === "CORE" ? row.outstanding_ugx : row.outstanding;
        if (balance == null) throw new Error("An active loan balance is unavailable.");
        return [decimal(balance)];
      });
      const total = exactSum(balances);
      if (total === null) throw new Error("Loan balance is unavailable.");
      setDebt({ value: total, error: null, loading: false });
    } catch (cause) {
      setDebt({ value: null, error: userError(cause), loading: false });
    }
  }, [client, environment]);

  const loadEnergy = useCallback(async (meter: TestMeter | undefined) => {
    const read = ++meterRead.current;
    if (!meter) {
      setEnergy({ value: null, error: null, loading: false });
      return;
    }
    setEnergy({ value: null, error: null, loading: true });
    try {
      const query = new URLSearchParams({ environment: meterReadEnvironment(environment) }).toString();
      const response = object(await client.get(`meter/mobile-meters/${meter.id}/?${query}`));
      const record = object(response.meter);
      if (record.id !== meter.id || record.meter_number !== meter.meter_number) {
        throw new Error("Meter assignment changed. Refresh and select an assigned meter.");
      }
      const physicalWh = response.meter_reported_remaining_wh;
      const simulatorWh = response.simulator_remaining_wh;
      const parsed: MeterEnergy = {
        available: decimal(response.available_kwh),
        pending: decimal(response.pending_kwh),
        confirmed: decimal(response.confirmed_kwh),
        physicalWh: physicalWh == null ? null : decimal(physicalWh),
        simulatorWh: simulatorWh == null ? null : decimal(simulatorWh),
      };
      if (meterRead.current === read) setEnergy({ value: parsed, error: null, loading: false });
    } catch (cause) {
      if (meterRead.current === read) setEnergy({ value: null, error: userError(cause), loading: false });
    }
  }, [client, environment]);

  useEffect(() => { void loadCash(); void loadDebt(); }, [loadCash, loadDebt]);
  const selectedMeter = meters.find(meter => String(meter.id) === selectedId);
  useEffect(() => { void loadEnergy(selectedMeter); }, [loadEnergy, selectedMeter]);

  const currency = environment === "MTN_SANDBOX" ? "EUR" : "UGX";
  const money = (value: string | null) => formatMoney(value, currency);
  const physical = energy.value?.physicalWh == null
    ? "No meter reading yet"
    : formatEnergy(String(Number(energy.value.physicalWh) / 1000));
  const simulator = energy.value?.simulatorWh == null
    ? null
    : formatEnergy(String(Number(energy.value.simulatorWh) / 1000));

  return <section className="wallet-overview space-y-4" aria-label="Account balances">
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div><h2 className="text-xl font-semibold">Your balances</h2><p className="text-sm text-muted-foreground">Cash, cloud entitlement, loan debt and meter readings are shown separately.</p></div>
      <Button variant="outline" onClick={() => { void loadCash(); void loadDebt(); void loadEnergy(selectedMeter); }}>Refresh</Button>
    </div>
    {meters.length > 0 && <label className="block max-w-sm space-y-2 text-sm font-medium">Meter
      <select className="h-10 w-full rounded-md border bg-background px-3" value={selectedId} onChange={event => setSelectedId(event.target.value)}>
        {meters.map(meter => <option key={meter.id} value={meter.id}>{meter.meter_number}</option>)}
      </select>
    </label>}
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Card><CardHeader><CardDescription>Cash wallet · core UGX</CardDescription><CardTitle className="text-2xl">{cash.loading ? "Loading…" : cash.value === null ? "Unavailable" : formatMoney(cash.value, "CORE")}</CardTitle></CardHeader>
        <CardContent>{cash.error && <p className="text-sm text-destructive" role="alert">{cash.error} <button className="underline" onClick={() => void loadCash()}>Retry</button></p>}
          <p className="text-xs text-muted-foreground">Electricity purchases are not cash deposits.</p></CardContent></Card>
      <Card><CardHeader><CardDescription>Cloud electricity · {environment}</CardDescription>
        <CardTitle className="text-2xl">{energy.loading ? "Loading…" : energy.value ? formatEnergy(energy.value.available) : "Unavailable"}</CardTitle>
      </CardHeader><CardContent>{energy.error && <p className="text-sm text-destructive" role="alert">{energy.error} <button className="underline" onClick={() => void loadEnergy(selectedMeter)}>Retry</button></p>}
        {energy.value && <details><summary className="cursor-pointer text-sm">View breakdown</summary>
          <p className="mt-2 text-sm">Pending delivery reservation: {formatEnergy(energy.value.pending)}</p>
          <p className="text-sm">Applied in simulator: {formatEnergy(energy.value.confirmed)}</p>
        </details>}
      </CardContent></Card>
      <Card><CardHeader><CardDescription>Outstanding loan debt · {environment}</CardDescription><CardTitle className="text-2xl">
        {debt.loading ? "Loading…" : debt.value === null ? "Unavailable" : money(debt.value)}
      </CardTitle></CardHeader><CardContent>{debt.error && <p className="text-sm text-destructive" role="alert">{debt.error} <button className="underline" onClick={() => void loadDebt()}>Retry</button></p>}
        <p className="text-xs text-muted-foreground">Only active loans in this environment.</p></CardContent></Card>
      <Card><CardHeader><CardDescription>Physical meter balance</CardDescription><CardTitle className="text-2xl">{physical}</CardTitle></CardHeader>
        <CardContent>{energy.error && <p className="text-sm text-destructive" role="alert">{energy.error}</p>}
          {simulator && <p className="text-xs text-muted-foreground">Simulator-reported remaining: {simulator}. Not a physical meter reading.</p>}
        </CardContent></Card>
    </div>
  </section>;
}
