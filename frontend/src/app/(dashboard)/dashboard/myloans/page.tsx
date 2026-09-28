import { redirect } from "next/navigation";

export default function MyLoansRedirect() {
  redirect("/dashboard/loans?tab=my-loans");
}
