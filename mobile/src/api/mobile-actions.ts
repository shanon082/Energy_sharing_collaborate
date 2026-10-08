export type MobileActions = { purchase: boolean; repayment: boolean; loan_application: boolean };
export const DISABLED_MOBILE_ACTIONS: MobileActions = {
  purchase: false, repayment: false, loan_application: false,
};

export function parseMobileActions(value: unknown): MobileActions {
  if (!value || typeof value !== "object" || Array.isArray(value)) return DISABLED_MOBILE_ACTIONS;
  const data = value as Record<string, unknown>;
  return {
    purchase: data.purchase === true,
    repayment: data.repayment === true,
    loan_application: data.loan_application === true,
  };
}
