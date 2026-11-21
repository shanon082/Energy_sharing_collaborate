import type { TestCurrency, TestEnvironment } from "./sandbox";

export function meterReadEnvironment(environment: TestEnvironment | "CORE", energyEnvironment?: "SANDBOX"): "CORE" | "UGX_DEMO" | "SANDBOX" {
  if (energyEnvironment === "SANDBOX") return energyEnvironment;
  return environment === "MTN_SANDBOX" ? "SANDBOX" : environment;
}

const SCALE = BigInt(1_000_000);

function micros(value: string): bigint | null {
  if (!/^\d+(?:\.\d{1,6})?$/.test(value)) return null;
  const [whole, fraction = ""] = value.split(".");
  return BigInt(whole) * SCALE + BigInt(fraction.padEnd(6, "0"));
}

function decimal(value: bigint): string {
  const whole = value / SCALE;
  const fraction = String(value % SCALE).padStart(6, "0").replace(/0+$/, "");
  return fraction ? `${whole}.${fraction}` : String(whole);
}

export function exactSum(values: Array<string | null | undefined>): string | null {
  let total = BigInt(0);
  for (const value of values) {
    if (value == null) return null;
    const parsed = micros(value);
    if (parsed === null) return null;
    total += parsed;
  }
  return decimal(total);
}

export function exactDifference(total: string, applied: string): string | null {
  const left = micros(total), right = micros(applied);
  if (left === null || right === null || right > left) return null;
  return decimal(left - right);
}

export function formatMoney(value: string | null | undefined, currency: TestCurrency | "CORE"): string {
  if (value == null || !/^\d+(?:\.\d{1,6})?$/.test(value)) return "Unavailable";
  const [whole, fraction = ""] = value.split(".");
  const prefix = currency === "EUR" ? "EUR TEST" : "UGX";
  return `${prefix} ${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}${fraction.replace(/0+$/, "") ? `.${fraction.replace(/0+$/, "")}` : ""}`;
}

export function formatEnergy(value: string | null | undefined): string {
  if (value == null || !/^\d+(?:\.\d+)?$/.test(value) || !Number.isFinite(Number(value))) return "Unavailable";
  return `${Number(value).toLocaleString("en-UG", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} kWh`;
}
