"use client";

import { useState, useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { get } from "@/lib/fetch-client";
import { Clock, ArrowUpRight, ArrowDownRight, Zap } from "lucide-react";
import { cn } from "@/lib/utils";

interface Transaction {
  id: string | number;
  transaction_type_display: string;
  transaction_type: string;
  amount?: number | string | null;
  units?: number | string | null;
  status: string;
  created_at: string;
  reference_id?: string;
  channel_display?: string;
}

export default function LatestTransactions() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchLatest = async () => {
      try {
        const response = await get<any>("transactions/history/?page=1&page_size=2");
        
        if (response.data?.success) {
          setTransactions(response.data.transactions || []);
        } else {
          setError("Failed to load recent transactions");
        }
      } catch (err) {
        console.error("Latest transactions fetch error:", err);
        setError("Could not load recent activity");
      } finally {
        setLoading(false);
      }
    };

    fetchLatest();
  }, []);

  // Safe number formatting function
  const formatUnits = (units: number | string | null | undefined): string => {
    if (units === null || units === undefined) return "";
    
    // Convert to number safely
    const num = typeof units === 'string' ? parseFloat(units) : units;
    
    // Check if it's a valid number
    if (isNaN(num)) return "";
    
    // Format with 2 decimal places
    return `${num.toFixed(2)} units`;
  };

  // Safe amount formatting function
  const formatAmount = (amount: number | string | null | undefined): string => {
    if (amount === null || amount === undefined) return "";
    
    // Convert to number safely
    const num = typeof amount === 'string' ? parseFloat(amount) : amount;
    
    // Check if it's a valid number
    if (isNaN(num)) return "";
    
    // Format with commas
    return `${num.toLocaleString()} UGX`;
  };

  const getIcon = (type: string) => {
    if (type.includes("PURCHASE") || type.includes("DISBURSEMENT")) {
      return <ArrowUpRight className="h-4 w-4 text-green-500" />;
    }
    if (type.includes("REPAYMENT") || type.includes("SHARE")) {
      return <ArrowDownRight className="h-4 w-4 text-amber-500" />;
    }
    if (type.includes("UNIT")) {
      return <Zap className="h-4 w-4 text-yellow-500" />;
    }
    return <Clock className="h-4 w-4 text-blue-500" />;
  };

  const getStatusBadge = (status: string) => {
    const variants: Record<string, string> = {
      COMPLETED: "bg-green-100 text-green-800 hover:bg-green-100",
      PENDING: "bg-yellow-100 text-yellow-800 hover:bg-yellow-100",
      FAILED: "bg-red-100 text-red-800 hover:bg-red-100",
      APPROVED: "bg-orange-100 text-orange-800 hover:bg-orange-100",
      DISBURSED: "bg-orange-100 text-orange-800 hover:bg-orange-100",
      SUCCESS: "bg-green-100 text-green-800 hover:bg-green-100",
      REJECTED: "bg-red-100 text-red-800 hover:bg-red-100",
    };
    
    const statusKey = status?.toUpperCase() || "PENDING";
    
    return (
      <Badge variant="outline" className={cn("text-xs", variants[statusKey] || "bg-gray-100")}>
        {status || "PENDING"}
      </Badge>
    );
  };

  // Safe date formatter
  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleString([], {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return "Invalid date";
    }
  };

  return (
    <Card className="border-dashed">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg font-semibold">Latest Activity</CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-4">
            {[...Array(2)].map((_, i) => (
              <div key={i} className="flex items-center gap-4">
                <Skeleton className="h-10 w-10 rounded-full" />
                <div className="space-y-2 flex-1">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-3 w-1/2" />
                </div>
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="text-center text-sm text-muted-foreground py-6">
            {error}
          </div>
        ) : transactions.length === 0 ? (
          <div className="text-center text-sm text-muted-foreground py-8">
            No recent transactions yet
          </div>
        ) : (
          <div className="space-y-4">
            {transactions.map((txn) => {
              const formattedAmount = formatAmount(txn.amount);
              const formattedUnits = formatUnits(txn.units);
              
              return (
                <div
                  key={txn.id}
                  className="flex items-center justify-between border-b pb-3 last:border-0 last:pb-0"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-muted">
                      {getIcon(txn.transaction_type)}
                    </div>
                    <div>
                      <p className="font-medium text-sm">
                        {txn.transaction_type_display || txn.transaction_type.replace(/_/g, ' ')}
                        {txn.channel_display && (
                          <span className="ml-1 text-xs font-normal text-muted-foreground">
                            · {txn.channel_display}
                          </span>
                        )}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {formatDate(txn.created_at)}
                      </p>
                      {txn.reference_id && (
                        <p className="text-xs text-gray-400 mt-0.5">
                          Ref: {txn.reference_id.slice(0, 8)}...
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="text-right space-y-1">
                    {(formattedAmount || formattedUnits) && (
                      <p className="font-medium text-sm">
                        {formattedAmount}
                        {formattedAmount && formattedUnits && <br />}
                        {formattedUnits}
                      </p>
                    )}
                    {getStatusBadge(txn.status)}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}