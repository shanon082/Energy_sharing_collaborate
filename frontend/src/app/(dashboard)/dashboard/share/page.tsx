import { redirect } from "next/navigation";

export default function LegacySharePage() {
  redirect("/dashboard/meter-allocation");
}
