

import SandboxWeb from "@/components/sandbox-web";
import { getSandboxAvailability } from "@/lib/features-server";
import { Suspense } from 'react'
import "../sandbox/sandbox.css";
import LoginForm from "./_components/form"
import DesktopSidebar from "../_components/desktop-sidebar"
import RightHeader from "../_components/right-header"


const BuyunitsPage = async () => {
  const sandbox = await getSandboxAvailability();
  return (
    <div className="grid min-h-screen w-full md:grid-cols-[220px_1fr] lg:grid-cols-[280px_1fr]">
      <DesktopSidebar />
      <div className="flex flex-col">
        <RightHeader />
        <main className="flex flex-1 flex-col gap-4 p-4 lg:gap-6 lg:p-6">
          <div className="flex items-center">
            <h1 className="text-lg font-semibold md:text-2xl">Buy Units</h1>
          </div>
          <div
            className="flex min-w-0 flex-1 justify-center rounded-lg border border-dashed shadow-sm"
          >
            <div className="flex flex-col gap-1 w-full">
              <Suspense>
                {sandbox.enabled ? <SandboxWeb view="purchase" /> : <LoginForm />}
              </Suspense> 
            </div>
          </div>
        </main>
      </div>
    </div>
  )
};

export default BuyunitsPage;