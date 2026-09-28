import { AUTHENTICATION_COOKIE, AUTHENTICATION_REFRESH_COOKIE } from "@/common/constants/auth-cookie";
import { cookies } from "next/headers";
import { ensureValidSession } from "@/lib/refresh-session";

export default async function authenticated() {
  const cookieStore = await cookies();
  const authCookie = cookieStore.get(AUTHENTICATION_COOKIE);
  const refreshCookie = cookieStore.get(AUTHENTICATION_REFRESH_COOKIE);

  if (authCookie?.value) {
    return true;
  }

  if (refreshCookie?.value) {
    return ensureValidSession();
  }

  return false;
}


