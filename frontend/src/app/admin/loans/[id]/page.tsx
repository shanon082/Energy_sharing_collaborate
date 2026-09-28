'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
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
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/use-toast';
import { get, post } from '@/lib/fetch-client';
import { getApiErrorMessage } from '@/lib/api-response';
import {
    ArrowLeft,
    DollarSign,
    Clock,
    CheckCircle,
    XCircle,
    AlertCircle,
    User,
    Calendar,
    Zap,
    TrendingUp,
    Download,
    CreditCard,
    FileText,
    History,
    Mail,
    Phone,
    MapPin,
    Home,
    Activity,
    Wallet,
    Percent,
    Award,
    Shield,
    Copy,
    ExternalLink
} from 'lucide-react';
import Link from 'next/link';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from '@/components/ui/dialog';
import { Separator } from '@/components/ui/separator';

interface LoanDetail {
    id: number;
    loan_id: string;
    user: {
        id: number;
        email: string;
        first_name: string;
        last_name: string;
        phone_number: string;
        gender: string;
        email_verified: boolean;
        account_active: boolean;
        created_at: string;
        last_login: string | null;
        profile_data: {
            monthly_expenditure: string;
            purchase_frequency: string;
            payment_consistency: string;
            disconnection_history: string;
            meter_sharing: string;
            monthly_income: string;
            income_stability: string;
            consumption_level: string;
            profile_complete: boolean;
        };
        meter?: {
            id: number;
            meter_no: string;
            static_ip: string;
            units: number;
            created_at: string;
            updated_at: string;
        };
        account_details?: {
            account_number: string;
            address: string;
            energy_preference: string;
            payment_method: string;
        };
    };
    purpose: string;
    amount_requested: number;
    amount_approved: number | null;
    tenure_months: number;
    interest_rate: number;
    status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'DISBURSED' | 'COMPLETED' | 'DEFAULTED';
    credit_score: number | null;
    loan_tier: string | null;
    tariff: {
        id: number;
        tariff_code: string;
        tariff_name: string;
        tariff_type: string;
        voltage_level: string;
        service_charge: number;
        blocks: TariffBlock[];
    } | null;
    rejection_reason: string | null;
    user_notified: boolean;
    created_at: string;
    updated_at: string;
    due_date: string | null;
    total_amount_due: number;
    amount_paid: number;
    outstanding_balance: number;
    is_eligible: boolean;
    disbursement?: {
        id: number;
        token: string;
        units_disbursed: number;
        disbursement_date: string;
        token_expiry: string;
        meter: {
            id: number;
            meter_no: string;
        };
    };
    repayments: Repayment[];
    units_calculated: number | null;
    cost_breakdown: CostBreakdown[] | null;
    status_display: string;
    tier_display: string | null;
}

interface TariffBlock {
    id: number;
    block_name: string;
    min_units: number;
    max_units: number | null;
    rate_per_unit: number;
    block_order: number;
}

interface Repayment {
    id: number;
    amount_paid: number;
    payment_date: string;
    units_paid: number;
    is_on_time: boolean;
    payment_reference: string;
    payment_method?: string;
    momo_transaction_id?: string;
    momo_phone_number?: string;
    payment_status?: string;
}

interface CostBreakdown {
    block_name: string;
    units: number;
    rate: number;
    cost: number;
    block_range: string;
}

export default function LoanDetailPage() {
    const params = useParams();
    const router = useRouter();
    const { toast } = useToast();
    const [loan, setLoan] = useState<LoanDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState('overview');
    const [showTokenDialog, setShowTokenDialog] = useState(false);
    const [disbursing, setDisbursing] = useState(false);

    const loanId = params.id;

    useEffect(() => {
        fetchLoanDetails();
    }, [loanId]);

    const fetchLoanDetails = async () => {
        try {
            setLoading(true);
            console.log('Fetching loan details for ID:', loanId);

            // Use the new admin detail endpoint
            const res = await get<any>(`admin/loans/${loanId}/`);

            console.log('API Response:', res);

            if (res.error) throw new Error('Failed to fetch loan details');

            // Handle response structure
            if (res.data) {
                if (res.data.loan) {
                    setLoan(res.data.loan);
                } else if (res.data.data) {
                    setLoan(res.data.data);
                } else {
                    setLoan(res.data);
                }
            }
        } catch (error) {
            console.error('Error fetching loan details:', error);
            toast({
                title: 'Error',
                description: 'Failed to load loan details',
                variant: 'destructive',
            });
        } finally {
            setLoading(false);
        }
    };


    const handleDisburse = async () => {
        if (!loan) return;
        setDisbursing(true);
        try {
            const res = await post<{ success?: boolean; message?: string; units_disbursed?: number }>(
                `admin/loans/${loan.id}/disburse/`,
                {}
            );
            if (res.error || !res.data?.success) {
                toast({
                    title: "Error",
                    description: getApiErrorMessage(res.error, "Failed to disburse loan"),
                    variant: "destructive",
                });
                return;
            }
            toast({
                title: "Success",
                description:
                    res.data.message +
                    (res.data.units_disbursed != null
                        ? ` (${res.data.units_disbursed} kWh)`
                        : ""),
            });
            await fetchLoanDetails();
        } catch {
            toast({
                title: "Error",
                description: "Failed to disburse loan",
                variant: "destructive",
            });
        } finally {
            setDisbursing(false);
        }
    };

    const getStatusBadge = (status: LoanDetail['status']) => {
        const variants = {
            PENDING: { variant: "secondary" as const, icon: Clock, label: "Pending", color: "bg-yellow-100 text-yellow-800" },
            APPROVED: { variant: "success" as const, icon: CheckCircle, label: "Approved", color: "bg-green-100 text-green-800" },
            REJECTED: { variant: "destructive" as const, icon: XCircle, label: "Rejected", color: "bg-red-100 text-red-800" },
            DISBURSED: { variant: "default" as const, icon: DollarSign, label: "Active", color: "bg-blue-100 text-blue-800" },
            COMPLETED: { variant: "outline" as const, icon: CheckCircle, label: "Completed", color: "bg-gray-100 text-gray-800" },
            DEFAULTED: { variant: "destructive" as const, icon: AlertCircle, label: "Defaulted", color: "bg-red-100 text-red-800" },
        };

        const { icon: Icon, label, color } = variants[status] || variants.PENDING;

        return (
            <Badge className={`${color} gap-1 border-0`}>
                <Icon className="h-3 w-3" />
                {label}
            </Badge>
        );
    };

    const getTierBadge = (tier: string | null) => {
        if (!tier) return null;

        const tierColors = {
            BRONZE: "bg-amber-100 text-amber-800 border-amber-300",
            SILVER: "bg-gray-200 text-gray-800 border-gray-400",
            GOLD: "bg-yellow-100 text-yellow-800 border-yellow-400",
            PLATINUM: "bg-indigo-100 text-indigo-800 border-indigo-400"
        };

        const colorClass = tierColors[tier as keyof typeof tierColors] || "bg-gray-100 text-gray-700";

        return (
            <Badge variant="outline" className={colorClass}>
                <Award className="h-3 w-3 mr-1" />
                {tier}
            </Badge>
        );
    };

    const formatCurrency = (amount: number | null) => {
        if (amount === null || amount === undefined) return 'N/A';
        return `UGX ${amount.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
    };

    const formatDate = (dateString: string | null) => {
        if (!dateString) return 'N/A';
        return new Date(dateString).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    const copyToClipboard = (text: string) => {
        navigator.clipboard.writeText(text);
        toast({
            title: 'Copied!',
            description: 'Copied to clipboard',
        });
    };

    if (loading) {
        return <LoanDetailSkeleton />;
    }

    if (!loan) {
        return (
            <div className="container mx-auto py-6">
                <Card>
                    <CardContent className="flex flex-col items-center justify-center py-12">
                        <AlertCircle className="h-12 w-12 text-muted-foreground mb-4" />
                        <h2 className="text-2xl font-bold mb-2">Loan Not Found</h2>
                        <p className="text-muted-foreground mb-4">The loan you're looking for doesn't exist or you don't have permission to view it.</p>
                        <Button onClick={() => router.push('/admin/loans')}>
                            <ArrowLeft className="mr-2 h-4 w-4" />
                            Back to Loans
                        </Button>
                    </CardContent>
                </Card>
            </div>
        );
    }

    const repaymentProgress = loan.total_amount_due > 0
        ? (loan.amount_paid / loan.total_amount_due) * 100
        : 0;

    return (
        <div className="container mx-auto py-6 space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <Button variant="outline" size="icon" onClick={() => router.back()}>
                        <ArrowLeft className="h-4 w-4" />
                    </Button>
                    <div>
                        <div className="flex items-center gap-2">
                            <h1 className="text-3xl font-bold tracking-tight">Loan {loan.loan_id}</h1>
                            {getStatusBadge(loan.status)}
                            {getTierBadge(loan.loan_tier)}
                        </div>
                        <p className="text-muted-foreground">
                            Applied on {formatDate(loan.created_at)}
                        </p>
                    </div>
                </div>
                <div className="flex gap-2">
                    {loan.status === 'PENDING' && (
                        <>
                            <Button variant="default" className="bg-green-600 hover:bg-green-700">
                                <CheckCircle className="mr-2 h-4 w-4" />
                                Approve
                            </Button>
                            <Button variant="destructive">
                                <XCircle className="mr-2 h-4 w-4" />
                                Reject
                            </Button>
                        </>
                    )}
                    {loan.status === 'APPROVED' && (
                        <Button variant="default" onClick={() => void handleDisburse()} disabled={disbursing}>
                            <CreditCard className="mr-2 h-4 w-4" />
                            {disbursing ? "Disbursing…" : "Disburse Loan"}
                        </Button>
                    )}
                    {loan.status === 'DISBURSED' && loan.disbursement && (
                        <Button variant="outline" onClick={() => setShowTokenDialog(true)}>
                            <Zap className="mr-2 h-4 w-4" />
                            View Token
                        </Button>
                    )}
                    <Button variant="outline">
                        <Download className="mr-2 h-4 w-4" />
                        Export PDF
                    </Button>
                </div>
            </div>

            {/* Key Metrics */}
            <div className="grid gap-4 md:grid-cols-4">
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium">Amount Requested</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{formatCurrency(loan.amount_requested)}</div>
                        {loan.amount_approved && (
                            <p className="text-xs text-green-600 mt-1">
                                Approved: {formatCurrency(loan.amount_approved)}
                            </p>
                        )}
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium">Outstanding Balance</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-red-600">
                            {formatCurrency(loan.outstanding_balance)}
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                            Total Due: {formatCurrency(loan.total_amount_due)}
                        </p>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium">Repayment Progress</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{repaymentProgress.toFixed(1)}%</div>
                        <div className="w-full bg-gray-200 rounded-full h-2 mt-2">
                            <div
                                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                                style={{ width: `${repaymentProgress}%` }}
                            />
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                            Paid: {formatCurrency(loan.amount_paid)}
                        </p>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium">Credit Score</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="flex items-baseline gap-1">
                            <span className={`text-2xl font-bold ${loan.credit_score && loan.credit_score >= 80 ? 'text-green-600' :
                                loan.credit_score && loan.credit_score >= 75 ? 'text-yellow-600' : 'text-red-600'
                                }`}>
                                {loan.credit_score || 'N/A'}
                            </span>
                            {loan.credit_score && <span className="text-muted-foreground">/100</span>}
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                            Interest: {loan.interest_rate}%
                        </p>
                    </CardContent>
                </Card>
            </div>

            {/* Main Content Tabs */}
            <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
                <TabsList>
                    <TabsTrigger value="overview">Overview</TabsTrigger>
                    <TabsTrigger value="customer">Customer Details</TabsTrigger>
                    <TabsTrigger value="repayments">Repayment History</TabsTrigger>
                    <TabsTrigger value="disbursement">Disbursement Info</TabsTrigger>
                    <TabsTrigger value="tariff">Tariff Breakdown</TabsTrigger>
                </TabsList>

                {/* Overview Tab */}
                <TabsContent value="overview" className="space-y-4">
                    <div className="grid gap-4 md:grid-cols-2">
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-lg">Loan Details</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <p className="text-sm text-muted-foreground">Loan ID</p>
                                        <div className="flex items-center gap-2">
                                            <p className="font-medium font-mono">{loan.loan_id}</p>
                                            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => copyToClipboard(loan.loan_id)}>
                                                <Copy className="h-3 w-3" />
                                            </Button>
                                        </div>
                                    </div>
                                    <div>
                                        <p className="text-sm text-muted-foreground">Status</p>
                                        <div>{getStatusBadge(loan.status)}</div>
                                    </div>
                                    <div>
                                        <p className="text-sm text-muted-foreground">Loan Tier</p>
                                        <p className="font-medium">{loan.loan_tier || 'Not Assigned'}</p>
                                    </div>
                                    <div>
                                        <p className="text-sm text-muted-foreground">Purpose</p>
                                        <p className="font-medium">{loan.purpose}</p>
                                    </div>
                                    <div>
                                        <p className="text-sm text-muted-foreground">Tenure</p>
                                        <p className="font-medium">{loan.tenure_months} months</p>
                                    </div>
                                    <div>
                                        <p className="text-sm text-muted-foreground">Interest Rate</p>
                                        <p className="font-medium">{loan.interest_rate}%</p>
                                    </div>
                                    <div>
                                        <p className="text-sm text-muted-foreground">Due Date</p>
                                        <p className="font-medium">{formatDate(loan.due_date)}</p>
                                    </div>
                                    <div>
                                        <p className="text-sm text-muted-foreground">Created At</p>
                                        <p className="font-medium">{formatDate(loan.created_at)}</p>
                                    </div>
                                </div>
                                {loan.rejection_reason && (
                                    <div className="bg-red-50 p-4 rounded-lg">
                                        <p className="text-sm font-medium text-red-800">Rejection Reason</p>
                                        <p className="text-sm text-red-600">{loan.rejection_reason}</p>
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader>
                                <CardTitle className="text-lg">Credit Assessment</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-4">
                                    <div className="flex items-center justify-between">
                                        <span className="text-sm">Credit Score</span>
                                        <span className={`font-bold ${loan.credit_score && loan.credit_score >= 80 ? 'text-green-600' :
                                            loan.credit_score && loan.credit_score >= 75 ? 'text-yellow-600' : 'text-red-600'
                                            }`}>
                                            {loan.credit_score || 'N/A'}/100
                                        </span>
                                    </div>
                                    <Separator />
                                    <div className="space-y-2">
                                        <h4 className="text-sm font-medium">Profile Data Used</h4>
                                        {loan.user.profile_data && (
                                            <div className="grid grid-cols-2 gap-2 text-sm">
                                                <div>
                                                    <p className="text-muted-foreground">Monthly Income</p>
                                                    <p>{loan.user.profile_data.monthly_income}</p>
                                                </div>
                                                <div>
                                                    <p className="text-muted-foreground">Payment Consistency</p>
                                                    <p>{loan.user.profile_data.payment_consistency}</p>
                                                </div>
                                                <div>
                                                    <p className="text-muted-foreground">Monthly Expenditure</p>
                                                    <p>{loan.user.profile_data.monthly_expenditure}</p>
                                                </div>
                                                <div>
                                                    <p className="text-muted-foreground">Income Stability</p>
                                                    <p>{loan.user.profile_data.income_stability}</p>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    </div>
                </TabsContent>

                {/* Customer Details Tab */}
                <TabsContent value="customer" className="space-y-4">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-lg">Customer Information</CardTitle>
                            <CardDescription>Personal and account details</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="grid md:grid-cols-2 gap-6">
                                <div className="space-y-4">
                                    <div className="flex items-center gap-4">
                                        <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center">
                                            <User className="h-6 w-6 text-primary" />
                                        </div>
                                        <div>
                                            <h3 className="font-semibold">{loan.user.first_name} {loan.user.last_name}</h3>
                                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                                <Mail className="h-3 w-3" />
                                                {loan.user.email}
                                            </div>
                                            <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                                <Phone className="h-3 w-3" />
                                                {loan.user.phone_number}
                                            </div>
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-2 gap-4">
                                        <div>
                                            <p className="text-sm text-muted-foreground">Gender</p>
                                            <p className="font-medium">{loan.user.gender || 'N/A'}</p>
                                        </div>
                                        <div>
                                            <p className="text-sm text-muted-foreground">Email Verified</p>
                                            <Badge variant={loan.user.email_verified ? "success" : "secondary"}>
                                                {loan.user.email_verified ? 'Verified' : 'Unverified'}
                                            </Badge>
                                        </div>
                                        <div>
                                            <p className="text-sm text-muted-foreground">Account Status</p>
                                            <Badge variant={loan.user.account_active ? "success" : "destructive"}>
                                                {loan.user.account_active ? 'Active' : 'Inactive'}
                                            </Badge>
                                        </div>
                                        <div>
                                            <p className="text-sm text-muted-foreground">Member Since</p>
                                            <p className="font-medium">{formatDate(loan.user.created_at)}</p>
                                        </div>
                                    </div>
                                </div>

                                <div className="space-y-4">
                                    <h4 className="font-medium">Meter Information</h4>
                                    {loan.user.meter ? (
                                        <div className="bg-muted p-4 rounded-lg space-y-2">
                                            <div className="flex justify-between">
                                                <span className="text-sm text-muted-foreground">Meter Number</span>
                                                <span className="font-mono font-medium">{loan.user.meter.meter_no}</span>
                                            </div>
                                            <div className="flex justify-between">
                                                <span className="text-sm text-muted-foreground">Current Units</span>
                                                <span className="font-medium">{loan.user.meter.units} kWh</span>
                                            </div>
                                            <div className="flex justify-between">
                                                <span className="text-sm text-muted-foreground">Static IP</span>
                                                <span className="font-medium">{loan.user.meter.static_ip}</span>
                                            </div>
                                        </div>
                                    ) : (
                                        <p className="text-muted-foreground">No meter registered</p>
                                    )}

                                    {loan.user.account_details && (
                                        <>
                                            <h4 className="font-medium mt-4">Account Details</h4>
                                            <div className="bg-muted p-4 rounded-lg space-y-2">
                                                <div className="flex justify-between">
                                                    <span className="text-sm text-muted-foreground">Account Number</span>
                                                    <span className="font-mono font-medium">{loan.user.account_details.account_number}</span>
                                                </div>
                                                <div className="flex justify-between">
                                                    <span className="text-sm text-muted-foreground">Address</span>
                                                    <span className="font-medium">{loan.user.account_details.address}</span>
                                                </div>
                                                <div className="flex justify-between">
                                                    <span className="text-sm text-muted-foreground">Payment Method</span>
                                                    <span className="font-medium">{loan.user.account_details.payment_method}</span>
                                                </div>
                                            </div>
                                        </>
                                    )}
                                </div>
                            </div>

                            <div className="mt-6 flex justify-end">
                                <Button variant="outline" onClick={() => router.push(`/admin/users/${loan.user.id}`)}>
                                    <ExternalLink className="mr-2 h-4 w-4" />
                                    View Full Customer Profile
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Repayment History Tab */}
                <TabsContent value="repayments" className="space-y-4">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-lg">Repayment History</CardTitle>
                            <CardDescription>
                                Total Paid: {formatCurrency(loan.amount_paid)} of {formatCurrency(loan.total_amount_due)}
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            {loan.repayments && loan.repayments.length > 0 ? (
                                <div className="rounded-md border overflow-x-auto">
                                    <div className="rounded-md border overflow-x-auto">
                                        <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>Date</TableHead>
                                            <TableHead>Amount Paid</TableHead>
                                            <TableHead>Units</TableHead>
                                            <TableHead>Reference</TableHead>
                                            <TableHead>Payment Method</TableHead>
                                            <TableHead>Status</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {loan.repayments.map((repayment) => (
                                            <TableRow key={repayment.id}>
                                                <TableCell>{formatDate(repayment.payment_date)}</TableCell>
                                                <TableCell className="font-medium">
                                                    {formatCurrency(repayment.amount_paid)}
                                                </TableCell>
                                                <TableCell>{repayment.units_paid} kWh</TableCell>
                                                <TableCell>
                                                    <div className="flex items-center gap-2">
                                                        <span className="font-mono text-xs">{repayment.payment_reference}</span>
                                                        <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => copyToClipboard(repayment.payment_reference)}>
                                                            <Copy className="h-3 w-3" />
                                                        </Button>
                                                    </div>
                                                </TableCell>
                                                <TableCell>{repayment.payment_method || 'Cash'}</TableCell>
                                                <TableCell>
                                                    <Badge variant={repayment.is_on_time ? "success" : "destructive"}>
                                                        {repayment.is_on_time ? 'On Time' : 'Late'}
                                                    </Badge>
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                        </Table>
                                    </div>
                                </div>
                            ) : (
                                <div className="text-center py-8">
                                    <History className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                                    <p className="text-muted-foreground">No repayments recorded yet</p>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Disbursement Info Tab */}
                <TabsContent value="disbursement" className="space-y-4">
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-lg">Disbursement Details</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {loan.disbursement ? (
                                <div className="space-y-6">
                                    <div className="grid md:grid-cols-2 gap-6">
                                        <div className="space-y-4">
                                            <div>
                                                <p className="text-sm text-muted-foreground">Disbursement Date</p>
                                                <p className="font-medium">{formatDate(loan.disbursement.disbursement_date)}</p>
                                            </div>
                                            <div>
                                                <p className="text-sm text-muted-foreground">Units Disbursed</p>
                                                <p className="font-medium text-2xl">{loan.disbursement.units_disbursed} kWh</p>
                                            </div>
                                            <div>
                                                <p className="text-sm text-muted-foreground">Meter</p>
                                                <p className="font-medium">{loan.disbursement.meter.meter_no}</p>
                                            </div>
                                        </div>

                                        <div className="space-y-4">
                                            <div>
                                                <p className="text-sm text-muted-foreground">Token</p>
                                                <div className="flex items-center gap-2">
                                                    <p className="font-mono font-bold text-xl bg-muted p-2 rounded">
                                                        {loan.disbursement.token}
                                                    </p>
                                                    <Button variant="outline" size="sm" onClick={() => copyToClipboard(loan.disbursement!.token)}>
                                                        <Copy className="h-4 w-4" />
                                                    </Button>
                                                </div>
                                            </div>
                                            <div>
                                                <p className="text-sm text-muted-foreground">Token Expiry</p>
                                                <p className="font-medium text-red-600">{formatDate(loan.disbursement.token_expiry)}</p>
                                            </div>
                                        </div>
                                    </div>

                                    <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                                        <h4 className="font-medium text-yellow-800 mb-2 flex items-center gap-2">
                                            <Zap className="h-4 w-4" />
                                            Token Information
                                        </h4>
                                        <p className="text-sm text-yellow-700">
                                            This token was generated for the meter {loan.disbursement.meter.meter_no} and expires on{' '}
                                            {formatDate(loan.disbursement.token_expiry)}. The token has been sent to the customer and
                                            should be used to load units into their meter.
                                        </p>
                                    </div>
                                </div>
                            ) : (
                                <div className="text-center py-8">
                                    <CreditCard className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                                    <p className="text-muted-foreground">Loan has not been disbursed yet</p>
                                    {loan.status === 'APPROVED' && (
                                        <Button className="mt-4" variant="default">
                                            <Zap className="mr-2 h-4 w-4" />
                                            Disburse Now
                                        </Button>
                                    )}
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {loan.units_calculated && loan.cost_breakdown && (
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-lg">Unit Calculation</CardTitle>
                                <CardDescription>
                                    Based on {loan.tariff?.tariff_name || 'default'} tariff
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-4">
                                    <div className="flex justify-between items-center">
                                        <span className="font-medium">Total Units</span>
                                        <span className="text-2xl font-bold">{loan.units_calculated} kWh</span>
                                    </div>

                                    <Table>
                                        <TableHeader>
                                            <TableRow>
                                                <TableHead>Block</TableHead>
                                                <TableHead>Range (kWh)</TableHead>
                                                <TableHead>Rate (UGX)</TableHead>
                                                <TableHead>Units</TableHead>
                                                <TableHead>Cost</TableHead>
                                            </TableRow>
                                        </TableHeader>
                                        <TableBody>
                                            {loan.cost_breakdown.map((block, index) => (
                                                <TableRow key={index}>
                                                    <TableCell>{block.block_name}</TableCell>
                                                    <TableCell>{block.block_range}</TableCell>
                                                    <TableCell>{block.rate}</TableCell>
                                                    <TableCell>{block.units.toFixed(2)}</TableCell>
                                                    <TableCell>{formatCurrency(block.cost)}</TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                </div>
                            </CardContent>
                        </Card>
                    )}
                </TabsContent>

                {/* Tariff Breakdown Tab */}
                <TabsContent value="tariff" className="space-y-4">
                    {loan.tariff ? (
                        <>
                            <Card>
                                <CardHeader>
                                    <CardTitle className="text-lg">Tariff Information</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="grid md:grid-cols-2 gap-6">
                                        <div className="space-y-2">
                                            <div>
                                                <p className="text-sm text-muted-foreground">Tariff Code</p>
                                                <p className="font-medium">{loan.tariff.tariff_code}</p>
                                            </div>
                                            <div>
                                                <p className="text-sm text-muted-foreground">Tariff Name</p>
                                                <p className="font-medium">{loan.tariff.tariff_name}</p>
                                            </div>
                                            <div>
                                                <p className="text-sm text-muted-foreground">Tariff Type</p>
                                                <p className="font-medium">{loan.tariff.tariff_type}</p>
                                            </div>
                                        </div>
                                        <div className="space-y-2">
                                            <div>
                                                <p className="text-sm text-muted-foreground">Voltage Level</p>
                                                <p className="font-medium">{loan.tariff.voltage_level}</p>
                                            </div>
                                            <div>
                                                <p className="text-sm text-muted-foreground">Service Charge</p>
                                                <p className="font-medium">{formatCurrency(loan.tariff.service_charge)}</p>
                                            </div>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>

                            <Card>
                                <CardHeader>
                                    <CardTitle className="text-lg">Tariff Blocks</CardTitle>
                                    <CardDescription>Progressive block rates for electricity consumption</CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <div className="rounded-md border overflow-x-auto">
                                        <Table>
                                        <TableHeader>
                                            <TableRow>
                                                <TableHead>Block Name</TableHead>
                                                <TableHead>Range (kWh)</TableHead>
                                                <TableHead>Rate per kWh (UGX)</TableHead>
                                                <TableHead>Order</TableHead>
                                            </TableRow>
                                        </TableHeader>
                                        <TableBody>
                                            {loan.tariff.blocks.map((block) => (
                                                <TableRow key={block.id}>
                                                    <TableCell className="font-medium">{block.block_name}</TableCell>
                                                    <TableCell>
                                                        {block.min_units} - {block.max_units || '∞'}
                                                    </TableCell>
                                                    <TableCell>{formatCurrency(block.rate_per_unit)}</TableCell>
                                                    <TableCell>{block.block_order}</TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                        </Table>
                                    </div>
                                </CardContent>
                            </Card>
                        </>
                    ) : (
                        <Card>
                            <CardContent className="text-center py-8">
                                <Zap className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                                <p className="text-muted-foreground">No tariff information available for this loan</p>
                            </CardContent>
                        </Card>
                    )}
                </TabsContent>
            </Tabs>

            {/* Token Dialog */}
            <Dialog open={showTokenDialog} onOpenChange={setShowTokenDialog}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Disbursement Token</DialogTitle>
                        <DialogDescription>
                            Token for meter {loan.disbursement?.meter.meter_no}
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                        <div className="bg-muted p-6 rounded-lg text-center">
                            <p className="text-sm text-muted-foreground mb-2">Token</p>
                            <p className="font-mono text-3xl font-bold tracking-wider">{loan.disbursement?.token}</p>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <p className="text-sm text-muted-foreground">Units</p>
                                <p className="font-medium text-xl">{loan.disbursement?.units_disbursed} kWh</p>
                            </div>
                            <div>
                                <p className="text-sm text-muted-foreground">Expiry Date</p>
                                <p className="font-medium">{formatDate(loan.disbursement?.token_expiry || null)}</p>
                            </div>
                        </div>
                        <div className="flex gap-2">
                            <Button className="flex-1" onClick={() => copyToClipboard(loan.disbursement?.token || '')}>
                                <Copy className="mr-2 h-4 w-4" />
                                Copy Token
                            </Button>
                            <Button variant="outline" className="flex-1" onClick={() => setShowTokenDialog(false)}>
                                Close
                            </Button>
                        </div>
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    );
}

function LoanDetailSkeleton() {
    return (
        <div className="container mx-auto py-6 space-y-6">
            <div className="flex items-center gap-4">
                <Skeleton className="h-10 w-10" />
                <div>
                    <Skeleton className="h-8 w-48 mb-2" />
                    <Skeleton className="h-4 w-32" />
                </div>
            </div>

            <div className="grid gap-4 md:grid-cols-4">
                {[...Array(4)].map((_, i) => (
                    <Card key={i}>
                        <CardHeader className="pb-2">
                            <Skeleton className="h-4 w-24" />
                        </CardHeader>
                        <CardContent>
                            <Skeleton className="h-8 w-32" />
                            <Skeleton className="h-4 w-24 mt-2" />
                        </CardContent>
                    </Card>
                ))}
            </div>

            <Card>
                <CardHeader>
                    <Skeleton className="h-6 w-32" />
                </CardHeader>
                <CardContent>
                    <div className="space-y-4">
                        <Skeleton className="h-10 w-full" />
                        <Skeleton className="h-32 w-full" />
                        <Skeleton className="h-32 w-full" />
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
