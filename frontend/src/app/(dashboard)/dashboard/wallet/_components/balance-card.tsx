"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Wallet, TrendingUp, TrendingDown, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useState } from "react";
import { useWallet } from "@/app/contexts/walletContext";

export default function BalanceCard() {
  const { walletData, isLoading, refreshBalances } = useWallet();
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = async () => {
    setRefreshing(true);
    await refreshBalances();
    setTimeout(() => setRefreshing(false), 1000);
  };

  return (
    <div className="grid gap-4 md:grid-cols-3">
      <Card className="bg-gradient-to-r from-green-500 to-green-600 text-white relative overflow-hidden">
        <div className="absolute top-2 right-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleRefresh}
            disabled={refreshing || isLoading}
            className="text-white hover:bg-green-600"
          >
            <RefreshCw className={`h-4 w-4 ${refreshing || isLoading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
        <CardHeader className="pb-2">
          <CardDescription className="text-green-100">Available Balance</CardDescription>
          <CardTitle className="text-3xl text-white">
            UGX {Number(walletData.wallet_balance).toLocaleString()}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 text-green-100">
            <Wallet className="h-4 w-4" />
            <span className="text-xs">Money available for transactions</span>
          </div>
        </CardContent>
      </Card>
      
      <Card>
        <CardHeader className="pb-2">
          <CardDescription>Unit Balance</CardDescription>
          <CardTitle className="text-3xl">
            {Number(walletData.unit_balance).toLocaleString()}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 text-muted-foreground">
            <TrendingUp className="h-4 w-4" />
            <span className="text-xs">Units available to share</span>
          </div>
        </CardContent>
      </Card>
      
      <Card>
        <CardHeader className="pb-2">
          <CardDescription>Meter Units</CardDescription>
          <CardTitle className="text-3xl">
            {Number(walletData.meter_units).toLocaleString()}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 text-muted-foreground">
            <TrendingDown className="h-4 w-4" />
            <span className="text-xs">Units on your physical meter</span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}