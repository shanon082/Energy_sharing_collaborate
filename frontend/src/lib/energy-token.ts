export type EnergyToken = {
  id: string; allocation_id: number; token: string; meter_number: string;
  energy_wh: string; energy_kwh: string; environment: "CORE" | "SANDBOX" | "UGX_DEMO";
  source: "PURCHASE" | "LOAN"; source_reference: string; state: "ISSUED" | "DELIVERY_PENDING" | "APPLIED";
  application_environment: "SOFTWARE_BENCH" | "UNCONFIRMED"; created_at: string;
};
export function parseEnergyTokens(value: unknown, allocationId?: number): EnergyToken[] {
  if (!value || typeof value !== "object" || !("tokens" in value) || !Array.isArray(value.tokens)) throw new Error("Token service returned an unreadable response.");
  return value.tokens.map((item: unknown) => {
    if (!item || typeof item !== "object") throw new Error("Invalid electricity token.");
    const row = item as Record<string, unknown>;
    if (typeof row.id !== "string" || !Number.isSafeInteger(row.allocation_id) ||
        (allocationId !== undefined && row.allocation_id !== allocationId) ||
        typeof row.token !== "string" || !/^[0-9]{15}$/.test(row.token) ||
        typeof row.meter_number !== "string" || typeof row.energy_wh !== "string" || !/^[0-9]+$/.test(row.energy_wh) ||
        typeof row.energy_kwh !== "string" || !/^[0-9]+(?:\.[0-9]+)?$/.test(row.energy_kwh) ||
        !["CORE", "SANDBOX", "UGX_DEMO"].includes(String(row.environment)) || !["PURCHASE", "LOAN"].includes(String(row.source)) ||
        typeof row.source_reference !== "string" || !["ISSUED", "DELIVERY_PENDING", "APPLIED"].includes(String(row.state)) ||
        (row.state === "APPLIED" && row.application_environment !== "SOFTWARE_BENCH")) throw new Error("Invalid electricity token or loading evidence.");
    return row as EnergyToken;
  });
}
export function tokenLoadingLabel(token: EnergyToken): string {
  return token.state === "APPLIED" ? "Units loaded on meter — software bench confirmation only." : "Awaiting meter confirmation.";
}
