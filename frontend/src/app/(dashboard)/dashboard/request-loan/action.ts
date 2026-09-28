"use server";

import { post } from "@/lib/fetch";
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

// export async function checkMomoPaymentStatus(externalId: string) {
//   const apiUrl =
//     process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

//   try {
//     const response = await fetch(
//       `${apiUrl}/loans/payment-status/${externalId}/`,
//       {
//         method: "GET",
//         headers: {
//           "Content-Type": "application/json",
//         },
//         credentials: "include",
//       }
//     );

//     if (!response.ok) {
//       throw new Error(`Failed to check payment status: ${response.status}`);
//     }

//     const data = await response.json();
//     return data;
//   } catch (error) {
//     console.error("Error checking payment status:", error);
//     throw error;
//   }
// }

export async function checkMomoPaymentStatus(externalId: string) {
  const apiUrl =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

  try {
    const response = await fetch(
      `${apiUrl}/loans/payment-status/${externalId}/`,
      {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include", // This is crucial for sending cookies/session
      }
    );

    if (response.status === 401) {
      throw new Error("Authentication required. Please log in again.");
    }

    if (!response.ok) {
      throw new Error(`Failed to check payment status: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error("Error checking payment status:", error);

    // If it's an auth error, redirect to login
    if (error instanceof Error && error.message.includes("Authentication")) {
      // You might want to redirect to login page here
      window.location.href = "/auth/login";
    }

    throw error;
  }
}
