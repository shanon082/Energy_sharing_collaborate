import DesktopSidebar from "../_components/desktop-sidebar";
import RightHeader from "../_components/right-header";
import AllocationLoadClient from "./_components/allocation-load-client";

export default function MeterAllocationPage() {
  return (
    <div className="grid min-h-screen w-full md:grid-cols-[220px_1fr] lg:grid-cols-[280px_1fr]">
      <DesktopSidebar />
      <div className="flex flex-col">
        <RightHeader />
        <main className="flex min-w-0 flex-1 flex-col gap-4 p-4 lg:gap-6 lg:p-6">
          <div>
            <h1 className="text-lg font-semibold md:text-2xl">Load Units</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Reserve purchased or loaned electricity for your own meter.
            </p>
          </div>
          <AllocationLoadClient />
        </main>
      </div>
    </div>
  );
}
