import { Suspense } from 'react'
import DesktopSidebar from "../_components/desktop-sidebar"
import RightHeader from "../_components/right-header"
import LoadShareClient from './_components/load_share_client';


const ShareunitsPage = async () => {
  return (
    <div className="grid min-h-screen w-full md:grid-cols-[220px_1fr] lg:grid-cols-[280px_1fr]">
      <DesktopSidebar />
      <div className="flex flex-col">
        <RightHeader />
        <main className="flex min-w-0 flex-1 flex-col gap-4 p-4 lg:gap-6 lg:p-6">
          <div>
            <h1 className="text-lg font-semibold md:text-2xl">Load / Share Units</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Load onto any of your meters or share kWh with another customer
            </p>
          </div>
          <Suspense>
            <LoadShareClient />
          </Suspense>
        </main>
      </div>
    </div>
  )
};

export default ShareunitsPage;