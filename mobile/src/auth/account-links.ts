export type AccountLink = { kind: "verify" | "reset"; uid: string; token: string };

// The URL is only a carrier. Django validates the uid and one-use/expiring token.
export function parseAccountLink(raw: string): AccountLink {
  let url: URL;
  try { url = new URL(raw.trim()); }
  catch { throw new Error("Paste the complete link from your account email."); }
  if (url.protocol !== "https:" && url.protocol !== "http:") {
    throw new Error("The account link must be a web link.");
  }
  const path = url.pathname.replace(/\/$/, "");
  const kind = path === "/auth/verify-email" ? "verify" :
    path === "/auth/reset-password" ? "reset" : null;
  const uid = url.searchParams.get("uid");
  const token = url.searchParams.get("token");
  if (!kind || !uid || !token || uid.length > 256 || token.length > 256) {
    throw new Error("This is not a complete verification or reset link.");
  }
  return { kind, uid, token };
}

export function accountTokenQuery(link: AccountLink): string {
  return `uid=${encodeURIComponent(link.uid)}&token=${encodeURIComponent(link.token)}`;
}
