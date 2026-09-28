'use client';

export const dynamic = "force-dynamic";

import { useEffect, useState } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
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
  Search,
  Filter,
  Download,
  Plus,
  DollarSign,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  MoreVertical,
  Eye,
  Zap,
  CreditCard,
  Calendar,
  TrendingUp,
  Users,
  Banknote,
  Activity
} from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { authFetch } from '@/lib/auth';
import { useToast } from '@/components/ui/use-toast';
import { useRouter } from 'next/navigation';
import { get, post } from '@/lib/fetch-client';
import { getApiErrorMessage } from '@/lib/api-response';
import Link from 'next/link';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

interface Loan {
  id: number;
  loan_id: string;  // Changed from loan_number to match backend
  user: {
    id: number;
    name: string;
    email: string;
    phone_number: string;
    account_active: boolean;
  };
  amount_requested: number;
  amount_approved: number | null;
  interest_rate: number;
  loan_tier: string | null;
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'DISBURSED' | 'COMPLETED' | 'DEFAULTED';
  purpose: string;
  tenure_months: number;
  created_at: string;
  credit_score: number | null;
  tariff: {
    id: number;
    tariff_code: string;
    tariff_name: string;
  } | null;
  disbursement?: {
    token: string;
    units_disbursed: number;
    disbursement_date: string;
    token_expiry: string;
  };
  outstanding_balance: number;
  total_amount_due: number;
  amount_paid: number;
  due_date: string | null;
  rejection_reason: string | null;
  repayments: LoanRepayment[];
}

interface LoanRepayment {
  id: number;
  amount_paid: number;
  payment_date: string;
  units_paid: number;
  is_on_time: boolean;
  payment_reference: string;
}

interface LoansDashboard {
  total_active_loans: number;
  loans_due_this_week: number;
  overdue_loans: number;
  repayment_rate_30d: number;
}

function normalizeAdminLoan(raw: Record<string, unknown>): Loan {
  const user = (raw.user ?? {}) as Loan["user"] & { phone?: string };

  let id = 0;
  if (typeof raw.id === "number" && Number.isFinite(raw.id)) {
    id = raw.id;
  } else if (typeof raw.id === "string" && /^\d+$/.test(raw.id)) {
    id = Number(raw.id);
  } else if (typeof raw.loan_id === "number" && Number.isFinite(raw.loan_id)) {
    // Legacy admin list API used loan_id for the database primary key.
    id = raw.loan_id;
  }

  const loanRef =
    (typeof raw.loan_ref === "string" && raw.loan_ref) ||
    (typeof raw.loan_id === "string" ? raw.loan_id : "") ||
    (id > 0 ? String(id) : "");

  return {
    ...(raw as unknown as Loan),
    id,
    loan_id: loanRef,
    user: {
      ...user,
      phone_number: user.phone_number ?? user.phone ?? "",
    },
  };
}

function formatUgx(amount: number) {
  return `UGX ${Math.round(amount).toLocaleString()}`;
}

function getLoanRowKey(loan: Loan): string {
  if (loan.id > 0) return `loan-${loan.id}`;
  if (loan.loan_id) return `loan-ref-${loan.loan_id}`;
  return `loan-${loan.created_at}-${loan.user?.email ?? "unknown"}`;
}

function getLoanPrimaryKey(loan: Loan | null): number | null {
  if (!loan) return null;
  if (Number.isFinite(loan.id) && loan.id > 0) return loan.id;
  const fallback = Number(loan.loan_id);
  return Number.isFinite(fallback) && fallback > 0 ? fallback : null;
}

export default function LoansManagementPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [loans, setLoans] = useState<Loan[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalLoans, setTotalLoans] = useState(0);
  const [selectedLoan, setSelectedLoan] = useState<Loan | null>(null);
  const [showLoanDetails, setShowLoanDetails] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [dashboard, setDashboard] = useState<LoansDashboard | null>(null);
  // Penalty waiver state
  const [waiverDialog, setWaiverDialog] = useState<Loan | null>(null);
  const [waiverReason, setWaiverReason] = useState('');
  const [waiverError, setWaiverError] = useState('');
  const [disburseDialog, setDisburseDialog] = useState<Loan | null>(null);
  const [disburseError, setDisburseError] = useState('');
  const limit = 10;

  const fetchLoans = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({
        page: currentPage.toString(),
        limit: limit.toString(),
        ...(search && { search }),
        ...(statusFilter !== 'all' && { status: statusFilter.toUpperCase() })
      });

      const res = await get<any>(`admin/loans/?${params}`);

      if (res.error) throw new Error('Failed to fetch loans');

      if (res.data && res.data.loans) {
        setLoans(res.data.loans.map((loan: Record<string, unknown>) => normalizeAdminLoan(loan)));
        setTotalPages(res.data.pagination?.pages || 1);
        setTotalLoans(res.data.pagination?.total || 0);
      }
    } catch (error) {
      console.error('Error fetching loans:', error);
      toast({
        title: 'Error',
        description: 'Failed to load loans',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status: Loan['status']) => {
    const variants = {
      PENDING: { variant: "secondary" as const, icon: Clock, label: "Pending" },
      APPROVED: { variant: "success" as const, icon: CheckCircle, label: "Approved" },
      REJECTED: { variant: "destructive" as const, icon: XCircle, label: "Rejected" },
      DISBURSED: { variant: "default" as const, icon: DollarSign, label: "Active" },
      COMPLETED: { variant: "outline" as const, icon: CheckCircle, label: "Completed" },
      DEFAULTED: { variant: "destructive" as const, icon: AlertCircle, label: "Defaulted" },
    };

    const { variant, icon: Icon, label } = variants[status] || variants.PENDING;

    return (
      <Badge variant={variant} className="gap-1">
        <Icon className="h-3 w-3" />
        {label}
      </Badge>
    );
  };

  const getTierBadge = (tier: string | null) => {
    if (!tier) return null;

    const tierColors = {
      BRONZE: "bg-amber-700/10 text-amber-700 border-amber-200",
      SILVER: "bg-gray-300/10 text-gray-600 border-gray-300",
      GOLD: "bg-yellow-400/10 text-yellow-700 border-yellow-300",
      PLATINUM: "bg-indigo-100 text-indigo-700 border-indigo-300"
    };

    const colorClass = tierColors[tier as keyof typeof tierColors] || "bg-gray-100 text-gray-700";

    return (
      <Badge variant="outline" className={colorClass}>
        {tier}
      </Badge>
    );
  };

  const exportLoans = () => {
    const csvContent = [
      ['Loan ID', 'Customer', 'Email', 'Phone', 'Amount Requested', 'Amount Approved',
        'Status', 'Tier', 'Interest Rate', 'Tenure', 'Created At', 'Credit Score'],
      ...loans.map(loan => [
        loan.loan_id,
        loan.user.name,
        loan.user.email,
        loan.user.phone_number,
        `UGX ${loan.amount_requested.toLocaleString()}`,
        loan.amount_approved ? `UGX ${loan.amount_approved.toLocaleString()}` : 'N/A',
        loan.status,
        loan.loan_tier || 'N/A',
        `${loan.interest_rate}%`,
        `${loan.tenure_months} months`,
        new Date(loan.created_at).toLocaleDateString(),
        loan.credit_score || 'N/A'
      ])
    ].map(row => row.join(',')).join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `loans_export_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
  };

  const approveLoan = async (loanId: number) => {
    setActionLoading(true);
    try {
      // TODO: Implement API call to approve loan
      // const res = await authFetch(`admin/loans/${loanId}/approve/`, {
      //   method: 'POST',
      // });

      toast({
        title: 'Success',
        description: 'Loan approved successfully',
      });
      fetchLoans();
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to approve loan',
        variant: 'destructive',
      });
    } finally {
      setActionLoading(false);
    }
  };

  const rejectLoan = async (loanId: number) => {
    setActionLoading(true);
    try {
      // TODO: Implement API call to reject loan
      // const res = await authFetch(`/api/admin/loans/${loanId}/reject/`, {
      //   method: 'POST',
      //   body: JSON.stringify({ reason: 'Rejected by admin' })
      // });

      toast({
        title: 'Success',
        description: 'Loan rejected',
      });
      fetchLoans();
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to reject loan',
        variant: 'destructive',
      });
    } finally {
      setActionLoading(false);
    }
  };

  const fetchDashboard = async () => {
    try {
      const res = await get<any>('admin/loans/dashboard/');
      if (res.data?.success) setDashboard(res.data);
    } catch {}
  };

  const disburseLoan = async () => {
    if (!disburseDialog) return;
    const loanPk = getLoanPrimaryKey(disburseDialog);
    if (!loanPk) {
      setDisburseError("Could not resolve loan ID. Refresh the page and try again.");
      return;
    }

    setActionLoading(true);
    setDisburseError("");
    try {
      const res = await post<{ success?: boolean; message?: string; units_disbursed?: number }>(
        `admin/loans/${loanPk}/disburse/`,
        {}
      );
      if (res.error || !res.data?.success) {
        const message = getApiErrorMessage(res.error, "Failed to disburse loan");
        setDisburseError(message);
        toast({ title: "Error", description: message, variant: "destructive" });
        return;
      }
      const units = res.data.units_disbursed;
      toast({
        title: "Success",
        description:
          res.data.message +
          (units != null ? ` (${units} kWh credited to wallet)` : ""),
      });
      setDisburseDialog(null);
      setDisburseError("");
      fetchLoans();
      fetchDashboard();
    } catch {
      const message = "Failed to disburse loan";
      setDisburseError(message);
      toast({ title: "Error", description: message, variant: "destructive" });
    } finally {
      setActionLoading(false);
    }
  };

  const waivePenalty = async () => {
    if (!waiverDialog || !waiverReason.trim()) return;
    const loanPk = getLoanPrimaryKey(waiverDialog);
    if (!loanPk) {
      setWaiverError("Could not resolve loan ID. Refresh the page and try again.");
      return;
    }

    setActionLoading(true);
    setWaiverError("");
    try {
      const res = await post<{ success?: boolean; message?: string }>(
        `admin/loans/${loanPk}/waive-penalty/`,
        { reason: waiverReason.trim() }
      );
      if (res.error || !res.data?.success) {
        const message = getApiErrorMessage(res.error, "Failed to waive penalty");
        setWaiverError(message);
        toast({
          title: "Error",
          description: message,
          variant: "destructive",
        });
        return;
      }
      toast({ title: "Success", description: res.data.message || "Late penalty waived" });
      setWaiverDialog(null);
      setWaiverReason("");
      setWaiverError("");
      fetchLoans();
    } catch {
      const message = "Failed to waive penalty";
      setWaiverError(message);
      toast({ title: "Error", description: message, variant: "destructive" });
    } finally {
      setActionLoading(false);
    }
  };

  useEffect(() => {
    fetchLoans();
    fetchDashboard();
  }, [currentPage, search, statusFilter]);

  // Calculate stats
  const stats = {
    total: loans.length,
    pending: loans.filter(l => l.status === 'PENDING').length,
    approved: loans.filter(l => l.status === 'APPROVED').length,
    disbursed: loans.filter(l => l.status === 'DISBURSED').length,
    completed: loans.filter(l => l.status === 'COMPLETED').length,
    defaulted: loans.filter(l => l.status === 'DEFAULTED').length,
    rejected: loans.filter(l => l.status === 'REJECTED').length,
    totalRequested: loans.reduce((acc, loan) => acc + loan.amount_requested, 0),
    totalApproved: loans.reduce((acc, loan) => acc + (loan.amount_approved || 0), 0),
    totalOutstanding: loans.reduce((acc, loan) => acc + loan.outstanding_balance, 0),
    avgCreditScore: Math.round(
      loans.filter(l => l.credit_score).reduce((acc, loan) => acc + (loan.credit_score || 0), 0) /
      loans.filter(l => l.credit_score).length || 0
    ),
  };

  if (loading && loans.length === 0) {
    return <LoansManagementSkeleton />;
  }

  return (
    <div className="container mx-auto py-6 space-y-6">
      {/* Spec Section 5 KPI widgets */}
      {dashboard && (
        <div className="grid gap-4 grid-cols-2 md:grid-cols-4">
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-xs font-medium text-muted-foreground">Active Loans</CardTitle></CardHeader>
            <CardContent><div className="text-2xl font-bold">{dashboard.total_active_loans}</div></CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-xs font-medium text-muted-foreground">Due This Week</CardTitle></CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{dashboard.loans_due_this_week}</div>
            </CardContent>
          </Card>
          <Card className={dashboard.overdue_loans > 0 ? "border-red-200" : ""}>
            <CardHeader className="pb-2"><CardTitle className="text-xs font-medium text-muted-foreground">Overdue</CardTitle></CardHeader>
            <CardContent>
              <div className={`text-2xl font-bold ${dashboard.overdue_loans > 0 ? "text-red-600" : ""}`}>
                {dashboard.overdue_loans}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-xs font-medium text-muted-foreground">Repayment Rate (30d)</CardTitle></CardHeader>
            <CardContent><div className="text-2xl font-bold">{dashboard.repayment_rate_30d}%</div></CardContent>
          </Card>
        </div>
      )}

      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Loan Management</h1>
          <p className="text-muted-foreground">
            Manage all loan applications, disbursements, and repayments
          </p>
          <div className="flex flex-col gap-2 mt-2 sm:flex-row">
            <Link href="/admin/loan-tiers">
              <Button variant="outline" size="sm" className="w-full sm:w-auto">
                <TrendingUp className="mr-2 h-4 w-4" />
                Manage Loan Tiers
              </Button>
            </Link>
            <Link href="/admin/tariffs">
              <Button variant="outline" size="sm" className="w-full sm:w-auto">
                <Zap className="mr-2 h-4 w-4" />
                Manage Tariffs
              </Button>
            </Link>
          </div>
        </div>
        <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:items-center">
          <Button variant="outline" onClick={exportLoans} className="w-full sm:w-auto">
            <Download className="mr-2 h-4 w-4" />
            Export CSV
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Total Loans</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total}</div>
            <p className="text-xs text-muted-foreground">
              UGX {stats.totalRequested.toLocaleString()} requested
            </p>
            <div className="flex gap-2 mt-2 text-xs">
              <Badge variant="secondary" className="gap-1">
                <CheckCircle className="h-3 w-3" />
                {stats.approved} Approved
              </Badge>
              <Badge variant="outline" className="gap-1">
                <Clock className="h-3 w-3" />
                {stats.pending} Pending
              </Badge>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Active Loans</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.disbursed}</div>
            <p className="text-xs text-muted-foreground">
              UGX {stats.totalOutstanding.toLocaleString()} outstanding
            </p>
            <div className="flex gap-2 mt-2 text-xs">
              <Badge variant="default" className="gap-1">
                <Activity className="h-3 w-3" />
                {stats.completed} Completed
              </Badge>
              <Badge variant="destructive" className="gap-1">
                <AlertCircle className="h-3 w-3" />
                {stats.defaulted} Defaulted
              </Badge>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Amount Approved</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              UGX {stats.totalApproved.toLocaleString()}
            </div>
            <p className="text-xs text-muted-foreground">
              {stats.totalRequested > 0
                ? ((stats.totalApproved / stats.totalRequested) * 100).toFixed(1)
                : 0}% approval rate
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Average Credit Score</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.avgCreditScore || 'N/A'}</div>
            <p className="text-xs text-muted-foreground">
              Based on {loans.filter(l => l.credit_score).length} applications
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
              <Input
                placeholder="Search by loan ID, customer name, email, or phone..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-full sm:w-[200px]">
                <Filter className="mr-2 h-4 w-4" />
                <SelectValue placeholder="Filter by status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Loans</SelectItem>
                <SelectItem value="PENDING">Pending</SelectItem>
                <SelectItem value="APPROVED">Approved</SelectItem>
                <SelectItem value="REJECTED">Rejected</SelectItem>
                <SelectItem value="DISBURSED">Active</SelectItem>
                <SelectItem value="COMPLETED">Completed</SelectItem>
                <SelectItem value="DEFAULTED">Defaulted</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Loan Details</TableHead>
                  <TableHead>Customer</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Status & Tier</TableHead>
                  <TableHead>Timeline</TableHead>
                  <TableHead>Credit Score</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loans.map((loan) => (
                  <TableRow key={getLoanRowKey(loan)}>
                    <TableCell>
                      <div className="flex flex-col">
                        <span className="font-medium font-mono text-xs">{loan.loan_id}</span>
                        <span className="text-sm truncate max-w-[150px]">
                          {loan.purpose?.substring(0, 30)}
                          {loan.purpose?.length > 30 ? '...' : ''}
                        </span>
                        {loan.tariff && (
                          <span className="text-xs text-muted-foreground">
                            {loan.tariff.tariff_code}
                          </span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col">
                        <span className="font-medium">{loan.user.name}</span>
                        <span className="text-xs text-muted-foreground">
                          {loan.user.email}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {loan.user.phone_number}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col">
                        <span className="font-medium">
                          UGX {loan.amount_requested.toLocaleString()}
                        </span>
                        {loan.amount_approved && (
                          <span className="text-xs text-green-600">
                            Approved: UGX {loan.amount_approved.toLocaleString()}
                          </span>
                        )}
                        {loan.status === 'DISBURSED' && loan.disbursement && (
                          <span className="text-xs text-blue-600">
                            Units: {loan.disbursement.units_disbursed} kWh
                          </span>
                        )}
                        <span className="text-xs text-muted-foreground">
                          {loan.tenure_months} months @ {loan.interest_rate}%
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col gap-1">
                        {getStatusBadge(loan.status)}
                        {getTierBadge(loan.loan_tier)}
                        {loan.status === 'DISBURSED' && loan.outstanding_balance > 0 && (
                          <Badge variant="outline" className="text-xs">
                            Balance: UGX {loan.outstanding_balance.toLocaleString()}
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col text-sm">
                        <span>
                          Applied: {new Date(loan.created_at).toLocaleDateString()}
                        </span>
                        {loan.due_date && (
                          <span className="text-xs text-muted-foreground">
                            Due: {new Date(loan.due_date).toLocaleDateString()}
                          </span>
                        )}
                        {loan.disbursement && (
                          <span className="text-xs text-green-600">
                            Disbursed: {new Date(loan.disbursement.disbursement_date).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      {loan.credit_score ? (
                        <div className="flex items-center gap-1">
                          <span className={`font-medium ${loan.credit_score >= 80 ? 'text-green-600' :
                              loan.credit_score >= 75 ? 'text-yellow-600' : 'text-red-600'
                            }`}>
                            {loan.credit_score}
                          </span>
                          <span className="text-xs text-muted-foreground">/100</span>
                        </div>
                      ) : (
                        <span className="text-muted-foreground text-sm">N/A</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setSelectedLoan(loan);
                            setShowLoanDetails(true);
                          }}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>

                        {loan.status === 'PENDING' && (
                          <>
                            <Button
                              size="sm"
                              onClick={() => approveLoan(loan.id)}
                              disabled={actionLoading}
                            >
                              Approve
                            </Button>
                            <Button
                              size="sm"
                              variant="destructive"
                              onClick={() => rejectLoan(loan.id)}
                              disabled={actionLoading}
                            >
                              Reject
                            </Button>
                          </>
                        )}

                        {loan.status === 'APPROVED' && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setDisburseError("");
                              setDisburseDialog(loan);
                            }}
                          >
                            <CreditCard className="h-4 w-4 mr-1" />
                            Disburse
                          </Button>
                        )}

                        {loan.status === 'DISBURSED' && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => router.push(`/admin/loans/${loan.id}`)}
                          >
                            View Details
                          </Button>
                        )}

                        {/* Penalty waiver — Admin only, for overdue active loans */}
                        {(loan.status === 'DISBURSED' || loan.status === 'APPROVED') && (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-amber-600 text-xs"
                            onClick={() => {
                              setWaiverReason("");
                              setWaiverError("");
                              setWaiverDialog(loan);
                            }}
                          >
                            Waive Penalty
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}

                {loans.length === 0 && !loading && (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center py-8">
                      <div className="flex flex-col items-center gap-2">
                        <Banknote className="h-12 w-12 text-muted-foreground" />
                        <p className="text-muted-foreground">No loans found</p>
                      </div>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-end space-x-2 py-4">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                disabled={currentPage === 1}
              >
                Previous
              </Button>
              <span className="text-sm">
                Page {currentPage} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
              >
                Next
              </Button>
            </div>
          )}
        </CardContent>
      </Card>


      {/* Loan Details Dialog */}
      <Dialog open={showLoanDetails} onOpenChange={setShowLoanDetails}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Loan Details - {selectedLoan?.loan_id || selectedLoan?.id}</DialogTitle>
            <DialogDescription>
              Complete information about this loan application
            </DialogDescription>
          </DialogHeader>

          {selectedLoan && (
            <Tabs defaultValue="details">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="details">Loan Details</TabsTrigger>
                <TabsTrigger value="customer">Customer Info</TabsTrigger>
                <TabsTrigger value="repayments">Repayments</TabsTrigger>
              </TabsList>

              <TabsContent value="details" className="space-y-4">
                <div className="grid grid-cols-2 gap-4 mt-4">
                  <div>
                    <p className="text-sm text-muted-foreground">Loan ID</p>
                    <p className="font-medium">{selectedLoan.loan_id || selectedLoan.id}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Status</p>
                    <div>{getStatusBadge(selectedLoan.status)}</div>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Amount Requested</p>
                    <p className="font-medium">
                      UGX {(selectedLoan.amount_requested || 0).toLocaleString()}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Amount Approved</p>
                    <p className="font-medium">
                      {selectedLoan.amount_approved
                        ? `UGX ${selectedLoan.amount_approved.toLocaleString()}`
                        : 'N/A'}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Interest Rate</p>
                    <p className="font-medium">{selectedLoan.interest_rate || 0}%</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Tenure</p>
                    <p className="font-medium">{selectedLoan.tenure_months || 6} months</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Loan Tier</p>
                    <p className="font-medium">{selectedLoan.loan_tier || 'N/A'}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Credit Score</p>
                    <p className="font-medium">{selectedLoan.credit_score || 'N/A'}/100</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Tariff</p>
                    <p className="font-medium">{selectedLoan.tariff?.tariff_name || 'N/A'}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Purpose</p>
                    <p className="font-medium">{selectedLoan.purpose || 'N/A'}</p>
                  </div>
                </div>

                {selectedLoan.disbursement && (
                  <>
                    <h3 className="font-semibold mt-4">Disbursement Details</h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-sm text-muted-foreground">Token</p>
                        <p className="font-medium font-mono">{selectedLoan.disbursement.token}</p>
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">Units Disbursed</p>
                        <p className="font-medium">{selectedLoan.disbursement.units_disbursed || 0} kWh</p>
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">Disbursement Date</p>
                        <p className="font-medium">
                          {selectedLoan.disbursement.disbursement_date
                            ? new Date(selectedLoan.disbursement.disbursement_date).toLocaleString()
                            : 'N/A'}
                        </p>
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">Token Expiry</p>
                        <p className="font-medium">
                          {selectedLoan.disbursement.token_expiry
                            ? new Date(selectedLoan.disbursement.token_expiry).toLocaleDateString()
                            : 'N/A'}
                        </p>
                      </div>
                    </div>
                  </>
                )}

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-muted-foreground">Total Amount Due</p>
                    <p className="font-medium">
                      UGX {(selectedLoan.total_amount_due || 0).toLocaleString()}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Amount Paid</p>
                    <p className="font-medium">
                      UGX {(selectedLoan.amount_paid || 0).toLocaleString()}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Outstanding Balance</p>
                    <p className="font-medium text-red-600">
                      UGX {(selectedLoan.outstanding_balance || 0).toLocaleString()}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Due Date</p>
                    <p className="font-medium">
                      {selectedLoan.due_date
                        ? new Date(selectedLoan.due_date).toLocaleDateString()
                        : 'N/A'}
                    </p>
                  </div>
                </div>

                {selectedLoan.rejection_reason && (
                  <div>
                    <p className="text-sm text-muted-foreground">Rejection Reason</p>
                    <p className="text-red-600">{selectedLoan.rejection_reason}</p>
                  </div>
                )}
              </TabsContent>

              <TabsContent value="customer">
                <div className="space-y-4 mt-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-sm text-muted-foreground">Name</p>
                      <p className="font-medium">{selectedLoan.user?.name || 'N/A'}</p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Email</p>
                      <p className="font-medium">{selectedLoan.user?.email || 'N/A'}</p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Phone</p>
                      <p className="font-medium">{selectedLoan.user?.phone_number || 'N/A'}</p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Account Status</p>
                      <Badge variant={selectedLoan.user?.account_active ? "success" : "secondary"}>
                        {selectedLoan.user?.account_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </div>
                  </div>

                  <Button
                    variant="outline"
                    className="w-full"
                    onClick={() => {
                      setShowLoanDetails(false);
                      router.push(`/admin/users/${selectedLoan.user?.id}`);
                    }}
                  >
                    <Users className="h-4 w-4 mr-2" />
                    View Full Customer Profile
                  </Button>
                </div>
              </TabsContent>

              <TabsContent value="repayments">
                <div className="space-y-4 mt-4">
                  {selectedLoan.repayments && selectedLoan.repayments.length > 0 ? (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Date</TableHead>
                          <TableHead>Amount</TableHead>
                          <TableHead>Units</TableHead>
                          <TableHead>Reference</TableHead>
                          <TableHead>Status</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {selectedLoan.repayments.map((repayment: any) => (
                          <TableRow key={repayment.id}>
                            <TableCell>
                              {repayment.payment_date
                                ? new Date(repayment.payment_date).toLocaleDateString()
                                : 'N/A'}
                            </TableCell>
                            <TableCell>
                              UGX {(repayment.amount_paid || 0).toLocaleString()}
                            </TableCell>
                            <TableCell>{repayment.units_paid || 0} kWh</TableCell>
                            <TableCell className="font-mono text-xs">
                              {repayment.payment_reference || 'N/A'}
                            </TableCell>
                            <TableCell>
                              <Badge variant={repayment.is_on_time ? "success" : "destructive"}>
                                {repayment.is_on_time ? 'On Time' : 'Late'}
                              </Badge>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  ) : (
                    <p className="text-center text-muted-foreground py-4">
                      No repayments recorded yet
                    </p>
                  )}
                </div>
              </TabsContent>
            </Tabs>
          )}
        </DialogContent>
      </Dialog>

      {/* Penalty waiver dialog (Admin only) */}
      <Dialog
        open={!!waiverDialog}
        onOpenChange={(open) => {
          if (!open) {
            setWaiverDialog(null);
            setWaiverReason("");
            setWaiverError("");
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Waive Late Penalty</DialogTitle>
            <DialogDescription>
              Waive late payment penalty for loan <strong>{waiverDialog?.loan_id}</strong> — {waiverDialog?.user.name}.
              This action will be audit-logged.
            </DialogDescription>
          </DialogHeader>
          <form
            className="space-y-3"
            onSubmit={(e) => {
              e.preventDefault();
              void waivePenalty();
            }}
          >
            <div className="space-y-1">
              <label className="text-sm font-medium">Reason for waiver *</label>
              <Input
                placeholder="e.g. Medical emergency, first-time offence"
                value={waiverReason}
                onChange={(e) => {
                  setWaiverReason(e.target.value);
                  if (waiverError) setWaiverError("");
                }}
              />
            </div>
            {waiverError && (
              <p className="text-sm text-destructive">{waiverError}</p>
            )}
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setWaiverDialog(null);
                  setWaiverReason("");
                  setWaiverError("");
                }}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={!waiverReason.trim() || actionLoading}>
                {actionLoading ? "Processing…" : "Confirm Waiver"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Disburse loan dialog */}
      <Dialog
        open={!!disburseDialog}
        onOpenChange={(open) => {
          if (!open) {
            setDisburseDialog(null);
            setDisburseError("");
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Disburse Loan</DialogTitle>
            <DialogDescription>
              Credit approved units to <strong>{disburseDialog?.user.name}</strong>&apos;s wallet for loan{" "}
              <strong>{disburseDialog?.loan_id}</strong> ({formatUgx(disburseDialog?.amount_approved ?? disburseDialog?.amount_requested ?? 0)}).
            </DialogDescription>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            This credits electricity units to the customer&apos;s unit wallet and marks the loan as disbursed.
          </p>
          {disburseError && <p className="text-sm text-destructive">{disburseError}</p>}
          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setDisburseDialog(null);
                setDisburseError("");
              }}
            >
              Cancel
            </Button>
            <Button onClick={() => void disburseLoan()} disabled={actionLoading}>
              {actionLoading ? "Disbursing…" : "Confirm Disbursement"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function LoansManagementSkeleton() {
  return (
    <div className="container mx-auto py-6 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        <div className="space-y-2">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-64" />
        </div>
        <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
          <Skeleton className="h-10 w-full sm:w-24" />
          <Skeleton className="h-10 w-full sm:w-24" />
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i}>
            <CardHeader className="pb-2">
              <Skeleton className="h-4 w-24" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-8 w-16" />
              <Skeleton className="h-4 w-32 mt-2" />
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row gap-4">
            <Skeleton className="h-10 flex-1" />
            <Skeleton className="h-10 w-full sm:w-48" />
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <Skeleton className="h-10 w-full" />
            {[...Array(5)].map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

