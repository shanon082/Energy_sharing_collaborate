"use server";

import { post, get } from "@/lib/fetch";

export async function lookupLoanByPhone(phone: string) {
  return get<{
    owner: { id: number; name: string; phone: string };
    loan: {
      id: number;
      loan_id: string;
      outstanding_balance: number;
      total_amount_due: number;
      status: string;
    };
  }>(`loans/lookup-by-phone/?phone=${encodeURIComponent(phone)}`);
}

export async function payForSomeone(data: {
  owner_phone: string;
  loan_id: number;
  amount: number;
  is_anonymous: boolean;
}) {
  return post<{
    message: string;
    owner_name: string;
    loan_id: string;
    units_added: number;
    outstanding_balance: number;
    loan_status: string;
    payment_reference: string;
    is_anonymous: boolean;
  }>("loans/pay-for-someone/", data);
}
