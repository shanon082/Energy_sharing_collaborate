"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Loader2, Shield, CheckCircle, AlertCircle } from "lucide-react";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import CardWrapper from "@/components/common/card-wrapper";
import { FormError } from "@/components/common/form-error";
import { FormSuccess } from "@/components/common/form-success";
import { useRouter } from "next/navigation";
import { get, post } from "@/lib/fetch";
import { getApiErrorMessage } from "@/lib/api-response";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";

const ShareSchema = z.object({
  meter_number: z
    .string()
    .min(10, "Meter number must be 10 digits")
    .max(10, "Meter number must be 10 digits")
    .regex(/^\d+$/, "Meter number must contain only digits"),
  units: z
    .number()
    .min(2, "Minimum units should be greater than 2 units")
    .max(1000, "Cannot share more than 1000 units at once"),
});

type ShareFormValues = z.infer<typeof ShareSchema>;

interface ShareFormProps {
  onSuccess?: () => void;
  onCancel?: () => void;
  onBack: () => void;
}

export default function ShareForm({ onSuccess, onCancel, onBack }: ShareFormProps) {
  const [error, setError] = useState<string | undefined>("");
  const [success, setSuccess] = useState("");
  const [isPending, setIsPending] = useState(false);
  const [unitBalance, setUnitBalance] = useState<number | null>(null);  // Changed from userBalance
  const [isLoadingBalance, setIsLoadingBalance] = useState(true);
  const [verificationStep, setVerificationStep] = useState(0);
  const [verificationCode, setVerificationCode] = useState("");
  const [transactionRef, setTransactionRef] = useState<string | null>(null);
  const [transactionDetails, setTransactionDetails] = useState<any>(null);

  const router = useRouter();
  
  // Fetch UNIT BALANCE - this is what's available to share
  const fetchUnitBalance = async () => {
    try {
      const response = await get<any>("wallet/balance/");
      console.log("Wallet balance response:", response.data); // Debug log
      
      if (!response.error && response.data?.success) {
        // IMPORTANT: Use unit_balance.balance for sharing units
        const availableUnits = Number(response.data.unit_balance?.balance || 0);
        setUnitBalance(availableUnits);
        console.log("Unit balance (available to share):", availableUnits);
      } else {
        console.error("Failed to fetch balance:", response.error);
        setUnitBalance(0);
      }
    } catch (error) {
      console.error("Failed to fetch unit balance:", error);
      setUnitBalance(0);
    } finally {
      setIsLoadingBalance(false);
    }
  };

  useEffect(() => {
    fetchUnitBalance();
  }, []);

  const form = useForm<ShareFormValues>({
    resolver: zodResolver(ShareSchema),
    defaultValues: {
      meter_number: "",
      units: 2,
    },
  });

  // Step 1: Submit initial share request
  const handleInitialSubmit = async (data: ShareFormValues) => {
    // Check against UNIT BALANCE (not money wallet)
    if (unitBalance !== null && data.units > unitBalance) {
      setError(`Insufficient units. You have ${unitBalance} units available to share`);
      return;
    }

    setIsPending(true);
    setError("");
    setSuccess("");

    try {
      const response = await post<any>("share/share-units/", {
        meter_number: data.meter_number,
        units: data.units,
      });

      if (response.data?.success === true || response.status === 200) {
        // Store transaction details for verification step
        setTransactionRef(response.data?.transaction_ref || null);
        setTransactionDetails({
          meter_number: data.meter_number,
          units: data.units,
          newBalance: unitBalance! - data.units,
        });
        
        setSuccess("Verification code sent to your email!");
        setVerificationStep(1);
      } else {
        console.error("Initial share failed:", response);
        setError(
          response.data?.error ||
          getApiErrorMessage(response.error, "Failed to initiate share")
        );
      }
    } catch (error: any) {
      console.error("Initial share error:", error);
      setError(error.message || "An error occurred");
    } finally {
      setIsPending(false);
    }
  };

  // Step 2: Submit verification code
  const handleVerificationSubmit = async () => {
    if (verificationCode.length !== 6) {
      setError("Please enter a 6-digit verification code");
      return;
    }

    if (!transactionDetails) {
      setError("No transaction details found. Please start over.");
      return;
    }

    setIsPending(true);
    setError("");
    setSuccess("");

    try {
      const response = await post<any>("share/share-units/", {
        meter_number: transactionDetails.meter_number,
        units: transactionDetails.units,
        verification_code: verificationCode,
        transaction_ref: transactionRef,
      });

      if (response.status >= 200 && response.status < 300 && response.data?.success) {
        setSuccess("Units shared successfully!");
        setVerificationStep(2);

        // Update local unit balance
        if (unitBalance !== null) {
          setUnitBalance(unitBalance - transactionDetails.units);
        }

        // Reset after success
        setTimeout(() => {
          form.reset();
          setVerificationStep(0);
          setVerificationCode("");
          setTransactionRef(null);
          setTransactionDetails(null);
          if (onSuccess) onSuccess();
          fetchUnitBalance(); // Refresh unit balance
        }, 3000);
      } else {
        setError(
          response.data?.error ||
          getApiErrorMessage(response.error, "Failed to verify code")
        );
      }
    } catch (error: any) {
      console.error("Verification error:", error);
      setError(error.message || "An error occurred");
    } finally {
      setIsPending(false);
    }
  };

  const handleCancelVerification = () => {
    setVerificationStep(0);
    setVerificationCode("");
    setTransactionRef(null);
    setTransactionDetails(null);
    setError("");
  };

  return (
    <CardWrapper title="Share Units">
      <div className="mb-4 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">Your Available Units to Share:</span>
          {isLoadingBalance ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Badge variant="secondary" className="text-sm font-medium">
              {unitBalance !== null ? `${unitBalance.toFixed(2)} units` : "0 units"}
            </Badge>
          )}
        </div>
        <Separator />
      </div>

      {verificationStep === 0 && (
        <Form {...form}>
          <form onSubmit={form.handleSubmit(handleInitialSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="meter_number"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Receiver's Meter Number</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="e.g., 0838123456"
                      {...field}
                      maxLength={10}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="units"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Units to Share</FormLabel>
                  <FormControl>
                    <div className="space-y-2">
                      <Input
                        type="number"
                        min="2"
                        max={unitBalance || 1000}
                        step="0.01"
                        placeholder="Enter Units"
                        {...field}
                        onChange={(e) =>
                          field.onChange(parseFloat(e.target.value) || 0)
                        }
                      />
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Shield className="h-3 w-3" />
                        <span>Minimum: 2 units | Maximum: {unitBalance || 1000} units</span>
                      </div>
                    </div>
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {unitBalance !== null && (
              <div className="text-sm text-muted-foreground">
                Available to share: {unitBalance.toFixed(2)} units
              </div>
            )}

            <FormError message={error} />
            <FormSuccess message={success} />

            <div className="flex gap-2">
              {onCancel && (
                <Button
                  type="button"
                  variant="outline"
                  onClick={onCancel}
                  className="flex-1"
                  disabled={isPending}
                >
                  Cancel
                </Button>
              )}
              <Button type="submit" disabled={isPending || !unitBalance || unitBalance < 2} className="flex-1">
                {isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Processing...
                  </>
                ) : (
                  "Share Units"
                )}
              </Button>
            </div>
          </form>
        </Form>
      )}

      {verificationStep === 1 && (
        <div className="space-y-4">
          <Alert className="bg-blue-50 border-blue-200">
            <Shield className="h-4 w-4" />
            <AlertDescription>
              <strong className="text-blue-800">Security Verification Required</strong>
              <p className="mt-1 text-sm text-muted-foreground">
                A verification code has been sent to your registered email address.
                Please enter the 6-digit code below to complete the transaction.
              </p>
            </AlertDescription>
          </Alert>

          <div className="space-y-2">
            <label className="text-sm font-medium">Verification Code</label>
            <Input
              type="text"
              placeholder="Enter 6-digit code"
              value={verificationCode}
              onChange={(e) =>
                setVerificationCode(e.target.value.replace(/\D/g, "").slice(0, 6))
              }
              maxLength={6}
              className="text-center text-lg font-mono tracking-widest"
            />
            <p className="text-xs text-muted-foreground">
              Check your email for the verification code
            </p>
          </div>

          {transactionDetails && (
            <div className="bg-muted p-4 rounded-md text-sm">
              <p className="font-medium mb-2">Transaction Details:</p>
              <div className="grid grid-cols-2 gap-2">
                <span className="text-muted-foreground">To Meter:</span>
                <span className="font-medium">{transactionDetails.meter_number}</span>
                <span className="text-muted-foreground">Units:</span>
                <span className="font-medium">{transactionDetails.units} units</span>
                <span className="text-muted-foreground">Your New Balance:</span>
                <span className="font-medium">
                  {transactionDetails.newBalance.toFixed(2)} units
                </span>
              </div>
            </div>
          )}

          <FormError message={error} />
          <FormSuccess message={success} />

          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={handleCancelVerification}
              className="flex-1"
              disabled={isPending}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={handleVerificationSubmit}
              disabled={isPending || verificationCode.length !== 6}
              className="flex-1"
            >
              {isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Verifying...
                </>
              ) : (
                "Confirm & Share"
              )}
            </Button>
          </div>
        </div>
      )}

      {verificationStep === 2 && (
        <div className="text-center space-y-4 py-4">
          <CheckCircle className="h-16 w-16 text-green-500 mx-auto" />
          <h3 className="text-lg font-semibold">Success!</h3>
          <p className="text-muted-foreground">
            {transactionDetails?.units} units have been successfully
            shared to meter {transactionDetails?.meter_number}
          </p>
          <p className="text-xs text-muted-foreground">
            A token has been sent to the receiver's email address.
          </p>
          <div className="flex gap-2">
            <Button
              type="button"
              onClick={() => {
                setVerificationStep(0);
                setVerificationCode("");
                setTransactionDetails(null);
                fetchUnitBalance();
              }}
              variant="outline"
              className="flex-1"
            >
              Share More Units
            </Button>
            <Button
              type="button"
              onClick={() => router.push("/dashboard")}
              className="flex-1"
            >
              Go to Dashboard
            </Button>
          </div>
        </div>
      )}
    </CardWrapper>
  );
}