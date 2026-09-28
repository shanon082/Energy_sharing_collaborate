import { Suspense } from 'react';
import DesktopSidebar from "../_components/desktop-sidebar";
import RightHeader from "../_components/right-header";
import TransList from './_components/transactionlist';


const TransactionPage = async () => {
  return (
    <div className="grid min-h-screen w-full md:grid-cols-[220px_1fr] lg:grid-cols-[280px_1fr]">
      <DesktopSidebar />
      <div className="flex min-w-0 flex-col overflow-x-hidden">
        <RightHeader />
        <main className="flex min-w-0 flex-1 flex-col gap-4 p-4 lg:gap-6 lg:p-6">
          <div className="flex items-center">
            <h1 className="text-lg font-semibold md:text-2xl">My Account Transactions</h1>
          </div>

          <div
            className="flex min-w-0 flex-1 justify-center rounded-lg border border-dashed shadow-sm" x-chunk="dashboard-02-chunk-1"
          >
            <div className="flex min-w-0 flex-col gap-1 w-full">
              <TransList />
            </div>
          </div>
        </main>
      </div>
    </div>
  )
};

export default TransactionPage;
