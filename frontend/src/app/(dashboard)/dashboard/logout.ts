"use server";

import { clearAuthSessionCookies } from "@/lib/session-cookies";
import { redirect } from "next/navigation";

export default async function logout() {
  await clearAuthSessionCookies();
  redirect("/auth/login");
}
