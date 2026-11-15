import { Suspense } from "react";
import DesktopSidebar from "../_components/desktop-sidebar";
import RightHeader from "../_components/right-header";
import MyMetersClient from "./_components/my-meters-client";

export default function MyMetersPage() {
  return (
    <div className="grid min-h-screen w-full md:grid-cols-[220px_1fr] lg:grid-cols-[280px_1fr]">
      <DesktopSidebar />
      <div className="flex flex-col">
        <RightHeader />
        <main className="flex min-w-0 flex-1 flex-col gap-4 p-4 lg:gap-6 lg:p-6">
          <div>
            <h1 className="text-lg font-semibold md:text-2xl">My Meters</h1>
            <p className="text-sm text-muted-foreground mt-1">
              View and manage your registered meters, check live balance, and load units
            </p>
          </div>
          <Suspense>
            <MyMetersClient />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
