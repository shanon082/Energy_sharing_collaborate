/** Consumer read contracts; exact amounts are strings, never fallback balances. */
import type { MeterInfo } from "./contracts.ts";

export type Receipt = { external_id: string; purpose: string; status: string; amount_ugx: string;
  currency: string; meter_no: string | null; loan_id: string | null;
  purchase_billed_ugx: string | null; purchase_residual_ugx: string | null;
  repayment_applied_ugx: string | null; repayment_excess_ugx: string | null;
  environment: "SIMULATOR" | "PROVIDER" | "UNCONFIRMED"; settlement_recorded: boolean;
  allocated_energy_kwh: string | null; delivery_confirmed_kwh: string | null;
  initiated_at: string; settled_at: string | null };
export type Notice = { id: number; message: string; occurred_at: string; is_read: boolean; meter_no: string | null };
export type HistoryRow = { id: number; transaction_type_display: string; status: string;
  recorded_amount: string | null; recorded_units: string | null; created_at: string };
export type Delivery = { id: number; command_id: string; request_id: string | null;
  amount_kwh: string; status: string; created_at: string; applied_at: string | null;
  application_confirmed: boolean; environment: string; source: string };
export type Page<T> = { rows: T[]; next: number | null };

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Unexpected activity response.");
  return value as Record<string, unknown>;
}
function text(value: unknown): string {
  if (typeof value !== "string") throw new Error("Invalid activity text.");
  return value;
}
function nullableText(value: unknown): string | null { return value === null ? null : text(value); }
function decimal(value: unknown, signed = false): string {
  const result = text(value);
  if (!(signed ? /^-?\d+(?:\.\d+)?$/ : /^\d+(?:\.\d+)?$/).test(result)) throw new Error("Invalid recorded amount.");
  return result;
}
function nullableDecimal(value: unknown, signed = false): string | null {
  return value === null ? null : decimal(value, signed);
}
function id(value: unknown): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value <= 0) throw new Error("Invalid record identity.");
  return value;
}
function boolean(value: unknown): boolean {
  if (typeof value !== "boolean") throw new Error("Invalid activity state.");
  return value;
}
function page<T>(payload: unknown, key: string, parse: (value: unknown) => T): Page<T> {
  const data = object(payload), paging = object(data.pagination);
  if (!Array.isArray(data[key])) throw new Error("Activity records unavailable.");
  const hasMore = boolean(paging.has_more);
  const next = paging.next_before_id === null ? null : id(paging.next_before_id);
  if (hasMore !== (next !== null)) throw new Error("Invalid activity pagination.");
  return { rows: data[key].map(parse), next };
}
export function parseReceipt(value: unknown): Receipt {
  const row = object(value);
  const status = text(row.status), purpose = text(row.purpose), environment = text(row.environment);
  if (!["PENDING", "FAILED", "SETTLED"].includes(status) || !["PURCHASE", "LOAN_REPAYMENT"].includes(purpose)
      || !["SIMULATOR", "PROVIDER", "UNCONFIRMED"].includes(environment) || row.currency !== "UGX") {
    throw new Error("Receipt contract is unavailable.");
  }
  const settled = boolean(row.settlement_recorded), settledAt = nullableText(row.settled_at);
  if (settled && (status !== "SETTLED" || !settledAt)) throw new Error("Receipt settlement evidence is incomplete.");
  return { external_id: text(row.external_id), purpose, status, amount_ugx: decimal(row.amount_ugx),
    currency: "UGX", meter_no: nullableText(row.meter_no), loan_id: nullableText(row.loan_id),
    purchase_billed_ugx: nullableDecimal(row.purchase_billed_ugx),
    purchase_residual_ugx: nullableDecimal(row.purchase_residual_ugx),
    repayment_applied_ugx: nullableDecimal(row.repayment_applied_ugx),
    repayment_excess_ugx: nullableDecimal(row.repayment_excess_ugx),
    environment: environment as Receipt["environment"], settlement_recorded: settled,
    allocated_energy_kwh: row.allocated_energy_kwh == null ? null : decimal(row.allocated_energy_kwh),
    delivery_confirmed_kwh: row.delivery_confirmed_kwh == null ? null : decimal(row.delivery_confirmed_kwh),
    initiated_at: text(row.initiated_at), settled_at: settledAt };
}
export function parseReceipts(payload: unknown): Page<Receipt> { return page(payload, "receipts", parseReceipt); }
export function parseNotices(payload: unknown): Page<Notice> {
  return page(payload, "notifications", (value) => {
    const row = object(value);
    return { id: id(row.id), message: text(row.message), occurred_at: text(row.occurred_at),
      is_read: boolean(row.is_read), meter_no: nullableText(row.meter_no) };
  });
}
export function parseHistory(payload: unknown): Page<HistoryRow> {
  return page(payload, "transactions", (value) => {
    const row = object(value);
    if (row.source !== "TRANSACTION_LOG" || row.units_confirmed !== false) throw new Error("Unsupported history source.");
    return { id: id(row.id), transaction_type_display: text(row.transaction_type_display),
      status: text(row.status), recorded_amount: nullableDecimal(row.recorded_amount, true),
      recorded_units: nullableDecimal(row.recorded_units, true), created_at: text(row.created_at) };
  });
}
export function parseDeliveries(payload: unknown, meter: MeterInfo): Page<Delivery> {
  const data = object(payload), selected = object(data.meter);
  if (selected.id !== meter.id || selected.meter_number !== meter.meter_number || data.meter_no !== meter.meter_number) {
    throw new Error("Delivery belongs to a different meter.");
  }
  return page(payload, "deliveries", (value) => {
    const row = object(value), status = text(row.status), confirmed = boolean(row.application_confirmed);
    const appliedAt = nullableText(row.applied_at);
    if (!["QUEUED", "DISPATCHED", "APPLIED", "FAILED", "EXPIRED", "OUTCOME_UNKNOWN"].includes(status)
        || (confirmed && (status !== "APPLIED" || !appliedAt))) throw new Error("Invalid delivery evidence.");
    return { id: id(row.id), command_id: text(row.command_id), request_id: nullableText(row.request_id),
      amount_kwh: decimal(row.amount_kwh), status, created_at: text(row.created_at), applied_at: appliedAt,
      application_confirmed: confirmed, environment: text(row.environment), source: text(row.source) };
  });
}
