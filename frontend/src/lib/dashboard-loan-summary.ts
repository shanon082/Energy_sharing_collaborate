type Domain = "UGX_DEMO" | "MTN_SANDBOX";
type Entry = Record<string, unknown>;
function object(v: unknown): v is Entry {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

export function loanSummary(payload: unknown, domain: Domain) {
  if (!object(payload) || !Array.isArray(payload.loans)) throw Error("Unreadable loan history.");
  const currency = domain === "UGX_DEMO" ? "UGX" : "EUR";
  const places = currency === "UGX" ? 0 : 2;
  const scale = 10 ** places;
  function minor(v: unknown) {
    if (typeof v !== "string" || !/^\d+(\.\d+)?$/.test(v)) throw Error("Invalid amount.");
    const [major, fraction = ""] = v.split(".");
    if (/[^0]/.test(fraction.slice(places))) throw Error("Unexpected precision.");
    const value = Number(major + fraction.slice(0, places).padEnd(places, "0"));
    if (!Number.isSafeInteger(value)) throw Error("Amount outside supported range.");
    return value;
  }
  const ids = new Set<string>();
  let active = 0, borrowed = 0, repaid = 0, outstanding = 0;
  for (const r of payload.loans) {
    if (!object(r) || !((r.environment === "UGX_DEMO" && r.currency === "UGX") ||
        (r.environment === "MTN_SANDBOX" && r.currency === "EUR"))) throw Error("Unknown currency domain.");
    if (r.environment !== domain) continue;
    if (typeof r.id !== "string" || !r.id || ids.has(r.id)) throw Error("Invalid or duplicate loan.");
    ids.add(r.id);
    if (r.status === "REJECTED") continue;
    if (r.status !== "DISBURSED" && r.status !== "COMPLETED") throw Error("Unknown loan status.");
    const due = minor(r.total_due), balance = minor(r.outstanding);
    if (balance > due || (r.status === "COMPLETED" && balance !== 0)) throw Error("Invalid balance.");
    if (r.status === "DISBURSED") active++;
    borrowed += minor(r.principal);
    repaid += due - balance; // Only debt applied; excludes excess, pending and purchases.
    outstanding += balance;
    if (![borrowed,repaid,outstanding].every(Number.isSafeInteger)) throw Error("Total outside supported range.");
  }
  return {active, borrowed: borrowed / scale, repaid: repaid / scale, outstanding: outstanding / scale,
    currency, limited: payload.loans.length >= 100};
}
