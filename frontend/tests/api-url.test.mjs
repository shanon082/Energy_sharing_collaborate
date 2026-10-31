import test from "node:test";
import assert from "node:assert/strict";
import { buildApiUrl, normalizeApiBase } from "../src/lib/api-url.ts";

test("API bases always end in one /api/v1 prefix", () => {
  for (const value of [
    "https://example.test",
    "https://example.test/api/v1/",
    "https://example.test/api/v1/api/v1",
  ]) {
    assert.equal(normalizeApiBase(value, true), "https://example.test/api/v1");
  }
});

test("API paths cannot duplicate the base prefix", () => {
  const base = normalizeApiBase("https://example.test/api/v1/");
  assert.equal(buildApiUrl(base, "/api/v1/auth/login/"), "https://example.test/api/v1/auth/login/");
  assert.equal(buildApiUrl(base, "auth/login/"), "https://example.test/api/v1/auth/login/");
});

test("production API bases require HTTPS and reject embedded credentials", () => {
  assert.throws(() => normalizeApiBase("http://example.test/api/v1", true), /secure HTTP/);
  assert.throws(() => normalizeApiBase("https://user:pass@example.test/api/v1", true), /secure HTTP/);
  assert.throws(() => normalizeApiBase("https://192.168.1.10/api/v1", true), /secure HTTP/);
});
