import { parseReceipt, type Receipt } from "./activity-contracts.ts";

export function parsePaymentRecovery(payload: unknown, expected: {
  purpose: "PURCHASE" | "LOAN_REPAYMENT"; binding: string; requestId: string | null;
}): { pending: boolean; receipt: (Receipt & { client_request_id: string | null }) | null } {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) throw new Error("Payment recovery unavailable.");
  const data = payload as Record<string, unknown>;
  if (typeof data.pending !== "boolean" || data.provider_polled !== false ||
      data.status_source !== "STORED_VERIFIED_SETTLEMENT") throw new Error("Payment recovery unavailable.");
  if (data.receipt === null) return { pending: data.pending, receipt: null };
  const parsed = parseReceipt(data.receipt);
  const raw = data.receipt as Record<string, unknown>;
  const id = typeof raw.client_request_id === "string" ? raw.client_request_id : null;
  if (parsed.purpose !== expected.purpose || (expected.purpose === "PURCHASE" ? parsed.meter_no : parsed.loan_id) !== expected.binding ||
      (expected.requestId && id !== expected.requestId)) throw new Error("Recovered payment binding does not match this request.");
  return { pending: data.pending, receipt: { ...parsed, client_request_id: id } };
}
