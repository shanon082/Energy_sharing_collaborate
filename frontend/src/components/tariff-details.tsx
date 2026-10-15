import { testMoney, type TariffPricing, type TestCurrency } from "../lib/sandbox";

/** Accepted server breakdown only; no frontend tariff formula. */
export function TariffDetails({ pricing, currency }: { pricing?: TariffPricing; currency: TestCurrency }) {
  if (!pricing) return null;
  const { inputs, breakdown } = pricing;
  return <div className="small tariff-details">
    <p>{inputs.tariff.name} · {inputs.tariff.code} · {inputs.version}</p>
    <p>Billing month {inputs.month}; owner’s paid demo purchases {inputs.monthly_purchased_kwh} kWh.</p>
    <p>Energy charge {testMoney(breakdown.energy_cost, currency)}; service charge {testMoney(breakdown.service_charge, currency)}; VAT {testMoney(breakdown.vat, currency)}; billed total {testMoney(breakdown.total, currency)}.</p>
    <p>Stored quote terms. Loan allocations and physical delivery do not advance paid purchase bands.</p>
  </div>;
}
