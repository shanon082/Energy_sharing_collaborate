/** Currency-isolated test contract, shared by Next.js and Capacitor. */
export type TestCurrency = "EUR" | "UGX";
export type TestEnvironment = "MTN_SANDBOX" | "UGX_DEMO";
export type SandboxCapabilities = { enabled: boolean; loans: boolean; purchases: boolean; repayments: boolean; currency?: TestCurrency; environment?: TestEnvironment; provider?: "MTN_SANDBOX" | "LOCAL_DEMO" };
export const NO_SANDBOX: SandboxCapabilities = { enabled: false, loans: false, purchases: false, repayments: false };
export function sandboxCapabilities(raw: unknown): SandboxCapabilities {
  if (!raw || typeof raw !== "object") return { ...NO_SANDBOX };
  const row = raw as Record<string, unknown>;
  const demo = row.currency === "UGX" && row.environment === "UGX_DEMO" && row.provider === "LOCAL_DEMO";
  const mtn = row.currency === "EUR" && row.provider === "MTN_SANDBOX" && (row.environment === undefined || row.environment === "MTN_SANDBOX");
  if (row.enabled !== true || (!demo && !mtn) || row.physical_delivery !== false) return { ...NO_SANDBOX };
  return { enabled: true, loans: row.loans === true, purchases: row.purchases === true, repayments: row.repayments === true, ...(demo ? { currency: "UGX", environment: "UGX_DEMO", provider: "LOCAL_DEMO" } as const : {}) };
}
export interface SandboxClient { get<T>(path: string): Promise<T>; post<T>(path: string, body: unknown): Promise<T> }
export type TestMeter = { id: number; meter_number: string; sandbox_inventory?: boolean };
export type Assessment = { owner_id?: number; meter_id?: number | null; minimum_score?: number; assessment_id?: number | null; evidence_updated_at?: string | null; eligible: boolean; reason: string; starter: boolean; score: number | null; profile_score: number | null;
  factors: Record<string, number> | null; purchase_points: number | null; qualifying_billed_eur?: string; qualifying_billed_test?: string | null; maximum: string | null; policy_id: string;
  assessment_status?: "PENDING" | "READY" | "UNAVAILABLE"; label?: string; provider?: string; assessed_at?: string | null; scoring_policy_version?: string; categories?: Record<string, string> | null };
export type TestPolicy = { id: string; currency?: TestCurrency; environment?: TestEnvironment; minimum: string; maximum: string; starter_limit: string; interest_percent: string; fee: string;
  rate_per_kwh: string | null; pricing_source?: string; due_days: number; penalty_percent: string; rounding: string; purchase_per_point: string; purchase_score_cap: number; score_threshold: number };
export type PricingStatus = { available: boolean; message: string; revision?: string; tariff_code?: string };
export type TariffPricing = { inputs_hash: string; inputs: { version: string; month: string; scope: string; vat_rate: string;
  tariff: { id: number; code: string; name: string }; monthly_purchased_kwh: string }; breakdown: {
  energy_cost: string; service_charge: string; subtotal: string; vat: string; total: string; lifeline_applied: boolean } };
export type TestTerms = { pricing?: TariffPricing; owner_id?: number; meter_id?: number; policy: TestPolicy; purpose: string; amount: string; energy_kwh: string; billed: string; residual: string;
  interest: string; fee: string; total_due: string; assessment: Assessment | null };
export type TestQuote = { id: string; terms_hash: string; expires_at: string; terms: TestTerms };
export type TestLoan = { currency: TestCurrency; environment: TestEnvironment; id: string; client_request_id: string; meter_id: number; status: "DISBURSED" | "COMPLETED" | "REJECTED";
  reason: string; principal: string; total_due: string; outstanding: string; due_at: string; closed_at: string | null;
  allocation_id: number | null; allocated_kwh: string | null; terms: TestTerms; assessment: Assessment };
export type TestPayment = { pricing?: TariffPricing; currency: TestCurrency; environment: TestEnvironment; provider?: "MTN_SANDBOX" | "LOCAL_DEMO";
  demo_eligible_at?: string | null; server_time?: string; observed_at?: number; reference: string; client_request_id: string; purpose: string; status: "PENDING" | "SETTLED" | "FAILED";
  amount: string; meter_id: number; loan_id: string | null; billed: string | null; residual: string | null; applied: string | null; excess: string | null;
  allocation_id?: number | null; allocated_kwh: string | null; initiated_at: string; settled_at: string | null; submission_state: string; reconciliation_error: string; next_check_at: string };
const obj = (value: unknown): Record<string, unknown> => {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Unreadable sandbox response.");
  return value as Record<string, unknown>;
};
/** Reject unavailable evidence masquerading as a real zero or an established score. */
export function parseStoredDemoAssessment(value: unknown, expected?: { owner: number; meterId: number | null }): Assessment {
  const row = obj(value);
  const ready = row.assessment_status === "READY";
  if (expected && (row.owner_id !== expected.owner || row.meter_id !== expected.meterId))
    throw new Error("Assessment does not belong to the selected meter/account.");
  if (!["READY", "PENDING", "UNAVAILABLE"].includes(String(row.assessment_status)) ||
    row.provider !== "SIMULATED_ACCOUNT_V1" || row.input_source !== "SIMULATED_ACCOUNT_INFORMATION" ||
    row.currency !== "UGX" || row.environment !== "UGX_DEMO" || typeof row.reason !== "string" ||
    typeof row.eligible !== "boolean" || typeof row.scoring_policy_version !== "string")
    throw new Error("Demo assessment evidence is unavailable.");
  if (ready) {
    if (!Number.isInteger(row.score) || Number(row.score) < 0 || Number(row.score) > 100 ||
      !Number.isInteger(row.profile_score) || !Number.isInteger(row.purchase_points) ||
      typeof row.maximum !== "string" || !/^\d+$/.test(row.maximum) ||
      typeof row.assessed_at !== "string" || !Number.isFinite(Date.parse(row.assessed_at)) ||
      !row.factors || typeof row.factors !== "object" || Array.isArray(row.factors))
      throw new Error("Completed demo assessment evidence is invalid.");
  } else if (row.score !== null || row.profile_score !== null || row.maximum !== null || row.eligible !== false || row.factors !== null)
    throw new Error("Pending demo assessment must not invent a score or allowance.");
  return row as unknown as Assessment;
}
export function testAmount(value: string): boolean { return /^\d{1,5}(?:\.\d{1,2})?$/.test(value) && Number(value) > 0 && Number(value) <= 10000; }
export function testDemoAmount(value: string): boolean { return /^[0-9]{1,7}$/.test(value) && Number(value) > 0 && Number(value) <= 1000000; }
export function testMoney(value: string | null | undefined, currency: TestCurrency = "EUR"): string {
  return value === null || value === undefined ? "Unavailable" : `${currency === "UGX" ? "UGX DEMO" : "EUR TEST"} ${value}`;
}
function validDomain(row: Record<string, unknown>): boolean {
  return (row.currency === "EUR" && row.environment === "MTN_SANDBOX") ||
    (row.currency === "UGX" && row.environment === "UGX_DEMO");
}
/** Countdown is presentation only. Completion must return a server SETTLED receipt. */
export function demoCountdown(row: TestPayment, now = Date.now()): number | null {
  if (row.environment !== "UGX_DEMO" || row.status !== "PENDING" || !row.server_time || !row.demo_eligible_at || row.observed_at === undefined) return null;
  return Math.max(0, Math.ceil((Date.parse(row.demo_eligible_at) - Date.parse(row.server_time) - Math.max(0, now - row.observed_at)) / 1000));
}
export function testPhone(value: string): boolean { return /^\d{10,15}$/.test(value); }
export function parseTestPayment(value: unknown): TestPayment {
  const row = obj(value);
  if (!validDomain(row) || !["PENDING", "SETTLED", "FAILED"].includes(String(row.status)) ||
    !["PURCHASE", "LOAN_REPAYMENT"].includes(String(row.purpose)) || typeof row.reference !== "string" || !/^[0-9a-f-]{36}$/i.test(row.reference) ||
    typeof row.amount !== "string" || !/^\d+(?:\.\d+)?$/.test(row.amount) || !Number.isSafeInteger(row.meter_id)) throw new Error("Invalid sandbox receipt; no UGX conversion is available.");
  if (row.environment === "UGX_DEMO" && (row.provider !== "LOCAL_DEMO" ||
    !/^[0-9]+(?:\.0+)?$/.test(row.amount as string) || Number(row.amount) > 1000000 || Number(row.amount) <= 0 || typeof row.server_time !== "string" || !Number.isFinite(Date.parse(row.server_time)) ||
    typeof row.demo_eligible_at !== "string" || !Number.isFinite(Date.parse(row.demo_eligible_at)) ||
    typeof row.initiated_at !== "string" || !Number.isFinite(Date.parse(row.initiated_at)) || Date.parse(row.demo_eligible_at) - Date.parse(row.initiated_at) < 5000))
    throw new Error("Invalid demo receipt or authorization deadline.");
  return { ...row, observed_at: Date.now() } as TestPayment;
}
function canonicalMoney(value: string): string {
  const [whole, fraction = ""] = value.split(".");
  const tail = fraction.replace(/0+$/, "");
  return whole.replace(/^0+(?=\d)/, "") + (tail ? `.${tail}` : "");
}
/** Validate accepted terms against this account, destination and exact request. */
export function parseTestQuote(value: unknown, expected: { owner: number; meterId: number; amount: string;
  purpose: "LOAN" | "PURCHASE"; currency: TestCurrency; environment: TestEnvironment }): TestQuote {
  const row = obj(value), terms = obj(row.terms), policy = obj(terms.policy);
  if (typeof row.id !== "string" || !/^[0-9a-f-]{36}$/i.test(row.id) ||
    typeof row.terms_hash !== "string" || !/^[0-9a-f]{64}$/i.test(row.terms_hash) ||
    typeof row.expires_at !== "string" || !Number.isFinite(Date.parse(row.expires_at)) ||
    terms.owner_id !== expected.owner || terms.meter_id !== expected.meterId || terms.purpose !== expected.purpose ||
    typeof terms.amount !== "string" || !/^\d+(?:\.\d+)?$/.test(terms.amount) ||
    canonicalMoney(terms.amount) !== canonicalMoney(expected.amount) ||
    policy.currency !== expected.currency || (policy.environment ?? "MTN_SANDBOX") !== expected.environment ||
    typeof policy.id !== "string" || !["energy_kwh", "billed", "residual", "interest", "fee", "total_due"].every(
      field => typeof terms[field] === "string" && /^\d+(?:\.\d+)?$/.test(terms[field] as string)))
    throw new Error("Quote does not match your account, meter, amount or test currency. Request fresh terms.");
  return row as unknown as TestQuote;
}
export function assertTestPaymentBinding(row: TestPayment, expected: {
  reference?: string; client_request_id: string; purpose: string; amount: string; meter_id: number;
  loan_id: string | null; currency: TestCurrency; environment: TestEnvironment;
}): void {
  if ((expected.reference !== undefined && row.reference !== expected.reference) ||
    row.client_request_id !== expected.client_request_id || row.purpose !== expected.purpose ||
    canonicalMoney(row.amount) !== canonicalMoney(expected.amount) || row.meter_id !== expected.meter_id ||
    row.loan_id !== expected.loan_id || row.currency !== expected.currency || row.environment !== expected.environment)
    throw new Error("Payment response does not match this request. Refresh to recover its stored outcome.");
}
export function parseTestLoan(value: unknown): TestLoan {
  const row = obj(value);
  if (!validDomain(row) || !["DISBURSED", "COMPLETED", "REJECTED"].includes(String(row.status)) ||
    typeof row.id !== "string" || !Number.isSafeInteger(row.meter_id) || typeof row.outstanding !== "string" || !/^\d+(?:\.\d+)?$/.test(row.outstanding)) throw new Error("Invalid sandbox loan.");
  return row as unknown as TestLoan;
}
export function mergePayments(history: unknown[], pending: unknown[]): TestPayment[] {
  return [...new Map([...history, ...pending].map(value => { const row = parseTestPayment(value); return [row.reference, row] as const; })).values()];
}
/** Only non-secret retry handles. This same prefix is cleared by mobile logout. */
export function retryKey(owner: number, purpose: "LOAN" | "PURCHASE" | "LOAN_REPAYMENT", environment: TestEnvironment = "MTN_SANDBOX"): string { return `gpawa:request:${owner}:sandbox:${environment === "UGX_DEMO" ? "UGX_DEMO:" : ""}${purpose}`; }
export function readRetry(owner: number, purpose: "LOAN" | "PURCHASE" | "LOAN_REPAYMENT", environment: TestEnvironment = "MTN_SANDBOX"): string | null {
  try { const value = localStorage.getItem(retryKey(owner, purpose, environment)); return value && /^[0-9a-f-]{36}$/i.test(value) ? value : null; } catch { return null; }
}
export function writeRetry(owner: number, purpose: "LOAN" | "PURCHASE" | "LOAN_REPAYMENT", id: string | null, environment: TestEnvironment = "MTN_SANDBOX"): void {
  try { if (id) localStorage.setItem(retryKey(owner, purpose, environment), id); else localStorage.removeItem(retryKey(owner, purpose, environment)); } catch { /* No financial state is cached. */ }
}
