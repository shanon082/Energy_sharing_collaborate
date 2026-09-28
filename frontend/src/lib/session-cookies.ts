"use server";

import { jwtDecode } from "jwt-decode";
import { cookies } from "next/headers";
import {
  AUTHENTICATION_COOKIE,
  AUTHENTICATION_REFRESH_COOKIE,
  REMEMBER_ME_COOKIE,
  REMEMBER_ME_DAYS,
} from "@/common/constants/auth-cookie";

type CookieOptions = {
  name: string;
  value: string;
  httpOnly: boolean;
  secure: boolean;
  sameSite: "lax" | "strict" | "none";
  path: string;
  expires?: Date;
};

function baseCookieOptions(): Omit<CookieOptions, "name" | "value"> {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
  };
}

export async function isRememberMeSession(): Promise<boolean> {
  const cookieStore = await cookies();
  return cookieStore.get(REMEMBER_ME_COOKIE)?.value === "1";
}

/** Persist JWT cookies after login or token refresh. */
export async function setAuthSessionCookies(
  access: string,
  refresh: string,
  rememberMe: boolean
) {
  const cookieStore = await cookies();
  const base = baseCookieOptions();

  const accessExpiry = new Date(jwtDecode<{ exp: number }>(access).exp * 1000);
  cookieStore.set({
    ...base,
    name: AUTHENTICATION_COOKIE,
    value: access,
    expires: accessExpiry,
  });

  const refreshExpiry = new Date(jwtDecode<{ exp: number }>(refresh).exp * 1000);

  if (rememberMe) {
    cookieStore.set({
      ...base,
      name: AUTHENTICATION_REFRESH_COOKIE,
      value: refresh,
      expires: refreshExpiry,
    });
    const rememberUntil = new Date();
    rememberUntil.setDate(rememberUntil.getDate() + REMEMBER_ME_DAYS);
    cookieStore.set({
      ...base,
      name: REMEMBER_ME_COOKIE,
      value: "1",
      expires: rememberUntil,
    });
  } else {
    // Session cookie — cleared when the browser closes.
    cookieStore.set({
      ...base,
      name: AUTHENTICATION_REFRESH_COOKIE,
      value: refresh,
    });
    cookieStore.delete(REMEMBER_ME_COOKIE);
  }
}

export async function clearAuthSessionCookies() {
  const cookieStore = await cookies();
  cookieStore.delete(AUTHENTICATION_COOKIE);
  cookieStore.delete(AUTHENTICATION_REFRESH_COOKIE);
  cookieStore.delete(REMEMBER_ME_COOKIE);
}
