"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from "@/components/ui/dropdown-menu"
import {
  EllipsisVertical,
} from "lucide-react";
import { get } from "@/lib/fetch-client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface Transaction {
  id: string | number;
  transaction_type: string;
  transaction_type_display: string;
  amount?: number | null;
  units?: number | null;
  status: string;
  reference_id?: string;
  channel?: string;
  channel_display?: string;
  details?: Record<string, unknown>;
  created_at: string;
}

interface HistorySummary {
  transactions_count: number;
  money_in_ugx: number;
  money_out_ugx: number;
  money_net_ugx: number;
  units_in_kwh: number;
  units_out_kwh: number;
  units_net_kwh: number;
}

const TYPE_FILTER_OPTIONS = [
  { value: "LOAN_APPLICATION", label: "Loan Application" },
  { value: "LOAN_DISBURSEMENT", label: "Loan Disbursement" },
  { value: "LOAN_REPAYMENT", label: "Loan Repayment" },
  { value: "UNIT_PURCHASE", label: "Unit Purchase / Top-up" },
  { value: "UNIT_SHARE", label: "Unit Share" },
  { value: "TOKEN_GENERATE", label: "STS Token" },
  { value: "WALLET_LOAD_AMI", label: "AMI Meter Load" },
];

const TransList = () => {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [selectedTransaction, setSelectedTransaction] = useState<Transaction | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<HistorySummary | null>(null);
  const [filters, setFilters] = useState({
    type: '',
    start_date: '',
    end_date: '',
  });

  const pageSize = 5;

  const fetchTransactions = async (currentPage: number) => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        page: currentPage.toString(),
        page_size: pageSize.toString(),
        ...(filters.type && { type: filters.type }),
        ...(filters.start_date && { start_date: filters.start_date }),
        ...(filters.end_date && { end_date: filters.end_date }),
      });

      const response = await get<any>(`transactions/history/?${params.toString()}`);
      if (response.data?.success) {
        setTransactions(response.data.transactions);
        setTotal(response.data.total);
        setSummary(response.data.summary ?? null);
      } else {
        setError('Failed to load transactions');
      }
    } catch (e) {
      setError('Error loading transactions');
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTransactions(page);
  }, [page, filters]);

  const handleFilterChange = (key: keyof typeof filters, value: string) => {
    setFilters(prev => ({ ...prev, [key]: value }));
    setPage(1);
  };

  const handleResetFilters = () => {
    setFilters({
      type: "",
      start_date: "",
      end_date: "",
    });
    setPage(1);
  };

  const handlePrintStatement = async () => {
    const params = new URLSearchParams({
      page: "1",
      page_size: "500",
      ...(filters.type && { type: filters.type }),
      ...(filters.start_date && { start_date: filters.start_date }),
      ...(filters.end_date && { end_date: filters.end_date }),
    });
    const response = await get<any>(`transactions/history/?${params.toString()}`);
    if (!response.data?.success) {
      setError("Could not prepare statement for printing.");
      return;
    }
    const printRows: Transaction[] = response.data.transactions || [];
    const printSummary: HistorySummary = response.data.summary || summary;
    const period = `${filters.start_date || "All time"} to ${filters.end_date || "Now"}`;
    const html = `
      <html>
        <head>
          <title>gPawa Statement</title>
          <style>
            body { font-family: Arial, sans-serif; padding: 24px; color: #111827; }
            h1 { margin: 0 0 6px 0; }
            .meta { color: #4b5563; margin-bottom: 18px; }
            .grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-bottom: 18px; }
            .card { border: 1px solid #d1d5db; border-radius: 8px; padding: 10px; }
            .label { font-size: 12px; color: #6b7280; }
            .value { font-size: 18px; font-weight: 700; margin-top: 4px; }
            table { width: 100%; border-collapse: collapse; font-size: 12px; }
            th, td { border-bottom: 1px solid #e5e7eb; padding: 8px 6px; text-align: left; }
            th { color: #374151; font-size: 11px; text-transform: uppercase; }
          </style>
        </head>
        <body>
          <h1>gPawa Transaction Statement</h1>
          <div class="meta">Period: ${period} | Generated: ${new Date().toLocaleString()}</div>
          <div class="grid">
            <div class="card"><div class="label">Transactions</div><div class="value">${printSummary?.transactions_count ?? 0}</div></div>
            <div class="card"><div class="label">Money In (UGX)</div><div class="value">${Number(printSummary?.money_in_ugx ?? 0).toLocaleString()}</div></div>
            <div class="card"><div class="label">Money Out (UGX)</div><div class="value">${Number(printSummary?.money_out_ugx ?? 0).toLocaleString()}</div></div>
            <div class="card"><div class="label">Net Money (UGX)</div><div class="value">${Number(printSummary?.money_net_ugx ?? 0).toLocaleString()}</div></div>
            <div class="card"><div class="label">Units In (kWh)</div><div class="value">${Number(printSummary?.units_in_kwh ?? 0).toFixed(2)}</div></div>
            <div class="card"><div class="label">Units Out (kWh)</div><div class="value">${Number(printSummary?.units_out_kwh ?? 0).toFixed(2)}</div></div>
          </div>
          <table>
            <thead><tr><th>ID</th><th>Type</th><th>Status</th><th>Amount/Units</th><th>Date</th></tr></thead>
            <tbody>
              ${printRows.map((txn) => `
                <tr>
                  <td>${displayId(txn.id)}</td>
                  <td>${txn.transaction_type_display || txn.transaction_type}</td>
                  <td>${txn.status}</td>
                  <td>${formatAmountUnits(txn)}</td>
                  <td>${txn.created_at}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </body>
      </html>
    `;
    const popup = window.open("", "_blank");
    if (!popup) {
      setError("Allow popups to print statement.");
      return;
    }
    popup.document.write(html);
    popup.document.close();
    popup.focus();
    popup.print();
  };

  const getTypeBadge = (txn: Transaction) => {
    const type = txn.transaction_type;
    const colors: Record<string, string> = {
      LOAN_APPLICATION: 'bg-blue-500',
      LOAN_DISBURSEMENT: 'bg-indigo-500',
      LOAN_REPAYMENT: 'bg-green-500',
      UNIT_PURCHASE: 'bg-yellow-500',
      UNIT_SHARE: 'bg-purple-500',
      TOKEN_GENERATE: 'bg-orange-500',
      WALLET_LOAD_AMI: 'bg-cyan-500',
    };
    const label = txn.transaction_type_display || type.replace(/_/g, ' ');
    return <Badge className={colors[type] || 'bg-gray-500'}>{label}</Badge>;
  };

  const getChannelBadge = (txn: Transaction) => {
    const label = txn.channel_display || txn.channel;
    if (!label) return null;
    const isUssd = label.toUpperCase().includes('USSD');
    return (
      <Badge variant="outline" className={isUssd ? 'border-violet-400 text-violet-700' : ''}>
        {label}
      </Badge>
    );
  };

  const formatAmountUnits = (txn: Transaction) => {
    const parts: string[] = [];
    if (txn.amount != null && !Number.isNaN(Number(txn.amount))) {
      parts.push(`${Number(txn.amount).toLocaleString()} UGX`);
    }
    if (txn.units != null && !Number.isNaN(Number(txn.units))) {
      parts.push(`${Number(txn.units).toFixed(2)} units`);
    }
    return parts.join(' · ') || '—';
  };

  const displayId = (id: string | number) => {
    const s = String(id);
    if (s.includes('-')) {
      return s.split('-').pop() ?? s;
    }
    return s;
  };

  if (loading) return <p>Loading transactions...</p>;
  if (error) return <p>{error}</p>;

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="flex flex-col gap-4 w-full">
      <h3 className="text-2xl text-left font-bold tracking-tight p-4">
        Transaction History
      </h3>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <Select
          value={filters.type || "ALL"}
          onValueChange={(v) => handleFilterChange('type', v === "ALL" ? "" : v)}
        >
          <SelectTrigger className="w-full sm:w-[200px]">
            <SelectValue placeholder="Filter by Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">All Types</SelectItem>
            {TYPE_FILTER_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Input
          type="date"
          placeholder="Start Date"
          value={filters.start_date}
          onChange={(e) => handleFilterChange('start_date', e.target.value)}
          className="w-full sm:w-auto"
        />
        <Input
          type="date"
          placeholder="End Date"
          value={filters.end_date}
          onChange={(e) => handleFilterChange('end_date', e.target.value)}
          className="w-full sm:w-auto"
        />
        <Button onClick={() => fetchTransactions(1)} className="w-full sm:w-auto">
          Apply Filters
        </Button>
        <Button
          variant="outline"
          onClick={handleResetFilters}
          className="w-full sm:w-auto"
        >
          Reset
        </Button>
        <Button onClick={handlePrintStatement} className="w-full sm:w-auto">
          Print Statement (PDF)
        </Button>
      </div>

      {summary && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
          <div className="rounded-lg border p-3">
            <p className="text-xs text-muted-foreground">Transactions</p>
            <p className="text-lg font-semibold">{summary.transactions_count}</p>
          </div>
          <div className="rounded-lg border p-3">
            <p className="text-xs text-muted-foreground">Money In (UGX)</p>
            <p className="text-lg font-semibold">{summary.money_in_ugx.toLocaleString()}</p>
          </div>
          <div className="rounded-lg border p-3">
            <p className="text-xs text-muted-foreground">Money Out (UGX)</p>
            <p className="text-lg font-semibold">{summary.money_out_ugx.toLocaleString()}</p>
          </div>
          <div className="rounded-lg border p-3">
            <p className="text-xs text-muted-foreground">Net Money (UGX)</p>
            <p className="text-lg font-semibold">{summary.money_net_ugx.toLocaleString()}</p>
          </div>
          <div className="rounded-lg border p-3">
            <p className="text-xs text-muted-foreground">Units In (kWh)</p>
            <p className="text-lg font-semibold">{summary.units_in_kwh.toFixed(2)}</p>
          </div>
          <div className="rounded-lg border p-3">
            <p className="text-xs text-muted-foreground">Units Out (kWh)</p>
            <p className="text-lg font-semibold">{summary.units_out_kwh.toFixed(2)}</p>
          </div>
        </div>
      )}

      <div className="rounded-md border overflow-x-auto w-full max-w-full">
        <Table className="w-full">
          <TableHeader>
            <TableRow>
              <TableHead>ID</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Channel</TableHead>
              <TableHead>Amount/Units</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Date</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {transactions.map((txn) => (
              <TableRow key={txn.id}>
                <TableCell className="font-mono text-xs">{displayId(txn.id)}</TableCell>
                <TableCell>{getTypeBadge(txn)}</TableCell>
                <TableCell>{getChannelBadge(txn) ?? '—'}</TableCell>
                <TableCell>{formatAmountUnits(txn)}</TableCell>
                <TableCell>
                  <Badge variant={txn.status === 'COMPLETED' ? 'default' : 'destructive'}>
                    {txn.status}
                  </Badge>
                </TableCell>
                <TableCell>{txn.created_at}</TableCell>
                <TableCell className="text-right">
                  <DropdownMenu>
                    <DropdownMenuTrigger><EllipsisVertical /></DropdownMenuTrigger>
                    <DropdownMenuContent>
                      <DropdownMenuItem onClick={() => setSelectedTransaction(txn)}>
                        View Details
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
            {transactions.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="text-center">No transactions found</TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between mt-4">
        <Button
          disabled={page === 1}
          onClick={() => setPage(page - 1)}
          className="w-full sm:w-auto"
        >
          Previous
        </Button>
        <span className="text-center">Page {page} of {totalPages}</span>
        <Button
          disabled={page >= totalPages}
          onClick={() => setPage(page + 1)}
          className="w-full sm:w-auto"
        >
          Next
        </Button>
      </div>

      <Dialog
        open={Boolean(selectedTransaction)}
        onOpenChange={(open) => {
          if (!open) setSelectedTransaction(null);
        }}
      >
        <DialogContent className="max-w-xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Transaction Details</DialogTitle>
            <DialogDescription>
              Details for transaction {selectedTransaction ? displayId(selectedTransaction.id) : "-"}.
            </DialogDescription>
          </DialogHeader>

          {selectedTransaction && (
            <div className="space-y-2 text-sm">
              <p><strong>ID:</strong> {selectedTransaction.id}</p>
              <p><strong>Type:</strong> {selectedTransaction.transaction_type_display || selectedTransaction.transaction_type}</p>
              {selectedTransaction.channel_display && (
                <p><strong>Channel:</strong> {selectedTransaction.channel_display}</p>
              )}
              <p><strong>Status:</strong> {selectedTransaction.status}</p>
              <p><strong>Amount:</strong> {selectedTransaction.amount ?? "—"}</p>
              <p><strong>Units:</strong> {selectedTransaction.units ?? "—"}</p>
              <p><strong>Reference ID:</strong> {selectedTransaction.reference_id || "—"}</p>
              <p>
                <strong>Date:</strong>{" "}
                {selectedTransaction.created_at ? new Date(selectedTransaction.created_at).toLocaleString() : "N/A"}
              </p>
              {selectedTransaction.details && (
                <div>
                  <p><strong>Extra Details:</strong></p>
                  <pre className="mt-1 rounded-md bg-muted p-3 text-xs overflow-x-auto">
                    {JSON.stringify(selectedTransaction.details, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default TransList;
