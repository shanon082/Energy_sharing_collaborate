"use server";

import { get, patch, post } from "@/lib/fetch";

export type RegisterMeterPayload = {
  meter_no: string;
  architecture: "STS" | "AMI";
  label?: string;
  iot_device_token?: string;
};

export async function registerMeter(payload: RegisterMeterPayload) {
  return post<{ success?: boolean; message?: string; error?: string }>(
    "meter/register/",
    payload
  );
}

export async function updateMeter(payload: RegisterMeterPayload & { current_meter_no: string }) {
  return patch<{ success?: boolean; message?: string; error?: string }>("meter/update/", payload);
}

export type CheckUnitsResult = {
  success?: boolean;
  meter_no?: string;
  units_kwh?: number;
  queried_at?: string;
  units_balance_kwh?: number;
  source?: string;
  message?: string;
  error?: string;
};

export async function checkMeterUnits(meterNo: string) {
  return get<CheckUnitsResult>(`meter/check-units/?meter_no=${encodeURIComponent(meterNo)}`);
}

export async function deleteMeter(meterNo: string, reason?: string) {
  return post<{ success?: boolean; message?: string; error?: string; deleted_meter_no?: string }>(
    "meter/delete/",
    { meter_no: meterNo, ...(reason ? { reason } : {}) }
  );
}

export type GenerateTokenResult = {
  success?: boolean;
  token?: string;
  units?: number;
  remaining_balance?: number;
  message?: string;
  error?: string;
};

export async function generateTokenFromWallet(data: { meter_no: string; amount: number }) {
  return post<GenerateTokenResult>("meter/generate-token/", {
    meter_no: data.meter_no,
    amount: data.amount,
  });
}
