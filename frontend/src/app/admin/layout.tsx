import { redirect } from "next/navigation";
import { getUserConfig } from "@/lib/account";
import { isStaffUser } from "@/lib/staff";
import AdminDesktopSidebar from "./_components/desktop_dashboard";
import AdminRightHeader from "./_components/admin_header";
import AdminBodyShell from "./_components/admin-body-shell";

interface UserConfig {
  user_role: string;
  is_admin: boolean;
  is_staff_member?: boolean;
  is_superuser?: boolean;
}

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const userData = await getUserConfig<UserConfig>();

  if (!userData) {
    redirect("/auth/login");
  }

  if (!isStaffUser(userData)) {
    redirect("/dashboard");
  }

  const displayRole =
    userData.is_superuser && userData.user_role !== "ADMIN"
      ? "ADMIN"
      : userData.user_role;

  return (
    <AdminBodyShell>
      <div className="flex min-h-screen w-full bg-background">
        <div className="hidden md:flex md:w-[220px] lg:w-[260px] shrink-0 flex-col sticky top-0 h-screen overflow-hidden">
          <AdminDesktopSidebar
            userRole={displayRole}
            isSuperuser={!!userData.is_superuser}
          />
        </div>
        <div className="flex min-w-0 flex-1 flex-col">
          <AdminRightHeader
            userRole={displayRole}
            isSuperuser={!!userData.is_superuser}
          />
          <main className="flex min-w-0 flex-1 flex-col gap-4 bg-background p-4 lg:gap-6 lg:p-6">
            {children}
          </main>
        </div>
      </div>
    </AdminBodyShell>
  );
}
