import { Capacitor } from "@capacitor/core";
import { SecureStoragePlugin } from "capacitor-secure-storage-plugin";

export type StoredSession = { refresh: string; userId: number };
export interface SessionStore {
  load(): Promise<StoredSession | null>;
  save(session: StoredSession): Promise<void>;
  clear(): Promise<void>;
}

const KEY = "gpawa.mobile.refresh.v1";

/** Browser preview is memory-only. Native storage fails closed if Keystore is unavailable. */
export class AndroidSecureStore implements SessionStore {
  private memory: StoredSession | null = null;

  private get nativeAndroid(): boolean {
    return Capacitor.isNativePlatform() && Capacitor.getPlatform() === "android";
  }

  async load(): Promise<StoredSession | null> {
    if (!this.nativeAndroid) return this.memory;
    try {
      const result = await SecureStoragePlugin.get({ key: KEY });
      const value: unknown = JSON.parse(result.value);
      if (typeof value !== "object" || value === null ||
          !("refresh" in value) || typeof value.refresh !== "string" ||
          !("userId" in value) || typeof value.userId !== "number") {
        await this.clear();
        return null;
      }
      return value as StoredSession;
    } catch {
      // A missing or unreadable key never falls back to ordinary Web storage.
      return null;
    }
  }

  async save(session: StoredSession): Promise<void> {
    if (!this.nativeAndroid) {
      this.memory = session;
      return;
    }
    await SecureStoragePlugin.set({ key: KEY, value: JSON.stringify(session) });
  }

  async clear(): Promise<void> {
    this.memory = null;
    if (this.nativeAndroid) {
      try { await SecureStoragePlugin.remove({ key: KEY }); } catch { /* missing key */ }
    }
  }
}
