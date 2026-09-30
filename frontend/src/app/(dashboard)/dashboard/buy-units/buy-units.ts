"use server";

import { BuyUnitSchema } from "@/lib/schema";
import { post } from "@/lib/fetch";
import { z } from "zod";

export const buyUnits = async (
  data: z.infer<typeof BuyUnitSchema>
) => {
  const res = await post<BuyUnitsResponse>("meter/buy-units/", data);

  return res;
};

export type PurchasePaymentStatus = {
  status: "PENDING" | "FAILED" | "SUCCESS";
  message: string;
  units_purchased?: number;
  amount_received_ugx?: string;
  purchase_billed_ugx?: string | null;
  purchase_residual_ugx?: string | null;
  requires_reconciliation?: boolean;
  transaction?: { amount: string; timestamp: string | null };
};

export const checkPaymentStatus = async (transactionId: string) => {
  const res = await post<PurchasePaymentStatus>("meter/check-payment-status/", { transaction_id: transactionId });

  return res;
};

type BuyUnitsPendingResponse = {
  status: "PENDING";
  message: string;
  external_id?: string;
  user_prompt?: string;
  transaction_id?: string | number;
  estimated_units?: number;
  tariff_applied?: string;
  loan_outstanding_deduction?: number;
  payment_mode?: "simulated" | "momo";
};

type BuyUnitsCompletedResponse = {
  token?: string;
  message: string;
  "Units purchased": string;
  wallet_balance?: string;
  status?: "SUCCESS";
  payment_status?: string;
  transaction?: unknown;
};

export type BuyUnitsResponse = BuyUnitsPendingResponse | BuyUnitsCompletedResponse;
