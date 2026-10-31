"use server";

import { get, post } from "@/lib/fetch";
import { getApiErrorMessage } from "@/lib/api-response";

export async function submitLoanApplication(formData: any) {
  try {
    const response = await post<any>("loans/apply/", formData);

    if (response.error) {
      const errorMessage = getApiErrorMessage(
        response.error,
        "Failed to submit loan application"
      );

      return {
        error: errorMessage,
        requiresMeter: errorMessage.toLowerCase().includes("meter"),
      };
    }

    return {
      success: "Loan application submitted successfully!",
      data: response.data,
    };
  } catch (err) {
    console.error("Loan submit error:", err);
    return { error: "Network error. Please try again." };
  }
}

export async function checkMomoPaymentStatus(externalId: string) {
  const response = await get<any>(
    `loans/payment-status/${encodeURIComponent(externalId)}/`
  );
  if (response.error) {
    throw new Error(
      getApiErrorMessage(response.error, "Failed to check payment status")
    );
  }
  return response.data;
}
