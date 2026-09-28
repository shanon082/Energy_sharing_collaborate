"use server";

import { API_URL } from "@/common/constants/api";
import { getErrorMessage } from "@/lib/errors";
import { LoginSchema } from "@/lib/schema";
import { setAuthSessionCookies } from "@/lib/session-cookies";
import { staffRedirectPath } from "@/lib/staff";
import { z } from "zod";

export const login = async (
  data: z.infer<typeof LoginSchema>,
  rememberMe = false
) => {
  try {
    const res = await fetch(`${API_URL}/auth/login/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: data.email,
        password: data.password,
        remember_me: rememberMe,
      }),
    });

    const parsedRes = await res.json();

    if (res.status === 400) {
      const emailError = parsedRes.email;
      const emailMsg = Array.isArray(emailError) ? emailError[0] : emailError;
      if (emailMsg && String(emailMsg).toLowerCase().includes("verify your email")) {
        return {
          error: "EMAIL_NOT_VERIFIED",
          message: String(emailMsg),
          email: data.email,
        };
      }

      const fieldErrors = parsedRes.non_field_errors;
      const fieldMsg = Array.isArray(fieldErrors) ? fieldErrors[0] : fieldErrors;
      const errorMessage =
        fieldMsg || parsedRes.detail || parsedRes.error || "Login failed";
      return { error: "LOGIN_FAILED", message: String(errorMessage) };
    }

    if (!res.ok) {
      return { error: "LOGIN_FAILED", message: getErrorMessage(parsedRes) };
    }

    if (parsedRes.requires_2fa) {
      return {
        requires_2fa: true,
        challenge_token: parsedRes.challenge_token as string,
        user: parsedRes.user,
        must_change_password: !!parsedRes.user?.must_change_password,
        rememberMe,
      };
    }

    if (parsedRes.access && parsedRes.refresh) {
      await setAuthSessionCookies(parsedRes.access, parsedRes.refresh, rememberMe);
    }

    const redirectTo = staffRedirectPath(parsedRes.user);

    return {
      success: "Login successful",
      redirectTo,
      user: parsedRes.user,
      must_change_password: !!parsedRes.user?.must_change_password,
      isAdmin:
        !!parsedRes.user?.is_admin ||
        staffRedirectPath(parsedRes.user).startsWith("/admin"),
    };
  } catch (err) {
    console.error("Login Error:", err);
    const cause = err instanceof Error && "cause" in err ? (err.cause as { code?: string }) : null;
    const refused = cause?.code === "ECONNREFUSED";
    return {
      error: "SERVER_ERROR",
      message: refused
        ? "Cannot reach the API server. Start the Django backend on port 8000 (see backend/) or set NEXT_PUBLIC_API_URL in frontend/.env.local."
        : "Server error occurred",
    };
  }
};
