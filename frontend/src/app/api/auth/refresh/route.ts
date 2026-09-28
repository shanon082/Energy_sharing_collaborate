import { NextResponse } from "next/server";
import { refreshAuthSession } from "@/lib/refresh-session";
import { clearAuthSessionCookies } from "@/lib/session-cookies";

/** Refresh access token using the httpOnly refresh cookie (browser + proxy). */
export async function POST() {
  const ok = await refreshAuthSession();
  if (!ok) {
    await clearAuthSessionCookies();
    return NextResponse.json({ success: false, message: "Session expired" }, { status: 401 });
  }
  return NextResponse.json({ success: true });
}
