import type { SessionStore } from "./secure-store.ts";

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;
  constructor(message: string, status: number, code?: string) {
    super(message); this.status = status; this.code = code;
  }
}
export class SessionExpired extends ApiError {
  constructor() { super("Session expired. Please sign in again.", 401, "SESSION_EXPIRED"); }
}
export class TransportError extends Error {
  constructor() { super("The app could not read an API response. Check the connection or cross-origin policy."); }
}
export class ResponseFormatError extends Error {
  constructor() { super("The API returned an unreadable response. Please try again."); }
}

export type ConsumerIdentity = {
  id: number; email: string; first_name: string; last_name: string;
  user_role: string; must_change_password?: boolean; email_verified?: boolean;
};

type LoginResult = { access?: string; refresh?: string; requires_2fa?: boolean; user?: ConsumerIdentity };
type RefreshResult = { access?: string; refresh?: string };
type FetchLike = typeof fetch;

function errorMessage(body: unknown, fallback: string): string {
  if (!body || typeof body !== "object") return fallback;
  const data = body as Record<string, unknown>;
  for (const value of Object.values(data)) {
    if (Array.isArray(value) && typeof value[0] === "string") return value[0];
  }
  for (const key of ["message", "detail", "error", "code"]) {
    if (typeof data[key] === "string") return data[key] as string;
  }
  return fallback;
}

export class SessionManager {
  private readonly baseUrl: string;
  private readonly store: SessionStore;
  private readonly send: FetchLike;
  private access: string | null = null;
  private userId: number | null = null;
  private refreshFlight: Promise<boolean> | null = null;
  private epoch = 0;
  private loggingOut = false;

  constructor(baseUrl: string, store: SessionStore, send: FetchLike = fetch) {
    this.baseUrl = baseUrl; this.store = store; this.send = send;
  }

  get identity(): number | null { return this.userId; }
  get authenticated(): boolean { return this.access !== null; }

  private async call(path: string, options: RequestInit = {}, token?: string): Promise<{ status: number; body: unknown }> {
    let response: Response;
    try {
      // Browser fetch can reject an invocation whose receiver is SessionManager.
      response = await this.send.call(globalThis, `${this.baseUrl}/${path.replace(/^\/+/, "")}`, {
        ...options,
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...options.headers,
        },
      });
    } catch { throw new TransportError(); }
    let body: unknown = null;
    if (response.status !== 204) {
      try { body = await response.json(); }
      catch {
        if (response.ok) throw new ResponseFormatError();
        // Keep the HTTP status authoritative even if its error body is not JSON.
      }
    }
    return { status: response.status, body };
  }

  private async clear(): Promise<void> {
    this.epoch += 1;
    this.access = null;
    this.userId = null;
    await this.store.clear();
  }

  async login(email: string, password: string): Promise<ConsumerIdentity> {
    if (this.loggingOut) throw new ApiError("Logout is still finishing. Please try again.", 409, "LOGOUT_IN_PROGRESS");
    const { status, body } = await this.call("auth/login/", {
      method: "POST", body: JSON.stringify({ email, password, remember_me: false }),
    });
    if (status >= 400) throw new ApiError(errorMessage(body, "Sign in failed."), status,
      status === 400 && errorMessage(body, "").toLowerCase().includes("verify") ? "UNVERIFIED" : undefined);
    const result = body as LoginResult | null;
    if (result?.requires_2fa) throw new ApiError("Staff two-factor sign in is available on the web app.", 403, "STAFF_2FA_REQUIRED");
    if (!result?.access || !result.refresh || !result.user || !Number.isInteger(result.user.id)) {
      throw new ApiError("Sign in returned an incomplete session.", 502);
    }
    if (result.user.user_role !== "CLIENT") throw new ApiError("Use the web app for staff accounts.", 403, "CONSUMER_ONLY");
    if (result.user.email_verified === false) throw new ApiError("Verify your email before signing in.", 403, "UNVERIFIED");
    if (this.refreshFlight) await this.refreshFlight.catch(() => false);
    await this.clear();
    try { await this.store.save({ refresh: result.refresh, userId: result.user.id }); }
    catch { throw new ApiError("Android secure storage is unavailable; sign in was not retained.", 503, "SECURE_STORAGE_UNAVAILABLE"); }
    this.userId = result.user.id;
    this.access = result.access;
    return result.user;
  }

  private async performRefresh(): Promise<boolean> {
    const session = await this.store.load();
    if (!session) { await this.clear(); return false; }
    const epoch = this.epoch;
    let response: { status: number; body: unknown };
    try {
      response = await this.call("auth/refresh/token/", {
        method: "POST", body: JSON.stringify({ refresh: session.refresh }),
      });
    } catch (error) {
      if (error instanceof TransportError || error instanceof ResponseFormatError) throw error;
      await this.clear(); return false;
    }
    if (response.status !== 200) { await this.clear(); return false; }
    const result = response.body as RefreshResult | null;
    if (epoch !== this.epoch) return false;
    if (!result?.access || !result.refresh) {
      await this.clear(); return false;
    }
    try { await this.store.save({ refresh: result.refresh, userId: session.userId }); }
    catch { await this.clear(); return false; }
    this.access = result.access;
    this.userId = session.userId;
    return true;
  }

  private refreshOnce(): Promise<boolean> {
    if (!this.refreshFlight) {
      this.refreshFlight = this.performRefresh().finally(() => { this.refreshFlight = null; });
    }
    return this.refreshFlight;
  }

  async restore(): Promise<boolean> {
    const session = await this.store.load();
    if (!session) return false;
    this.userId = session.userId;
    return this.refreshOnce();
  }

  async getAccount(): Promise<ConsumerIdentity> {
    const account = await this.get<ConsumerIdentity>("auth/mobile-account/");
    if (account.id !== this.userId || account.user_role !== "CLIENT") {
      await this.clear();
      throw new SessionExpired();
    }
    return account;
  }

  async get<T>(path: string): Promise<T> { return this.request<T>(path); }

  async post<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>(path, "POST", body);
  }

  async patch<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>(path, "PATCH", body);
  }

  async publicGet<T>(path: string): Promise<T> {
    return this.publicRequest<T>(path, "GET");
  }

  async publicPost<T>(path: string, body: unknown): Promise<T> {
    return this.publicRequest<T>(path, "POST", body);
  }

  async publicPatch<T>(path: string, body: unknown): Promise<T> {
    return this.publicRequest<T>(path, "PATCH", body);
  }

  private async publicRequest<T>(path: string, method: string, body?: unknown): Promise<T> {
    const response = await this.call(path, { method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
    if (response.status >= 400) throw new ApiError(errorMessage(response.body, "Request failed."), response.status);
    return response.body as T;
  }

  private async request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
    if (this.loggingOut) throw new SessionExpired();
    if (!this.access) {
      if (!await this.refreshOnce()) throw new SessionExpired();
    }
    const epoch = this.epoch;
    const usedAccess = this.access;
    const options: RequestInit = { method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) };
    let response = await this.call(path, options, usedAccess ?? undefined);
    if (response.status === 401) {
      // Never replay a financial or other mutation after an uncertain response.
      if (method !== "GET") { await this.clear(); throw new SessionExpired(); }
      if (usedAccess === this.access && !await this.refreshOnce()) throw new SessionExpired();
      if (epoch !== this.epoch || !this.access) throw new SessionExpired();
      response = await this.call(path, options, this.access);
    }
    if (epoch !== this.epoch) throw new SessionExpired();
    if (response.status >= 400) throw new ApiError(errorMessage(response.body, "Request failed."), response.status);
    return response.body as T;
  }

  async logout(): Promise<void> {
    this.loggingOut = true;
    try {
      if (this.refreshFlight) await this.refreshFlight.catch(() => false);
      const session = await this.store.load();
      const access = this.access;
      await this.clear();
      if (session && access) {
        try {
          const revoked = await this.call("auth/mobile-logout/", {
            method: "POST", body: JSON.stringify({ refresh: session.refresh }),
          }, access);
          if (revoked.status === 401) {
            // One bounded refresh allows revocation when only the access token expired.
            const rotated = await this.call("auth/refresh/token/", {
              method: "POST", body: JSON.stringify({ refresh: session.refresh }),
            });
            const pair = rotated.body as RefreshResult | null;
            if (rotated.status === 200 && pair?.access && pair.refresh) {
              await this.call("auth/mobile-logout/", {
                method: "POST", body: JSON.stringify({ refresh: pair.refresh }),
              }, pair.access);
            }
          }
        } catch { /* Local logout is immediate; offline revocation needs a connection. */ }
      }
    } finally { this.loggingOut = false; }
  }
}
