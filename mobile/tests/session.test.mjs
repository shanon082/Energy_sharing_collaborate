import test from "node:test";
import assert from "node:assert/strict";
import { SessionManager, SessionExpired, ApiError, TransportError, ResponseFormatError } from "../src/auth/session.ts";
import { parseFeatureAvailability, DISABLED_FEATURES } from "../../frontend/src/lib/features.ts";
import { apiBaseUrl } from "../src/api/url-policy.ts";
import { parseAllocation, parseMeters } from "../src/api/contracts.ts";
import { probeConnection } from "../src/api/diagnostics.ts";

const base = "https://api.example.invalid/api/v1";
const user = { id: 1, email: "owner@example.invalid", first_name: "A", last_name: "B",
  user_role: "CLIENT", email_verified: true, must_change_password: false };

function store() {
  let value = null;
  return { load: async () => value, save: async (next) => { value = next; },
    clear: async () => { value = null; } };
}
function json(body, status = 200) { return Response.json(body, { status }); }
function route(fetcher) { return async (url, options) => fetcher(new URL(url).pathname, options); }

test("login retains only refresh and rejects unverified/staff responses", async () => {
  const saved = store();
  const session = new SessionManager(base, saved, route((path) => {
    if (path.endsWith("auth/login/")) return json({ access: "access", refresh: "refresh", user });
    return json({ id: 1, user_role: "CLIENT" });
  }));
  assert.equal((await session.login(user.email, "test-only")).id, 1);
  assert.deepEqual(await saved.load(), { refresh: "refresh", userId: 1 });
  assert.equal(session.authenticated, true);

  const unverified = new SessionManager(base, store(), route(() =>
    json({ email: ["Please verify your email address before logging in."] }, 400)));
  await assert.rejects(unverified.login(user.email, "test-only"), (error) =>
    error instanceof ApiError && error.code === "UNVERIFIED");
  const staff = new SessionManager(base, store(), route(() =>
    json({ requires_2fa: true, challenge_token: "not-retained" })));
  await assert.rejects(staff.login(user.email, "test-only"), (error) =>
    error instanceof ApiError && error.code === "STAFF_2FA_REQUIRED");
});

test("concurrent 401s share one rotated refresh and never retry endlessly", async () => {
  const saved = store();
  let refreshes = 0;
  let oldRequests = 0;
  const session = new SessionManager(base, saved, route((path, options) => {
    if (path.endsWith("auth/login/")) return json({ access: "old", refresh: "refresh-old", user });
    if (path.endsWith("auth/refresh/token/")) {
      refreshes++;
      return json({ access: "new", refresh: "refresh-new" });
    }
    if (options.headers.Authorization === "Bearer old") { oldRequests++; return json({ detail: "expired" }, 401); }
    return json({ ok: true });
  }));
  await session.login(user.email, "test-only");
  const values = await Promise.all([session.get("first/"), session.get("second/")]);
  assert.deepEqual(values, [{ ok: true }, { ok: true }]);
  assert.equal(oldRequests, 2);
  assert.equal(refreshes, 1);
  assert.deepEqual(await saved.load(), { refresh: "refresh-new", userId: 1 });

  const expired = new SessionManager(base, store(), route((path) =>
    path.endsWith("auth/login/") ? json({ access: "old", refresh: "refresh", user }) :
      json({ detail: "expired" }, 401)));
  await expired.login(user.email, "test-only");
  await assert.rejects(expired.get("first/"), SessionExpired);
});

test("logout clears locally, revokes remotely, and mismatched account clears session", async () => {
  const saved = store();
  let revocations = 0;
  const session = new SessionManager(base, saved, route((path) => {
    if (path.endsWith("auth/login/")) return json({ access: "access", refresh: "refresh", user });
    if (path.endsWith("auth/mobile-logout/")) { revocations++; return new Response(null, { status: 204 }); }
    return json({ ...user, id: 2 });
  }));
  await session.login(user.email, "test-only");
  await assert.rejects(session.getAccount(), SessionExpired);
  assert.equal(await saved.load(), null);
  await session.login(user.email, "test-only");
  await session.logout();
  assert.equal(revocations, 1);
  assert.equal(await saved.load(), null);
  assert.equal(session.authenticated, false);
});

test("transport errors preserve existing session and do not invent balances", async () => {
  const saved = store();
  let reachable = true;
  const session = new SessionManager(base, saved, route((path) =>
    path.endsWith("auth/login/") ? json({ access: "access", refresh: "refresh", user }) :
      reachable ? json({}) : Promise.reject(new TypeError("fetch failed"))));
  await session.login(user.email, "test-only");
  reachable = false;
  await assert.rejects(session.get("meter/my-meter/"), TransportError);
  assert.deepEqual(await saved.load(), { refresh: "refresh", userId: 1 });
  assert.throws(() => parseAllocation({ unit: "kWh", delivery_environment: "SIMULATOR",
    available_kwh: 0, pending_kwh: "0.00", confirmed_kwh: "0.00" }), /Invalid exact amount/);
  assert.deepEqual(parseMeters({ success: true, data: { has_meter: false } }), []);
});

test("login attempts the LAN URL despite an offline navigator hint", async () => {
  const previousNavigator = Object.getOwnPropertyDescriptor(globalThis, "navigator");
  let requestedUrl;
  Object.defineProperty(globalThis, "navigator", { configurable: true, value: { onLine: false } });
  try {
    const session = new SessionManager("http://192.168.97.107:8000/api/v1", store(),
      async (url) => {
        requestedUrl = url;
        return json({ access: "access", refresh: "refresh", user });
      });
    await session.login(user.email, "test-only");
    assert.equal(requestedUrl, "http://192.168.97.107:8000/api/v1/auth/login/");
  } finally {
    if (previousNavigator) Object.defineProperty(globalThis, "navigator", previousNavigator);
    else delete globalThis.navigator;
  }
});

test("session calls browser fetch with the global receiver", async () => {
  let calls = 0;
  function browserFetch(url) {
    if (this !== globalThis) throw new TypeError("Illegal invocation");
    calls++;
    assert.equal(url, `${base}/auth/login/`);
    return json({ access: "access", refresh: "refresh", user });
  }
  const session = new SessionManager(base, store(), browserFetch);
  assert.equal((await session.login(user.email, "test-only")).id, 1);
  assert.equal(calls, 1);
});

test("HTTP authentication and response format failures are distinct from transport failures", async () => {
  const invalid = new SessionManager(base, store(), async () => json({ detail: "Invalid credentials" }, 401));
  await assert.rejects(invalid.login(user.email, "test-only"), (error) =>
    error instanceof ApiError && error.status === 401 && error.message === "Invalid credentials");
  const serverError = new SessionManager(base, store(), async () =>
    new Response("Gateway error", { status: 502, headers: { "Content-Type": "text/plain" } }));
  await assert.rejects(serverError.login(user.email, "test-only"), (error) =>
    error instanceof ApiError && error.status === 502);
  const unreadable = new SessionManager(base, store(), async () =>
    new Response("not json", { status: 200, headers: { "Content-Type": "text/plain" } }));
  await assert.rejects(unreadable.login(user.email, "test-only"), ResponseFormatError);
  const unreachable = new SessionManager(base, store(), async () => { throw new TypeError("fetch failed"); });
  await assert.rejects(unreachable.login(user.email, "test-only"), TransportError);
});

test("successful login and failed account fetch are distinct stages", async () => {
  const saved = store();
  const paths = [];
  const session = new SessionManager(base, saved, async (url) => {
    paths.push(new URL(url).pathname);
    if (url.endsWith("auth/login/")) return json({ access: "access", refresh: "refresh", user });
    throw new TypeError("WebView fetch failed");
  });
  await session.login(user.email, "test-only");
  await assert.rejects(session.getAccount(), TransportError);
  assert.deepEqual(paths, ["/api/v1/auth/login/", "/api/v1/auth/mobile-account/"]);
  assert.deepEqual(await saved.load(), { refresh: "refresh", userId: 1 });
});

test("debug connection probe sends no credentials and distinguishes CORS from transport", async () => {
  const requests = [];
  const api = "http://192.168.97.107:8000/api/v1";
  const report = await probeConnection(api, "http://localhost", async (url, options) => {
    requests.push({ url, options });
    if (options.mode === "no-cors") return { type: "opaque" };
    if (url.endsWith("auth/mobile-account/")) return json({ detail: "Invalid token" }, 401);
    if (options.method === "GET" && !options.headers) return json({ features: {} });
    throw new TypeError("Failed to fetch");
  });
  assert.equal(report.origin, "http://localhost");
  assert.equal(report.simpleGet, "HTTP 200");
  assert.equal(report.jsonGet, "Fetch blocked or failed");
  assert.equal(report.loginPreflight, "Fetch blocked or failed");
  assert.equal(report.accountGet, "HTTP 401");
  assert.match(report.opaqueGet, /Reached host/);
  assert.deepEqual(requests.map(({ url }) => url), [
    `${api}/features/`, `${api}/features/`, `${api}/auth/login/`,
    `${api}/auth/mobile-account/`, `${api}/features/`,
  ]);
  assert.equal(requests[2].options.body, "{}");
  assert.equal(requests[3].options.headers.Authorization, "Bearer diagnostic-invalid-token");
  assert.ok(requests.every(({ options }) => !options.body || options.body === "{}"));
});

test("feature availability fails closed and release API requires HTTPS", () => {
  assert.deepEqual(parseFeatureAvailability(null), DISABLED_FEATURES);
  assert.equal(parseFeatureAvailability({ peer_sharing: "true" }).peer_sharing, false);
  assert.equal(parseFeatureAvailability({ peer_sharing: true }).peer_sharing, true);
  assert.equal(apiBaseUrl("https://api.example.invalid/api/v1/", "production"), base);
  assert.throws(() => apiBaseUrl("http://api.example.invalid/api/v1", "production"), /HTTPS/);
  assert.equal(apiBaseUrl("http://10.0.2.2:8000/api/v1", "android-debug"), "http://10.0.2.2:8000/api/v1");
  assert.throws(() => apiBaseUrl("http://public.example.invalid/api/v1", "android-debug"), /private LAN/);
});
