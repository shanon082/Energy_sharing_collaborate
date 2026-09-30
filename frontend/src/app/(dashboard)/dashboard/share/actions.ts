"use server";

import { post } from "@/lib/fetch";

export type ApplyWalletUnitsResult = {
  status?: "QUEUED";
  deliveries?: { id: number; command_id: string; amount_kwh: string; status: string }[];
  success?: boolean;
  message?: string;
  error?: string;
  units_applied?: number;
  meter_balance?: number;
  pending_delivery_kwh?: number;
  remaining_wallet_balance?: number;
  live_units_kwh?: number | null;
  live_queried_at?: string | null;
  delivery_status?: "delivered" | "pending";
};

export type AmiLoadSuccessResult = {
  units_applied: number;
  meter_balance: number;
  pending_delivery_kwh: number;
  remaining_wallet_balance: number;
  live_units_kwh: number | null;
  live_queried_at: string | null;
  delivery_status: "delivered" | "pending";
  message: string;
};

export async function applyWalletUnits(data: {
  meter_no: string;
  amount: string | number;
}): Promise<{ data?: ApplyWalletUnitsResult; error?: unknown; status: number }> {
  return post<ApplyWalletUnitsResult>("meter/apply-wallet-units/", data);
}
