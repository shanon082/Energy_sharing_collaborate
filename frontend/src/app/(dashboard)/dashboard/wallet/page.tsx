import { Suspense } from 'react'
import DesktopSidebar from "../_components/desktop-sidebar"
import RightHeader from "../_components/right-header"
import Deposit from './_components/deposit';
import Withdraw from './_components/withdraw';
import BalanceCard from './_components/balance-card';
import { get } from '@/lib/fetch';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { History, Wallet as WalletIcon } from "lucide-react";
import { WalletProvider } from '@/app/contexts/walletContext';


async function getWalletData() {
    const response = await get<any>("wallet/balance/");
    if (response.error || !response.data?.success) {
        return { wallet_balance: "0.00", unit_balance: "0.00", meter_units: 0 };
    }
    return {
        wallet_balance: response.data.wallet?.balance || "0.00",
        unit_balance: response.data.unit_balance?.balance || "0.00",
        meter_units: response.data.total_meter_units || 0
    };
}

const WalletsPage = async () => {
    const initialWalletData = await getWalletData();

    return (
        <WalletProvider initialData={initialWalletData}>
            <div className="grid min-h-screen w-full md:grid-cols-[220px_1fr] lg:grid-cols-[280px_1fr]">
                <DesktopSidebar />
                <div className="flex flex-col">
                    <RightHeader />
                    <main className="flex flex-1 flex-col gap-4 p-4 lg:gap-6 lg:p-6">
                        <div className="flex items-center justify-between">
                            <h1 className="text-lg font-semibold md:text-2xl">Wallet Management</h1>
                        </div>
                        
                        {/* Balance Overview Cards - Live Updates */}
                        <BalanceCard />
                        
                        {/* Deposit and Withdraw Section */}
                        <div className="grid gap-4 md:grid-cols-2">
                            <Deposit />
                            <Withdraw />
                        </div>
                        
                        {/* Transaction History Section */}
                        {/* <Card>
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2">
                                    <History className="h-5 w-5" />
                                    Recent Transactions
                                </CardTitle>
                                <CardDescription>
                                    Your recent wallet transactions
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                <Suspense fallback={<div>Loading transactions...</div>}>
                                    <div className="text-center py-8 text-muted-foreground">
                                        <History className="h-12 w-12 mx-auto mb-3 opacity-50" />
                                        <p>Transaction history will appear here</p>
                                    </div>
                                </Suspense>
                            </CardContent>
                        </Card> */}
                        
                        {/* Information Section */}
                        <Card className="bg-blue-50 border-blue-200">
                            <CardContent className="pt-6">
                                <div className="flex items-start gap-3">
                                    <WalletIcon className="h-5 w-5 text-blue-600 mt-0.5" />
                                    <div className="text-sm text-blue-800">
                                        <p className="font-medium mb-1">About Wallet Transactions:</p>
                                        <ul className="list-disc list-inside space-y-1 text-xs">
                                            <li>Deposits and withdrawals are processed securely through MTN Mobile Money (Sandbox Mode)</li>
                                            <li>Use your wallet balance to purchase electricity units or repay loans</li>
                                        </ul>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    </main>
                </div>
            </div>
        </WalletProvider>
    )
};

export default WalletsPage;