"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import {
  FileTextIcon,
  CheckCircleIcon,
  ClockIcon,
  DollarSignIcon,
  AlertCircleIcon,
  TrendingUpIcon,
} from "lucide-react";
import { get } from "@/lib/fetch";
import { useEffect, useState, useCallback } from "react";
import { useFeatures } from "@/contexts/features-context";

interface LoanStats {
  active_loans: number;
  pending_applications: number;
  approved_loans: number;
  total_repayments: number | string;
  total_borrowed: number | string;
  outstanding_balance: number | string;
  total_loans: number;
}

interface WalletBalanceResponse {
  success: boolean;
  wallet?: { balance?: string | number | null };
  unit_balance?: { balance?: string | number | null };
  total_meter_units?: string | number | null;
}

export default function LoanOverview() {
  const { peer_sharing } = useFeatures();
  const [stats, setStats] = useState<LoanStats>({
    active_loans: 0,
    pending_applications: 0,
    approved_loans: 0,
    total_repayments: 0,
    total_borrowed: 0,
    outstanding_balance: 0,
    total_loans: 0,
  });
  const [loading, setLoading] = useState(true);
  const [moneyBalance, setMoneyBalance] = useState<number>(0);  // UGX money
  const [unitBalance, setUnitBalance] = useState<number>(0);   // Energy units available to share
  const [meterUnits, setMeterUnits] = useState<number>(0);     // Units already on meters

  // Fetch all balances
  const fetchBalances = useCallback(async () => {
    try {
      const response = await get<WalletBalanceResponse>("wallet/balance/");
      
      if (!response.error && response.data?.success) {
        // Money in wallet (UGX) - for deposits/withdrawals/purchases
        setMoneyBalance(Number(response.data.wallet?.balance || 0));
        
        // Units available for sharing (energy units from purchases/loans)
        // FIX: Use unit_balance.balance
        setUnitBalance(Number(response.data.unit_balance?.balance || 0));
        
        // Units already loaded on meters
        // FIX: Use total_meter_units
        setMeterUnits(Number(response.data.total_meter_units || 0));
      }
    } catch (error) {
      console.error("Error fetching balances:", error);
    }
  }, []);

  useEffect(() => {
    void fetchBalances();
  }, [fetchBalances]);

  useEffect(() => {
    async function fetchLoanStats() {
      try {
        const response = await get<LoanStats>("loans/stats/");

        if (response.error) {
          console.warn("Failed to fetch loan stats:", response.error);
          return;
        }

        if (response.data) setStats(response.data);
      } catch (error) {
        console.error("Error fetching loan stats:", error);
      } finally {
        setLoading(false);
      }
    }

    void fetchLoanStats();
  }, []);

  // Format currency values
  const formatCurrency = (amount: number | string) => {
    return new Intl.NumberFormat("en-UG", {
      style: "currency",
      currency: "UGX",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(Number(amount));
  };


  if (loading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i}>
            <CardHeader className="pb-2">
              <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded animate-pulse w-1/2"></div>
              <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded animate-pulse mt-2"></div>
            </CardHeader>
            <CardContent>
              <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded animate-pulse w-3/4"></div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {/* Active Loans */}
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardDescription>Active Loans</CardDescription>
              <ClockIcon className="h-4 w-4 text-blue-500" />
            </div>
            <CardTitle className="text-4xl">{stats.active_loans}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xs text-muted-foreground">
              Currently active electricity loans
            </div>
          </CardContent>
        </Card>

        {/* Money Wallet Card */}
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardDescription>Wallet Balance</CardDescription>
              <DollarSignIcon className="h-4 w-4 text-green-500" />
            </div>
            <CardTitle className="text-3xl">
              {formatCurrency(moneyBalance)}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xs text-muted-foreground">
              Legacy wallet ledger; spending is paused until provenance is reconciled.
            </div>
          </CardContent>
        </Card>
        
        {/* Unit Balance Card (available to share) */}
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardDescription>Historical unit balance</CardDescription>
              <TrendingUpIcon className="h-4 w-4 text-blue-500" />
            </div>
            <CardTitle className="text-4xl">
              {unitBalance.toFixed(2)}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xs text-muted-foreground">
              Historical aggregate; delivery eligibility is shown in Electricity allocation below.
            </div>
          </CardContent>
        </Card>
        
        {/* Meter Units Card */}
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardDescription>Reported meter snapshot</CardDescription>
              <AlertCircleIcon className="h-4 w-4 text-yellow-500" />
            </div>
            <CardTitle className="text-4xl">
              {meterUnits.toFixed(2)}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xs text-muted-foreground">
              Legacy meter snapshot; confirmed new delivery is shown below.
            </div>
          </CardContent>
        </Card>

        {/* Approved Loans */}
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardDescription>Approved Loans</CardDescription>
              <CheckCircleIcon className="h-4 w-4 text-green-500" />
            </div>
            <CardTitle className="text-4xl">{stats.approved_loans}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xs text-muted-foreground">
              Successfully approved
            </div>
          </CardContent>
        </Card>

        {/* Total Loans */}
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardDescription>Total Loans</CardDescription>
              <TrendingUpIcon className="h-4 w-4 text-purple-500" />
            </div>
            <CardTitle className="text-4xl">{stats.total_loans}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xs text-muted-foreground">
              All-time applications
            </div>
          </CardContent>
        </Card>

        {/* Total Borrowed */}
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardDescription>Total Borrowed</CardDescription>
              <DollarSignIcon className="h-4 w-4 text-green-500" />
            </div>
            <CardTitle className="text-3xl">
              {formatCurrency(stats.total_borrowed)}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xs text-muted-foreground">
              Total amount borrowed
            </div>
          </CardContent>
        </Card>

        {/* Total Repayments */}
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardDescription>Total Repayments</CardDescription>
              <DollarSignIcon className="h-4 w-4 text-blue-500" />
            </div>
            <CardTitle className="text-3xl">
              {formatCurrency(stats.total_repayments)}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xs text-muted-foreground">Amount repaid</div>
          </CardContent>
        </Card>

        {/* Outstanding Balance */}
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardDescription>Outstanding Payback Amount</CardDescription>
              <DollarSignIcon className="h-4 w-4 text-orange-500" />
            </div>
            <CardTitle className="text-3xl">
              {formatCurrency(stats.outstanding_balance)}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-xs text-muted-foreground">
              Amount yet to be repaid
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions Card */}
      <Card className="border-slate-200/80 bg-white/90 shadow-sm dark:border-white/10 dark:bg-card/95 dark:shadow-black/20">
        <CardHeader className="pb-2">
          <CardDescription>Quick Actions</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col md:flex-row gap-2">
          <Button asChild variant="outline" className="flex-1">
            <Link href="/dashboard/request-loan">
              <FileTextIcon className="h-4 w-4 mr-2" />
              Apply for Loan
            </Link>
          </Button>
          <Button asChild variant="outline" className="flex-1">
            <Link href="/dashboard/myloans">
              <CheckCircleIcon className="h-4 w-4 mr-2" />
              View My Loans
            </Link>
          </Button>
          {peer_sharing && <Button asChild variant="outline" className="flex-1">
            <Link href="/dashboard/share">
              <TrendingUpIcon className="h-4 w-4 mr-2" />
              Share Units
            </Link>
          </Button>}
        </CardContent>
      </Card>
    </div>
  );
}
