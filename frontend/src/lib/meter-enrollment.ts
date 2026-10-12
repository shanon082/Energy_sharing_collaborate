/** Prototype declarations are strings, not utility ownership or device evidence. */
export const PROTOTYPE_OWNERSHIP_NOTICE = "Meter linked for prototype testing. Ownership and live readings are not verified with the electricity provider.";
export function normalizePrototypeMeterNumber(value: unknown): string {
  if (typeof value !== "string") throw new Error("Enter the meter number as text.");
  const number = value.trim();
  if (!number || number.length > 100 || /[\u0000-\u001f\u007f-\u009f]/u.test(number)) {
    throw new Error("Enter a meter number, at most 100 characters, without control characters.");
  }
  return number;
}
export type LinkedPrototypeMeter = {
  id: number; meter_number: string; label: string; architecture: string; status: string;
  sandbox_inventory: true; ownership_provenance?: "SELF_DECLARED";
  enrolled_at?: string; hardware_connection?: "PENDING";
};
export function parsePrototypeEnrollment(raw: unknown, expectedNumber: string): { meter: LinkedPrototypeMeter; message: string } {
  if (!raw || typeof raw !== "object") throw new Error("The server did not confirm a linked prototype meter.");
  const response = raw as Record<string, unknown>;
  const meter = response.meter as Record<string, unknown> | undefined;
  if (response.success !== true || !["SELF_DECLARED", "LINKED"].includes(String(response.status)) ||
      !meter || typeof meter !== "object" || !Number.isSafeInteger(meter.id) || Number(meter.id) <= 0 ||
      meter.meter_number !== normalizePrototypeMeterNumber(expectedNumber) || meter.sandbox_inventory !== true ||
      meter.status !== "ACTIVE" || typeof meter.label !== "string" || typeof meter.architecture !== "string" ||
      typeof response.message !== "string" ||
      (response.status === "SELF_DECLARED" && (meter.ownership_provenance !== "SELF_DECLARED" ||
        meter.hardware_connection !== "PENDING" || typeof meter.enrolled_at !== "string"))) {
    throw new Error("The server did not confirm a linked prototype meter. Retrying the same number is safe.");
  }
  return { meter: meter as unknown as LinkedPrototypeMeter, message: response.message };
}
