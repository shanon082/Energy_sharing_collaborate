import type { TestEnvironment, TestMeter } from "./sandbox";

export type ConsumerScreen = "home" | "meters" | "loans" | "apply" | "purchase" | "activity" | "account";
export const CONSUMER_PATHS: Record<ConsumerScreen, string> = { home: "/dashboard", meters: "/dashboard/my-meters", loans: "/dashboard/loans", apply: "/dashboard/request-loan", purchase: "/dashboard/buy-units", activity: "/dashboard/transactions", account: "/dashboard/myaccount" };
export function consumerScreen(path: string, tab?: string | null): ConsumerScreen | null {
  if (path === "/dashboard/request-loan") return "apply";
  if (path === "/dashboard/loans" && tab === "apply") return "apply";
  if (path === "/dashboard/wallet") return "home";
  return (Object.keys(CONSUMER_PATHS) as ConsumerScreen[]).find(key => CONSUMER_PATHS[key] === path) ?? null;
}
export function defaultConsumerMeter(meters: TestMeter[], selected: string | null): TestMeter | null {
  if (selected !== null) return meters.find(meter => String(meter.id) === selected) ?? null;
  return meters.length === 1 ? meters[0] : null;
}
export function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Unreadable account response.");
  return value as Record<string, unknown>;
}
export function exactAmount(value: unknown): string {
  if (typeof value !== "string" || !/^\d+(?:\.\d{1,6})?$/.test(value)) throw new Error("This amount is unavailable.");
  return value;
}
export type ConsumerSummary = { owner_id: number; environment: TestEnvironment; currency: "UGX" | "EUR";
  scope: "OWNER"; meter_id: null; loan_count: number; active_loan_count: number;
  principal: string; total_due: string; applied_repayments: string; outstanding: string };
export function parseConsumerSummary(raw: unknown, owner: number, environment: TestEnvironment): ConsumerSummary {
  const row = record(raw);
  if (row.owner_id !== owner || row.environment !== environment || row.currency !== (environment === "UGX_DEMO" ? "UGX" : "EUR") ||
      row.scope !== "OWNER" || row.meter_id !== null || !Number.isSafeInteger(row.active_loan_count) || Number(row.active_loan_count) < 0 || !Number.isSafeInteger(row.loan_count) || Number(row.loan_count) < 0 || Number(row.active_loan_count) > Number(row.loan_count))
    throw new Error("The summary does not match this account and environment.");
  for (const key of ["principal", "total_due", "applied_repayments", "outstanding"]) exactAmount(row[key]);
  return row as ConsumerSummary;
}
/** Read tickets are also useful outside React, including delayed-response tests. */
export class ConsumerReadScope {
  private generation = 0;
  begin() { return ++this.generation; }
  current(ticket: number) { return ticket === this.generation; }
  invalidate() { this.generation++; }
}
