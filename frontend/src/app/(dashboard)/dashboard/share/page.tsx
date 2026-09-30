import { Suspense } from 'react'
import DesktopSidebar from "../_components/desktop-sidebar"
import RightHeader from "../_components/right-header"
import LoadShareClient from './_components/load_share_client';
import { getFeatureAvailability } from '@/lib/features-server';


const ShareunitsPage = async () => {
  const { peer_sharing } = await getFeatureAvailability();
  return (
    <div className="grid min-h-screen w-full md:grid-cols-[220px_1fr] lg:grid-cols-[280px_1fr]">
      <DesktopSidebar />
      <div className="flex flex-col">
        <RightHeader />
        <main className="flex min-w-0 flex-1 flex-col gap-4 p-4 lg:gap-6 lg:p-6">
          <div>
            <h1 className="text-lg font-semibold md:text-2xl">{peer_sharing ? 'Allocation / Share Units' : 'My Electricity Allocation'}</h1>
            <p className="text-sm text-muted-foreground mt-1">
              {peer_sharing ? 'Review your meter allocation or share when enabled' : 'Review entitlement and simulated delivery for your selected meter'}
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
