export type StaffRole = "ADMIN" | "CUSTOMER_SERVICE" | "OPERATOR";

const STAFF_ROLES: StaffRole[] = ["ADMIN", "CUSTOMER_SERVICE", "OPERATOR"];

export interface StaffUserLike {
  user_role?: string | null;
  is_admin?: boolean;
  is_staff_member?: boolean;
  is_superuser?: boolean;
  redirect_to?: string;
  must_change_password?: boolean;
}

export function isStaffUser(user?: StaffUserLike | null): boolean {
  if (!user) return false;
  if (user.is_staff_member || user.is_superuser) return true;
  if (user.is_admin) return true;
  const role = user.user_role ?? "";
  return STAFF_ROLES.includes(role as StaffRole);
}

export function staffRedirectPath(user?: StaffUserLike | null): string {
  if (user?.must_change_password && !isStaffUser(user)) {
    return "/change-password";
  }
  if (user?.redirect_to) return user.redirect_to;
  return isStaffUser(user) ? "/admin/dashboard" : "/dashboard";
}

export function staffRoleLevel(role?: string | null): number {
  if (role === "ADMIN") return 3;
  if (role === "OPERATOR") return 2;
  if (role === "CUSTOMER_SERVICE") return 1;
  return 0;
}
