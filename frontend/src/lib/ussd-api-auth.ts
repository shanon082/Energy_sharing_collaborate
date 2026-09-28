import { cookies } from "next/headers";
import { AUTHENTICATION_COOKIE } from "@/common/constants/auth-cookie";
import { ensureValidSession } from "@/lib/refresh-session";

/** Bearer token for server-side USSD simulator API routes (web portal session). */
export async function getUssdAuthHeaders(): Promise<Record<string, string>> {
  await ensureValidSession();
  const token = (await cookies()).get(AUTHENTICATION_COOKIE)?.value;
  if (!token) {
    return {};
  }
  return { Authorization: `Bearer ${token}` };
}

export async function requireUssdAuthHeaders(): Promise<Record<string, string> | null> {
  const headers = await getUssdAuthHeaders();
  if (!headers.Authorization) {
    return null;
  }
  return headers;
}
