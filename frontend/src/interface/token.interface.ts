import { Profile } from "./user-profile.interface";
import { Wallet } from "./user.interface";

export type Token = {
  id: number;
  token: string;
  units: string;
  is_used: boolean;
  source: "LOAN" | "PURCHASE" | "SHARE";
  loan_id?: string;
  created_at: string;
  source_display: string;
};
