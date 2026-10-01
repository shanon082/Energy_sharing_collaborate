export function apiBaseUrl(raw: string, mode: string): string {
  const value = raw.trim().replace(/\/+$/, "");
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new Error("Set VITE_API_BASE_URL to the Django /api/v1 URL.");
  }
  if (!/^https?:$/.test(url.protocol) || url.username || url.password || url.search || url.hash) {
    throw new Error("API URL must be a plain HTTP(S) origin and path without credentials.");
  }
  if (url.protocol !== "https:" && !["development", "android-debug", "test"].includes(mode)) {
    throw new Error("Release builds require an HTTPS API URL.");
  }
  if (url.protocol === "http:" && mode === "android-debug" &&
      !/^(localhost|127\.0\.0\.1|10\.0\.2\.2|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})$/.test(url.hostname)) {
    throw new Error("Debug HTTP is limited to emulator loopback and private LAN hosts.");
  }
  return value;
}
