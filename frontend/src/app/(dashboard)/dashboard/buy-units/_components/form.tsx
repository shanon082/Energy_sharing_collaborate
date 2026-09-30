"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState, useTransition, useEffect, useCallback, useRef } from "react";
import PhoneInput from "react-phone-number-input";
import "react-phone-number-input/style.css";
import type { z } from "zod";
import { Terminal, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";

import { Input } from "@/components/anim/input";
import CardWrapper from "@/components/common/card-wrapper";
import { FormError } from "@/components/common/form-error";
import { FormSuccess } from "@/components/common/form-success";
import { Button } from "@/components/ui/button";
import { Input as ShadInput } from "@/components/ui/input";
import { BreakdownCard } from "@/components/ui/breakdown-card";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { BuyUnitSchema } from "@/lib/schema";
import { useForm } from "react-hook-form";
import { buyUnits, checkPaymentStatus, type BuyUnitsResponse, type PurchasePaymentStatus } from "../buy-units";
import { useAccount } from "@/hooks/use-account";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { get } from "@/lib/fetch-client";
import { getApiErrorMessage } from "@/lib/api-response";
import { notifyWalletBalanceUpdated } from "@/lib/wallet-events";
import { useSelectedMeter } from "@/contexts/selected-meter-context";

function formatUGX(n: number) {
  return `UGX ${Math.round(n).toLocaleString()}`;
}

function formatExactUGX(value: string | null | undefined) {
  return value == null ? "—" : `UGX ${value}`;
}

interface UnitEstimate {
  estimated_units: number;
  tariff?: string | null;
  gross_amount?: number;
  deductions?: number;
  net_amount?: number;
  energy_cost?: number;
  service_charge?: number;
  vat?: number;
  total_bill?: number;
  insufficient_amount?: boolean;
  minimum_payment?: number;
  service_charge_included?: boolean;
  monthly_units_consumed?: number;
  lifeline_remaining_kwh?: number;
  current_tier_band?: string;
}

function buildEstimateRows(estimate: UnitEstimate, grossAmount: number) {
  const rows: { label: string; value: string; muted?: boolean }[] = [
    { label: "Payment amount", value: formatUGX(grossAmount) },
  ];

  if (estimate.deductions && estimate.deductions > 0) {
    rows.push({ label: "Loan repayment", value: `− ${formatUGX(estimate.deductions)}` });
    rows.push({
      label: "Net for energy",
      value: formatUGX(estimate.net_amount ?? grossAmount - estimate.deductions),
    });
  }

  if (estimate.energy_cost != null) {
    rows.push({ label: "Energy charge", value: formatUGX(estimate.energy_cost) });
  }
  if (estimate.service_charge != null && estimate.service_charge > 0) {
    rows.push({
      label: estimate.service_charge_included
        ? "Service charge (monthly)"
        : "Service charge",
      value: formatUGX(estimate.service_charge),
    });
  } else if (estimate.service_charge_included === false) {
    rows.push({
      label: "Service charge",
      value: "Already paid this month",
      muted: true,
    });
  }
  if (estimate.vat != null) {
    rows.push({ label: "VAT (18%)", value: formatUGX(estimate.vat) });
  }

  return rows;
}

export default function BuyUnitsForm() {
  const [error, setError] = useState<string | undefined>("");
  const [success, setSuccess] = useState("");
  const [isPending, startTransition] = useTransition();
  const [paymentStatus, setPaymentStatus] = useState<
    "idle" | "pending" | "success" | "reconciliation" | "failed"
  >("idle");
  const [transactionId, setTransactionId] = useState<string | null>(null);
  const [unitsPurchased, setUnitsPurchased] = useState<number | null>(null);
  const [transactionDetails, setTransactionDetails] = useState<PurchasePaymentStatus | null>(null);
  const [showSuccessModal, setShowSuccessModal] = useState(false);
  const [pollingCount, setPollingCount] = useState(0);

  // Estimate state
  const [estimate, setEstimate] = useState<UnitEstimate | null>(null);
  const [estimating, setEstimating] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const estimateTimeout = useRef<NodeJS.Timeout | null>(null);

  const { loading } = useAccount();
  const { meters } = useSelectedMeter();

  const isPendingBuyUnitsResponse = (
    response: BuyUnitsResponse | undefined
  ): response is Extract<BuyUnitsResponse, { status: "PENDING" }> =>
    typeof response === "object" &&
    response !== null &&
    "status" in response &&
    response.status === "PENDING";

  const form = useForm<z.infer<typeof BuyUnitSchema>>({
    resolver: zodResolver(BuyUnitSchema),
    defaultValues: { amount: 0, phone_number: "", payment_source: "PHONE", meter_no: "" },
  });

  useEffect(() => {
    if (paymentStatus === "success") {
      const timer = setTimeout(() => setShowSuccessModal(true), 5000);
      return () => clearTimeout(timer);
    }
  }, [paymentStatus]);

  // Debounced estimate on amount change
  const fetchEstimate = useCallback(async (amount: number) => {
    if (!Number.isInteger(amount) || amount < 100) {
      setEstimate(null);
      return;
    }
    setEstimating(true);
    try {
      const res = await get<UnitEstimate>(`meter/estimate-units/?amount=${amount}`);
      if (res.data?.estimated_units != null) {
        setEstimate(res.data);
      } else {
        setEstimate(null);
      }
    } catch {
      setEstimate(null);
    } finally {
      setEstimating(false);
    }
  }, []);

  const handleAmountChange = (value: number) => {
    if (estimateTimeout.current) clearTimeout(estimateTimeout.current);
    estimateTimeout.current = setTimeout(() => fetchEstimate(value), 500);
  };

  const checkStatus = useCallback(async (id: string) => {
    try {
      const result = await checkPaymentStatus(id);

      if (result.data?.status === "SUCCESS") {
        setPaymentStatus((result.data.units_purchased ?? 0) > 0 ? "success" : "reconciliation");
        setUnitsPurchased(result.data.units_purchased || 0);
        setTransactionDetails(result.data);
        setSuccess(result.data.message);
        notifyWalletBalanceUpdated();
        return true;
      } else if (result.data?.status === "FAILED") {
        setPaymentStatus("failed");
        setError(result.data.message || "Payment failed");
        return true;
      }
      return false;
    } catch (error) {
      console.error("Error checking payment status:", error);
      return false;
    }
  }, []);

  // Polling — stops after 25 attempts (~75 s) and surfaces a timeout error
  const MAX_POLL_ATTEMPTS = 25;
  useEffect(() => {
    if (paymentStatus === "pending" && transactionId) {
      let mounted = true;
      let timeoutId: NodeJS.Timeout;
      let attempts = 0;

      const poll = async () => {
        if (!mounted) return;

        if (attempts >= MAX_POLL_ATTEMPTS) {
          setPaymentStatus("idle");
          setError(
            "Payment remains unverified. Reconciliation continues after you leave this page; no units have been credited yet."
          );
          return;
        }

        const complete = await checkStatus(transactionId);
        attempts += 1;

        if (!complete && mounted) {
          setPollingCount((prev) => prev + 1);
          timeoutId = setTimeout(poll, 3000);
        }
      };

      poll();

      return () => {
        mounted = false;
        clearTimeout(timeoutId);
      };
    }
  }, [paymentStatus, transactionId, checkStatus]);

  useEffect(() => {
    if (paymentStatus === "pending") setPollingCount(0);
  }, [paymentStatus]);

  async function onSubmit(values: z.infer<typeof BuyUnitSchema>) {
    setError("");
    setSuccess("");
    setPaymentStatus("pending");
    setTransactionId(null);
    setPollingCount(0);
    setShowConfirm(false);

    startTransition(async () => {
      try {
        const data = await buyUnits(values);

        if (data?.error) {
          setPaymentStatus("failed");
          if (typeof data.error === "object") {
            if (data.error?.amount) {
              form.setError("amount", {
                type: "custom",
                message: Array.isArray(data.error.amount) ? data.error.amount[0] : "Invalid amount",
              });
            }
            if (data.error?.phone_number) {
              form.setError("phone_number", {
                type: "custom",
                message: Array.isArray(data.error.phone_number) ? data.error.phone_number[0] : "Invalid phone number",
              });
            }
          }
          setError(getApiErrorMessage(data.error, "Failed to process payment"));
          return;
        }

        const responseData = data.data;

        if (isPendingBuyUnitsResponse(responseData)) {
          setTransactionId(
            responseData.transaction_id !== undefined
              ? String(responseData.transaction_id)
              : null
          );
          setSuccess(
            responseData.user_prompt || responseData.message || "Processing payment..."
          );
        } else {
          setPaymentStatus("failed");
          setError("Payment initiation was not confirmed. No units have been credited.");
        }
      } catch {
        setPaymentStatus("failed");
        setError("Failed to process payment");
      }
    });
  }

  const amount = form.watch("amount");
  const phone = form.watch("phone_number");

  const handleReviewClick = async () => {
    const valid = await form.trigger();
    if (!valid) return;
    if (!estimate && amount >= 100) await fetchEstimate(Number(amount));
    setShowConfirm(true);
  };

  if (loading) return null;

  return (
    <>
      <CardWrapper title="Buy Electricity">
        {/* --- SUCCESS MODAL --- */}
        <Dialog open={showSuccessModal} onOpenChange={setShowSuccessModal}>
          <DialogContent className="sm:max-w-md bg-background border-border">
            <DialogHeader>
              <DialogTitle className="text-green-600 dark:text-green-400 flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5" />
                Payment Successful!
              </DialogTitle>
              <DialogDescription className="text-muted-foreground">
                Verified electricity units have been added to your unit balance.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4">
              <BreakdownCard
                rows={[
                  { label: "Amount Received", value: formatExactUGX(transactionDetails?.amount_received_ugx) },
                  { label: "Energy Billed", value: formatExactUGX(transactionDetails?.purchase_billed_ugx) },
                  { label: "UGX for Reconciliation", value: formatExactUGX(transactionDetails?.purchase_residual_ugx) },
                  { label: "Units Purchased", value: `${unitsPurchased ?? 0} kWh` },
                  { label: "Status", value: "Payment verified; meter delivery pending" },
                  ...(transactionDetails?.transaction?.timestamp
                    ? [{ label: "Date", value: new Date(transactionDetails.transaction.timestamp).toLocaleString(), muted: true }]
                    : []),
                ]}
                totalLabel="Units Added"
                totalValue={`${unitsPurchased ?? 0} kWh`}
              />


              <div className="flex gap-3">
                <Button
                  onClick={() => {
                    setShowSuccessModal(false);
                    form.reset();
                    setPaymentStatus("idle");
                    setEstimate(null);
                  }}
                  className="flex-1 gpawa-gradient text-white"
                >
                  Done
                </Button>
                <Button
                  onClick={() => {
                    setShowSuccessModal(false);
                    form.reset();
                    setPaymentStatus("idle");
                    setEstimate(null);
                  }}
                  variant="outline"
                  className="flex-1"
                >
                  Buy More
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* --- CONFIRM BOTTOM SHEET --- */}
        <BottomSheet
          open={showConfirm}
          onClose={() => {
            setShowConfirm(false);
          }}
          title="Confirm Purchase"
          primaryAction={{
            label: "Pay Now",
            onClick: form.handleSubmit(onSubmit),
            loading: isPending || paymentStatus === "pending",
            disabled: isPending || paymentStatus === "pending",
          }}
        >
          <BreakdownCard
            rows={[
              ...(estimate
                ? buildEstimateRows(estimate, Number(amount))
                : [{ label: "Payment amount", value: formatUGX(Number(amount)) }]),
              { label: "Payment Method", value: "Mobile telecom service provider" },
              { label: "Phone", value: phone || "—" },
            ]}
            totalLabel="You Pay"
            totalValue={formatUGX(Number(amount))}
            subline={
              estimate
                ? `Estimated yield: ${estimate.estimated_units} kWh (ERA Code 10.1)`
                : undefined
            }
          />
        </BottomSheet>

        {/* --- PAYMENT STATUS ALERTS --- */}
        {paymentStatus === "pending" && (
          <Alert className="mb-4 border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-900/20">
            <Loader2 className="h-4 w-4 animate-spin text-blue-600 dark:text-blue-400" />
            <AlertTitle className="text-blue-800 dark:text-blue-300">
              Processing Payment
            </AlertTitle>
            <AlertDescription className="text-blue-700 dark:text-blue-400">
              <div className="space-y-2">
                <p>
                  {success || "Check your phone and approve the Mobile Money payment."}
                </p>
                <div className="flex items-center gap-2 text-sm">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  <span>Checking status... ({pollingCount + 1})</span>
                </div>
                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all duration-1000 ease-out"
                    style={{ width: `${Math.min((pollingCount + 1) * 10, 100)}%` }}
                  />
                </div>
              </div>
            </AlertDescription>
          </Alert>
        )}

        {paymentStatus === "success" && !showSuccessModal && (
          <Alert className="mb-4 border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20">
            <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
            <AlertTitle className="text-green-800 dark:text-green-300">
              Payment Verified
            </AlertTitle>
            <AlertDescription className="text-green-700 dark:text-green-400">
              {success} Meter delivery is tracked separately from payment settlement.
            </AlertDescription>
          </Alert>
        )}

        {paymentStatus === "reconciliation" && (
          <Alert className="mb-4 border-amber-300 bg-amber-50 dark:bg-amber-900/20">
            <AlertTitle>Payment received; energy requires reconciliation</AlertTitle>
            <AlertDescription>
              {success} {formatExactUGX(transactionDetails?.amount_received_ugx)} was received;
              no electricity was allocated. Keep your payment reference for support.
            </AlertDescription>
          </Alert>
        )}

        {paymentStatus === "failed" && (
          <Alert className="mb-4 border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20">
            <XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
            <AlertTitle className="text-red-800 dark:text-red-300">
              Payment Failed
            </AlertTitle>
            <AlertDescription className="text-red-700 dark:text-red-400">
              {error}
            </AlertDescription>
          </Alert>
        )}

        {/* --- FORM --- */}
        <div>
          <Form {...form}>
            <form className="space-y-6">
              <div className="space-y-4">
                <FormField
                  control={form.control}
                  name="meter_no"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Meter to receive this allocation</FormLabel>
                      <FormControl>
                        <select
                          {...field}
                          disabled={isPending || paymentStatus === "pending"}
                          className="w-full rounded-md border border-input bg-background px-3 py-2"
                        >
                          <option value="">Choose a meter</option>
                          {meters.filter((m) => m.status === "ACTIVE").map((m) => (
                            <option key={m.meter_number} value={m.meter_number}>
                              {m.label} ({m.meter_number})
                            </option>
                          ))}
                        </select>
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="payment_source"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className="text-foreground">Pay From</FormLabel>
                      <FormControl>
                        <div className="grid grid-cols-1 gap-2">
                          <Button
                            type="button"
                            variant={field.value === "PHONE" ? "default" : "outline"}
                            onClick={() => field.onChange("PHONE")}
                            disabled={isPending || paymentStatus === "pending"}
                          >
                            Phone
                          </Button>
                        </div>
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="amount"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className="text-foreground">Amount (UGX)</FormLabel>
                      <FormControl>
                        <Input
                          disabled={isPending || paymentStatus === "pending"}
                          type="number"
                          step="1"
                          placeholder="5000"
                          {...field}
                          onChange={(e) => {
                            const val = Number(e.target.value) || 0;
                            field.onChange(val);
                            handleAmountChange(val);
                          }}
                          className="bg-background border-input text-foreground placeholder:text-muted-foreground"
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                {/* Live estimate */}
                {(estimating || estimate != null) && Number(amount) >= 100 && (
                  <div className="space-y-2">
                    <BreakdownCard
                      rows={
                        estimate
                          ? buildEstimateRows(estimate, Number(amount))
                          : [{ label: "Payment amount", value: formatUGX(Number(amount)) }]
                      }
                      totalLabel="You Get"
                      totalValue={estimating ? "…" : `${estimate?.estimated_units ?? 0} kWh`}
                      subline={
                        estimate?.tariff
                          ? `ERA domestic tariff (${estimate.tariff}) — tiered blocks incl. service & VAT`
                          : "Based on ERA domestic tariff (Code 10.1)"
                      }
                    />
                    {!estimating &&
                      estimate?.insufficient_amount &&
                      estimate.minimum_payment != null && (
                        <p className="text-sm text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-md px-3 py-2">
                          {estimate.service_charge_included
                            ? `Your first purchase this month includes a fixed service charge and VAT. `
                            : ``}
                          Enter at least{" "}
                          <strong>{formatUGX(Math.ceil(estimate.minimum_payment))}</strong> to
                          receive any units. Units are credited to your account after verified payment.
                        </p>
                      )}
                    {!estimating &&
                      estimate &&
                      !estimate.insufficient_amount &&
                      estimate.service_charge_included === false && (
                        <p className="text-sm text-blue-800 dark:text-blue-300 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 rounded-md px-3 py-2">
                          Service charge already paid this month — your full payment goes to
                          energy. You have purchased{" "}
                          <strong>{(estimate.monthly_units_consumed ?? 0).toFixed(2)} kWh</strong>{" "}
                          so far this month
                          {estimate.lifeline_remaining_kwh != null &&
                          estimate.lifeline_remaining_kwh > 0 ? (
                            <>
                              {" "}
                              with up to{" "}
                              <strong>{estimate.lifeline_remaining_kwh.toFixed(2)} kWh</strong>{" "}
                              still at the lifeline rate (250 UGX/kWh).
                            </>
                          ) : null}{" "}
                          A second purchase often shows more kWh than your first payment because
                          the monthly service fee is not deducted again.
                        </p>
                      )}
                    {!estimating &&
                      estimate &&
                      estimate.service_charge_included &&
                      estimate.estimated_units > 0 &&
                      estimate.estimated_units < 1 &&
                      Number(amount) >= 100 && (
                        <p className="text-sm text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-md px-3 py-2">
                          Most of this payment covers the monthly service charge (UGX 3,360) and
                          VAT. For meaningful energy units on your first purchase this month, pay
                          at least <strong>{formatUGX(5000)}</strong> (ERA Case 2 ≈ 3.5 kWh) or
                          more.
                        </p>
                      )}
                  </div>
                )}

                <FormField
                  control={form.control}
                  name="phone_number"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className="font-semibold text-foreground">
                        Mobile payment number
                      </FormLabel>
                      <FormControl>
                        <PhoneInput
                          disabled={isPending || paymentStatus === "pending"}
                          {...field}
                          international
                          defaultCountry="UG"
                          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                          inputComponent={ShadInput}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <FormError message={paymentStatus !== "failed" ? error : undefined} />
              <FormSuccess message={success} />

              <Button
                type="button"
                onClick={handleReviewClick}
                disabled={isPending || paymentStatus === "pending"}
                className="w-full gpawa-gradient text-white font-semibold"
              >
                {paymentStatus === "pending" ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Processing…
                  </>
                ) : (
                  <>
                    <Terminal className="mr-2 h-4 w-4" /> Review & Pay
                  </>
                )}
              </Button>
            </form>
          </Form>
        </div>
      </CardWrapper>
    </>
  );
}
