"use client";
import { clearPrivateBrowserState } from "@/lib/session-storage";

/** Client-side session refresh via httpOnly refresh cookie. */
export async function refreshAuthToken(): Promise<boolean> {
  try {
    const response = await fetch("/api/auth/refresh", {
      method: "POST",
      credentials: "include",
      cache: "no-store",
    });
    if (!response.ok) clearPrivateBrowserState();
    return response.ok;
  } catch {
    return false;
  }
}

export async function clientAuthFetch(url: string, options: RequestInit = {}) {
  let response = await fetch(url, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    },
  });

  if (response.status === 401) {
    const refreshed = await refreshAuthToken();
    if (refreshed) {
      response = await fetch(url, {
        ...options,
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          ...(options.headers as Record<string, string>),
        },
      });
    }
    if (response.status === 401 && typeof window !== "undefined") {
      clearPrivateBrowserState();
      window.location.href = "/auth/login?session=expired";
    }
  }

  return response;
}
