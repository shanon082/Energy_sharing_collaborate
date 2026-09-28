'use client';

export const dynamic = "force-dynamic";

import { useEffect, useState, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Skeleton } from '@/components/ui/skeleton';
import { AlertTriangle, RefreshCw, Search } from 'lucide-react';
import { get, post } from "@/lib/fetch-client";

interface Transaction {
  id: string;
  type: string;
  user: { id: number; name: string; phone: string };
  amount_kwh: number;
  amount_ugx: number;
  source: string;
  destination: string;
  meter_no: string | null;
  sts_token: string;
  payment_reference: string;
  status: string;
  channel: string;
  failure_reason: string;
  is_flagged: boolean;
  created_at: string;
}

const STATUS_COLORS: Record<string, string> = {
  COMPLETED: "bg-green-100 text-green-800",
  FAILED: "bg-red-100 text-red-800",
  PENDING: "bg-yellow-100 text-yellow-800",
  REVERSED: "bg-gray-100 text-gray-800",
};

const TYPE_LABELS: Record<string, string> = {
  PURCHASE: "Purchase",
  GENERATE_TOKEN: "Generate Token",
  TRANSFER_OUT: "Transfer Out",
  TRANSFER_IN: "Transfer In",
  CREDIT: "Credit",
  REPAYMENT_AUTO: "Auto Repayment",
  REPAYMENT_DIRECT: "Direct Repayment",
  PENALTY: "Penalty",
  REFUND: "Refund",
};

export default function TransactionsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const showFlagged = searchParams.get('flagged') === 'true';

  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);

  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [flaggedOnly, setFlaggedOnly] = useState(showFlagged);

  const [selectedTxn, setSelectedTxn] = useState<Transaction | null>(null);
  const [refundDialog, setRefundDialog] = useState(false);
  const [refundReason, setRefundReason] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fetchTransactions = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), limit: '20' });
      if (search) params.set('user', search);
      if (typeFilter && typeFilter !== 'all') params.set('type', typeFilter);
      if (statusFilter && statusFilter !== 'all') params.set('status', statusFilter);
      if (dateFrom) params.set('date_from', dateFrom);
      if (dateTo) params.set('date_to', dateTo);

      const endpoint = flaggedOnly
        ? 'admin/transactions/flagged/'
        : `admin/transactions/?${params}`;

      const res = await get<any>(endpoint);
      if (res.data) {
        setTransactions(
          flaggedOnly ? res.data.flagged_transactions : res.data.transactions
        );
        setTotal(res.data.pagination?.total || 0);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [page, search, typeFilter, statusFilter, dateFrom, dateTo, flaggedOnly]);

  useEffect(() => { fetchTransactions(); }, [fetchTransactions]);

  async function handleRefund() {
    if (!selectedTxn || !refundReason.trim()) return;
    setSubmitting(true);
    try {
      const res = await post<any>(`admin/transactions/${selectedTxn.id}/refund/`, {
        reason: refundReason,
      });
      if (res.data?.success) {
        setRefundDialog(false);
        setRefundReason('');
        fetchTransactions();
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Transaction Monitor</h1>
        <div className="flex gap-2">
          <Button
            variant={flaggedOnly ? "default" : "outline"}
            size="sm"
            onClick={() => { setFlaggedOnly(!flaggedOnly); setPage(1); }}
          >
            <AlertTriangle className="h-4 w-4 mr-2" />
            {flaggedOnly ? "All Transactions" : "Flagged Only"}
          </Button>
          <Button variant="outline" size="sm" onClick={fetchTransactions}>
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Filters */}
      {!flaggedOnly && (
        <Card>
          <CardContent className="pt-4">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              <div className="relative col-span-2 md:col-span-1">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search user..."
                  className="pl-8"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
              <Select value={typeFilter} onValueChange={setTypeFilter}>
                <SelectTrigger><SelectValue placeholder="Type" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  {Object.entries(TYPE_LABELS).map(([k, v]) => (
                    <SelectItem key={k} value={k}>{v}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger><SelectValue placeholder="Status" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Statuses</SelectItem>
                  <SelectItem value="COMPLETED">Completed</SelectItem>
                  <SelectItem value="FAILED">Failed</SelectItem>
                  <SelectItem value="PENDING">Pending</SelectItem>
                  <SelectItem value="REVERSED">Reversed</SelectItem>
                </SelectContent>
              </Select>
              <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
              <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {flaggedOnly ? "Flagged Transactions" : `Transactions (${total.toLocaleString()})`}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-2">
              {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
            </div>
          ) : transactions.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">No transactions found</p>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-muted-foreground text-xs">
                      <th className="text-left py-2 pr-3">ID</th>
                      <th className="text-left py-2 pr-3">Type</th>
                      <th className="text-left py-2 pr-3">User</th>
                      <th className="text-right py-2 pr-3">kWh</th>
                      <th className="text-right py-2 pr-3">UGX</th>
                      <th className="text-left py-2 pr-3">Status</th>
                      <th className="text-left py-2 pr-3">Channel</th>
                      <th className="text-left py-2 pr-3">Date</th>
                      <th className="text-left py-2">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {transactions.map((t) => (
                      <tr key={t.id} className="border-b last:border-0 hover:bg-muted/40">
                        <td className="py-2 pr-3 font-mono text-xs text-muted-foreground">
                          {t.id.slice(0, 8)}…
                          {t.is_flagged && <AlertTriangle className="inline h-3 w-3 text-amber-500 ml-1" />}
                        </td>
                        <td className="py-2 pr-3">{TYPE_LABELS[t.type] ?? t.type}</td>
                        <td className="py-2 pr-3">
                          <div>{t.user.name}</div>
                          <div className="text-xs text-muted-foreground">{t.user.phone}</div>
                        </td>
                        <td className="py-2 pr-3 text-right tabular-nums">{t.amount_kwh.toFixed(2)}</td>
                        <td className="py-2 pr-3 text-right tabular-nums">{t.amount_ugx.toLocaleString()}</td>
                        <td className="py-2 pr-3">
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[t.status] ?? ''}`}>
                            {t.status}
                          </span>
                        </td>
                        <td className="py-2 pr-3 text-muted-foreground">{t.channel}</td>
                        <td className="py-2 pr-3 text-muted-foreground whitespace-nowrap text-xs">
                          {new Date(t.created_at).toLocaleString()}
                        </td>
                        <td className="py-2">
                          <div className="flex gap-1">
                            <Button variant="ghost" size="sm" className="h-7 text-xs"
                              onClick={() => router.push(`/admin/transactions/${t.id}`)}>
                              View
                            </Button>
                            {t.status === 'FAILED' && (
                              <Button variant="ghost" size="sm" className="h-7 text-xs text-red-600"
                                onClick={() => { setSelectedTxn(t); setRefundDialog(true); }}>
                                Refund
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!flaggedOnly && (
                <div className="flex items-center justify-between mt-4">
                  <p className="text-sm text-muted-foreground">
                    Page {page} of {Math.ceil(total / 20)}
                  </p>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>
                      Previous
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => setPage(p => p + 1)} disabled={page >= Math.ceil(total / 20)}>
                      Next
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Refund dialog */}
      <Dialog open={refundDialog} onOpenChange={setRefundDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Issue Refund</DialogTitle>
            <DialogDescription>
              Refund transaction <span className="font-mono">{selectedTxn?.id.slice(0, 12)}…</span> to {selectedTxn?.user.name}.
              Amount: UGX {selectedTxn?.amount_ugx.toLocaleString()}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <label className="text-sm font-medium">Reason for refund (required)</label>
            <Input
              placeholder="e.g. CVS server timeout, token not delivered"
              value={refundReason}
              onChange={(e) => setRefundReason(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRefundDialog(false)}>Cancel</Button>
            <Button onClick={handleRefund} disabled={!refundReason.trim() || submitting}>
              {submitting ? "Processing…" : "Confirm Refund"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
