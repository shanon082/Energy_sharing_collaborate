"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Loader2, Shield, AlertTriangle, CheckCircle } from "lucide-react";
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
import { post, get } from "@/lib/fetch-client";
import { getApiErrorMessage } from "@/lib/api-response";
import { meterNumberFieldSchema } from "@/lib/meter-validation";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";

const TransferSchema = z
  .object({
    meter_no_old: meterNumberFieldSchema(),
    meter_no_new: meterNumberFieldSchema(),
  })
  .refine((data) => data.meter_no_old !== data.meter_no_new, {
    message: "Old and new meter numbers must be different",
    path: ["meter_no_new"],
  });

type TransferFormValues = z.infer<typeof TransferSchema>;
type WalletBalanceResponse = {
  success: boolean;
  wallet?: { balance?: string };
  total_balance?: string;
  meters?: Array<{ balance?: string }>;
};

type TransferUnitsResponse = {
  success?: boolean;
};

interface TransferFormProps {
  onSuccess?: () => void;
  onCancel?: () => void;
}

export default function TransferForm({
  onSuccess,
  onCancel,
}: TransferFormProps) {
  const [error, setError] = useState<string | undefined>("");
  const [success, setSuccess] = useState("");
  const [isPending, setIsPending] = useState(false);
  const [userBalance, setUserBalance] = useState<number | null>(null);
  const [isLoadingBalance, setIsLoadingBalance] = useState(true);
  const [verificationStep, setVerificationStep] = useState(0);
  const [verificationCode, setVerificationCode] = useState("");
  const [userMeters, setUserMeters] = useState<any[]>([]);

  const router = useRouter();

   useEffect(() => {
     const fetchBalance = async () => {
       try {
         const response = await get<WalletBalanceResponse>("wallet/balance");
  
         if (!response.error && response.data?.success) {
           const apiData = response.data;
           const walletBal = parseFloat(
             apiData.wallet?.balance || apiData.total_balance || "0"
           );
           const meters = apiData.meters || [];
           setUserMeters(meters);
  
           // Prioritize active meter balance (permanent: always uses real meter units)
           let finalBalance = walletBal;
           if (meters.length > 0) {
             const activeMeterBal = parseFloat(meters[0].balance || "0");
             finalBalance = activeMeterBal > 0 ? activeMeterBal : walletBal; 
           }
  
           setUserBalance(finalBalance);
           console.log("Set userBalance:", finalBalance);
         } else {
           console.error(
             "Balance fetch failed:",
             response.error || "Unknown error"
           );
           setError(
             getApiErrorMessage(response.error, "Failed to load balance. Please refresh.")
           );
         }
       } catch (error) {
         console.error("Failed to fetch balance:", error);
         setError("Network error. Please check your connection and try again.");
       } finally {
         setIsLoadingBalance(false);
       }
     };
  
     fetchBalance();
   }, []);

  const form = useForm<TransferFormValues>({
    resolver: zodResolver(TransferSchema),
    defaultValues: {
      meter_no_old: "",
      meter_no_new: "",
    },
  });

  const onSubmit = async (data: TransferFormValues) => {
    if (verificationStep === 0) {
      // First step: Show verification
      if (userBalance !== null && userBalance <= 0) {
        setError("No units to transfer");
        return;
      }
      setVerificationStep(1);
      return;
    }

    if (verificationStep === 1) {
      // Second step: Verify and submit
      if (verificationCode !== "123456") {
        setError("Invalid verification code");
        return;
      }

      setIsPending(true);
      setError("");
      setSuccess("");

      try {
        const response = await post<TransferUnitsResponse>("/transfer-units/", {
          meter_no_old: data.meter_no_old,
          meter_no_new: data.meter_no_new,
          verification_code: verificationCode,
        });

        if (response.data?.success) {
          setSuccess("Units transferred successfully!");
          setVerificationStep(2);

          // Reset form after success
          setTimeout(() => {
            form.reset();
            setVerificationStep(0);
            setVerificationCode("");
            if (onSuccess) onSuccess();
          }, 3000);
        } else {
          setError(getApiErrorMessage(response.error, "Failed to transfer units"));
          setVerificationStep(0);
        }
      } catch (error: any) {
        setError(error.message || "An error occurred");
        setVerificationStep(0);
      } finally {
        setIsPending(false);
      }
    }
  };

  const handleCancelVerification = () => {
    setVerificationStep(0);
    setVerificationCode("");
    setError("");
  };

  return (
    <CardWrapper
      title="Transfer Units to New Account"
      // description="Transfer all units when moving to a new location"
    >
      <div className="mb-4 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">Your Balance:</span>
          {isLoadingBalance ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Badge variant="secondary" className="text-sm font-medium">
              {userBalance !== null ? `${userBalance.toFixed(2)} units` : "N/A"}
            </Badge>
          )}
        </div>
        <Alert variant="destructive" className="bg-red-50 border-red-200">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription className="text-sm">
            This will transfer ALL units from your old meter and deactivate it.
            This action cannot be undone.
          </AlertDescription>
        </Alert>
        <Separator />
      </div>

      {verificationStep === 0 && (
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="meter_no_old"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Current Meter Number</FormLabel>
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
              name="meter_no_new"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>New Meter Number</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="e.g., 2438765432"
                      {...field}
                      maxLength={10}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

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
              <Button type="submit" disabled={isPending} className="flex-1">
                {isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Verifying...
                  </>
                ) : (
                  "Continue to Verification"
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
              For security, please verify this transfer. A verification code has
              been sent to your registered email.
            </AlertDescription>
          </Alert>

          <div className="space-y-2">
            <label className="text-sm font-medium">Verification Code</label>
            <Input
              type="text"
              placeholder="Enter 6-digit code"
              value={verificationCode}
              onChange={(e) =>
                setVerificationCode(
                  e.target.value.replace(/\D/g, "").slice(0, 6)
                )
              }
              maxLength={6}
            />
          </div>

          <div className="bg-muted p-3 rounded-md text-sm">
            <p className="font-medium">Transfer Details:</p>
            <div className="grid grid-cols-2 gap-2 mt-2">
              <span className="text-muted-foreground">From Meter:</span>
              <span>{form.getValues().meter_no_old}</span>
              <span className="text-muted-foreground">To Meter:</span>
              <span>{form.getValues().meter_no_new}</span>
              <span className="text-muted-foreground">Units to Transfer:</span>
              <span>{userBalance?.toFixed(2)} units (ALL)</span>
              <span className="text-muted-foreground">Note:</span>
              <span className="text-red-500 text-sm">
                Old meter will be deactivated
              </span>
            </div>
          </div>

          <FormError message={error} />

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
              onClick={() => form.handleSubmit(onSubmit)()}
              disabled={isPending || verificationCode.length !== 6}
              className="flex-1"
            >
              {isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Processing...
                </>
              ) : (
                "Confirm & Transfer"
              )}
            </Button>
          </div>
        </div>
      )}

      {verificationStep === 2 && (
        <div className="text-center space-y-4 py-4">
          <CheckCircle className="h-16 w-16 text-green-500 mx-auto" />
          <h3 className="text-lg font-semibold">Transfer Complete!</h3>
          <p className="text-muted-foreground">
            All {userBalance?.toFixed(2)} units have been transferred from{" "}
            {form.getValues().meter_no_old} to {form.getValues().meter_no_new}
          </p>
          <p className="text-sm text-amber-600 bg-amber-50 p-2 rounded">
            Your old meter {form.getValues().meter_no_old} has been deactivated.
          </p>
        </div>
      )}
    </CardWrapper>
  );
}
