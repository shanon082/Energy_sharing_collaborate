import { Profile } from "./user-profile.interface"

export type Country = {
    code: string,
    name: string
}


// export type User = {
//     is_admin: boolean
//     user_role: string
//     id: number,
//     first_name: string,
//     last_name: string,
//     email: string,
//     phone_number: string,
//     profile: Profile,
//     wallet: Wallet,
//     gender: "MALE" | "FEMALE" 
// }

export type Wallet = {
    wallet_id: string,
    balance: string,
    currency: string,
    total_earnings: number
}

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  phone_number: string;
  profile: {
    email_verified: boolean;
  };
  wallet: Wallet,
  gender: "MALE" | "FEMALE"
  account_is_active: boolean;
  user_role: string;
  is_admin: boolean;
  is_staff_member?: boolean;
  is_superuser?: boolean;
  must_change_password?: boolean;
  account_details?: {
    account_number: string;
    address?: string;
    energy_preference?: string;
    payment_method?: string;
  };
  has_complete_profile?: boolean;
  // Add new fields for setup status
  setup_status?: {
    has_meter: boolean;
    has_complete_profile: boolean;
    completed_setup: boolean;
  };
  profile_data?: {
    monthly_expenditure?: string;
    purchase_frequency?: string;
    payment_consistency?: string;
    disconnection_history?: string;
    meter_sharing?: string;
    monthly_income?: string;
    income_stability?: string;
    consumption_level?: string;
  };
}
