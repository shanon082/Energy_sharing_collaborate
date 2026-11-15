import SandboxWeb from "@/components/sandbox-web";
import DesktopSidebar from "../(dashboard)/dashboard/_components/desktop-sidebar";
import RightHeader from "../(dashboard)/dashboard/_components/right-header";
import { FeaturesProvider } from "@/contexts/features-context";
import { DISABLED_FEATURES } from "@/lib/features";
import "../(dashboard)/dashboard/sandbox/sandbox.css";

const views = new Set(["purchase", "apply", "loans", "activity", "wallet"]);

export default async function ConsumerPreview({
  searchParams,
}: {
  searchParams: Promise<{ view?: string }>;
}) {
  const { view = "purchase" } = await searchParams;
  const selectedView = views.has(view) ? view : "purchase";
  return <FeaturesProvider features={DISABLED_FEATURES}>
    <div className="grid min-h-screen w-full md:grid-cols-[220px_1fr] lg:grid-cols-[280px_1fr]">
      <DesktopSidebar />
      <div className="flex min-w-0 flex-col overflow-x-hidden">
        <RightHeader />
        <main className="flex min-w-0 flex-1 flex-col gap-4 p-4 lg:gap-6 lg:p-6">
          <h1 className="text-lg font-semibold md:text-2xl">{selectedView}</h1>
          {selectedView === "wallet" ? <SandboxWeb view="wallet" /> :
            <SandboxWeb view={selectedView as "purchase" | "apply" | "loans" | "activity"} />}
        </main>
      </div>
    </div>
  </FeaturesProvider>;
}
