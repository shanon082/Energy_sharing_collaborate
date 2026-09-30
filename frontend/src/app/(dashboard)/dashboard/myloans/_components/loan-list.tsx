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
} from "@/components/ui/dropdown-menu";
import {
  CheckCheck,
  Clock10Icon,
  EllipsisVertical,
  XIcon
} from "lucide-react";
import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { FileTextIcon } from "@radix-ui/react-icons";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import BuyUnitsSuggestion from "../../request-loan/_components/buy-units-suggestion";
import RepaymentForm from "../../request-loan/_components/repayment-form";
import { get } from "@/lib/fetch-client";

const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

interface LoanRepayment {
  id: number;
  amount_paid: string;
  payment_date: string;
  units_paid: number;
  is_on_time: boolean;
}

interface Loan {
  id: number;
  loan_id: string;
  purpose: string;
  amount_requested: string;
  amount_approved: string | null;
  tenure_months: number;
  interest_rate: number;
  status: string;
  credit_score: number | null;
  monthly_expenditure: string;
  purchase_frequency: string;
  payment_consistency: string;
  disconnection_history: string;
  meter_sharing: string;
  monthly_income: string;
  income_stability: string;
  consumption_level: string;
  created_at: string;
  rejection_reason: string | null;
  user_notified: boolean;
  repayments: LoanRepayment[];
  disbursement_units: number | null;
  total_amount_due: number;
  outstanding_balance: number;
  due_date: string | null;
}

interface LoanListProps {
  loans: Loan[];
}

export default function LoanList({ loans }: LoanListProps) {
  const [selectedLoan, setSelectedLoan] = useState<Loan | null>(null);
  const [detailLoan, setDetailLoan] = useState<Loan | null>(null);
  const [showRepaymentForm, setShowRepaymentForm] = useState(false);
  const [showBuySuggestion, setShowBuySuggestion] = useState(false);
  const [notificationMessage, setNotificationMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const safeParseFloat = (value: string | null | undefined, defaultValue: number = 0): number => {
    if (!value) return defaultValue;
    const parsed = parseFloat(value);
    return isNaN(parsed) ? defaultValue : parsed;
  };

  const safeParseRepaymentAmount = (amount: string | undefined): number => {
    if (!amount) return 0;
    const parsed = parseFloat(amount);
    return isNaN(parsed) ? 0 : parsed;
  };

  const calculateOutstandingBalance = (loan: Loan): number => {
    return loan.outstanding_balance || 0;
  };

  // const calculateOutstandingBalance = (loan: Loan): number => {
  //   if (!loan.amount_approved) return 0;

  //   const approvedAmount = safeParseFloat(loan.amount_approved, 0);
  //   if (approvedAmount === 0) return 0;

  //   const interestRate = loan.interest_rate || 10.0;
  //   const tenureMonths = loan.tenure_months || 6;

  //   const interest = (approvedAmount * parseFloat(interestRate.toString()) / 100) * (tenureMonths / 12);
  //   const totalAmountDue = approvedAmount + interest;

  //   const totalPaid = loan.repayments.reduce((sum, repayment) => {
  //     return sum + safeParseRepaymentAmount(repayment.amount_paid);
  //   }, 0);

  //   return Math.max(0, totalAmountDue - totalPaid);
  // };

  const getLoanStatus = (loan: Loan): string => {
    return loan.status?.toUpperCase() || 'UNKNOWN';
  };

  const isLoanCompleted = (loan: Loan): boolean => {
    return getLoanStatus(loan) === 'COMPLETED';
  };

  const canRepay = (loan: Loan): boolean => {
    const status = getLoanStatus(loan);
    const balance = calculateOutstandingBalance(loan);
    return (status === 'DISBURSED' || status === 'DEFAULTED') && balance > 0;
  };

  const handleRepaymentSuccess = () => {
    setShowRepaymentForm(false);
    setSelectedLoan(null);
    setSuccessMessage("Payment processed successfully!");
    fetchLoans();

    // Clear success message after 3 seconds
    setTimeout(() => {
      setSuccessMessage(null);
    }, 3000);
  };

  const fetchLoans = async () => {
    try {
      const response = await get('loans/my-loans/');
      // Update loans state if you're managing it locally
      // setLoans(response.data || response.results || []);
    } catch (error) {
      console.error('Error refreshing loans:', error);
    }
  };

  const formatAmount = (amount: string | null | undefined): string => {
    if (!amount) return '0';
    const num = safeParseFloat(amount);
    return num.toLocaleString();
  };

  const getStatusDisplay = (loan: Loan) => {
    const status = getLoanStatus(loan);
    const statusMap: Record<string, { text: string; className: string }> = {
      'PENDING': { text: 'Pending', className: 'bg-yellow-100 text-yellow-800' },
      'APPROVED': { text: 'Approved', className: 'bg-green-100 text-green-800' },
      'REJECTED': { text: 'Rejected', className: 'bg-red-100 text-red-800' },
      'DISBURSED': { text: 'Disbursed', className: 'bg-blue-100 text-blue-800' },
      'COMPLETED': { text: 'Completed', className: 'bg-gray-100 text-gray-800' },
      'DEFAULTED': { text: 'Defaulted', className: 'bg-red-200 text-red-900' },
    };

    const config = statusMap[status] || { text: status, className: 'bg-gray-100 text-gray-800' };

    return {
      ...config,
      rejectionReason: loan.rejection_reason && status === 'REJECTED' ? loan.rejection_reason : null
    };
  };

  // Clear messages after 5 seconds
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [successMessage]);

  useEffect(() => {
    if (errorMessage) {
      const timer = setTimeout(() => setErrorMessage(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [errorMessage]);

  if (!loans || loans.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        You don't have any loan applications yet.
      </div>
    );
  }
  const getStatusExplanation = (loan: Loan): string => {
    const status = getLoanStatus(loan);
    const explanations: Record<string, string> = {
      'PENDING': 'Your loan application is under review',
      'APPROVED': 'Loan approved. Energy allocation is being recorded.',
      'DISBURSED': 'Energy has been allocated to your unit balance. You can now make repayments.',
      'COMPLETED': 'Loan has been fully repaid - Thank you!',
      'REJECTED': 'Your loan application was not approved',
      'DEFAULTED': 'Loan repayment is overdue',
    };
    return explanations[status] || 'Unknown status';
  };

  const isPastDue = (loan: Loan): boolean => {
    if (!loan.due_date) return false;
    return new Date() > new Date(loan.due_date);
  };

  const repayableLoan = loans.find((loan) => canRepay(loan)) ?? null;

  return (
    <div className="w-full space-y-4">
      {/* Success/Error Messages */}
      {successMessage && (
        <div className="bg-green-50 border border-green-200 text-green-800 rounded-md p-4">
          <p className="text-sm font-medium">{successMessage}</p>
        </div>
      )}

      {errorMessage && (
        <div className="bg-red-50 border border-red-200 text-red-800 rounded-md p-4">
          <p className="text-sm font-medium">{errorMessage}</p>
        </div>
      )}

      {repayableLoan && (
        <div className="flex flex-col gap-3 rounded-md border bg-muted/30 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-medium">Repay your active loan</p>
            <p className="text-sm text-muted-foreground">
              Outstanding: {calculateOutstandingBalance(repayableLoan).toLocaleString()} UGX
            </p>
          </div>
          <Button
            onClick={() => {
              setSelectedLoan(repayableLoan);
              setShowRepaymentForm(true);
            }}
          >
            Repay loan
          </Button>
        </div>
      )}

      <div className="rounded-md border overflow-x-auto w-full max-w-full">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[120px]">Loan ID</TableHead>
              <TableHead>Purpose</TableHead>
              <TableHead className="text-right">Amount</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Balance</TableHead>
              <TableHead>Units</TableHead>
              <TableHead>Applied</TableHead>
              <TableHead>Due Date</TableHead>
              <TableHead className="w-[100px]">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loans.map((loan) => {
              const outstandingBalance = calculateOutstandingBalance(loan);
              const statusDisplay = getStatusDisplay(loan);

              return (
                <TableRow key={loan.id} className="hover:bg-muted/50">
                  <TableCell className="font-medium">{loan.loan_id}</TableCell>
                  <TableCell className="max-w-[200px] truncate" title={loan.purpose}>
                    {loan.purpose}
                  </TableCell>
                  <TableCell className="text-right font-medium">
                    {loan.amount_approved
                      ? `${formatAmount(loan.amount_approved)} UGX`
                      : `${formatAmount(loan.amount_requested)} UGX (Requested)`
                    }
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-col">
                      <div className={cn(
                        "inline-flex px-2 py-1 rounded-full text-xs font-semibold",
                        statusDisplay.className
                      )}>
                        {statusDisplay.text}
                      </div>
                      <div className="text-xs text-gray-500 mt-1 max-w-[200px]">
                        {getStatusExplanation(loan)}
                      </div>
                      {statusDisplay.rejectionReason && (
                        <div className="text-xs text-red-600 mt-1 line-clamp-2" title={statusDisplay.rejectionReason}>
                          {statusDisplay.rejectionReason}
                        </div>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    {outstandingBalance > 0
                      ? <span className="text-red-600 font-medium">{outstandingBalance.toLocaleString()} UGX</span>
                      : <span className="text-green-600 font-medium">Paid</span>
                    }
                  </TableCell>
                  <TableCell className="text-sm font-mono">
                    {loan.disbursement_units ? `${loan.disbursement_units}` : "-"}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {new Date(loan.created_at).toLocaleDateString('en-US', {
                      year: 'numeric',
                      month: 'short',
                      day: 'numeric'
                    })}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {loan.due_date ? new Date(loan.due_date).toLocaleDateString('en-US', {
                      year: 'numeric',
                      month: 'short',
                      day: 'numeric'
                    }) : "-"}
                  </TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-8 w-8 p-0">
                          <EllipsisVertical className="h-4 w-4" />
                          <span className="sr-only">Open menu</span>
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-48">
                        <DropdownMenuItem
                          onClick={() => setDetailLoan(loan)}
                          className="cursor-pointer"
                        >
                          <span className="flex items-center">
                            <FileTextIcon className="h-4 w-4 mr-2" />
                            View Details
                          </span>
                        </DropdownMenuItem>

                        {canRepay(loan) && (
                          <DropdownMenuItem
                            onClick={() => {
                              setSelectedLoan(loan);
                              setShowRepaymentForm(true);
                            }}
                            className="cursor-pointer"
                          >
                            <span className="flex items-center">
                              <CheckCheck className="h-4 w-4 mr-2" />
                              Make Payment
                            </span>
                          </DropdownMenuItem>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      {/* Repayment Form Modal */}
      {showRepaymentForm && selectedLoan && (
        <RepaymentForm
          loan={selectedLoan}
          onSuccess={handleRepaymentSuccess}
          onCancel={() => {
            setShowRepaymentForm(false);
            setSelectedLoan(null);
          }}
        />
      )}

      {/* Buy Units Suggestion Modal */}
      {showBuySuggestion && (
        <BuyUnitsSuggestion
          message={notificationMessage}
          onClose={() => {
            setShowBuySuggestion(false);
            setNotificationMessage("");
          }}
        />
      )}

      <Dialog
        open={Boolean(detailLoan)}
        onOpenChange={(open) => {
          if (!open) setDetailLoan(null);
        }}
      >
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Loan Details</DialogTitle>
            <DialogDescription>
              Details for {detailLoan?.loan_id ?? "selected loan"}.
            </DialogDescription>
          </DialogHeader>

          {detailLoan && (
            <div className="space-y-2 text-sm">
              <p><strong>Loan ID:</strong> {detailLoan.loan_id}</p>
              <p><strong>Purpose:</strong> {detailLoan.purpose || "-"}</p>
              <p><strong>Status:</strong> {getLoanStatus(detailLoan)}</p>
              <p><strong>Requested Amount:</strong> {formatAmount(detailLoan.amount_requested)} UGX</p>
              <p><strong>Approved Amount:</strong> {formatAmount(detailLoan.amount_approved)} UGX</p>
              <p><strong>Outstanding Balance:</strong> {calculateOutstandingBalance(detailLoan).toLocaleString()} UGX</p>
              <p><strong>Interest Rate:</strong> {detailLoan.interest_rate ?? "-"}%</p>
              <p><strong>Tenure (months):</strong> {detailLoan.tenure_months ?? "-"}</p>
              <p><strong>Credit Score:</strong> {detailLoan.credit_score ?? "-"}</p>
              <p><strong>Disbursement Units:</strong> {detailLoan.disbursement_units ?? "-"}</p>
              <p>
                <strong>Applied At:</strong>{" "}
                {detailLoan.created_at ? new Date(detailLoan.created_at).toLocaleString() : "N/A"}
              </p>
              <p>
                <strong>Due Date:</strong>{" "}
                {detailLoan.due_date ? new Date(detailLoan.due_date).toLocaleDateString() : "-"}
              </p>
              {detailLoan.rejection_reason && (
                <p><strong>Rejection Reason:</strong> {detailLoan.rejection_reason}</p>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
