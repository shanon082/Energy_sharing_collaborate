"use client";

import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AlertCircle, CheckCircle, X, Edit, Eye, Info, User as UserIcon, Zap as Meter } from "lucide-react";
import { cn } from "@/lib/utils";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { post, get } from "@/lib/fetch-client";
import { getApiErrorMessage } from "@/lib/api-response";
import { User as UserType } from "@/interface/user.interface";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

// Schema for user profile/loan assessment
const UserProfileSchema = z.object({
    monthly_expenditure: z.enum([
        "<50,000 UGX",
        "50,000–100,000 UGX",
        "100,001–200,000 UGX",
        "200,001–300,000 UGX",
        ">300,000 UGX"
    ]).optional(),
    purchase_frequency: z.enum([
        "Daily",
        "Weekly",
        "Bi-weekly",
        "Monthly",
        "Rarely"
    ]).optional(),
    payment_consistency: z.enum([
        "Always on time",
        "Often on time",
        "Sometimes late",
        "Mostly late",
        "Never paid"
    ]).optional(),
    disconnection_history: z.enum([
        "No disconnections",
        "1–2 disconnections",
        "3–4 disconnections",
        ">4 disconnections",
        "Frequently disconnected"
    ]).optional(),
    meter_sharing: z.enum([
        "No sharing",
        "Shared with 1 household",
        "Shared with 2+ households",
        "Commercial sharing"
    ]).optional(),
    monthly_income: z.enum([
        "<100,000 UGX",
        "100,000–199,999 UGX",
        "200,000–499,999 UGX",
        "500,000–999,999 UGX",
        ">1,000,000 UGX"
    ]).optional(),
    income_stability: z.enum([
        "Fixed and stable",
        "Regular but variable",
        "Seasonal income",
        "Irregular but frequent",
        "Unstable income"
    ]).optional(),
    consumption_level: z.enum([
        "Very low (<50 kWh)",
        "Low (50–99 kWh)",
        "Moderate (100–200 kWh)",
        "High (>200 kWh)",
        "Extremely high (>300 kWh)"
    ]).optional(),
});

type UserProfileFormValues = z.infer<typeof UserProfileSchema>;

interface ProfileManagementModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSuccess: () => void;
    userData: UserType;
    mode: 'view' | 'edit' | 'setup';
}

export default function ProfileManagementModal({ 
    isOpen, 
    onClose, 
    onSuccess, 
    userData,
    mode = 'view'
}: ProfileManagementModalProps) {
    const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [isEditing, setIsEditing] = useState(mode === 'edit');
    const [meterData, setMeterData] = useState<any>(null);
    const [activeTab, setActiveTab] = useState('profile');

    const form = useForm<UserProfileFormValues>({
        resolver: zodResolver(UserProfileSchema),
        defaultValues: {
            monthly_expenditure: userData.profile_data?.monthly_expenditure as any || undefined,
            purchase_frequency: userData.profile_data?.purchase_frequency as any || undefined,
            payment_consistency: userData.profile_data?.payment_consistency as any || undefined,
            disconnection_history: userData.profile_data?.disconnection_history as any || undefined,
            meter_sharing: userData.profile_data?.meter_sharing as any || undefined,
            monthly_income: userData.profile_data?.monthly_income as any || undefined,
            income_stability: userData.profile_data?.income_stability as any || undefined,
            consumption_level: userData.profile_data?.consumption_level as any || undefined,
        },
    });

    // Fetch meter data when modal opens
    useEffect(() => {
        if (isOpen) {
            fetchMeterData();
        }
    }, [isOpen]);

    const fetchMeterData = async () => {
        try {
            const response = await get<any>('meter/my-meter/');
            if (!response.error && response.data) {
                setMeterData(response.data);
            }
        } catch (error) {
            console.error('Failed to fetch meter data:', error);
        }
    };

    const onSubmit = async (values: UserProfileFormValues) => {
        setIsLoading(true);
        setMessage(null);

        try {
            // Save user profile data
            const response = await post<any>('auth/user-profile/', values);

            if (response.error) {
                setMessage({ type: 'error', text: getApiErrorMessage(response.error, "Failed to save profile") });
            } else {
                setMessage({ type: 'success', text: 'Profile updated successfully!' });
                setIsEditing(false);
                setTimeout(() => {
                    onSuccess();
                }, 1500);
            }
        } catch (err: any) {
            setMessage({ type: 'error', text: err.message || "Failed to save profile" });
        } finally {
            setIsLoading(false);
        }
    };

    const handleClose = () => {
        onClose();
    };

    const handleEditToggle = () => {
        if (isEditing) {
            // Save changes
            form.handleSubmit(onSubmit)();
        } else {
            setIsEditing(true);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <Card className="w-full max-w-4xl max-h-[90vh] overflow-y-auto relative">
                <Button
                    variant="ghost"
                    size="icon"
                    className="absolute right-2 top-2 h-6 w-6"
                    onClick={handleClose}
                    disabled={isLoading}
                >
                    <X className="h-4 w-4" />
                </Button>

                <CardHeader className="pb-4">
                    <div className="flex items-center space-x-3">
                        <div className="flex items-center justify-center w-12 h-12 bg-blue-100 rounded-full">
                            <UserIcon className="h-6 w-6 text-blue-600" />
                        </div>
                        <div>
                            <CardTitle className="text-lg">
                                {isEditing ? 'Edit Your Profile' : 'Your Profile'}
                            </CardTitle>
                            <CardDescription>
                                {isEditing 
                                    ? 'Update your profile information'
                                    : 'View your profile details and setup status'}
                            </CardDescription>
                        </div>
                    </div>
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

                    <Tabs defaultValue="profile" value={activeTab} onValueChange={setActiveTab}>
                        <TabsList className="grid grid-cols-3 mb-6">
                            <TabsTrigger value="profile">Profile Info</TabsTrigger>
                            <TabsTrigger value="meter">Meter Details</TabsTrigger>
                            <TabsTrigger value="setup">Setup Status</TabsTrigger>
                        </TabsList>

                        {/* Profile Information Tab */}
                        <TabsContent value="profile" className="space-y-4">
                            <div className="flex justify-between items-center mb-4">
                                <h3 className="text-lg font-medium">Profile Information</h3>
                                <Button
                                    variant={isEditing ? "default" : "outline"}
                                    size="sm"
                                    onClick={handleEditToggle}
                                    disabled={isLoading}
                                >
                                    {isLoading ? (
                                        <div className="h-4 w-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                                    ) : isEditing ? (
                                        <>
                                            <CheckCircle className="h-4 w-4 mr-2" />
                                            Save Changes
                                        </>
                                    ) : (
                                        <>
                                            <Edit className="h-4 w-4 mr-2" />
                                            Edit Profile
                                        </>
                                    )}
                                </Button>
                            </div>

                            <Form {...form}>
                                <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        {/* Read-only basic info */}
                                        <div className="space-y-2">
                                            <label className="text-sm font-medium text-foreground">Full Name</label>
                                            <Input
                                                value={`${userData.first_name} ${userData.last_name}`}
                                                readOnly
                                                className="bg-gray-50 text-gray-700"
                                            />
                                        </div>

                                        <div className="space-y-2">
                                            <label className="text-sm font-medium text-foreground">Email</label>
                                            <Input
                                                value={userData.email}
                                                readOnly
                                                className="bg-gray-50 text-gray-700"
                                            />
                                        </div>

                                        <div className="space-y-2">
                                            <label className="text-sm font-medium text-foreground">Phone Number</label>
                                            <Input
                                                value={userData.phone_number}
                                                readOnly
                                                className="bg-gray-50 text-gray-700"
                                            />
                                        </div>

                                        {/* Account Details */}
                                        <div className="space-y-2">
                                            <label className="text-sm font-medium text-foreground">Account Number</label>
                                            <Input
                                                value={userData.account_details?.account_number || 'Not set'}
                                                readOnly
                                                className="bg-gray-50 text-gray-700"
                                            />
                                        </div>

                                        {/* Editable Profile Fields */}
                                        <FormField
                                            control={form.control}
                                            name="monthly_expenditure"
                                            render={({ field }) => (
                                                <FormItem>
                                                    <FormLabel>Monthly Electricity Expenditure</FormLabel>
                                                    <Select 
                                                        onValueChange={field.onChange} 
                                                        value={field.value}
                                                        disabled={!isEditing}
                                                    >
                                                        <FormControl>
                                                            <SelectTrigger>
                                                                <SelectValue placeholder="Not set" />
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
                                                        disabled={!isEditing}
                                                    >
                                                        <FormControl>
                                                            <SelectTrigger>
                                                                <SelectValue placeholder="Not set" />
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

                                    {isEditing && (
                                        <div className="flex justify-end space-x-2 pt-4">
                                            <Button
                                                type="button"
                                                variant="outline"
                                                onClick={() => setIsEditing(false)}
                                                disabled={isLoading}
                                            >
                                                Cancel
                                            </Button>
                                            <Button
                                                type="submit"
                                                disabled={isLoading}
                                            >
                                                {isLoading ? 'Saving...' : 'Save Changes'}
                                            </Button>
                                        </div>
                                    )}
                                </form>
                            </Form>
                        </TabsContent>

                        {/* Meter Details Tab */}
                        <TabsContent value="meter" className="space-y-4">
                            <div className="flex items-center space-x-2 mb-4">
                                <Meter className="h-5 w-5 text-blue-600" />
                                <h3 className="text-lg font-medium">Meter Information</h3>
                            </div>

                            {meterData ? (
                                <div className="space-y-4">
                                    {meterData.success && meterData.data.has_meter ? (
                                        <>
                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                <div className="space-y-2">
                                                    <label className="text-sm font-medium text-foreground">Meter Number</label>
                                                    <Input
                                                        value={meterData.data.meter_number || ''}
                                                        readOnly
                                                        className="bg-gray-50 font-mono text-gray-700"
                                                    />
                                                </div>
                                                <div className="space-y-2">
                                                    <label className="text-sm font-medium text-foreground">Static IP</label>
                                                    <Input
                                                        value={meterData.data.static_ip || ''}
                                                        readOnly
                                                        className="bg-gray-50 font-mono text-gray-700"
                                                    />
                                                </div>
                                                <div className="space-y-2">
                                                    <label className="text-sm font-medium text-foreground">Available Units</label>
                                                    <Input
                                                        value={`${meterData.data.units || 0} units`}
                                                        readOnly
                                                        className="bg-gray-50 text-gray-700"
                                                    />
                                                </div>
                                                <div className="space-y-2">
                                                    <label className="text-sm font-medium text-foreground">Status</label>
                                                    <div className="flex items-center">
                                                        <div className="h-2 w-2 rounded-full bg-green-500 mr-2"></div>
                                                        <span className="text-sm">Registered</span>
                                                    </div>
                                                </div>
                                            </div>
                                            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                                                <div className="flex items-center">
                                                    <CheckCircle className="h-5 w-5 text-green-600 mr-2" />
                                                    <p className="text-sm text-green-800">
                                                        Your meter is successfully registered and ready for use.
                                                    </p>
                                                </div>
                                            </div>
                                        </>
                                    ) : (
                                        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center">
                                            <Meter className="h-12 w-12 text-yellow-600 mx-auto mb-3" />
                                            <h4 className="font-medium text-yellow-800 mb-2">No Meter Registered</h4>
                                            <p className="text-sm text-yellow-700 mb-4">
                                                You haven't registered a meter yet. Register a meter to start using electricity services.
                                            </p>
                                            <Button
                                                onClick={() => {
                                                    onClose();
                                                    // You might want to trigger meter registration from here
                                                }}
                                                variant="outline"
                                                className="border-yellow-300 text-yellow-700 hover:bg-yellow-50"
                                            >
                                                Register Meter
                                            </Button>
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <div className="text-center py-8">
                                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4" />
                                    <p className="text-gray-600">Loading meter information...</p>
                                </div>
                            )}
                        </TabsContent>

                        {/* Setup Status Tab */}
                        <TabsContent value="setup" className="space-y-4">
                            <div className="flex items-center space-x-2 mb-4">
                                <Info className="h-5 w-5 text-blue-600" />
                                <h3 className="text-lg font-medium">Setup Status</h3>
                            </div>

                            <div className="space-y-4">
                                {/* Setup Progress */}
                                <div className="space-y-2">
                                    <div className="flex justify-between text-sm">
                                        <span>Setup Progress</span>
                                        <span className="font-medium">100%</span>
                                    </div>
                                    <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                                        <div className="h-full bg-green-500 w-full rounded-full"></div>
                                    </div>
                                </div>

                                {/* Setup Steps */}
                                <div className="space-y-3">
                                    <div className="flex items-center justify-between p-3 bg-green-50 border border-green-200 rounded-lg">
                                        <div className="flex items-center space-x-3">
                                            <div className="h-6 w-6 bg-green-100 rounded-full flex items-center justify-center">
                                                <CheckCircle className="h-4 w-4 text-green-600" />
                                            </div>
                                            <div>
                                                <p className="font-medium text-green-800">Account Registration</p>
                                                <p className="text-xs text-green-700">Your account is active and verified</p>
                                            </div>
                                        </div>
                                        <span className="text-xs px-2 py-1 bg-green-100 text-green-800 rounded-full">Complete</span>
                                    </div>

                                    <div className="flex items-center justify-between p-3 bg-green-50 border border-green-200 rounded-lg">
                                        <div className="flex items-center space-x-3">
                                            <div className="h-6 w-6 bg-green-100 rounded-full flex items-center justify-center">
                                                <CheckCircle className="h-4 w-4 text-green-600" />
                                            </div>
                                            <div>
                                                <p className="font-medium text-green-800">Meter Registration</p>
                                                <p className="text-xs text-green-700">
                                                    {meterData?.data?.has_meter 
                                                        ? `Meter ${meterData.data.meter_number} registered`
                                                        : 'Meter registration complete'
                                                    }
                                                </p>
                                            </div>
                                        </div>
                                        <span className="text-xs px-2 py-1 bg-green-100 text-green-800 rounded-full">Complete</span>
                                    </div>

                                    <div className="flex items-center justify-between p-3 bg-green-50 border border-green-200 rounded-lg">
                                        <div className="flex items-center space-x-3">
                                            <div className="h-6 w-6 bg-green-100 rounded-full flex items-center justify-center">
                                                <CheckCircle className="h-4 w-4 text-green-600" />
                                            </div>
                                            <div>
                                                <p className="font-medium text-green-800">Profile Completion</p>
                                                <p className="text-xs text-green-700">Your profile is complete and ready for loans</p>
                                            </div>
                                        </div>
                                        <span className="text-xs px-2 py-1 bg-green-100 text-green-800 rounded-full">Complete</span>
                                    </div>
                                </div>

                                {/* Completion Status */}
                                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                                    <div className="flex items-center space-x-2 mb-2">
                                        <CheckCircle className="h-5 w-5 text-blue-600" />
                                        <h4 className="font-medium text-blue-800">Setup Complete!</h4>
                                    </div>
                                    <p className="text-sm text-blue-700">
                                        You have successfully completed all setup steps. You can now:
                                    </p>
                                    <ul className="mt-2 space-y-1 text-sm text-blue-700">
                                        <li className="flex items-center">
                                            <div className="h-1.5 w-1.5 bg-blue-500 rounded-full mr-2"></div>
                                            Apply for electricity loans
                                        </li>
                                        <li className="flex items-center">
                                            <div className="h-1.5 w-1.5 bg-blue-500 rounded-full mr-2"></div>
                                            Buy electricity units
                                        </li>
                                        <li className="flex items-center">
                                            <div className="h-1.5 w-1.5 bg-blue-500 rounded-full mr-2"></div>
                                            Share units with other users
                                        </li>
                                        <li className="flex items-center">
                                            <div className="h-1.5 w-1.5 bg-blue-500 rounded-full mr-2"></div>
                                            View transaction history
                                        </li>
                                    </ul>
                                </div>
                            </div>
                        </TabsContent>
                    </Tabs>
                </CardContent>
            </Card>
        </div>
    );
}
