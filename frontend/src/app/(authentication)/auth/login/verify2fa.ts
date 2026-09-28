"use server";

import { API_URL } from "@/common/constants/api";
import { setAuthSessionCookies } from "@/lib/session-cookies";
import { staffRedirectPath } from "@/lib/staff";

export const verify2FA = async (
  challengeToken: string,
  code: string,
  rememberMe = false
) => {
  try {
    const res = await fetch(`${API_URL}/admin/2fa/login-verify/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ challenge_token: challengeToken, code }),
    });

    const parsedRes = await res.json();

    if (!res.ok) {
      return { error: parsedRes.error || "Invalid 2FA code" };
    }

    if (parsedRes.access && parsedRes.refresh) {
      const useRemember =
        rememberMe || Boolean(parsedRes.remember_me);
      await setAuthSessionCookies(
        parsedRes.access,
        parsedRes.refresh,
        useRemember
      );
    }

    const redirectTo = staffRedirectPath(parsedRes.user);

    return {
      success: true,
      redirectTo,
      user: parsedRes.user,
    };
  } catch (err) {
    console.error("2FA verify error:", err);
    return { error: "Server error during 2FA verification" };
  }
};
