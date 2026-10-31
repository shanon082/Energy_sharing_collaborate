import test from "node:test";
import assert from "node:assert/strict";
import { isSameOriginProxyRequest } from "../src/lib/proxy-security.ts";

test("proxy allows safe methods but requires the exact origin for state changes", () => {
  const siteOrigin = "https://energy-sharing-collaborate.vercel.app";

  assert.equal(isSameOriginProxyRequest("GET", null, siteOrigin), true);
  assert.equal(isSameOriginProxyRequest("POST", siteOrigin, siteOrigin), true);
  assert.equal(isSameOriginProxyRequest("PATCH", siteOrigin, siteOrigin), true);
  assert.equal(isSameOriginProxyRequest("DELETE", "https://attacker.example", siteOrigin), false);
  assert.equal(isSameOriginProxyRequest("POST", null, siteOrigin), false);
  assert.equal(isSameOriginProxyRequest("POST", "not a URL", siteOrigin), false);
});
