export function normalizeApiBase(value: string, production = false): string {
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new Error("API_URL must be an absolute HTTP(S) URL.");
  }

  const host = url.hostname.replace(/^\[|\]$/g, "").toLowerCase();
  const privateIpv4 =
    /^(?:0|10|127|169\.254|192\.168)\./.test(host) ||
    /^172\.(?:1[6-9]|2\d|3[01])\./.test(host);
  const privateIpv6 = host === "::1" || /^(?:fc|fd|fe[89ab])/i.test(host);

  if (
    !["http:", "https:"].includes(url.protocol) ||
    (production && url.protocol !== "https:") ||
    (production &&
      (host === "localhost" ||
        host.endsWith(".localhost") ||
        host.endsWith(".local") ||
        privateIpv4 ||
        privateIpv6)) ||
    url.username ||
    url.password ||
    url.search ||
    url.hash
  ) {
    throw new Error("API_URL must be a secure HTTP(S) base URL without credentials or query parameters.");
  }

  const prefix = url.pathname.replace(/\/+$/, "").replace(/(?:\/api\/v1)+$/i, "");
  url.pathname = `${prefix}/api/v1`;
  return url.toString().replace(/\/$/, "");
}

export function buildApiUrl(base: string, path: string): string {
  return `${base.replace(/\/+$/, "")}/${normalizeApiPath(path)}`;
}

export function normalizeApiPath(path: string): string {
  return path.trim().replace(/^\/+/, "").replace(/^(?:api\/v1\/?)+/i, "");
}
