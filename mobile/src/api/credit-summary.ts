import { parseStoredDemoAssessment } from "../../../frontend/src/lib/sandbox.ts";

export type Credit = {
  score: number | null; limit: string | null; reason: string | null;
  calculatedAt: string | null; factors: Record<string, number>; simulated: boolean;
};
/** Reuse server evidence; distinguish the current demo maximum from core limits. */
export function parseCreditSummary(input: unknown): Credit {
  if (!input || typeof input !== "object" || Array.isArray(input)) throw new Error("Your assessment is temporarily unavailable.");
  const value = input as Record<string, unknown>;
  if (value.environment === "UGX_DEMO" || value.input_source === "SIMULATED_ACCOUNT_INFORMATION") {
    const assessment = parseStoredDemoAssessment(value);
    return { score: assessment.score, limit: assessment.maximum, reason: assessment.reason,
      calculatedAt: assessment.assessed_at ?? null, factors: assessment.factors ?? {}, simulated: true };
  }
  if (!(value.score === null || typeof value.score === "number" && Number.isInteger(value.score) && value.score >= 0 && value.score <= 100))
    throw new Error("Your assessment is temporarily unavailable.");
  const factors: Record<string, number> = {};
  if (value.factors != null) {
    if (typeof value.factors !== "object" || Array.isArray(value.factors)) throw new Error("Assessment factors are unavailable.");
    for (const [key, score] of Object.entries(value.factors)) {
      if (typeof score !== "number" || !Number.isFinite(score) || score < 0 || score > 100)
        throw new Error("Assessment factors are unavailable.");
      factors[key] = score;
    }
  }
  return { score: value.score,
    limit: typeof value.max_loan_ugx === "string" && /^\d+(\.\d+)?$/.test(value.max_loan_ugx) ? value.max_loan_ugx : null,
    reason: typeof value.reason === "string" ? value.reason : null,
    calculatedAt: typeof value.calculated_at === "string" ? value.calculated_at : null, factors, simulated: false };
}
