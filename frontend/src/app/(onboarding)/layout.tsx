import authenticated from "@/lib/authenticated";
import { getUserConfig } from "@/lib/account";
import { isStaffUser } from "@/lib/staff";
import { redirect } from "next/navigation";

export default async function OnboardingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const isAuth = await authenticated();
  if (!isAuth) {
    redirect("/auth/login");
  }

  const userConfig = await getUserConfig<{ must_change_password?: boolean }>();
  if (!userConfig?.must_change_password) {
    redirect(isStaffUser(userConfig) ? "/admin/dashboard" : "/dashboard");
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-emerald-50 to-blue-100 dark:from-blue-950 dark:via-emerald-900/20 dark:to-blue-900 flex items-center justify-center p-4">
      {children}
    </div>
  );
}
