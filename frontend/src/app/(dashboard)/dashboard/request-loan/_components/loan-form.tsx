"use client"
import { zodResolver } from "@hookform/resolvers/zod";
import { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { FileTextIcon, Zap, AlertTriangle, Loader2 } from "lucide-react";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import CardWrapper from "@/components/common/card-wrapper";
import { FormError } from "@/components/common/form-error";
import { FormSuccess } from "@/components/common/form-success";
import { useRouter } from 'next/navigation';
import { submitLoanApplication } from "../action";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import TokenPopup from "./token-popup";
import BuyUnitsSuggestion from "./buy-units-suggestion";
import { get } from "@/lib/fetch-client";
import Link from "next/link";

const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

type LoanFormValues = z.infer<typeof LoanApplicationSchema>;

const LoanApplicationSchema = z.object({
    purpose: z.string().min(10, "Please describe the purpose of the loan"),
    amount_requested: z.number().min(5000, "Minimum loan amount is 5,000 UGX").max(200000, "Maximum loan amount is 200,000 UGX"),
    tenure_months: z.number().min(1).max(12, "Maximum tenure is 12 months"),
    monthly_expenditure: z.enum([
        "<50,000 UGX",
        "50,000–100,000 UGX",
        "100,001–200,000 UGX",
        "200,001–300,000 UGX",
        ">300,000 UGX"
    ]),
    purchase_frequency: z.enum([
        "Daily",
        "Weekly",
        "Bi-weekly",
        "Monthly",
        "Rarely"
    ]),
    payment_consistency: z.enum([
        "Always on time",
        "Often on time",
        "Sometimes late",
        "Mostly late",
        "Never paid"
    ]),
    disconnection_history: z.enum([
        "No disconnections",
        "1–2 disconnections",
        "3–4 disconnections",
        ">4 disconnections",
        "Frequently disconnected"
    ]),
    meter_sharing: z.enum([
        "No sharing",
        "Shared with 1 household",
        "Shared with 2+ households",
        "Commercial sharing"
    ]),
    monthly_income: z.enum([
        "<100,000 UGX",
        "100,000–199,999 UGX",
        "200,000–499,999 UGX",
        "500,000–999,999 UGX",
        ">1,000,000 UGX"
    ]),
    income_stability: z.enum([
        "Fixed and stable",
        "Regular but variable",
        "Seasonal income",
        "Irregular but frequent",
        "Unstable income"
    ]),
    consumption_level: z.enum([
        "Very low (<50 kWh)",
        "Low (50–99 kWh)",
        "Moderate (100–200 kWh)",
        "High (>200 kWh)",
        "Extremely high (>300 kWh)"
    ]),
});

interface LoanApplicationResponse {
    loan_id: string;
    credit_score: number;
    status: string;
    amount_requested: number;
    amount_approved: number;
    loan_tier: string;
    max_eligible_amount: number;
    interest_rate: number;
    token?: string;
    units_disbursed?: number;
    token_expiry?: string;
    message?: string;
    rejection_reason?: string;
}

// function displayTierInfo(tier: string) {
//   const tierInfo = {
//     'BRONZE': { color: 'text-orange-600', label: 'Bronze Tier' },
//     'SILVER': { color: 'text-gray-600', label: 'Silver Tier' },
//     'GOLD': { color: 'text-yellow-600', label: 'Gold Tier' },
//     'PLATINUM': { color: 'text-blue-600', label: 'Platinum Tier' }
//   };
//   return tierInfo[tier] || { color: 'text-gray-600', label: 'Standard' };
// }

export default function LoanApplicationForm() {
    const [error, setError] = useState<string | undefined>("");
    const [success, setSuccess] = useState("");
    const [isPending, setIsPending] = useState(false);
    const [showTokenPopup, setShowTokenPopup] = useState(false);
    const [showBuySuggestion, setShowBuySuggestion] = useState(false);
    const [showMeterAlert, setShowMeterAlert] = useState(false);
    const [hasMeter, setHasMeter] = useState<boolean | null>(null);
    const [isCheckingMeter, setIsCheckingMeter] = useState(true);
    const [isCheckingLoans, setIsCheckingLoans] = useState(true);
    const [hasBlockingLoan, setHasBlockingLoan] = useState(false);
    const [loanBlockMessage, setLoanBlockMessage] = useState<string | null>(null);
    const [loanResult, setLoanResult] = useState<{
        status: string;
        token?: string;
        units_disbursed?: number;
        rejection_reason?: string;
        message?: string;
    } | null>(null);

    const router = useRouter();
    useEffect(() => {
        const checkUserMeter = async () => {
            try {
                setIsCheckingMeter(true);

                // Use your fetch wrapper instead of raw fetch
                const response = await get<any>('meter/my-meter/');

                if (response.error) {
                    if (response.status === 401) {
                        router.push('/auth/login');
                        return;
                    }

                    setHasMeter(false);
                    setShowMeterAlert(true);
                    return;
                }

                if (response.data) {
                    setHasMeter(response.data.has_meter);
                    if (!response.data.has_meter) {
                        setShowMeterAlert(true);
                    }
                } else {
                    setHasMeter(false);
                    setShowMeterAlert(true);
                }
            } catch (error) {
                console.error('Error checking meter:', error);
                setHasMeter(false);
                setShowMeterAlert(true);
            } finally {
                setIsCheckingMeter(false);
            }
        };

        checkUserMeter();
    }, []);

    useEffect(() => {
        const checkLoanStatus = async () => {
            try {
                setIsCheckingLoans(true);
                const response = await get<any>('loans/stats/');

                if (!response.error && response.data) {
                    const hasBlocking = response.data.has_blocking_loan ??
                        ((response.data.pending_applications ?? 0) > 0 ||
                         (response.data.active_loans ?? 0) > 0 ||
                         Number(response.data.outstanding_balance ?? 0) > 0);

                    if (hasBlocking) {
                        setHasBlockingLoan(true);
                        setLoanBlockMessage("You already have a pending or unpaid loan. Please clear it before requesting another.");
                    } else {
                        setHasBlockingLoan(false);
                        setLoanBlockMessage(null);
                    }
                }
            } catch (error) {
                console.error("Error checking loan status:", error);
            } finally {
                setIsCheckingLoans(false);
            }
        };

        checkLoanStatus();
    }, []);

    const form = useForm<LoanFormValues>({
        resolver: zodResolver(LoanApplicationSchema),
        defaultValues: {
            purpose: "",
            amount_requested: undefined,
            tenure_months: undefined,
            monthly_expenditure: undefined,
            purchase_frequency: undefined,
            payment_consistency: undefined,
            disconnection_history: undefined,
            meter_sharing: undefined,
            monthly_income: undefined,
            income_stability: undefined,
            consumption_level: undefined,
        },
    });

    const onSubmit = async (values: LoanFormValues) => {
        if (!hasMeter) {
            setShowMeterAlert(true);
            setError("Please register your meter first");
            return;
        }
        setIsPending(true);
        setError("");
        setSuccess("");
        setLoanResult(null);
        setShowTokenPopup(false);
        setShowBuySuggestion(false);
        setShowMeterAlert(false);

        try {
            const result = await submitLoanApplication(values);

            if (result.error) {
                setError(result.error);
                return;
            }

            if (result.data) {
                setLoanResult(result.data);

                if (result.data.status === 'APPROVED') {
                    setSuccess(result.data.message || "Loan approved! We're crediting your units now - if they don't arrive shortly, contact support.");
                    setTimeout(() => {
                        router.push('/dashboard/myloans');
                    }, 3000);
                } else if (result.data.status === 'REJECTED') {
                    setError(result.data.rejection_reason || "Loan application was rejected");
                    setShowBuySuggestion(true);
                } else {
                    setSuccess(result.data.message || 'Loan application submitted successfully!');
                    setTimeout(() => {
                        router.push('/dashboard/myloans');
                    }, 3000);
                }
            }
        } catch (err: any) {
            console.error('Submission error:', err);
            setError(err.message || 'An error occurred while submitting your application.');
        } finally {
            setIsPending(false);
        }
    };

    const handleRegisterMeter = () => {
        router.push('/dashboard/request-loan/register-meter');
    };

    if (isCheckingMeter || isCheckingLoans) {
        return (
            <CardWrapper title="Apply for Electricity Loan">
                <div className="flex items-center justify-center p-8">
                    <Loader2 className="h-8 w-8 animate-spin text-blue-600 mr-3" />
                    <span>Checking your meter registration and loan status...</span>
                </div>
            </CardWrapper>
        );
    }

    return (
        <>
            <CardWrapper title="Apply for Electricity Loan">
                {/* Alerts */}
                {(showMeterAlert || hasBlockingLoan) && (
                    <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
                        <div className="flex items-start space-x-3">
                            <AlertTriangle className="h-5 w-5 text-red-600 mt-0.5 flex-shrink-0" />
                            <div className="flex-1">
                                <h3 className="font-medium text-red-800 mb-1">Action Required</h3>
                                <p className="text-sm text-red-700 mb-3">
                                    {loanBlockMessage ? loanBlockMessage : "You need to register your electricity meter before applying for a loan."}
                                </p>
                                <div className="flex flex-col sm:flex-row gap-2">
                                    {showMeterAlert && (
                                        <Button
                                            onClick={handleRegisterMeter}
                                            size="sm"
                                            className="bg-yellow-600 hover:bg-yellow-700 flex-1"
                                        >
                                            <Zap className="h-4 w-4 mr-2" />
                                            Register Meter Now
                                        </Button>
                                    )}
                                    {hasBlockingLoan && (
                                        <Button asChild size="sm" variant="outline" className="flex-1">
                                            <Link href="/dashboard/myloans">
                                                View / Pay Loan
                                            </Link>
                                        </Button>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                )}
                <div className={(!hasMeter || hasBlockingLoan) ? "opacity-50 pointer-events-none" : ""}>
                    <Form {...form}>
                        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <FormField
                                    control={form.control}
                                    name="purpose"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>Purpose of Loan</FormLabel>
                                            <FormControl>
                                                <Input
                                                    placeholder="e.g., To purchase electricity units for household use"
                                                    {...field}
                                                />
                                            </FormControl>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />
                                <FormField
                                    control={form.control}
                                    name="amount_requested"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>Amount Requested (UGX)</FormLabel>
                                            <FormControl>
                                                <Input
                                                    type="number"
                                                    placeholder="Enter amount (5,000 - 200,000 UGX)"
                                                    {...field}
                                                    onChange={(e) => field.onChange(parseInt(e.target.value) || 0)}
                                                />
                                            </FormControl>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />
                                <FormField
                                    control={form.control}
                                    name="tenure_months"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>Tenure (months)</FormLabel>
                                            <FormControl>
                                                <Input
                                                    type="number"
                                                    min={1}
                                                    max={12}
                                                    placeholder="1–12 (each month = 30 days from disbursement)"
                                                    {...field}
                                                    onChange={(e) => field.onChange(parseInt(e.target.value) || 0)}
                                                />
                                            </FormControl>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />

                                <FormField
                                    control={form.control}
                                    name="monthly_expenditure"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>Monthly Electricity Expenditure</FormLabel>
                                            <Select
                                                onValueChange={field.onChange}
                                                value={field.value}
                                            >
                                                <FormControl>
                                                    <SelectTrigger>
                                                        <SelectValue placeholder="Select expenditure range" />
                                                    </SelectTrigger>
                                                </FormControl>
                                                <SelectContent>
                                                    <SelectItem value="<50,000 UGX">Less than 50,000 UGX</SelectItem>
                                                    <SelectItem value="50,000–100,000 UGX">50,000–100,000 UGX</SelectItem>
                                                    <SelectItem value="100,001–200,000 UGX">100,001–200,000 UGX</SelectItem>
                                                    <SelectItem value="200,001–300,000 UGX">200,001–300,000 UGX</SelectItem>
                                                    <SelectItem value=">300,000 UGX">Over 300,000 UGX</SelectItem>
                                                </SelectContent>
                                            </Select>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />

                                <FormField
                                    control={form.control}
                                    name="purchase_frequency"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>Purchase Frequency</FormLabel>
                                            <Select
                                                onValueChange={field.onChange}
                                                value={field.value}
                                            >
                                                <FormControl>
                                                    <SelectTrigger>
                                                        <SelectValue placeholder="Select purchase frequency" />
                                                    </SelectTrigger>
                                                </FormControl>
                                                <SelectContent>
                                                    <SelectItem value="Daily">Daily</SelectItem>
                                                    <SelectItem value="Weekly">Weekly</SelectItem>
                                                    <SelectItem value="Bi-weekly">Bi-weekly</SelectItem>
                                                    <SelectItem value="Monthly">Monthly</SelectItem>
                                                    <SelectItem value="Rarely">Rarely</SelectItem>
                                                </SelectContent>
                                            </Select>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />

                                <FormField
                                    control={form.control}
                                    name="payment_consistency"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>Payment Consistency</FormLabel>
                                            <Select
                                                onValueChange={field.onChange}
                                                value={field.value}
                                            >
                                                <FormControl>
                                                    <SelectTrigger>
                                                        <SelectValue placeholder="Select payment consistency" />
                                                    </SelectTrigger>
                                                </FormControl>
                                                <SelectContent>
                                                    <SelectItem value="Always on time">Always on time</SelectItem>
                                                    <SelectItem value="Often on time">Often on time</SelectItem>
                                                    <SelectItem value="Sometimes late">Sometimes late</SelectItem>
                                                    <SelectItem value="Mostly late">Mostly late</SelectItem>
                                                    <SelectItem value="Never paid">Never paid</SelectItem>
                                                </SelectContent>
                                            </Select>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />

                                <FormField
                                    control={form.control}
                                    name="disconnection_history"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>Disconnection History</FormLabel>
                                            <Select
                                                onValueChange={field.onChange}
                                                value={field.value}
                                            >
                                                <FormControl>
                                                    <SelectTrigger>
                                                        <SelectValue placeholder="Select disconnection history" />
                                                    </SelectTrigger>
                                                </FormControl>
                                                <SelectContent>
                                                    <SelectItem value="No disconnections">No disconnections</SelectItem>
                                                    <SelectItem value="1–2 disconnections">1–2 disconnections</SelectItem>
                                                    <SelectItem value="3–4 disconnections">3–4 disconnections</SelectItem>
                                                    <SelectItem value=">4 disconnections">Over 4 disconnections</SelectItem>
                                                    <SelectItem value="Frequently disconnected">Frequently disconnected</SelectItem>
                                                </SelectContent>
                                            </Select>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />

                                <FormField
                                    control={form.control}
                                    name="meter_sharing"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>Meter Sharing</FormLabel>
                                            <Select
                                                onValueChange={field.onChange}
                                                value={field.value}
                                            >
                                                <FormControl>
                                                    <SelectTrigger>
                                                        <SelectValue placeholder="Select meter sharing status" />
                                                    </SelectTrigger>
                                                </FormControl>
                                                <SelectContent>
                                                    <SelectItem value="No sharing">No sharing</SelectItem>
                                                    <SelectItem value="Shared with 1 household">Shared with 1 household</SelectItem>
                                                    <SelectItem value="Shared with 2+ households">Shared with 2+ households</SelectItem>
                                                    <SelectItem value="Commercial sharing">Commercial sharing</SelectItem>
                                                </SelectContent>
                                            </Select>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />

                                <FormField
                                    control={form.control}
                                    name="monthly_income"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>Monthly Income</FormLabel>
                                            <Select
                                                onValueChange={field.onChange}
                                                value={field.value}
                                            >
                                                <FormControl>
                                                    <SelectTrigger>
                                                        <SelectValue placeholder="Select income range" />
                                                    </SelectTrigger>
                                                </FormControl>
                                                <SelectContent>
                                                    <SelectItem value="<100,000 UGX">Less than 100,000 UGX</SelectItem>
                                                    <SelectItem value="100,000–199,999 UGX">100,000–199,999 UGX</SelectItem>
                                                    <SelectItem value="200,000–499,999 UGX">200,000–499,999 UGX</SelectItem>
                                                    <SelectItem value="500,000–999,999 UGX">500,000–999,999 UGX</SelectItem>
                                                    <SelectItem value=">1,000,000 UGX">Over 1,000,000 UGX</SelectItem>
                                                </SelectContent>
                                            </Select>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />

                                <FormField
                                    control={form.control}
                                    name="income_stability"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>Income Stability</FormLabel>
                                            <Select
                                                onValueChange={field.onChange}
                                                value={field.value}
                                            >
                                                <FormControl>
                                                    <SelectTrigger>
                                                        <SelectValue placeholder="Select income stability" />
                                                    </SelectTrigger>
                                                </FormControl>
                                                <SelectContent>
                                                    <SelectItem value="Fixed and stable">Fixed and stable</SelectItem>
                                                    <SelectItem value="Regular but variable">Regular but variable</SelectItem>
                                                    <SelectItem value="Seasonal income">Seasonal income</SelectItem>
                                                    <SelectItem value="Irregular but frequent">Irregular but frequent</SelectItem>
                                                    <SelectItem value="Unstable income">Unstable income</SelectItem>
                                                </SelectContent>
                                            </Select>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />

                                <FormField
                                    control={form.control}
                                    name="consumption_level"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>Consumption Level</FormLabel>
                                            <Select
                                                onValueChange={field.onChange}
                                                value={field.value}
                                            >
                                                <FormControl>
                                                    <SelectTrigger>
                                                        <SelectValue placeholder="Select consumption level" />
                                                    </SelectTrigger>
                                                </FormControl>
                                                <SelectContent>
                                                    <SelectItem value="Very low (<50 kWh)">Very low (less than 50 kWh)</SelectItem>
                                                    <SelectItem value="Low (50–99 kWh)">Low (50–99 kWh)</SelectItem>
                                                    <SelectItem value="Moderate (100–200 kWh)">Moderate (100–200 kWh)</SelectItem>
                                                    <SelectItem value="High (>200 kWh)">High (over 200 kWh)</SelectItem>
                                                    <SelectItem value="Extremely high (>300 kWh)">Extremely high (over 300 kWh)</SelectItem>
                                                </SelectContent>
                                            </Select>
                                            <FormMessage />
                                        </FormItem>
                                    )}
                                />
                            </div>

                            <FormError message={error} />
                            <FormSuccess message={success} />

                            <Button type="submit" disabled={isPending} className="w-full">
                                {isPending ? (
                                    <>
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        Submitting...
                                    </>
                                ) : (
                                    "Submit Loan Application"
                                )}
                            </Button>
                        </form>
                    </Form>
                </div>
            </CardWrapper>

            {/* Token Popup for Approved Loans */}
            {showTokenPopup && loanResult?.token && (
                <TokenPopup
                    token={loanResult.token}
                    units={loanResult.units_disbursed || 0}
                    onClose={() => {
                        setShowTokenPopup(false);
                        setTimeout(() => {
                            router.push('/dashboard/myloans');
                        }, 500);
                    }}
                />
            )}

            {/* Buy Units Suggestion for Rejected Loans */}
            {showBuySuggestion && (
                <BuyUnitsSuggestion
                    message={loanResult?.rejection_reason || "Your loan application couldn't be approved at this time."}
                    onClose={() => {
                        setShowBuySuggestion(false);
                        setTimeout(() => {
                            router.push('/dashboard/myloans');
                        }, 500);
                    }}
                />
            )}
        </>
    );
}
