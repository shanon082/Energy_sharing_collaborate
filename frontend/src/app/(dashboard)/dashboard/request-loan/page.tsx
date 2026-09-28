import { redirect } from "next/navigation";

export default function RequestLoanRedirect() {
  redirect("/dashboard/loans?tab=apply");
}
