export const ALLOCATION_LEDGERS = ["SANDBOX", "UGX_DEMO", "CORE"] as const;
export function readLedgerBalance(raw: unknown, meterId: number) {
  if (!raw || typeof raw !== "object" || !("meter" in raw) || !raw.meter || typeof raw.meter !== "object" || !("id" in raw.meter) || raw.meter.id !== meterId)
    throw new Error("Meter assignment changed; refresh your meters.");
  const row = raw as Record<string, unknown>;
  const exact = (key: string) => {
    const value = row[key];
    if (typeof value !== "string" || !/^\d+(?:\.\d+)?$/.test(value)) throw new Error("Balance unavailable.");
    return value;
  };
  return { available: exact("available_kwh"), pending: exact("pending_kwh"), confirmed: exact("confirmed_kwh") };
}
