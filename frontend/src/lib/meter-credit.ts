import type { Assessment, PricingStatus, TestPolicy } from "./sandbox";

/** Changes to material evidence invalidate consent; a read timestamp does not. */
export function assessmentContextKey(value: Assessment, policy: TestPolicy, pricing: PricingStatus): string {
  return JSON.stringify([value.owner_id, value.meter_id, value.assessment_id, value.score, value.maximum,
    value.eligible, value.reason, value.assessment_status, value.scoring_policy_version,
    value.evidence_updated_at, policy, pricing]);
}

export function loanProgressionReason(value: Assessment | null, meterId: number | null, amount: string): string | null {
  if (meterId === null) return "Select your meter to view its assessment and eligibility.";
  if (!value || value.meter_id !== undefined && value.meter_id !== meterId) return "Assessment pending for this meter.";
  if (value.score === null || value.assessment_status && value.assessment_status !== "READY") return value.reason || "Assessment pending for this meter.";
  if (value.score < 80) return `This meter’s credit score is ${value.score}%. A minimum of 80% is required to apply for a loan.`;
  if (!value.eligible) return value.reason;
  const cents = (text: string) => {
    if (!/^\d+(?:\.\d{1,2})?$/.test(text)) return null;
    const [whole, fraction = ""] = text.split(".");
    return BigInt(whole) * BigInt(100) + BigInt(fraction.padEnd(2, "0"));
  };
  const requested = cents(amount), maximum = value.maximum === null ? null : cents(value.maximum);
  if (maximum === null) return "This meter’s loan limit is unavailable.";
  if (requested !== null && requested > maximum) return "Requested principal exceeds this meter’s current loan limit.";
  return null;
}
