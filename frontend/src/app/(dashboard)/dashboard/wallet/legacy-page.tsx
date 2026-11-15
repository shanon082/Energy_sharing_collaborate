import DesktopSidebar from "../_components/desktop-sidebar"
import RightHeader from "../_components/right-header"
import Deposit from './_components/deposit';
import Withdraw from './_components/withdraw';
import { getFeatureAvailability } from '@/lib/features-server';
import SandboxWeb from "@/components/sandbox-web";
import "../sandbox/sandbox.css";

const WalletsPage = async () => {
    const { wallet_deposits, wallet_withdrawals } = await getFeatureAvailability();

    return (
            <div className="grid min-h-screen w-full md:grid-cols-[220px_1fr] lg:grid-cols-[280px_1fr]">
                <DesktopSidebar />
                <div className="flex flex-col">
                    <RightHeader />
                    <main className="flex flex-1 flex-col gap-4 p-4 lg:gap-6 lg:p-6">
                        <div className="flex items-center justify-between">
                            <h1 className="text-lg font-semibold md:text-2xl">Wallet</h1>
                        </div>
                        <SandboxWeb view="wallet" />
                        {(wallet_deposits || wallet_withdrawals) && <div className="grid gap-4 md:grid-cols-2">
                            {wallet_deposits && <Deposit />}
                            {wallet_withdrawals && <Withdraw />}
                        </div>}
                    </main>
                </div>
            </div>
    )
};

export default WalletsPage;
