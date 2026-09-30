"use server";

import { getErrorMessage } from "@/lib/errors";
import { post, get } from "@/lib/fetch";
import { getApiErrorMessage } from "@/lib/api-response";

export async function disburseLoan(loanId: number) {
  try {
    console.log('Disbursing loan:', loanId);
    
    const response = await post<any>(`loans/disburse/${loanId}/`, {});
    
    if (response.error) {
      
      if (response.status === 401) {
        throw new Error('Authentication expired. Please log in again.');
      }
      throw new Error(getApiErrorMessage(response.error, 'Failed to disburse loan'));
    }

    return response.data;
    
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}

export async function repayLoan(loanId: number, amount: number, paymentSource: "WALLET" | "PHONE" = "WALLET") {
  void loanId; void amount; void paymentSource;
  throw new Error("Unverified repayment is unavailable. Use verified Mobile Money repayment.");
}

export async function repayLoanWithMomo(amount: number, phoneNumber: string, loanId?: number) {
  try {
    const path = loanId
      ? `loans/repay/momo/${loanId}/`
      : "loans/repay/momo/active/";
    const response = await post<any>(path, {
      amount,
      phone_number: phoneNumber,
    });
    
    if (response.error) {
      
      if (response.status === 401) {
        throw new Error('Authentication expired. Please log in again.');
      }
      throw new Error(getApiErrorMessage(response.error, 'Mobile Money payment failed'));
    }

    return response.data;
    
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}

export async function checkPaymentStatus(externalId: string) {
  try {
    
    const response = await get<any>(`loans/payment-status/${encodeURIComponent(externalId)}/`);
    
    if (response.error) {
      
      if (response.status === 401) {
        throw new Error('Authentication expired. Please log in again.');
      }
      throw new Error(getApiErrorMessage(response.error, 'Failed to check payment status'));
    }

    return response.data;
    
  } catch (error) {
    throw new Error(getErrorMessage(error));
  }
}

export async function getLoanDetails(loanId: number) {
  try {
    console.log('Fetching loan details:', loanId);
    
    const response = await post<any>(`loans/loan/${loanId}/`, {});
    
    if (response.error) {
      console.error('Loan details error:', response.error);
      
      if (response.status === 401) {
        throw new Error('Authentication expired. Please log in again.');
      }
      throw new Error(getApiErrorMessage(response.error, 'Failed to fetch loan details'));
    }

    console.log('Loan details success:', response.data);
    return response.data;
    
  } catch (error) {
    console.error('Loan details error:', error);
    throw new Error(getErrorMessage(error));
  }
}
