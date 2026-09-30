"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Loader2, AlertTriangle, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { StepWizard } from "@/components/ui/step-wizard";
import { SegmentedSelector } from "@/components/ui/segmented-selector";
import { BreakdownCard } from "@/components/ui/breakdown-card";
import { InfoBanner } from "@/components/ui/info-banner";
import { FormError } from "@/components/common/form-error";
import { get } from "@/lib/fetch-client";
import { submitLoanApplication } from "../action";
import { getApiErrorMessage } from "@/lib/api-response";
import { useSelectedMeter } from "@/contexts/selected-meter-context";

const STEPS = [
  { label: "Amount" },
  { label: "Purpose" },
  { label: "T&C" },
  { label: "Submit" },
];

const PURPOSE_OPTIONS = [
  { label: "Energy Recharge", value: "ENERGY_RECHARGE" },
  { label: "Electricity Utility Arrears", value: "UEDCL_ARREARS" },
  { label: "Business", value: "BUSINESS" },
  { label: "Personal", value: "PERSONAL" },
];

const PLATFORM_MAX_LOAN = 200_000;
const MIN_LOAN_AMOUNT = 5_000;
const LOAN_MONTH_DAYS = 30;
const LOAN_TENURE_MIN = 1;
const LOAN_TENURE_MAX = 12;

interface LoanEligibility {
  creditScore: number;
  maxEligible: number;
  platformMax: number;
  minCreditScore: number;
  loanTier: string | null;
  isEligible: boolean;
  profileComplete: boolean;
  interestRate: number | null;
  trustLevel: string;
  starterMax: number;
  loansCompletedOnTime: number;
}

function formatUGX(n: number) {
  return `UGX ${n.toLocaleString("en-UG", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

interface LoanStatsResponse {
  has_blocking_loan?: boolean;
  active_loans?: number;
  pending_applications?: number;
  outstanding_balance?: string | number;
  credit_score?: number;
  max_eligible_amount?: number;
  platform_max_loan?: number;
  min_credit_score?: number;
  loan_tier?: string | null;
  is_loan_eligible?: boolean;
  profile_complete_for_scoring?: boolean;
  interest_rate?: number | null;
  trust_level?: string;
  starter_max_loan?: number;
  loans_completed_on_time?: number;
}

interface LoanBreakdown {
  principal: number;
  interestRate: number;   // annual %, from backend
  tenureMonths: number;
  interest: number;
  total: number;
  dueDate: string;
}

function computeBreakdown(amount: number, tenure: number, annualRate: number): LoanBreakdown {
  const interest = amount * (annualRate / 100) * (tenure / 12);
  const total = amount + interest;
  const due = new Date();
  due.setDate(due.getDate() + tenure * LOAN_MONTH_DAYS);
  return {
    principal: amount,
    interestRate: annualRate,
    tenureMonths: tenure,
    interest,
    total,
    dueDate: due.toLocaleDateString("en-UG", { day: "numeric", month: "short", year: "numeric" }),
  };
}

interface Props {
  onSuccess?: () => void;
  onCancel?: () => void;
}

export default function SimpleLoanForm({ onSuccess, onCancel }: Props) {
  const router = useRouter();
  const { meters } = useSelectedMeter();
  const [step, setStep] = useState(0);
  const [error, setError] = useState("");
  const [isPending, setIsPending] = useState(false);
  const [hasActiveLoan, setHasActiveLoan] = useState(false);
  const [isChecking, setIsChecking] = useState(true);

  // Form state
  const [amount, setAmount] = useState<number | "">("");
  const [meterNo, setMeterNo] = useState("");
  const [tenure, setTenure] = useState(1);
  const [purpose, setPurpose] = useState("ENERGY_RECHARGE");
  const [purposeNote, setPurposeNote] = useState("");
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [annualRate, setAnnualRate] = useState(12);
  const [eligibility, setEligibility] = useState<LoanEligibility>({
    creditScore: 0,
    maxEligible: 0,
    platformMax: PLATFORM_MAX_LOAN,
    minCreditScore: 75,
    loanTier: null,
    isEligible: false,
    profileComplete: false,
    interestRate: null,
    trustLevel: "starter",
    starterMax: 30_000,
    loansCompletedOnTime: 0,
  });

  const loadEligibility = useCallback(async () => {
    try {
      const statsRes = await get<LoanStatsResponse>("loans/stats/");
      if (statsRes.data) {
        const stats = statsRes.data;
        const hasBlocking =
          stats.has_blocking_loan ??
          ((stats.active_loans ?? 0) > 0 ||
            (stats.pending_applications ?? 0) > 0 ||
            Number(stats.outstanding_balance ?? 0) > 0);
        setHasActiveLoan(hasBlocking);
        setEligibility({
          creditScore: Number(stats.credit_score ?? 0),
          maxEligible: Number(stats.max_eligible_amount ?? 0),
          platformMax: Number(stats.platform_max_loan ?? PLATFORM_MAX_LOAN),
          minCreditScore: Number(stats.min_credit_score ?? 75),
          loanTier: stats.loan_tier ?? null,
          isEligible: Boolean(stats.is_loan_eligible),
          profileComplete: Boolean(stats.profile_complete_for_scoring),
          interestRate: stats.interest_rate != null ? Number(stats.interest_rate) : null,
          trustLevel: String(stats.trust_level ?? "starter"),
          starterMax: Number(stats.starter_max_loan ?? 30_000),
          loansCompletedOnTime: Number(stats.loans_completed_on_time ?? 0),
        });
        if (stats.interest_rate) {
          setAnnualRate(Number(stats.interest_rate));
        }
      }
    } catch {
      /* ignore */
    } finally {
      setIsChecking(false);
    }
  }, []);

  useEffect(() => {
    loadEligibility();
  }, [loadEligibility]);

  useEffect(() => {
    const onFocus = () => {
      loadEligibility();
    };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [loadEligibility]);

  const amountCap = eligibility.isEligible
    ? Math.min(eligibility.maxEligible, eligibility.platformMax)
    : eligibility.platformMax;

  const breakdown = amount
    ? computeBreakdown(Number(amount), tenure, annualRate)
    : null;

  const monthlyRate = (annualRate / 12).toFixed(2);

  // ── Step validation ───────────────────────────────────────────────
  const canProceed = useCallback(() => {
    if (step === 0) {
      const value = Number(amount);
      return (
        value >= MIN_LOAN_AMOUNT &&
        value <= amountCap &&
        tenure >= LOAN_TENURE_MIN &&
        tenure <= LOAN_TENURE_MAX &&
        !!meterNo &&
        eligibility.isEligible
      );
    }
    if (step === 1) return !!purpose;
    if (step === 2) return termsAccepted;
    return true;
  }, [step, amount, tenure, meterNo, purpose, termsAccepted, amountCap, eligibility.isEligible]);

  const handleNext = () => {
    setError("");
    if (!canProceed()) {
      if (step === 0) {
        if (!eligibility.isEligible) {
          setError(
            `Your credit score is ${eligibility.creditScore}/100 (minimum ${eligibility.minCreditScore}). Complete your profile or improve your score before applying.`
          );
        } else {
          setError(`Choose a meter and enter an amount between ${formatUGX(MIN_LOAN_AMOUNT)} and ${formatUGX(amountCap)} with tenure ${LOAN_TENURE_MIN}–${LOAN_TENURE_MAX} months.`);
        }
      }
      if (step === 2) setError("You must accept the terms to continue.");
      return;
    }
    setStep((s) => s + 1);
  };

  // ── Submit ────────────────────────────────────────────────────────
  const handleSubmit = async () => {
    if (!termsAccepted) { setError("Accept the terms first."); return; }
    setIsPending(true);
    setError("");
    try {
      const purposeText = PURPOSE_OPTIONS.find(o => o.value === purpose)?.label ?? purpose;
      const result = await submitLoanApplication({
        purpose: purposeNote ? `${purposeText}: ${purposeNote}` : purposeText,
        amount_requested: Number(amount),
        tenure_months: tenure,
        meter_no: meterNo,
      });
      if (result.data) {
        if (onSuccess) { onSuccess(); }
        else { router.push("/dashboard/myloans"); }
      } else if (result.error) {
        setError(getApiErrorMessage(result.error, "Failed to submit application"));
      }
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setIsPending(false);
    }
  };

  // ── Loading state ─────────────────────────────────────────────────
  if (isChecking) {
    return (
      <div className="flex items-center justify-center p-10">
        <Loader2 className="h-6 w-6 animate-spin text-primary mr-2" />
        <span className="text-muted-foreground text-sm">Checking your loan status…</span>
      </div>
    );
  }

  if (hasActiveLoan) {
    return (
      <div className="space-y-4">
        <Alert>
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Active Loan</AlertTitle>
          <AlertDescription>You have an active loan. Repay it before applying for a new one.</AlertDescription>
        </Alert>
        <Button onClick={() => router.push("/dashboard/myloans")} className="w-full">View My Loans</Button>
      </div>
    );
  }

  if (!eligibility.isEligible) {
    return (
      <div className="space-y-4">
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Borrowing temporarily limited</AlertTitle>
          <AlertDescription>
            Your limit is <strong>{formatUGX(eligibility.maxEligible)}</strong> (score{" "}
            {eligibility.creditScore}/100). Repay any overdue loan to restore your full starter access of{" "}
            {formatUGX(eligibility.starterMax)}.
          </AlertDescription>
        </Alert>
        <Button onClick={() => router.push("/dashboard/myloans")} className="w-full">
          Repay loan
        </Button>
        <Button variant="outline" onClick={() => router.push("/dashboard")} className="w-full">
          Back to Dashboard
        </Button>
      </div>
    );
  }

  // ── Wizard ────────────────────────────────────────────────────────
  return (
    <div className="space-y-6">
      <StepWizard steps={STEPS} currentStep={step} />

      {/* ── Step 0: Amount ── */}
      {step === 0 && (
        <div className="space-y-4">
          <div>
            <h2 className="text-xl font-bold">How much do you need?</h2>
            <p className="text-muted-foreground text-sm mt-0.5">
              Your eligible limit: <strong>{formatUGX(eligibility.maxEligible)}</strong>
              {eligibility.loanTier && <> ({eligibility.loanTier} tier)</>}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Credit score: {eligibility.creditScore}/100 · Platform maximum: {formatUGX(eligibility.platformMax)}
            </p>
          </div>

          <div className="rounded-xl border border-primary/20 bg-primary/5 p-3 text-sm flex gap-2">
            <Info className="h-4 w-4 shrink-0 text-primary mt-0.5" />
            <p>
              {eligibility.trustLevel === "starter" ? (
                <>
                  <strong>Starter access:</strong> every customer can borrow up to{" "}
                  {formatUGX(eligibility.starterMax)}. Repay on time to unlock higher limits (+UGX 15,000
                  per loan).
                </>
              ) : eligibility.trustLevel === "building" ? (
                <>
                  <strong>Trust building:</strong> you have repaid {eligibility.loansCompletedOnTime}{" "}
                  loan{eligibility.loansCompletedOnTime === 1 ? "" : "s"} on time. Keep it up to grow your
                  limit toward {formatUGX(eligibility.platformMax)}.
                </>
              ) : (
                <>
                  You can borrow up to <strong>{formatUGX(amountCap)}</strong>. Platform maximum is{" "}
                  {formatUGX(eligibility.platformMax)} for top-tier customers.
                </>
              )}
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="loan-meter">Meter for this loan allocation</Label>
            <select
              id="loan-meter"
              value={meterNo}
              onChange={(e) => setMeterNo(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2"
            >
              <option value="">Choose a meter</option>
              {meters.filter((m) => m.status === "ACTIVE").map((m) => (
                <option key={m.meter_number} value={m.meter_number}>
                  {m.label} ({m.meter_number})
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="amount">Amount (UGX)</Label>
            <Input
              id="amount"
              type="number"
              min={MIN_LOAN_AMOUNT}
              max={amountCap}
              placeholder="e.g. 50,000"
              value={amount}
              onChange={(e) => setAmount(e.target.value ? Number(e.target.value) : "")}
              className="text-base"
            />
            <p className="text-xs text-muted-foreground">
              Min: {formatUGX(MIN_LOAN_AMOUNT)} · Your max: {formatUGX(amountCap)}
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="tenure">Repayment period (months)</Label>
            <Input
              id="tenure"
              type="number"
              min={LOAN_TENURE_MIN}
              max={LOAN_TENURE_MAX}
              value={tenure}
              onChange={(e) => setTenure(Number(e.target.value) || 1)}
            />
            <p className="text-xs text-muted-foreground">
              Choose {LOAN_TENURE_MIN}–{LOAN_TENURE_MAX} months. Each month = {LOAN_MONTH_DAYS} days from when the loan is disbursed.
            </p>
          </div>

          {breakdown && (
            <BreakdownCard
              rows={[
                { label: "Principal", value: formatUGX(breakdown.principal) },
                { label: `Interest (${monthlyRate}%/month)`, value: formatUGX(breakdown.interest) },
                { label: "Estimated Due Date", value: breakdown.dueDate, muted: true },
              ]}
              totalLabel="Estimated Total Before Overdue Charges"
              totalValue={formatUGX(breakdown.total)}
            />
          )}

          <InfoBanner>
            This preview uses your current eligibility rate of {annualRate}% annually. Final approved terms are stored with the loan; financial policy is still under review.
          </InfoBanner>
        </div>
      )}

      {/* ── Step 1: Purpose ── */}
      {step === 1 && (
        <div className="space-y-4">
          <div>
            <h2 className="text-xl font-bold">Loan Purpose</h2>
            <p className="text-muted-foreground text-sm mt-0.5">Select the primary reason for this loan.</p>
          </div>

          <SegmentedSelector
            options={PURPOSE_OPTIONS}
            value={purpose}
            onChange={setPurpose}
          />

          <div className="space-y-2">
            <Label htmlFor="purposeNote">Additional details (optional)</Label>
            <Input
              id="purposeNote"
              placeholder="e.g. Paying for monthly electricity bill"
              value={purposeNote}
              onChange={(e) => setPurposeNote(e.target.value)}
            />
          </div>
        </div>
      )}

      {/* ── Step 2: Terms ── */}
      {step === 2 && breakdown && (
        <div className="space-y-4">
          <div>
            <h2 className="text-xl font-bold">Terms & Conditions</h2>
            <p className="text-muted-foreground text-sm mt-0.5">Review the prototype calculation before submitting.</p>
          </div>

          <div className="rounded-xl border border-border p-4 space-y-2 text-sm text-muted-foreground bg-muted/30">
            <p>1. <strong>Interest:</strong> {monthlyRate}% per month ({annualRate}% per annum) on the principal sum, applied pro-rata over {tenure} month{tenure > 1 ? "s" : ""} ({tenure * LOAN_MONTH_DAYS} days).</p>
            <p>2. <strong>Fees:</strong> The current prototype does not post a processing fee. The final fee policy requires approval.</p>
            <p>3. <strong>Late payments:</strong> The prototype calculates an overdue charge on principal after the due date. The final late-charge policy requires approval.</p>
            <p>4. <strong>Repayment:</strong> Only provider-verified payments reduce debt. Whole-UGX payments above remaining debt are recorded for reconciliation.</p>
          </div>

          <BreakdownCard
            rows={[
              { label: "Principal", value: formatUGX(breakdown.principal) },
              { label: `Interest (${monthlyRate}%/month × ${tenure} mo)`, value: formatUGX(breakdown.interest) },
              { label: "Estimated Due Date", value: breakdown.dueDate, muted: true },
            ]}
            totalLabel="Estimated Total Before Overdue Charges"
            totalValue={formatUGX(breakdown.total)}
          />

          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={termsAccepted}
              onChange={(e) => setTermsAccepted(e.target.checked)}
              className="mt-1 accent-primary w-4 h-4"
            />
            <span className="text-sm">I understand this prototype estimate and request the electricity loan.</span>
          </label>
        </div>
      )}

      {/* ── Step 3: Confirm & Submit ── */}
      {step === 3 && breakdown && (
        <div className="space-y-4">
          <div>
            <h2 className="text-xl font-bold">Confirm Application</h2>
            <p className="text-muted-foreground text-sm mt-0.5">Review your application before submitting.</p>
          </div>

          <BreakdownCard
            rows={[
              { label: "Loan Amount", value: formatUGX(breakdown.principal) },
              { label: "Purpose", value: PURPOSE_OPTIONS.find(o => o.value === purpose)?.label ?? purpose },
              { label: "Tenure", value: `${tenure} month${tenure > 1 ? "s" : ""} (${tenure * LOAN_MONTH_DAYS} days)` },
              { label: `Interest (${monthlyRate}%/month)`, value: formatUGX(breakdown.interest) },
              { label: "Estimated Due Date", value: breakdown.dueDate, muted: true },
            ]}
            totalLabel="Estimated Total Before Overdue Charges"
            totalValue={formatUGX(breakdown.total)}
          />

          {isPending && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Submitting your application…
            </div>
          )}
        </div>
      )}

      <FormError message={error} />

      {/* ── Navigation ── */}
      <div className="flex gap-3 pt-2">
        {step > 0 && (
          <Button variant="outline" onClick={() => { setError(""); setStep(s => s - 1); }} disabled={isPending} className="flex-1">
            Back
          </Button>
        )}
        {onCancel && step === 0 && (
          <Button variant="outline" onClick={onCancel} disabled={isPending} className="flex-1">
            Cancel
          </Button>
        )}

        {step < STEPS.length - 1 ? (
          <Button onClick={handleNext} className="flex-1 gpawa-gradient text-white">
            Continue
          </Button>
        ) : (
          <Button
            onClick={handleSubmit}
            disabled={isPending || !termsAccepted}
            className="flex-1 gpawa-gradient text-white font-semibold"
          >
            {isPending ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Submitting…</> : "Submit Application"}
          </Button>
        )}
      </div>
    </div>
  );
}
