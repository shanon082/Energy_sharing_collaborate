import { apiBaseUrl } from "./url-policy.ts";
import { accountCompletionMode } from "../auth/account-links.ts";

export const API_BASE_URL = apiBaseUrl(
  import.meta.env.VITE_API_BASE_URL ||
    (import.meta.env.MODE === "android-debug" ? "http://10.0.2.2:8000/api/v1" : ""),
  import.meta.env.MODE,
);

// UI only: Django still validates tokens, passwords and account state.
export const ACCOUNT_COMPLETION = accountCompletionMode(import.meta.env.VITE_ACCOUNT_COMPLETION);
