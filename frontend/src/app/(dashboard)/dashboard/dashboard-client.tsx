// app/dashboard/dashboard-client.tsx
"use client";

import { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { useRouter } from 'next/navigation';
import DesktopSidebar from './_components/desktop-sidebar';
import RightHeader from './_components/right-header';
import LoanOverview from './_components/loan-overview';
import MeterRegistrationPopup from './_components/meter-registration-popup';
import LatestTransactions from './_components/latest-transactions';
import MeterUnitsPanel from './_components/meter-units-panel';
import { useSelectedMeter } from '@/contexts/selected-meter-context';
import { User } from '@/interface/user.interface';
import { Zap, Brain } from 'lucide-react';
import CreditScoreModal from './_components/credit-score-modal';

const MeterManagementModal = dynamic(
  () => import('./_components/meter-registration-modal'),
  { ssr: false }
);

type SetupStep = 'loading' | 'meter' | 'complete';

interface DashboardClientProps {
  initialStep: SetupStep;
  userConfig: User | null;
  userHasMeter: boolean;
}

export default function DashboardClient({
  initialStep,
  userConfig,
  userHasMeter,
}: DashboardClientProps) {
  const [currentStep, setCurrentStep] = useState<SetupStep>(initialStep);
  const [isMeterPopupOpen, setIsMeterPopupOpen] = useState(false);
  const [isMeterManagementOpen, setIsMeterManagementOpen] = useState(false);
  const [isCreditScoreOpen, setIsCreditScoreOpen] = useState(false);
  const router = useRouter();
  const { refreshMeters } = useSelectedMeter();

  useEffect(() => {
    if (initialStep === 'meter' && !userHasMeter) {
      setIsMeterPopupOpen(true);
      setCurrentStep('meter');
    } else {
      setCurrentStep('complete');
    }
  }, [initialStep, userHasMeter]);

  const handleMeterSuccess = () => {
    setIsMeterPopupOpen(false);
    setCurrentStep('complete');
    refreshMeters();
    router.refresh();
  };

  const handleMeterManagementSuccess = () => {
    setIsMeterManagementOpen(false);
    refreshMeters();
    router.refresh();
  };

  const openMeterManagement = () => {
    setIsMeterManagementOpen(true);
  };

  const openCreditScore = () => {
    setIsCreditScoreOpen(true);
  };

  if (currentStep === 'loading' || !userConfig) {
    return (
      <div className="grid min-h-screen w-full md:grid-cols-[220px_1fr] lg:grid-cols-[280px_1fr]">
        <DesktopSidebar />
        <div className="flex min-w-0 flex-col overflow-x-hidden">
          <RightHeader />
          <main className="flex min-w-0 flex-1 flex-col gap-4 p-4 lg:gap-6 lg:p-6">
            <div className="flex justify-center items-center h-64">
              <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4" />
                <p>Loading dashboard...</p>
              </div>
            </div>
          </main>
        </div>
      </div>
    );
  }

  return (
    <div className="grid min-h-screen w-full md:grid-cols-[220px_1fr] lg:grid-cols-[280px_1fr]">
      <DesktopSidebar />
      <div className="flex min-w-0 flex-col overflow-x-hidden">
        <RightHeader onMeterClick={openMeterManagement} />

        {currentStep === 'meter' && !userHasMeter && (
          <MeterRegistrationPopup
            isOpen={isMeterPopupOpen}
            onClose={() => setIsMeterPopupOpen(false)}
            onSuccess={handleMeterSuccess}
            forceCompletion
          />
        )}

        <MeterManagementModal
          isOpen={isMeterManagementOpen}
          onClose={() => setIsMeterManagementOpen(false)}
          onSuccess={handleMeterManagementSuccess}
          userData={userConfig}
        />

        <CreditScoreModal
          isOpen={isCreditScoreOpen}
          onClose={() => setIsCreditScoreOpen(false)}
        />

        <main className="flex min-w-0 flex-1 flex-col gap-4 p-4 lg:gap-6 lg:p-6">
          <div className="flex items-center justify-between">
            <h1 className="text-lg font-semibold md:text-2xl">Dashboard</h1>

            {currentStep === 'complete' && (
              <div className="flex gap-2">
                <button
                  onClick={openCreditScore}
                  className="px-4 py-2 text-sm bg-purple-100 text-purple-700 rounded-lg hover:bg-purple-200 transition-colors flex items-center gap-2"
                >
                  <Brain className="h-4 w-4" />
                  Credit Score
                </button>
                <button
                  onClick={openMeterManagement}
                  className="px-4 py-2 text-sm bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 transition-colors flex items-center gap-2"
                >
                  <Zap className="h-4 w-4" />
                  {userHasMeter ? 'Manage Meter' : 'Register Meter'}
                </button>
              </div>
            )}
          </div>

          {currentStep === 'meter' && (
            <div className="flex flex-1 flex-col items-center justify-center rounded-lg border border-dashed p-8 text-center">
              <div className="mx-auto flex max-w-[420px] flex-col items-center justify-center text-center">
                <div className="flex items-center justify-center w-20 h-20 bg-blue-100 rounded-full mb-4">
                  <span className="text-2xl">P</span>
                </div>
                <h3 className="mt-4 text-lg font-semibold">Step 1: Complete Meter Registration</h3>
                <p className="mb-4 mt-2 text-sm text-muted-foreground">
                  Please register your electricity meter to continue using gPawa services.
                </p>
                <p className="text-xs text-muted-foreground">Follow the steps in the popup above to continue.</p>
              </div>
            </div>
          )}

          <LoanOverview />

          {/* {currentStep === 'complete' && userHasMeter && <MeterUnitsPanel />} */}

          <div className="flex flex-1 justify-center rounded-lg border border-dashed shadow-sm">
            <div className="flex flex-col gap-1 w-full">
              <h3 className="text-2xl text-left font-bold tracking-tight p-4">Latest transactions</h3>
              <LatestTransactions />
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}