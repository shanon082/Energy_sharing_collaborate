"use client";

const PRIVATE_STORAGE_KEYS = new Set([
  "gpawa:user_email",
  "gpawa_selected_meter_no",
  "authToken",
]);
const PRIVATE_STORAGE_PREFIXES = ["gpawa:request:"];

export function clearPrivateBrowserState(): void {
  if (typeof window === "undefined") return;

  try {
    const storage = window.localStorage;
    for (let index = storage.length - 1; index >= 0; index -= 1) {
      const key = storage.key(index);
      if (
        key &&
        (PRIVATE_STORAGE_KEYS.has(key) ||
          PRIVATE_STORAGE_PREFIXES.some((prefix) => key.startsWith(prefix)))
      ) {
        storage.removeItem(key);
      }
    }
  } catch (error) {
    console.error("Could not clear private browser state.", error);
  }
}
