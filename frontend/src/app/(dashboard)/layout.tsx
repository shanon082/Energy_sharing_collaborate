import { User } from "@/interface/user.interface";
import { getUserConfig } from "@/lib/account";
import authenticated from "@/lib/authenticated";
import { isStaffUser } from "@/lib/staff";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { SelectedMeterProvider } from "@/contexts/selected-meter-context";

export default async function UserProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const headersList = await headers();
  const pathname = headersList.get("x-current-path") || "";
  const isAuth = await authenticated();

  if (!isAuth) {
    redirect("/auth/login");
  }

  const userConfig = await getUserConfig<User>();

  if (userConfig && isStaffUser(userConfig)) {
    redirect("/admin/dashboard");
  }

  if (userConfig?.must_change_password) {
    redirect("/change-password");
  }

  const email_verified = userConfig?.profile?.email_verified;

  if (userConfig && email_verified === false && pathname !== "/ck/verify/email") {
    redirect("/auth/verify-email");
  }

  return <SelectedMeterProvider>{children}</SelectedMeterProvider>;
}
