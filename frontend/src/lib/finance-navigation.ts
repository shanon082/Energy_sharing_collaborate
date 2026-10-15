/** Presentation-only Back behavior; never submits, cancels or refunds a request. */
export function financeBackAction(state: {
  view: string; busy: boolean; pending: boolean; hasQuote: boolean;
  confirming: boolean; repaying: boolean; reviewingRepayment: boolean;
}): "wait" | "terms" | "amount" | "repayment" | "loans" | "none" {
  if (state.busy) return "wait";
  if (state.view === "apply" && state.confirming && state.hasQuote) return "terms";
  if ((state.view === "apply" || state.view === "purchase") && state.hasQuote) return "amount";
  if (state.view === "loans" && state.repaying && !state.pending)
    return state.reviewingRepayment ? "repayment" : "loans";
  if (state.view === "apply") return "loans";
  return "none";
}
