"use client";
import { useEffect, useState } from "react";
import { get, post, patch } from "../../lib/fetch-client";
import { getApiErrorMessage } from "../../lib/api-response";
import type { SandboxClient } from "../../lib/sandbox";
import { withRequestDeadline } from "../../lib/request-deadline";

async function unwrap<T>(response: Awaited<ReturnType<typeof get<T>>>): Promise<T> {
  if (response.error) throw new Error(getApiErrorMessage(response.error, "The request could not be completed."));
  if (response.data === undefined) throw new Error("The API returned no readable data.");
  return response.data;
}
export const consumerClient: SandboxClient = {
  get: async <T,>(path: string) => unwrap<T>(await get<T>(path)),
  post: async <T,>(path: string, body: unknown) => unwrap<T>(await post<T>(path, body)),
};
export async function patchAccount<T>(body: unknown): Promise<T> { return unwrap<T>(await patch<T>("auth/mobile-account-details/", body)); }

/** Scope changes mask old data immediately, even before effect cleanup runs. */
export function useConsumerRead<T>(path: string | null, parse: (raw: unknown) => T, revision: number, owner: number, retainOnRefresh = false) {
  const key = JSON.stringify([owner, path, revision]);
  const scope = JSON.stringify([owner, path]);
  const [result, setResult] = useState<{ key: string; scope: string; value: T | null; error: string | null } | null>(null);
  useEffect(() => {
    if (path === null) return;
    let current = true;
    void withRequestDeadline(() => consumerClient.get<unknown>(path)).then(raw => {
      const value = parse(raw);
      if (current) setResult({ key, scope, value, error: null });
    }).catch(cause => { if (current) setResult(previous => ({ key, scope,
      value: retainOnRefresh && previous?.scope === scope ? previous.value : null,
      error: cause instanceof Error ? cause.message : "Data unavailable." })); });
    return () => { current = false; };
  }, [path, parse, key, scope, retainOnRefresh]);
  // Only capability metadata opts in; financial reads mask stale scopes by default.
  return result?.key === key ? { ...result, loading: false } : {
    value: retainOnRefresh && result?.scope === scope ? result.value : null, error: null, loading: path !== null };
}
