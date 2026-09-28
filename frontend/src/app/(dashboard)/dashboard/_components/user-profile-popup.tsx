"use client";

import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AlertCircle, CheckCircle, User, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { post, get } from "@/lib/fetch-client";
import { getApiErrorMessage } from "@/lib/api-response";

// Schema for user profile/loan assessment
const UserProfileSchema = z.object({
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

type UserProfileFormValues = z.infer<typeof UserProfileSchema>;

interface UserProfilePopupProps {
    isOpen: boolean;
    onClose: () => void;
    onSuccess: () => void;
    forceCompletion?: boolean;
    mode?: 'setup' | 'edit';
}

export default function UserProfilePopup({ 
    isOpen, 
    onClose, 
    onSuccess, 
    forceCompletion = false,
    mode = 'setup'
}: UserProfilePopupProps) {
    const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [isAuthValid, setIsAuthValid] = useState(true);

    const form = useForm<UserProfileFormValues>({
        resolver: zodResolver(UserProfileSchema),
        defaultValues: {
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

    useEffect(() => {
        if (isOpen) {
            const checkAuthAndRole = async () => {
                try {
                    const response = await get<{
                        is_admin?: boolean;
                        user_role?: string;
                    }>('auth/get-user-config/');
                    if (response.error) {
                        if (response.status === 401) {
                            setIsAuthValid(false);
                            window.location.href = '/auth/login?session=expired';
                        }
                        return;
                    }

                    const userData = response.data;
                    setIsAuthValid(true);

                    if (mode === 'setup' && (userData?.is_admin || userData?.user_role === 'ADMIN')) {
                        onSuccess();
                    }
                } catch (error) {
                    console.error('Auth check failed:', error);
                }
            };
            checkAuthAndRole();

            const loadProfile = async () => {
                try {
                    const profileRes = await get<{
                        profile_data?: Partial<UserProfileFormValues>;
                    }>('auth/user-profile/');
                    const data = profileRes.data?.profile_data;
                    if (data) {
                        form.reset({
                            monthly_expenditure: data.monthly_expenditure as UserProfileFormValues['monthly_expenditure'],
                            purchase_frequency: data.purchase_frequency as UserProfileFormValues['purchase_frequency'],
                            payment_consistency: data.payment_consistency as UserProfileFormValues['payment_consistency'],
                            disconnection_history: data.disconnection_history as UserProfileFormValues['disconnection_history'],
                            meter_sharing: data.meter_sharing as UserProfileFormValues['meter_sharing'],
                            monthly_income: data.monthly_income as UserProfileFormValues['monthly_income'],
                            income_stability: data.income_stability as UserProfileFormValues['income_stability'],
                            consumption_level: data.consumption_level as UserProfileFormValues['consumption_level'],
                        });
                    }
                } catch (error) {
                    console.error('Failed to load profile assessment:', error);
                }
            };
            loadProfile();
        }
    }, [isOpen, onSuccess, mode, form]);

    const onSubmit = async (values: UserProfileFormValues) => {
        setIsLoading(true);
        setMessage(null);

        try {
            const response = await post<any>('auth/user-profile/', values);

            if (response.error) {
                setMessage({ type: 'error', text: getApiErrorMessage(response.error, "Failed to save profile") });
            } else {
                setMessage({ type: 'success', text: 'Profile completed successfully!' });
                setTimeout(() => {
                    onSuccess();
                    if (mode === 'setup') {
                        onClose();
                    }
                }, 1500);
            }
        } catch (err: any) {
            setMessage({ type: 'error', text: err.message || "Failed to save profile" });
        } finally {
            setIsLoading(false);
        }
    };

    const handleClose = () => {
        if (!forceCompletion && mode === 'edit') {
            onClose();
        }
        // Don't allow closing during mandatory setup
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto relative">
                {mode === 'edit' && (
                    <Button
                        variant="ghost"
                        size="icon"
                        className="absolute right-2 top-2 h-6 w-6"
                        onClick={handleClose}
                        disabled={isLoading}
                    >
                        <X className="h-4 w-4" />
                    </Button>
                )}
                
                <CardHeader className="text-center pb-4">
                    <div className="flex items-center justify-center w-12 h-12 bg-blue-100 rounded-full mb-3 mx-auto">
                        <User className="h-6 w-6 text-blue-600" />
                    </div>
                    <CardTitle className="text-lg">
                        {mode === 'setup' 
                            ? (forceCompletion ? "Step 2: Complete Your Profile" : "Complete Your Profile")
                            : "Edit Your Profile"
                        }
                    </CardTitle>
                    <CardDescription>
                        {mode === 'setup'
                            ? (forceCompletion 
                                ? "Final step: Help us understand your electricity usage patterns for better loan assessment"
                                : "Help us understand your electricity usage patterns for better loan assessment")
                            : "Update your profile information"
                        }
                    </CardDescription>
                </CardHeader>

                <CardContent>
                    {message && (
                        <Alert
                            className={cn("mb-4",
                                message.type === 'success'
                                    ? "border-green-200 bg-green-50"
                                    : "border-red-200 bg-red-50"
                            )}
                        >
                            {message.type === 'success' ? (
                                <CheckCircle className="h-4 w-4 text-green-600" />
                            ) : (
                                <AlertCircle className="h-4 w-4 text-red-600" />
                            )}
                            <AlertTitle className={message.type === 'success' ? 'text-green-800' : 'text-red-800'}>
                                {message.type === 'success' ? 'Success!' : 'Error'}
                            </AlertTitle>
                            <AlertDescription className={message.type === 'success' ? 'text-green-700' : 'text-red-700'}>
                                {message.text}
                            </AlertDescription>
                        </Alert>
                    )}

                    <Form {...form}>
                        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <FormField
                                    control={form.control}
                                    name="monthly_expenditure"
                                    render={({ field }) => (
                                        <FormItem>
                                            <FormLabel>Monthly Electricity Expenditure</FormLabel>
                                            <Select onValueChange={field.onChange} value={field.value}>
                                                <FormControl>
                                                    <SelectTrigger>
                                                        <SelectValue placeholder="Select expenditure" />
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
                                            <Select onValueChange={field.onChange} value={field.value}>
                                                <FormControl>
                                                    <SelectTrigger>
                                                        <SelectValue placeholder="Select frequency" />
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
                                            <Select onValueChange={field.onChange} value={field.value}>
                                                <FormControl>
                                                    <SelectTrigger>
                                                        <SelectValue placeholder="Select consistency" />
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
                                            <Select onValueChange={field.onChange} value={field.value}>
                                                <FormControl>
                                                    <SelectTrigger>
                                                        <SelectValue placeholder="Select history" />
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
                                            <Select onValueChange={field.onChange} value={field.value}>
                                                <FormControl>
                                                    <SelectTrigger>
                                                        <SelectValue placeholder="Select sharing status" />
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
                                            <Select onValueChange={field.onChange} value={field.value}>
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
                                            <Select onValueChange={field.onChange} value={field.value}>
                                                <FormControl>
                                                    <SelectTrigger>
                                                        <SelectValue placeholder="Select stability" />
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
                                            <Select onValueChange={field.onChange} value={field.value}>
                                                <FormControl>
                                                    <SelectTrigger>
                                                        <SelectValue placeholder="Select consumption" />
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

                            <div className="flex gap-2 pt-4">
                                {mode === 'edit' && (
                                    <Button
                                        type="button"
                                        variant="outline"
                                        className="flex-1"
                                        onClick={handleClose}
                                        disabled={isLoading}
                                    >
                                        Cancel
                                    </Button>
                                )}
                                <Button
                                    type="submit"
                                    className={mode === 'edit' ? "flex-1" : "w-full"}
                                    disabled={isLoading}
                                >
                                    {isLoading ? (
                                        <>
                                            <User className="h-4 w-4 mr-2 animate-spin" />
                                            Saving...
                                        </>
                                    ) : (
                                        <>
                                            <User className="h-4 w-4 mr-2" />
                                            {mode === 'setup' 
                                                ? (forceCompletion ? "Complete Setup to Continue" : "Complete Profile")
                                                : "Save Changes"
                                            }
                                        </>
                                    )}
                                </Button>
                            </div>
                        </form>
                    </Form>
                </CardContent>
            </Card>
        </div>
    );
}
