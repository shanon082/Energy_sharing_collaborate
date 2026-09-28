'use server';

import { cookies } from "next/headers";
import { AUTHENTICATION_COOKIE } from "@/common/constants/auth-cookie";

export async function getAuthToken() {
  const cookieStore = await cookies();
  return cookieStore.get(AUTHENTICATION_COOKIE)?.value;
}

export async function getAuthHeaders() {
  const token = await getAuthToken();
  return {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  };
}

export async function authFetch(url: string, options: RequestInit = {}) {
  const token = await getAuthToken();
  
  const headers = {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
    ...options.headers,
  };

  return fetch(url, {
    ...options,
    headers,
    credentials: 'include',
  });
}