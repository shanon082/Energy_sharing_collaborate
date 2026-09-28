export const dynamic = "force-dynamic";

import DesktopSidebar from "../_components/desktop-sidebar";
import RightHeader from "../_components/right-header";
import PowerUsageClient from "./_components/power-usage-client";

export default function PowerUsagePage() {
  return (
    <div className="grid min-h-screen w-full md:grid-cols-[220px_1fr] lg:grid-cols-[280px_1fr]">
      <DesktopSidebar />
      <div className="flex min-w-0 flex-col overflow-x-hidden">
        <RightHeader />
        <main className="flex min-w-0 flex-1 flex-col gap-4 p-4 lg:gap-6 lg:p-6">
          <PowerUsageClient />
        </main>
      </div>
    </div>
  );
}
