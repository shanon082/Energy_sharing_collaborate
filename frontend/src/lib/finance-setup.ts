import type { Assessment, PricingStatus, SandboxClient, TestCurrency, TestEnvironment, TestPolicy } from './sandbox';

type Setup = { assessment: Assessment; policy: TestPolicy; pricing?: PricingStatus; purchase_policy?: TestPolicy; purchase_pricing?: PricingStatus };
type Domain = { currency: TestCurrency; environment: TestEnvironment };

function matchingPolicy(policy: TestPolicy, domain: Domain): TestPolicy {
  if (!policy || policy.currency !== domain.currency || (policy.environment ?? 'MTN_SANDBOX') !== domain.environment ||
      typeof policy.id !== 'string' || typeof policy.minimum !== 'string' || typeof policy.maximum !== 'string')
    throw new Error('Server terms do not match this operation’s currency and environment. Refresh after updating the backend.');
  return policy;
}

/** Independent read contexts, not a scoring or pricing implementation. An
 * assessment failure must not hide payment terms or prevent durable recovery.
 * Reuse the existing assessment endpoint for older hosted contracts as well. */
export async function readFinanceSetup(client: SandboxClient, meterId: number | undefined, ugxLending: boolean,
  payment: Domain, loan: Domain) {
  const base = `sandbox/assessment/?${meterId === undefined ? '' : `meter_id=${meterId}`}`;
  const paymentRead = client.get<Setup>(base);
  const loanRead = ugxLending ? client.get<Setup>(`${base}${meterId === undefined ? '' : '&'}lending=ugx`) : paymentRead;
  const [lending, purchase] = await Promise.allSettled([
    loanRead.then(row => ({assessment: row.assessment, policy: matchingPolicy(row.policy, loan),
      pricing: row.pricing ?? {available: false, message: 'Loan pricing is missing from the server response.'}})),
    paymentRead.then(row => ({policy: matchingPolicy(row.purchase_policy ?? row.policy, payment),
      pricing: row.purchase_pricing ?? row.pricing ?? {available: false, message: 'Purchase pricing is missing from the server response.'}})),
  ]);
  return {lending, purchase};
}
