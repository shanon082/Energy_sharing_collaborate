"use server";

import { API_URL } from "@/common/constants/api";
import { getErrorMessage } from "@/lib/errors";
import { jwtDecode } from "jwt-decode";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { BuyUnitSchema } from "@/lib/schema";
import { post } from "@/lib/fetch";
import { z } from "zod";
import {
  AUTHENTICATION_COOKIE,
  AUTHENTICATION_REFRESH_COOKIE,
} from "@/common/constants/auth-cookie";

export const buyUnits = async (
  data: z.infer<typeof BuyUnitSchema>
) => {
  const res = await post<BuyUnitsResponse>("meter/buy-units/", data);

  console.log("Buy units: ", res.data);
  return res;
};

// Add payment status check function
export const checkPaymentStatus = async (transactionId: string) => {
  const res = await post<{
    status: string;
    message: string;
    units_purchased?: number;
    token?: string;
    transaction?: any;
  }>("meter/check-payment-status/", { transaction_id: transactionId });

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
