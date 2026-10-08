export function isPositiveWholeUgx(value: string): boolean {
  return /^(?:[1-9]\d*)$/.test(value);
}

export function wholeUgxWithinDebt(amount: string, outstanding: string | null): boolean {
  if (!isPositiveWholeUgx(amount) || !outstanding ||
      !/^\d+(?:\.\d{1,2})?$/.test(outstanding)) return false;
  // Never infer that fractional debt permits taking an extra whole UGX.
  return BigInt(amount) <= BigInt(outstanding.split(".")[0]);
}
