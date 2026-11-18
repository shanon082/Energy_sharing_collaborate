/** Explain the same prerequisites that disable quote review; never changes eligibility. */
export function quoteAvailabilityReason(input: { busy: boolean; refreshing: boolean; offline: boolean; unresolved: boolean; pending: boolean;
  blocked: boolean; policy: boolean; allowed: boolean; pricing: {available: boolean; message: string}; validAmount: boolean;
  purpose: "LOAN" | "PURCHASE"; assessmentReady: boolean; loanReason: string | null }): string | null {
  if (input.busy) return "A request is in progress. Wait for its result.";
  if (input.offline) return "Reconnect before requesting terms.";
  if (input.unresolved) return "A previous request needs reconciliation. Refresh its stored status before submitting another request.";
  if (input.pending) return "A previous payment is pending. Wait for its confirmed outcome before continuing.";
  if (input.refreshing) return "Refreshing your account and pricing. Please wait.";
  if (!input.policy) return "Loan and purchase terms are unavailable. Refresh or contact prototype support.";
  if (!input.allowed) return "This operation is unavailable in the current server mode.";
  if (!input.pricing.available) return input.pricing.message || "Pricing is unavailable. The testing backend needs a configured tariff.";
  if (!input.validAmount) return "Enter a positive amount in the displayed test currency and precision.";
  if (input.purpose === "LOAN" && (!input.assessmentReady || input.loanReason)) return input.loanReason || "This meter’s assessment is pending or unavailable.";
  if (input.blocked) return "Account actions are unavailable. Refresh your session before continuing.";
  return null;
}
