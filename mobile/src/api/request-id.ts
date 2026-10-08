// A UUID is a retry handle, not a credential. Store only this handle so an
// interrupted initiation can be retried manually after a WebView restart.
type Purpose = "purchase" | "repayment" | "delivery";

function key(owner: number | null, purpose: Purpose, target: string): string | null {
  return Number.isInteger(owner) && owner !== null && target
    ? `gpawa:request:${owner}:${purpose}:${encodeURIComponent(target)}` : null;
}

export function savedRequestId(owner: number | null, purpose: Purpose, target: string): string | null {
  const storageKey = key(owner, purpose, target);
  if (!storageKey) return null;
  try {
    const value = localStorage.getItem(storageKey);
    return value && /^[0-9a-f-]{36}$/i.test(value) ? value : null;
  } catch { return null; }
}

export function saveRequestId(owner: number | null, purpose: Purpose, target: string, id: string): void {
  const storageKey = key(owner, purpose, target);
  if (!storageKey) return;
  try { localStorage.setItem(storageKey, id); } catch { /* Storage may be unavailable. */ }
}

export function clearRequestId(owner: number | null, purpose: Purpose, target: string): void {
  const storageKey = key(owner, purpose, target);
  if (!storageKey) return;
  try { localStorage.removeItem(storageKey); } catch { /* Storage may be unavailable. */ }
}

export function clearOwnerRequestIds(owner: number | null): void {
  if (!Number.isInteger(owner) || owner === null) return;
  const prefix = `gpawa:request:${owner}:`;
  try {
    for (let index = localStorage.length - 1; index >= 0; index--) {
      const storageKey = localStorage.key(index);
      if (storageKey?.startsWith(prefix)) localStorage.removeItem(storageKey);
    }
  } catch { /* Storage may be unavailable. */ }
}
