/** Django API base URL — server-side (login, proxy) and client fetches. */
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_URL ||
  "http://localhost:8000/api/v1";