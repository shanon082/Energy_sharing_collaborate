const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export function isSameOriginProxyRequest(
  method: string,
  origin: string | null,
  requestOrigin: string,
): boolean {
  if (SAFE_METHODS.has(method.toUpperCase())) return true;
  if (!origin) return false;

  try {
    return new URL(origin).origin === requestOrigin;
  } catch {
    return false;
  }
}
