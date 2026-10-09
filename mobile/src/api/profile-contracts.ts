export type Choice = { value: string; label: string };
export type Assessment = { values: Record<string, string | null>;
  choices: Record<string, Choice[]>; complete_for_scoring: boolean };
export type Details = { account_number: string | null; address: string | null;
  energy_preference: string | null; payment_method: string | null };
export type AccountDetails = { values: Details | null; details_available: boolean;
  choices: { energy_preference: Choice[]; payment_method: Choice[] } };

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Profile data is unavailable.");
  return value as Record<string, unknown>;
}
function nullableText(value: unknown): string | null {
  if (value !== null && typeof value !== "string") throw new Error("Invalid profile value.");
  return value;
}
function choices(value: unknown): Choice[] {
  if (!Array.isArray(value)) throw new Error("Profile choices are unavailable.");
  const seen = new Set<string>();
  return value.map((item) => {
    const row = record(item);
    if (typeof row.value !== "string" || !row.value || typeof row.label !== "string" || seen.has(row.value)) {
      throw new Error("Invalid profile choice.");
    }
    seen.add(row.value);
    return { value: row.value, label: row.label };
  });
}
export function parseAssessment(payload: unknown): Assessment {
  const data = record(payload), values = record(data.values), options = record(data.choices);
  if (typeof data.complete_for_scoring !== "boolean" ||
      Object.keys(values).length !== Object.keys(options).length) throw new Error("Assessment data is unavailable.");
  const parsed: Assessment = { values: {}, choices: {}, complete_for_scoring: data.complete_for_scoring };
  for (const key of Object.keys(options)) {
    parsed.values[key] = nullableText(values[key]);
    parsed.choices[key] = choices(options[key]);
  }
  return parsed;
}
export function parseAccountDetails(payload: unknown): AccountDetails {
  const data = record(payload), options = record(data.choices);
  if (typeof data.details_available !== "boolean") throw new Error("Account details are unavailable.");
  if (!data.details_available && data.values !== null) throw new Error("Inconsistent account details.");
  let values: Details | null = null;
  if (data.details_available) {
    const fields = record(data.values);
    values = { account_number: nullableText(fields.account_number), address: nullableText(fields.address),
      energy_preference: nullableText(fields.energy_preference), payment_method: nullableText(fields.payment_method) };
  }
  return { values, details_available: data.details_available,
    choices: { energy_preference: choices(options.energy_preference), payment_method: choices(options.payment_method) } };
}
