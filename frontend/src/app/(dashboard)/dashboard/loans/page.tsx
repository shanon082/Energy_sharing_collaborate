export const dynamic = "force-dynamic";

import { Suspense } from "react";
import DesktopSidebar from "../_components/desktop-sidebar";
import RightHeader from "../_components/right-header";
import LoansClient from "./_components/loans-client";
import { get } from "@/lib/fetch";
import { getFeatureAvailability } from "@/lib/features-server";
import FeatureUnavailable from "@/components/common/feature-unavailable";

async function getLoans() {
  try {
    const response = await get<any>("loans/my-loans/");
    if (response.error) return [];
    return Array.isArray(response.data)
      ? response.data
      : response.data?.results || response.data?.data || [];
  } catch {
    return [];
  }
}

export default async function LoansPage({
  searchParams,
}: {
  searchParams: Promise<{ tab?: string }>;
}) {
  const loans = await getLoans();
  const params = await searchParams;
  const { third_party_repayment } = await getFeatureAvailability();
  if (params?.tab === "pay-for-someone" && !third_party_repayment) return <FeatureUnavailable />;
  const defaultTab = params?.tab ?? "my-loans";

  return (
    <div className="grid min-h-screen w-full md:grid-cols-[220px_1fr] lg:grid-cols-[280px_1fr]">
      <DesktopSidebar />
      <div className="flex min-w-0 flex-col overflow-x-hidden">
        <RightHeader />
        <main className="flex min-w-0 flex-1 flex-col gap-4 p-4 lg:gap-6 lg:p-6">
          <div>
            <h1 className="text-lg font-semibold md:text-2xl">Loans</h1>
            <p className="text-sm text-muted-foreground mt-1">
              {third_party_repayment
                ? "Apply for a loan, view your loan history, or pay off someone else's loan."
                : "Apply for a loan or view your loan history."}
            </p>
          </div>
          <Suspense fallback={<div className="p-4 text-muted-foreground">Loading…</div>}>
            <LoansClient loans={loans} defaultTab={defaultTab} />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
