import type { Metadata } from "next";
import "@/styles/globals.css";
import { Inter as FontSans } from "next/font/google";
import PublicHeader from "@/components/common/public-header";
import authenticated from "@/lib/authenticated";
import { get } from "@/lib/fetch";
import { headers } from "next/headers";
import { staffRedirectPath } from "@/lib/staff";
import { redirect } from "next/navigation";

export const metadata: Metadata = {
  title: "Power Loans",
  description: "Share with the world",
};

const fontSans = FontSans({
  subsets: ["latin"],
  variable: "--font-sans",
});

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const headersList = await headers();
  const pathname = headersList.get("x-current-path") || "";
  const search = headersList.get("x-current-search") || "";
  const isAuth = await authenticated();
  const isVerificationRoute = pathname.startsWith("/auth/verify-email");
  const isVerifiedLoginRoute = pathname === "/auth/login" && search.includes("verified=1");

  if (isAuth && !isVerificationRoute && !isVerifiedLoginRoute) {
    const config = await get<any>("auth/get-user-config/");
    if (!config.error && config.data) {
      if (config.data.must_change_password && !config.data.is_staff_member && !config.data.is_superuser) {
        redirect("/change-password");
      }
      redirect(staffRedirectPath(config.data));
    }
    redirect("/dashboard");
  }

  return (
    <>
      <PublicHeader />
      {children}
      {/* <PublicFooter /> */}
    </>
  );
}
