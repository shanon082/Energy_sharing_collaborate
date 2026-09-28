import { z } from "zod";

export const METER_NO_MAX_LENGTH = 100;

export function isValidMeterNumber(value: string): boolean {
  const trimmed = (value || "").trim();
  return trimmed.length > 0 && trimmed.length <= METER_NO_MAX_LENGTH;
}

export function meterNumberFieldSchema() {
  return z
    .string()
    .trim()
    .min(1, "Meter number is required")
    .max(METER_NO_MAX_LENGTH, `Meter number must be at most ${METER_NO_MAX_LENGTH} characters`);
}
