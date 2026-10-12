/** Format validation; never evidence of ownership. No server/browser dependencies. */
export function normalizeUgandanPhone(value: string): string {
  const input = value.trim();
  if (/^0[0-9]{9}$/.test(input)) return `+256${input.slice(1)}`;
  if (/^\+?256[0-9]{9}$/.test(input)) return `+${input.replace(/^\+/, "")}`;
  throw new Error("Use 0771000111, 256771000111 or +256771000111; digits only.");
}

export function isUgandanPhone(value: string): boolean {
  try { normalizeUgandanPhone(value); return true; } catch { return false; }
}
