/** Currency-isolated test contract, shared by Next.js and Capacitor. */
export type SandboxCapabilities = { enabled: boolean; loans: boolean; purchases: boolean; repayments: boolean };
export const NO_SANDBOX: SandboxCapabilities = { enabled: false, loans: false, purchases: false, repayments: false };
export function sandboxCapabilities(raw: unknown): SandboxCapabilities {
  if (!raw || typeof raw !== "object") return { ...NO_SANDBOX };
  const row = raw as Record<string, unknown>;
  if (row.enabled !== true || row.currency !== "EUR" || row.provider !== "MTN_SANDBOX" || row.physical_delivery !== false) return { ...NO_SANDBOX };
  return { enabled: true, loans: row.loans === true, purchases: row.purchases === true, repayments: row.repayments === true };
}
export interface SandboxClient { get<T>(path: string): Promise<T>; post<T>(path: string, body: unknown): Promise<T> }
export type TestMeter = { id: number; meter_number: string; sandbox_inventory?: boolean };
export type Assessment = { eligible: boolean; reason: string; starter: boolean; score: number | null; profile_score: number | null;
  factors: Record<string, number> | null; purchase_points: number; qualifying_billed_eur: string; maximum: string; policy_id: string };
export type TestPolicy = { id: string; minimum: string; maximum: string; starter_limit: string; interest_percent: string; fee: string;
  rate_per_kwh: string; due_days: number; penalty_percent: string; rounding: string; purchase_per_point: string; purchase_score_cap: number; score_threshold: number };
export type TestTerms = { policy: TestPolicy; purpose: string; amount: string; energy_kwh: string; billed: string; residual: string;
  interest: string; fee: string; total_due: string; assessment: Assessment | null };
export type TestQuote = { id: string; terms_hash: string; expires_at: string; terms: TestTerms };
export type TestLoan = { id: string; client_request_id: string; meter_id: number; status: "DISBURSED" | "COMPLETED" | "REJECTED";
  reason: string; principal: string; total_due: string; outstanding: string; due_at: string; closed_at: string | null;
  allocation_id: number | null; allocated_kwh: string | null; terms: TestTerms; assessment: Assessment };
export type TestPayment = { reference: string; client_request_id: string; purpose: string; status: "PENDING" | "SETTLED" | "FAILED";
  amount: string; meter_id: number; loan_id: string | null; billed: string | null; residual: string | null; applied: string | null; excess: string | null;
  allocated_kwh: string | null; initiated_at: string; settled_at: string | null; submission_state: string; reconciliation_error: string; next_check_at: string };
const obj = (value: unknown): Record<string, unknown> => {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Unreadable sandbox response.");
  return value as Record<string, unknown>;
};
export function testAmount(value: string): boolean { return /^\d{1,5}(?:\.\d{1,2})?$/.test(value) && Number(value) > 0 && Number(value) <= 10000; }
export function testPhone(value: string): boolean { return /^\d{10,15}$/.test(value); }
export function parseTestPayment(value: unknown): TestPayment {
  const row = obj(value);
  if (row.currency !== "EUR" || row.environment !== "MTN_SANDBOX" || !["PENDING", "SETTLED", "FAILED"].includes(String(row.status)) ||
    !["PURCHASE", "LOAN_REPAYMENT"].includes(String(row.purpose)) || typeof row.reference !== "string" || !/^[0-9a-f-]{36}$/i.test(row.reference) ||
    typeof row.amount !== "string" || !/^\d+(?:\.\d+)?$/.test(row.amount) || !Number.isSafeInteger(row.meter_id)) throw new Error("Invalid sandbox receipt; no UGX conversion is available.");
  return row as unknown as TestPayment;
}
export function parseTestLoan(value: unknown): TestLoan {
  const row = obj(value);
  if (row.currency !== "EUR" || row.environment !== "MTN_SANDBOX" || !["DISBURSED", "COMPLETED", "REJECTED"].includes(String(row.status)) ||
    typeof row.id !== "string" || !Number.isSafeInteger(row.meter_id) || typeof row.outstanding !== "string" || !/^\d+(?:\.\d+)?$/.test(row.outstanding)) throw new Error("Invalid sandbox loan.");
  return row as unknown as TestLoan;
}
export function mergePayments(history: unknown[], pending: unknown[]): TestPayment[] {
  return [...new Map([...history, ...pending].map(value => { const row = parseTestPayment(value); return [row.reference, row] as const; })).values()];
}
/** Only non-secret retry handles. This same prefix is cleared by mobile logout. */
export function retryKey(owner: number, purpose: "LOAN" | "PURCHASE" | "LOAN_REPAYMENT"): string { return `gpawa:request:${owner}:sandbox:${purpose}`; }
export function readRetry(owner: number, purpose: "LOAN" | "PURCHASE" | "LOAN_REPAYMENT"): string | null {
  try { const value = localStorage.getItem(retryKey(owner, purpose)); return value && /^[0-9a-f-]{36}$/i.test(value) ? value : null; } catch { return null; }
}
export function writeRetry(owner: number, purpose: "LOAN" | "PURCHASE" | "LOAN_REPAYMENT", id: string | null): void {
  try { if (id) localStorage.setItem(retryKey(owner, purpose), id); else localStorage.removeItem(retryKey(owner, purpose)); } catch { /* No financial state is cached. */ }
}
