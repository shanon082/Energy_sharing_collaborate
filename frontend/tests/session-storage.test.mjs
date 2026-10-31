import test from "node:test";
import assert from "node:assert/strict";

class MemoryStorage {
  values = new Map();
  get length() { return this.values.size; }
  key(index) { return [...this.values.keys()][index] ?? null; }
  getItem(key) { return this.values.get(key) ?? null; }
  setItem(key, value) { this.values.set(key, String(value)); }
  removeItem(key) { this.values.delete(key); }
}

test("logout cleanup removes account-bound browser data but preserves preferences", async () => {
  const localStorage = new MemoryStorage();
  for (const key of [
    "gpawa:user_email",
    "gpawa_selected_meter_no",
    "authToken",
    "gpawa:request:42:sandbox:UGX_DEMO:LOAN",
    "theme",
  ]) {
    localStorage.setItem(key, "stored");
  }
  globalThis.window = { localStorage };
  const { clearPrivateBrowserState } = await import("../src/lib/session-storage.ts");

  clearPrivateBrowserState();

  assert.deepEqual([...localStorage.values.keys()], ["theme"]);
  delete globalThis.window;
});
