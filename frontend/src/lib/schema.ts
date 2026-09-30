import { z } from "zod";
import validator from "validator";
import dayjs from "dayjs";
import { get, patch } from "./fetch";
import { getApiErrorMessage } from "./api-response";
import type { ComponentType } from "react";

export const createAccountSchema = z
  .object({
    first_name: z.string().min(2).max(50),
    last_name: z.string().min(2).max(50),
    email: z.string().email("Please provide a valid email address"),
    phone_number: z.string().refine(validator.isMobilePhone),
    gender: z.enum(["OTHER", "MALE", "FEMALE"]),
    password: z
      .string()
      .min(6, "Password should be atleast 6 characters long")
      .max(24, "Password should be a maximum of 24 characters"),
    confirm_password: z.string(),
    // country: z.string().min(1, "Country is required"),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: "Passwords don't match",
    path: ["confirm_password"],
  });

export const settingsSchema = z
  .object({
    first_name: z.string().min(2).max(50),
    last_name: z.string().min(2).max(50),
    email: z.string().email("Please provide a valid email address"),
    phone_number: z.string().refine(validator.isMobilePhone),
    gender: z.enum(["OTHER", "MALE", "FEMALE"]),
    password: z.string().optional(),
    confirm_password: z.string(),
    current_password: z
      .string()
      .min(6, "Password must be atleast 6 characters"),
    code: z.string().optional(),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: "Passwords don't match",
    path: ["confirm_password"],
  });

export const AccountSetupSchema = z.object({
  account_type: z.enum(["PERSONAL", "MERCHANT"]),
});

export const AccountCountrySchema = z.object({
  country: z.string().length(2, "Invalid country selected"),
});

export const PasswordRegistrationSchema = z
  .object({
    password: z
      .string()
      .min(6, "Password should be atleast 6 characters long")
      .max(24, "Password should be a maximum of 24 characters"),
    password_confirm: z.string(),
  })
  .refine((data) => data.password === data.password_confirm, {
    message: "Passwords don't match",
    path: ["password_confirm"],
  });

const securePasswordField = z
  .string()
  .min(12, "Password must be at least 12 characters")
  .regex(
    /^(?=\S*[A-Z])(?=\S*[a-z])(?=\S*\d)\S+$/,
    "Password must include uppercase, lowercase, and a number"
  );

export const ResetPasswordSchema = z
  .object({
    password: securePasswordField,
    confirm_password: z.string().min(1, "Please confirm your password"),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

export const PasswordResetSchema = z
  .object({
    password: z
      .string()
      .min(6, "Password should be atleast 6 characters long")
      .max(24, "Password should be a maximum of 24 characters"),
    confirm_password: z.string(),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: "Passwords don't match",
    path: ["confirm_password"],
  });

export const ForgotPasswordSchema = z.object({
  email: z.string().email(),
});

export enum AccountType {
  PERSONAL = "PERSONAL",
  MERCHANT = "MERCHANT",
}

export const registerSchema = z.object({
  email: z.string().email(),
});

export const sendVerificationEmailSchema = z.object({
  email: z.string().email(),
});

export const emailVerificationSchema = z.object({
  otp: z.string().length(6),
});

export const resendVerificationEmailSchema = z.object({
  email: z.string().email(),
});

export const CountryPhoneSetupSchema = z.object({
  country: z.string(),
  phone: z.string().refine(validator.isMobilePhone),
});

export const phoneVerificationSchema = z.object({
  otp: z.string().length(6),
});

export type PublicUser = {
  username: string;
  first_name: string;
  last_name: string;
};

export type PrivateUser = {
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  phone_number: string;
  profile_photo?: string;
  emailVerified?: string;
  createdAt: Date;
  updatedAt?: Date;
};

export const NewPasswordSchema = z
  .object({
    password: z
      .string()
      .min(6, "Password should be atleast 6 characters long")
      .max(24, "Password should be a maximum of 24 characters"),
    password_confirm: z.string(),
  })
  .refine((data) => data.password === data.password_confirm, {
    message: "Passwords don't match",
    path: ["password_confirm"],
  });

export const ResetSchema = z.object({
  email: z.string().email({
    message: "Email is required",
  }),
});

export const LoginSchema = z.object({
  email: z.string().email({
    message: "Email is required",
  }),
  password: z.string().min(1, {
    message: "Password is required",
  }),
  code: z.optional(z.string()),
});

export const RegisterSchema = z.object({
  email: z.string().email({
    message: "Email is required",
  }),
  password: z.string().min(6, {
    message: "Minimum 6 characters required",
  }),
  name: z.string().min(1, {
    message: "Name is required",
  }),
});

export const DepositSchema = z.object({
  phone_number: z.string().refine(validator.isMobilePhone),
  payment_method: z.enum(["mpesa", "yo_uganda"]),
  amount: z.coerce.number().min(1, { message: "Minimum deposit amount is $1" }),
});
export const BuyAtSchema = z.object({
  phone_number: z.string().refine(validator.isMobilePhone),
  amount: z.coerce.number().min(1, { message: "Please enter amount" }),
});

export const ActivateSchema = z.object({
  package: z.enum(["NONE", "STARTER", "BRONZE", "DIAMOND", "PLATINUM"]),
  leg: z.enum(["LEFT", "RIGHT"]).optional(),
  placement_id: z.string().optional(),
});

export const TransferSchema = z.object({
  referral_code: z.string().min(1, {
    message: "Referral code is required",
  }),
  amount: z.coerce
    .number()
    .min(1, { message: "Minimum transfer amount is $1" }),
  current_password: z.string().min(6, "Password must be atleast 6 characters"),
});

export const BuyUnitSchema = z.object({
  meter_no: z.string().min(1, "Choose the meter for this electricity purchase"),
  phone_number: z.string(),
  amount: z.number().int("Enter a whole-UGX amount")
    .min(1, { message: "Enter a positive UGX amount" }),
  payment_source: z.enum(["WALLET", "PHONE"]),
}).superRefine((data, ctx) => {
  if (data.payment_source === "PHONE" && !validator.isMobilePhone(data.phone_number || "")) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["phone_number"],
      message: "Please enter a valid phone number",
    });
  }
});

export const EditProfileSchema = z.object({
  firstName: z
    .string()
    .min(3, "First name is required and must be atleast 3 characters long"),
  lastName: z
    .string()
    .min(3, "Last name is required and must be atleast 3 characters long"),
  dateOfBirth: z.string().refine(
    (data) => {
      console.log("date: ", data);
      return dayjs(data, "DD-MM-YYYY").isValid();
    },
    { message: "Invalid date of birth" }
  ),
  address: z.string().min(1, "Address is required"),
  city: z.string().min(1, "City is required"),
  postalCode: z.string().min(1, "Postal code is required"),
  country: z.string().length(2, "Invalid country selected"),
  phone: z.string().refine(validator.isMobilePhone),
});

export type SidebarProps = {
  isOpen?: boolean;
  toggleIsOpen?: (option: boolean) => void;
};

export enum TransactionType {
  //deposit | withdraw | transfer | investment
  DEPOSIT = "deposit",
  WITHDRAW = "withdraw",
  TRANSFER = "transfer",
  INVESTMENT = "investment",
}

export enum TransactionStatus {
  // pending | completed | failed
  PENDING = "pending",
  COMPLETED = "completed",
  FAILED = "failed",
}

export enum TransactionProvider {
  // crypto | mpesa | emoney
  USDT = "usdt",
  MPESAKE = "mpesake",
  EMONEY = "emoney",
  MTNUG = "mtnug",
  AIRTELUG = "airtelug",
}

export type DashboardNavigationType = {
  name: string;
  href: string;
  icon?: ComponentType<{ className?: string }>;
  current: boolean;
};

export interface UserAccount {
  id: string;
  accountNumber: string;
  meterNumber: string;
  phoneNumber: string;
  email: string;
  firstName: string;
  lastName: string;
  address?: string;
  energyPreference?: string;
  paymentMethod?: string;
}

// export const getAccountData = async (): Promise<UserAccount> => {
//   try {
//     const response = await get<{
//       account_details: {
//         account_number: string;
//         // meter_number: string;
//         address: string;
//         energy_preference: string;
//         payment_method: string;
//       };
//       first_name: string;
//       last_name: string;
//       email: string;
//       phone_number: string;
//       id: string;
//     }>("auth/get-user-config/");

//     if (response.error) {
//       throw new Error(response.error.message || "Failed to fetch account data");
//     }

//     return {
//       id: response.data.id,
//       accountNumber: response.data?.account_details?.account_number || "",
//       // meterNumber: response.data?.account_details?.meter_number || "",
//       phoneNumber: response.data.phone_number,
//       email: response.data.email,
//       firstName: response.data.first_name,
//       lastName: response.data.last_name,
//       address: response.data.account_details?.address,
//       energyPreference: response.data.account_details?.energy_preference,
//       paymentMethod: response.data.account_details?.payment_method,
//     };
//   } catch (error) {
//     console.error("Failed to fetch account data:", error);
//     throw error;
//   }
// };

// export const updateAccountData = async (
//   data: UserAccount
// ): Promise<UserAccount> => {
//   try {
//     // Only send fields that can be updated
//     const updateData = {
//       address: data.address,
//       energy_preference: data.energyPreference,
//       payment_method: data.paymentMethod,
//     };

//     console.log("Sending update data:", updateData);

//     const response = await patch("auth/update-account-details/", updateData);

//     if (response.error) {
//       throw new Error(
//         response.error.message || "Failed to update account data"
//       );
//     }

//     const updatedAccountData = await getAccountData();
//     return updatedAccountData;
//   } catch (error) {
//     console.error("Failed to update account data:", error);
//     throw error;
//   }
// };

// Loan Status Enum
export enum LoanStatus {
  PENDING = "PENDING",
  APPROVED = "APPROVED",
  DISBURSED = "DISBURSED",
  COMPLETED = "COMPLETED",
  REJECTED = "REJECTED"
}

// Loan Tier Enum
export enum LoanTier {
  BRONZE = "BRONZE",
  SILVER = "SILVER",
  GOLD = "GOLD",
  PLATINUM = "PLATINUM"
}

// Payment Method Enum
export enum PaymentMethod {
  CREDIT_CARD = "CREDIT_CARD",
  MOBILE_MONEY = "MOBILE_MONEY",
  BANK_TRANSFER = "BANK_TRANSFER"
}

// Energy Preference Enum
export enum EnergyPreference {
  SOLAR = "SOLAR",
  HYDRO = "HYDRO",
  THERMAL = "THERMAL",
  OTHER = "OTHER"
}

// Profile Status Enum
export enum ProfileCompletionStatus {
  BASIC = "BASIC",
  METER_REGISTERED = "METER_REGISTERED",
  PROFILE_COMPLETE = "PROFILE_COMPLETE",
  LOAN_ELIGIBLE = "LOAN_ELIGIBLE"
}

// Loan Interface
export interface LoanApplication {
  id: number;
  loan_id: string;
  status: LoanStatus;
  loan_tier?: LoanTier;
  amount_requested: number;
  amount_approved?: number;
  credit_score?: number;
  purpose: string;
  tenure_months: number;
  interest_rate?: number;
  outstanding_balance?: number;
  total_amount_due?: number;
  created_at: string;
  due_date?: string;
  disbursement_token?: string;
  disbursement_units?: number;
  is_eligible: boolean;
  tariff_details?: {
    tariff_code: string;
    tariff_name: string;
  };
  units_calculated?: number;
  cost_breakdown?: Array<{
    block_name: string;
    units: number;
    rate: number;
    cost: number;
  }>;
}

// Meter Interface
export interface MeterDetails {
  meter_no: string;
  static_ip: string;
  units: number;
  has_meter: boolean;
  created_at?: string;
  last_updated?: string;
}

// User Profile Interface
export interface UserProfile {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  phoneNumber: string;
  gender?: string;
  emailVerified: boolean;
  accountActive: boolean;
  userRole: string;
  isAdmin: boolean;
  
  // Account Details
  accountNumber: string;
  address?: string;
  energyPreference?: EnergyPreference;
  paymentMethod?: PaymentMethod;
  
  // Meter Information
  meter?: MeterDetails;
  
  // Loan Information
  loans: LoanApplication[];
  loanStats?: {
    active_loans: number;
    total_loans: number;
    total_borrowed: number;
    total_repayments: number;
    outstanding_balance: number;
    credit_score?: number;
  };
  
  // Profile Completion
  profileCompletion: {
    hasCompleteProfile: boolean;
    hasMeter: boolean;
    isLoanEligible: boolean;
    completionPercentage: number;
    missingFields: string[];
  };
}

// Enhanced User Account Interface (for backward compatibility)
export interface UserAccount {
  id: string;
  accountNumber: string;
  meterNumber: string;
  phoneNumber: string;
  email: string;
  firstName: string;
  lastName: string;
  address?: string;
  energyPreference?: string;
  paymentMethod?: string;
  meter?: MeterDetails;
  loans?: LoanApplication[];
  profileCompletion?: {
    hasCompleteProfile: boolean;
    hasMeter: boolean;
    isLoanEligible: boolean;
  };
}

// Profile Update Schema
export const ProfileUpdateSchema = z.object({
  firstName: z.string().min(2, "First name must be at least 2 characters"),
  lastName: z.string().min(2, "Last name must be at least 2 characters"),
  email: z.string().email("Please provide a valid email address"),
  phoneNumber: z.string().refine(validator.isMobilePhone, "Please provide a valid phone number"),
  address: z.string().optional(),
  energyPreference: z.nativeEnum(EnergyPreference).optional(),
  paymentMethod: z.nativeEnum(PaymentMethod).optional(),
}).refine((data) => {
  // Email validation for updates
  if (data.email && !validator.isEmail(data.email)) {
    return false;
  }
  return true;
});

// Get comprehensive user profile data
export const getUserProfile = async (): Promise<UserProfile> => {
  try {
    // Fetch user config
    const userConfigResponse = await get<{
      id: string;
      first_name: string;
      last_name: string;
      email: string;
      phone_number: string;
      gender?: string;
      profile: {
        email_verified: boolean;
      };
      account_is_active: boolean;
      user_role: string;
      is_admin: boolean;
      is_staff: boolean;
      is_superuser: boolean;
      account_details: {
        account_number: string;
        address: string;
        energy_preference: EnergyPreference;
        payment_method: PaymentMethod;
      };
    }>("auth/get-user-config/");

    if (userConfigResponse.error || !userConfigResponse.data) {
      throw new Error(getApiErrorMessage(userConfigResponse.error, "Failed to fetch user config"));
    }

    // Fetch meter information
    const meterResponse = await get<{
      success: boolean;
      data: {
        has_meter: boolean;
        meter_number?: string;
        static_ip?: string;
        units?: number;
      };
    }>("meter/my-meter/");

    // Fetch loans
    const loansResponse = await get<LoanApplication[] | { results?: LoanApplication[]; data?: LoanApplication[] }>("loans/my-loans/");

    // Fetch loan stats
    type LoanStatsPayload = {
      active_loans?: number;
      total_loans?: number;
      total_borrowed?: string | number;
      total_repayments?: string | number;
      outstanding_balance?: string | number;
      credit_score?: number | null;
    };
    const loanStatsResponse = await get<LoanStatsPayload | { data: LoanStatsPayload }>("loans/stats/");

    const rawLoans = loansResponse.data;
    const loansData = Array.isArray(rawLoans)
      ? rawLoans
      : rawLoans?.results || rawLoans?.data || [];

    const rawStats = loanStatsResponse.data;
    const statsData = rawStats && "data" in rawStats ? rawStats.data : rawStats;
    
    const loanStats = statsData
      ? {
          active_loans: Number(statsData.active_loans || 0),
          total_loans: Number(statsData.total_loans || 0),
          total_borrowed: Number(statsData.total_borrowed || 0),
          total_repayments: Number(statsData.total_repayments || 0),
          outstanding_balance: Number(statsData.outstanding_balance || 0),
          credit_score: statsData.credit_score ? Number(statsData.credit_score) : undefined,
        }
      : undefined;

    const userConfig = userConfigResponse.data;
    
    // Build meter details
    let meterDetails: MeterDetails | undefined;
    if (meterResponse.data?.success && meterResponse.data.data.has_meter) {
      meterDetails = {
        meter_no: meterResponse.data.data.meter_number || "",
        static_ip: meterResponse.data.data.static_ip || "",
        units: meterResponse.data.data.units || 0,
        has_meter: true
      };
    }

    // Calculate profile completion
    const missingFields: string[] = [];
    if (!userConfig.first_name || !userConfig.last_name) missingFields.push("Name");
    if (!userConfig.email) missingFields.push("Email");
    if (!userConfig.phone_number) missingFields.push("Phone");
    if (!userConfig.account_details?.address) missingFields.push("Address");
    if (!meterDetails?.has_meter) missingFields.push("Meter Registration");
    
    const hasCompleteProfile = userConfig.profile?.email_verified && 
                              userConfig.first_name && 
                              userConfig.last_name && 
                              userConfig.email && 
                              userConfig.phone_number && 
                              userConfig.account_details?.address;
    
    const completionPercentage = Math.round(
      (100 - (missingFields.length / 6) * 100)
    );

    return {
      id: userConfig.id,
      email: userConfig.email,
      firstName: userConfig.first_name,
      lastName: userConfig.last_name,
      phoneNumber: userConfig.phone_number,
      gender: userConfig.gender,
      emailVerified: userConfig.profile?.email_verified || false,
      accountActive: userConfig.account_is_active,
      userRole: userConfig.user_role,
      isAdmin: userConfig.is_admin,
      
      accountNumber: userConfig.account_details?.account_number || "",
      address: userConfig.account_details?.address,
      energyPreference: userConfig.account_details?.energy_preference,
      paymentMethod: userConfig.account_details?.payment_method,
      
      meter: meterDetails,
      loans: loansData,
      loanStats,
      
      profileCompletion: {
        hasCompleteProfile: !!hasCompleteProfile,
        hasMeter: !!meterDetails?.has_meter,
        isLoanEligible: (loanStats?.credit_score || 0) >= 75,
        completionPercentage,
        missingFields
      }
    };
  } catch (error) {
    console.error("Failed to fetch user profile:", error);
    throw error;
  }
};

// Update profile data
export const updateProfileData = async (data: Partial<UserProfile>): Promise<UserProfile> => {
  try {
    // Update account details if provided
    if (data.address || data.energyPreference || data.paymentMethod) {
      const updateData = {
        address: data.address,
        energy_preference: data.energyPreference,
        payment_method: data.paymentMethod,
      };

      const response = await patch("auth/update-account-details/", updateData);

      if (response.error) {
        throw new Error(getApiErrorMessage(response.error, "Failed to update account details"));
      }
    }

    // Update user settings if name, email, or phone changed
    if (data.firstName || data.lastName || data.email || data.phoneNumber) {
      // Note: This would require additional API endpoint for updating user settings
      console.warn("User settings update requires additional implementation");
    }

    // Return updated profile
    return await getUserProfile();
  } catch (error) {
    console.error("Failed to update profile data:", error);
    throw error;
  }
};

// Get account data (for backward compatibility)
export const getAccountData = async (): Promise<UserAccount> => {
  const profile = await getUserProfile();
  
  return {
    id: profile.id,
    accountNumber: profile.accountNumber,
    meterNumber: profile.meter?.meter_no || "",
    phoneNumber: profile.phoneNumber,
    email: profile.email,
    firstName: profile.firstName,
    lastName: profile.lastName,
    address: profile.address,
    energyPreference: profile.energyPreference,
    paymentMethod: profile.paymentMethod,
    meter: profile.meter,
    loans: profile.loans,
    profileCompletion: {
      hasCompleteProfile: profile.profileCompletion.hasCompleteProfile,
      hasMeter: profile.profileCompletion.hasMeter,
      isLoanEligible: profile.profileCompletion.isLoanEligible
    }
  };
};

// Update account data (for backward compatibility)
export const updateAccountData = async (data: UserAccount): Promise<UserAccount> => {
  const profileUpdate: Partial<UserProfile> = {
    firstName: data.firstName,
    lastName: data.lastName,
    email: data.email,
    phoneNumber: data.phoneNumber,
    address: data.address,
    energyPreference: data.energyPreference as EnergyPreference,
    paymentMethod: data.paymentMethod as PaymentMethod,
  };
  
  const updatedProfile = await updateProfileData(profileUpdate);
  
  return {
    id: updatedProfile.id,
    accountNumber: updatedProfile.accountNumber,
    meterNumber: updatedProfile.meter?.meter_no || "",
    phoneNumber: updatedProfile.phoneNumber,
    email: updatedProfile.email,
    firstName: updatedProfile.firstName,
    lastName: updatedProfile.lastName,
    address: updatedProfile.address,
    energyPreference: updatedProfile.energyPreference,
    paymentMethod: updatedProfile.paymentMethod,
    meter: updatedProfile.meter,
    loans: updatedProfile.loans,
    profileCompletion: {
      hasCompleteProfile: updatedProfile.profileCompletion.hasCompleteProfile,
      hasMeter: updatedProfile.profileCompletion.hasMeter,
      isLoanEligible: updatedProfile.profileCompletion.isLoanEligible
    }
  };
};
