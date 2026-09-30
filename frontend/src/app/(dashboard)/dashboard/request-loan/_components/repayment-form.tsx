"use client";
import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { X, Smartphone, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { getErrorMessage } from "@/lib/errors";
import { checkPaymentStatus, repayLoanWithMomo } from "../../myloans/action";

interface RepaymentFormProps {
  loan: {
    id: number;
    loan_id: string;
    amount_approved: string | null;
    tenure_months: number;
    interest_rate: number;
    repayments: Array<{
      id: number;
      amount_paid: string;
      payment_date: string;
      units_paid: number;
      is_on_time: boolean;
    }>;
    outstanding_balance: number;
    total_amount_due: number;
  };
  onSuccess: () => void;
  onCancel: () => void;
}

export default function RepaymentForm({
  loan,
  onSuccess,
  onCancel,
}: RepaymentFormProps) {
  const [amount, setAmount] = useState<string>("");
  const [phoneNumber, setPhoneNumber] = useState<string>("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [momoStatus, setMomoStatus] = useState<
    "idle" | "pending" | "success" | "failed"
  >("idle");
  const [externalId, setExternalId] = useState<string | null>(null);
  const [pollingCount, setPollingCount] = useState(0);

  const outstandingBalance = loan.outstanding_balance || 0;
  const [paymentMode, setPaymentMode] = useState<"full" | "partial">("full");
  const quickAmounts = [5000, 10000, 20000, 50000];

  useEffect(() => {
    const fullAmount = String(Math.ceil(outstandingBalance));
    if (paymentMode === "full") {
      setAmount(fullAmount);
    } else if (paymentMode === "partial") {
      setAmount((current) => current === fullAmount ? "" : current);
    }
  }, [paymentMode, outstandingBalance]);

  // Format phone number for Uganda
  const formatPhoneNumber = (input: string): string => {
    const digits = input.replace(/\D/g, "");
    if (digits.startsWith("0")) return "256" + digits.slice(1);
    if (digits.startsWith("256")) return digits;
    return "256" + digits;
  };

  // Validate form input
  const validateForm = (): string | null => {
    if (!amount || !/^\d+$/.test(amount) || Number(amount) <= 0)
      return "Please enter a valid amount";

    const paymentAmount = parseFloat(amount);
    if (paymentAmount > Math.ceil(outstandingBalance)) {
      return `Amount exceeds outstanding balance of ${outstandingBalance.toLocaleString()} UGX`;
    }
    // if (paymentAmount < 1000) return "Minimum payment amount is 1,000 UGX";
    if (!phoneNumber.trim())
      return "Phone number is required for Mobile Money payments";

    const formattedPhone = formatPhoneNumber(phoneNumber);
    if (formattedPhone.length !== 12 || !formattedPhone.startsWith("256")) {
      return "Please enter a valid Ugandan phone number (e.g., 07XXXXXXXX or 2567XXXXXXXX)";
    }

    return null;
  };

  // Only a provider-verified status from Django can complete this repayment.
  useEffect(() => {
    if (!externalId || momoStatus !== "pending") return;
    if (pollingCount >= 25) {
      setExternalId(null);
      setSuccess("Payment is still unverified. Reconciliation continues after you leave this page.");
      setIsProcessing(false);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const result = await checkPaymentStatus(externalId);
        if (result.payment_status === "SUCCESS") {
          setMomoStatus("success");
          setSuccess(Number(result.excess_ugx || 0) > 0
            ? `Payment verified. UGX ${result.amount_applied_ugx} reduced debt; UGX ${result.excess_ugx} needs reconciliation.`
            : result.message || "Payment verified and debt reduced.");
          setIsProcessing(false);
        } else if (result.payment_status === "FAILED") {
          setMomoStatus("failed");
          setError("Payment failed. Your debt was not reduced.");
          setIsProcessing(false);
        } else {
          setPollingCount((count) => count + 1);
        }
      } catch {
        setSuccess("Verification is temporarily unavailable. Reconciliation continues in the background.");
        setExternalId(null);
        setIsProcessing(false);
      }
    }, 3000);
    return () => clearTimeout(timer);
  }, [externalId, momoStatus, pollingCount]);

  // Auto-close and refresh 10s after success
  useEffect(() => {
    if (momoStatus === "success") {
      const timer = setTimeout(() => {
        onSuccess();
        window.location.reload();
      }, 10000);

      return () => clearTimeout(timer);
    }
  }, [momoStatus, onSuccess]);

  const handleRepayment = async () => {
    const validationError = validateForm();
    if (validationError) {
      setError(validationError);
      return;
    }

    setIsProcessing(true);
    setError(null);
    setSuccess(null);
    setMomoStatus("pending");
    setExternalId(null);
    setPollingCount(0);

    try {
      const formattedPhone = formatPhoneNumber(phoneNumber);
      const result = await repayLoanWithMomo(parseFloat(amount), formattedPhone, loan.id);

      if (result.status === "PENDING") {
        setExternalId(result.external_id);
        setSuccess(
          "Payment initiated! Please approve the transaction on your phone."
        );
      } else {
        throw new Error(result.error || "Mobile Money payment failed");
      }
    } catch (err: unknown) {
      setMomoStatus("failed");
      setError(getErrorMessage(err));
      setIsProcessing(false);
    }
  };

  const handleAmountChange = (value: string) => {
    setAmount(value.replace(/\D/g, ""));
  };

  const handlePhoneChange = (value: string) => {
    const cleaned = value.replace(/[^\d\s\-+()]/g, "");
    setPhoneNumber(cleaned);
  };

  const getStatusIcon = () => {
    switch (momoStatus) {
      case "pending":
        return <Loader2 className="h-4 w-4 animate-spin" />;
      case "success":
        return <CheckCircle2 className="h-4 w-4 text-green-600" />;
      case "failed":
        return <XCircle className="h-4 w-4 text-red-600" />;
      default:
        return null;
    }
  };

  const getStatusMessage = () => {
    if (momoStatus === "pending" && pollingCount > 0) {
      // return `Checking payment status... (${pollingCount}/6)`;
      return `Checking payment status....`;
    }
    return success;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-background/80 backdrop-blur-sm"
        onClick={onCancel}
      />

      <div className="relative z-50 w-full max-w-md max-h-[90vh] overflow-y-auto">
        <Card className="relative">
          <Button
            variant="ghost"
            size="icon"
            className="absolute top-2 right-2 h-8 w-8"
            onClick={onCancel}
          >
            <X className="h-4 w-4" />
          </Button>

          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              <Smartphone className="h-5 w-5" />
              Loan Payment - {loan.loan_id}
            </CardTitle>
            <div className="space-y-2 text-sm text-muted-foreground">
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="space-y-1">
                  <div className="flex justify-between">
                    <span>Outstanding:</span>
                    <span className="font-semibold text-red-600">
                      {outstandingBalance.toLocaleString()} UGX
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </CardHeader>

          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">Pay by verified Mobile Money. Wallet spending is paused pending balance reconciliation.</p>

            {(
              <div className="space-y-2">
                <label className="text-sm font-medium">
                  MTN Mobile Money Number
                </label>
                <Input
                  type="tel"
                  placeholder="07XXXXXXXX or 2567XXXXXXXX"
                  value={phoneNumber}
                  onChange={(e) => handlePhoneChange(e.target.value)}
                  className="flex-1"
                  disabled={isProcessing && momoStatus === "pending"}
                />
                <p className="text-xs text-muted-foreground">
                  Debt changes only after the provider confirms the UGX payment.
                </p>
              </div>
            )}

            {/* Amount Input */}
            <div className="space-y-2">
              <label className="text-sm font-medium">
                Payment Amount (UGX)
              </label>
              <Input
                type="text"
                placeholder="Enter amount"
                value={amount}
                onChange={(e) => handleAmountChange(e.target.value)}
                className="text-lg font-medium"
                disabled={
                  (isProcessing && momoStatus === "pending") ||
                  paymentMode === "full"
                }
              />
              <p className="text-xs text-muted-foreground">
                Minimum: 1,000 UGX • Maximum:{" "}
                {outstandingBalance.toLocaleString()} UGX
              </p>

              {/* Quick Amount Buttons */}
              <div className="flex flex-wrap gap-2 pt-1">
                {quickAmounts.map((quickAmount) => (
                  <Button
                    key={quickAmount}
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setPaymentMode("partial");
                      setAmount(quickAmount.toString());
                    }}
                    disabled={
                      (isProcessing && momoStatus === "pending") ||
                      quickAmount > Math.ceil(outstandingBalance)
                    }
                    className={cn(
                      "text-xs",
                      amount === quickAmount.toString() &&
                        "bg-primary text-primary-foreground"
                    )}
                  >
                    {quickAmount.toLocaleString()}
                  </Button>
                ))}
              </div>
            </div>

            {/* Status Messages */}
            {error && (
              <div className="bg-destructive/10 border border-destructive/30 text-destructive rounded-lg p-3">
                <p className="text-sm font-medium">{error}</p>
              </div>
            )}

            {success && (
              <div
                className={cn(
                  "border rounded-lg p-3",
                  momoStatus === "pending"
                    ? "bg-yellow-50 border-yellow-200 text-yellow-800"
                    : momoStatus === "success"
                    ? "bg-green-50 border-green-200 text-green-800"
                    : "bg-blue-50 border-blue-200 text-blue-800"
                )}
              >
                <div className="flex items-center gap-2">
                  {getStatusIcon()}
                  <p className="text-sm font-medium">{getStatusMessage()}</p>
                </div>
              </div>
            )}

            {/* Action Button */}
            <div className="flex gap-2 pt-2">
              <Button
                variant="outline"
                onClick={onCancel}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button
                onClick={handleRepayment}
                disabled={
                  (isProcessing && momoStatus === "pending") ||
                  !amount ||
                  parseFloat(amount) <= 0 ||
                  parseFloat(amount) > Math.ceil(outstandingBalance)
                }
                className="flex-1"
              >
                {isProcessing ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />{" "}
                    Processing...
                  </>
                ) : (
                  `Pay ${parseFloat(amount || "0").toLocaleString()} UGX`
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
