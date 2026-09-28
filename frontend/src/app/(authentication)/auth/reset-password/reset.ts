"use server";

import { API_URL } from "@/common/constants/api";
import { AUTHENTICATION_COOKIE } from "@/common/constants/auth-cookie";
import {
  ApiResponse,
  getApiErrorMessage,
  toApiError,
} from "@/lib/api-response";
import { ResetPasswordSchema } from "@/lib/schema";
import { cookies } from "next/headers";
import { z } from "zod";

async function publicResetRequest<T>(
  path: string,
  method: "GET" | "PATCH",
  body?: unknown
): Promise<ApiResponse<T>> {
  try {
    const res = await fetch(`${API_URL}/${path}`, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });

    const contentType = res.headers.get("content-type");
    let parsedBody: unknown;
    if (contentType?.includes("application/json")) {
      try {
        parsedBody = await res.json();
      } catch {
        parsedBody = undefined;
      }
    } else {
      const text = await res.text();
      parsedBody = text ? { message: text } : undefined;
    }

    if (!res.ok) {
      return {
        error: toApiError(parsedBody, `Request failed with status ${res.status}`),
        status: res.status,
      };
    }

    return { data: parsedBody as T, status: res.status };
  } catch {
    return {
      error: { message: "Network error occurred" },
      status: 0,
    };
  }
}

export async function validateResetLink(uid: string, token: string) {
  const response = await publicResetRequest<{ message?: string }>(
    `auth/reset-password/?uid=${encodeURIComponent(uid)}&token=${encodeURIComponent(token)}`,
    "GET"
  );

  return response.error
    ? {
        error: getApiErrorMessage(
          response.error,
          "Invalid or expired reset link. Please request a new one."
        ),
      }
    : { success: true };
}

export async function resetPassword(
  uid: string,
  token: string,
  data: z.infer<typeof ResetPasswordSchema>
) {
  const response = await publicResetRequest<{ message?: string }>(
    `auth/reset-password/?uid=${encodeURIComponent(uid)}&token=${encodeURIComponent(token)}`,
    "PATCH",
    data
  );

  if (response.error) {
    return {
      error: getApiErrorMessage(
        response.error,
        "Failed to reset password. The link may have expired — request a new one."
      ),
    };
  }

  const cookieStore = await cookies();
  cookieStore.delete(AUTHENTICATION_COOKIE);

  return {
    success: "Password reset successfully! Please log in with your new password.",
    redirectTo: "/auth/login",
  };
}
