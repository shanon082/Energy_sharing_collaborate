import "server-only";
import { buildApiUrl, normalizeApiBase } from "@/lib/api-url";

const defaultApiUrl =
  process.env.NODE_ENV === "production"
    ? "https://shanonsimon.alwaysdata.net/api/v1"
    : "http://localhost:8000/api/v1";

/** Server-only Django API origin; browser requests use the same-origin proxy. */
export const API_URL = normalizeApiBase(
  process.env.API_URL || defaultApiUrl,
  process.env.NODE_ENV === "production",
);

export const apiEndpoint = (path: string) => buildApiUrl(API_URL, path);