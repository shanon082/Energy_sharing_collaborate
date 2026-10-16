import { z } from "zod";
import { METER_NUMBER_MESSAGE, normalizePrototypeMeterNumber } from "./meter-enrollment";
export const METER_NO_MAX_LENGTH = 11;
export function isValidMeterNumber(value: string): boolean {
  try { normalizePrototypeMeterNumber(value); return true; } catch { return false; }
}
export function meterNumberFieldSchema() { return z.string().trim().refine(isValidMeterNumber, METER_NUMBER_MESSAGE); }
