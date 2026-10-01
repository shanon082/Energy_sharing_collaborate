import { apiBaseUrl } from "./url-policy.ts";

export const API_BASE_URL = apiBaseUrl(
  import.meta.env.VITE_API_BASE_URL ||
    (import.meta.env.MODE === "android-debug" ? "http://10.0.2.2:8000/api/v1" : ""),
  import.meta.env.MODE,
);
