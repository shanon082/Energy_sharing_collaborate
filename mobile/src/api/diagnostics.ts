export type ConnectionProbe = {
  origin: string;
  api: string;
  simpleGet: string;
  jsonGet: string;
  loginPreflight: string;
  accountGet: string;
  opaqueGet: string;
};

async function check(url: string, options: RequestInit, send: typeof fetch): Promise<string> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await send(url, { ...options, cache: "no-store", signal: controller.signal });
    return response.type === "opaque" ? "Reached host; response hidden by no-cors" : `HTTP ${response.status}`;
  } catch (error) {
    return error instanceof DOMException && error.name === "AbortError" ? "Timed out" : "Fetch blocked or failed";
  } finally {
    clearTimeout(timeout);
  }
}

/** Debug-only checks. No account identifiers, passwords, real tokens, or response bodies are sent or shown. */
export async function probeConnection(api: string, origin: string, send: typeof fetch = fetch): Promise<ConnectionProbe> {
  const features = `${api}/features/`;
  return {
    origin,
    api,
    simpleGet: await check(features, { method: "GET" }, send),
    jsonGet: await check(features, { method: "GET", headers: { "Content-Type": "application/json" } }, send),
    // Empty JSON exercises the browser's login preflight; Django should return HTTP 400.
    loginPreflight: await check(`${api}/auth/login/`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
    }, send),
    // A fixed invalid token tests the Authorization preflight without using a real session.
    accountGet: await check(`${api}/auth/mobile-account/`, {
      method: "GET", headers: {
        "Content-Type": "application/json", Authorization: "Bearer diagnostic-invalid-token",
      },
    }, send),
    opaqueGet: await check(features, { method: "GET", mode: "no-cors" }, send),
  };
}
