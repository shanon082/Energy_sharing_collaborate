'use server';

import { post } from "@/lib/fetch";
import { getApiErrorMessage } from "@/lib/api-response";
import { getSandboxAvailability } from "@/lib/features-server";
import { normalizePrototypeMeterNumber, parsePrototypeEnrollment } from "@/lib/meter-enrollment";

type MeterResponse = { success: boolean; status: string; request_id?: string; message: string; meter?: unknown };

export async function prototypeEnrollmentEnabled() {
  return (await getSandboxAvailability()).enabled;
}

export async function registerMeter(formData: { meter_no: string }) {
  try {
    const normalized = normalizePrototypeMeterNumber(formData.meter_no);
    const response = await post<MeterResponse>('meter/register/', { meter_no: normalized });
    if (response.error) return { error: getApiErrorMessage(response.error, "Could not confirm meter request") };
    if (response.data?.status === "SELF_DECLARED" || (response.data?.status === "LINKED" && response.data.meter)) {
      const linked = parsePrototypeEnrollment(response.data, normalized);
      return { success: linked.message, data: response.data };
    }
    if (response.data?.status === "LINKED") return { success: response.data.message, data: response.data };
    if (response.data?.status !== "PENDING") return { error: response.data?.message || "The server did not confirm a meter request." };
    return { success: "Meter request recorded; staff verification is required.", data: response.data };
  } catch {
    return { error: "Could not confirm meter request. Check your connection; retrying the same number is safe." };
  }
}
