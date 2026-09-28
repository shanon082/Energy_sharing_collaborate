"use server";

import { cookies } from "next/headers";
import { API_URL } from "@/common/constants/api";
import {
  AUTHENTICATION_COOKIE,
  AUTHENTICATION_REFRESH_COOKIE,
} from "@/common/constants/auth-cookie";
import { isRememberMeSession, setAuthSessionCookies } from "@/lib/session-cookies";

/** Exchange refresh cookie for new access (and rotated refresh) tokens. */
export async function refreshAuthSession(): Promise<boolean> {
  const cookieStore = await cookies();
  const refreshToken = cookieStore.get(AUTHENTICATION_REFRESH_COOKIE)?.value;
  if (!refreshToken) {
    return false;
  }

  try {
    const res = await fetch(`${API_URL}/auth/refresh/token/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh: refreshToken }),
      cache: "no-store",
    });

    if (!res.ok) {
      return false;
    }

    const data = (await res.json()) as { access?: string; refresh?: string };
    if (!data.access) {
      return false;
    }

    const rememberMe = await isRememberMeSession();
    await setAuthSessionCookies(
      data.access,
      data.refresh ?? refreshToken,
      rememberMe
    );
    return true;
  } catch {
    return false;
  }
}

/** If access cookie expired but refresh remains, silently renew the session. */
export async function ensureValidSession(): Promise<boolean> {
  const cookieStore = await cookies();
  if (cookieStore.get(AUTHENTICATION_COOKIE)?.value) {
    return true;
  }
  if (!cookieStore.get(AUTHENTICATION_REFRESH_COOKIE)?.value) {
    return false;
  }
  return refreshAuthSession();
}
