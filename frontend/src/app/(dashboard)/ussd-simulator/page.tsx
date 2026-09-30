"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import DesktopSidebar from "../dashboard/_components/desktop-sidebar";
import RightHeader from "../dashboard/_components/right-header";

type HistoryItem = {
  requestText: string;
  responseText: string;
  kind: "CON" | "END" | "OTHER";
};

type PortalAccount = {
  phone_number: string;
  email: string;
};

type MeterOption = {
  meter_no: string;
  email: string;
};

function createSessionId() {
  return `WEB-${Math.random().toString(36).slice(2, 10).toUpperCase()}`;
}

function getKind(message: string): "CON" | "END" | "OTHER" {
  const text = message.trim();
  if (text.startsWith("CON ")) return "CON";
  if (text.startsWith("END ")) return "END";
  return "OTHER";
}

function formatUssdDisplay(message: string): string {
  const text = message.trim();
  if (text.startsWith("END ")) return text.slice(4);
  if (text.startsWith("CON ")) return text.slice(4);
  return text;
}

export default function UssdSimulatorPage() {
  const [sessionId, setSessionId] = useState(createSessionId());
  const [serviceCode, setServiceCode] = useState("*123#");
  const [account, setAccount] = useState<PortalAccount | null>(null);
  const [meterOptions, setMeterOptions] = useState<MeterOption[]>([]);
  const [pathParts, setPathParts] = useState<string[]>([]);
  const [nextReply, setNextReply] = useState("1");
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");
  const [loadingAccount, setLoadingAccount] = useState(true);
  const [authError, setAuthError] = useState<string>("");

  const phoneNumber = account?.phone_number ?? "";

  const currentText = useMemo(() => pathParts.join("*"), [pathParts]);
  const lastItem = history[history.length - 1];
  const canContinue = !lastItem || lastItem.kind === "CON" || lastItem.kind === "OTHER";
  const currentPrompt = lastItem ? formatUssdDisplay(lastItem.responseText) : "Dial to start";
  const sessionTimeoutMessage = useMemo(() => {
    const text = (lastItem?.responseText || "").toLowerCase();
    return text.includes("session expired")
      ? formatUssdDisplay(lastItem?.responseText || "")
      : "";
  }, [lastItem]);
  const expectsMeterNumberInput = useMemo(() => {
    const prompt = currentPrompt.toLowerCase();
    return prompt.includes("receiver meter number") || prompt.includes("enter meter number");
  }, [currentPrompt]);

  useEffect(() => {
    async function loadAccount() {
      try {
        const res = await fetch("/api/ussd/phones", { cache: "no-store", credentials: "include" });
        if (res.status === 401) {
          setAuthError("Sign in to use the USSD simulator.");
          return;
        }
        const data = await res.json();
        if (res.status === 403 && data?.code === "FEATURE_DISABLED") {
          setAuthError(data.message);
          return;
        }
        const options: PortalAccount[] = data?.results ?? [];
        if (options.length === 0) {
          setAuthError("No phone number on your account. Add one in My Account first.");
          return;
        }
        setAccount(options[0]);
      } catch {
        setAuthError("Could not load your account for USSD simulation.");
      } finally {
        setLoadingAccount(false);
      }
    }
    void loadAccount();
  }, []);

  useEffect(() => {
    async function loadMeters() {
      if (!account?.phone_number) {
        setMeterOptions([]);
        return;
      }

      try {
        const res = await fetch("/api/ussd/meters", { cache: "no-store", credentials: "include" });
        const data = await res.json();
        setMeterOptions(data?.results ?? []);
      } catch {
        setMeterOptions([]);
      }
    }

    void loadMeters();
  }, [account?.phone_number]);

  useEffect(() => {
    if (!expectsMeterNumberInput) return;
    if (meterOptions.length === 0) return;

    const exists = meterOptions.some((m) => m.meter_no === nextReply);
    if (!exists) {
      setNextReply(meterOptions[0].meter_no);
    }
  }, [expectsMeterNumberInput, meterOptions, nextReply]);

  async function send(textValue: string) {
    if (!phoneNumber) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/ussd/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          sessionId,
          serviceCode,
          phoneNumber,
          text: textValue,
        }),
      });
      const data = await res.json();
      if (res.status === 401) {
        setAuthError("Your session expired. Sign in again to continue.");
        return;
      }
      if (res.status === 403 && data?.code === "FEATURE_DISABLED") {
        setError(data.message);
        return;
      }
      const responseText: string = data?.response || data?.error || "No response";
      const kind = getKind(responseText);
      if (kind === "END" && responseText.toLowerCase().includes("session expired")) {
        setPathParts([]);
      }
      setHistory((prev) => [
        ...prev,
        {
          requestText: textValue,
          responseText,
          kind,
        },
      ]);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  function startNewSession() {
    setSessionId(createSessionId());
    setPathParts([]);
    setNextReply("1");
    setHistory([]);
    setError("");
  }

  function clearPath() {
    setPathParts([]);
    setNextReply("1");
  }

  async function openMenu() {
    setPathParts([]);
    await send("");
  }

  async function submitReply() {
    if (!nextReply.trim()) return;
    const next = [...pathParts, nextReply.trim()];
    setPathParts(next);
    setNextReply("1");
    await send(next.join("*"));
  }

  async function submitNavKey(key: string) {
    const next = [...pathParts, key];
    setPathParts(next);
    setNextReply("1");
    await send(next.join("*"));
  }

  const simulatorDisabled = loadingAccount || !!authError || !phoneNumber;

  return (
    <div className="grid min-h-screen w-full md:grid-cols-[220px_1fr] lg:grid-cols-[280px_1fr]">
      <DesktopSidebar />
      <div className="flex flex-col">
        <RightHeader />
        <main className="mx-auto w-full max-w-6xl flex-1 p-3 sm:p-6">
          <div className="mb-4">
            <h1 className="text-xl font-bold sm:text-2xl">USSD Simulator</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Simulates USSD for your logged-in web account only. Sessions time out after 90 seconds of inactivity.
            </p>
          </div>

          {authError ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
              <p>{authError}</p>
              {authError.includes("Sign in") ? (
                <Link href="/auth/login" className="mt-2 inline-block text-sm font-semibold text-blue-600 hover:underline">
                  Go to sign in
                </Link>
              ) : (
                <Link href="/dashboard/myaccount" className="mt-2 inline-block text-sm font-semibold text-blue-600 hover:underline">
                  Update My Account
                </Link>
              )}
            </div>
          ) : null}

          {sessionTimeoutMessage ? (
            <div className="mb-4 rounded-lg border border-orange-300 bg-orange-50 p-4 text-orange-900 dark:border-orange-900 dark:bg-orange-950/40 dark:text-orange-100">
              <p className="font-medium">Session timeout</p>
              <p className="mt-1 text-sm">{sessionTimeoutMessage}</p>
              <button
                type="button"
                className="mt-3 rounded-md bg-orange-600 px-3 py-2 text-sm font-semibold text-white hover:bg-orange-700"
                onClick={startNewSession}
              >
                Start new session
              </button>
            </div>
          ) : null}

          <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
            <div className="rounded-3xl bg-neutral-900 p-4 shadow-2xl">
              <div className="rounded-2xl bg-[#111827] p-3 sm:p-4">
                <p className="mb-3 text-xs text-neutral-400">Africa&apos;s Talking style session</p>

                <div className="mb-3 rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2">
                  <p className="text-xs text-neutral-400">Portal account (fixed)</p>
                  {loadingAccount ? (
                    <p className="text-sm text-neutral-300">Loading your account…</p>
                  ) : account ? (
                    <>
                      <p className="text-sm font-medium text-white">{account.phone_number}</p>
                      <p className="text-xs text-neutral-400">{account.email}</p>
                    </>
                  ) : (
                    <p className="text-sm text-neutral-400">—</p>
                  )}
                </div>

                <label className="mb-3 block">
                  <span className="mb-1 block text-xs text-neutral-300">Dial Code</span>
                  <input
                    className="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-white"
                    value={serviceCode}
                    onChange={(e) => setServiceCode(e.target.value)}
                    disabled={simulatorDisabled}
                  />
                </label>

                <div className="mb-3 rounded-md border border-neutral-700 bg-neutral-950 p-3">
                  <p className="mb-1 text-xs text-neutral-400">USSD Screen</p>
                  <pre className="max-h-64 whitespace-pre-wrap break-words text-sm text-neutral-100">
                    {currentPrompt}
                  </pre>
                </div>

                <label className="block">
                  <span className="mb-1 block text-xs text-neutral-300">Reply</span>
                  {expectsMeterNumberInput ? (
                    <select
                      className="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-white"
                      value={nextReply}
                      onChange={(e) => setNextReply(e.target.value)}
                      disabled={loading || !canContinue || meterOptions.length === 0 || simulatorDisabled}
                    >
                      {meterOptions.length === 0 ? <option value="">No receiver meters available</option> : null}
                      {meterOptions.map((opt) => (
                        <option key={opt.meter_no} value={opt.meter_no}>
                          {opt.meter_no} ({opt.email})
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      className="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-white"
                      placeholder="Enter option (e.g 1)"
                      value={nextReply}
                      onChange={(e) => setNextReply(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") void submitReply();
                      }}
                      disabled={loading || !canContinue || simulatorDisabled}
                    />
                  )}
                </label>

                <div className="mt-3 grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    className="rounded-md border border-neutral-600 px-3 py-2 text-sm text-white disabled:opacity-60"
                    onClick={() => void submitNavKey("#")}
                    disabled={loading || !canContinue || simulatorDisabled}
                  >
                    Back (#)
                  </button>
                  <button
                    type="button"
                    className="rounded-md border border-neutral-600 px-3 py-2 text-sm text-white disabled:opacity-60"
                    onClick={() => void submitNavKey("*")}
                    disabled={loading || !canContinue || simulatorDisabled}
                  >
                    Main Menu (*)
                  </button>
                  <button
                    className="rounded-md bg-amber-500 px-3 py-2 text-sm font-semibold text-black disabled:opacity-60"
                    onClick={openMenu}
                    disabled={loading || simulatorDisabled}
                  >
                    Dial
                  </button>
                  <button
                    className="rounded-md bg-white px-3 py-2 text-sm font-semibold text-black disabled:opacity-60"
                    onClick={submitReply}
                    disabled={loading || !canContinue || simulatorDisabled}
                  >
                    Send
                  </button>
                  <button
                    className="rounded-md border border-neutral-600 px-3 py-2 text-sm text-white"
                    onClick={clearPath}
                    disabled={loading || simulatorDisabled}
                  >
                    Clear
                  </button>
                  <button
                    className="rounded-md border border-neutral-600 px-3 py-2 text-sm text-white"
                    onClick={startNewSession}
                    disabled={loading || simulatorDisabled}
                  >
                    New Session
                  </button>
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <div className="rounded border bg-white p-4 dark:bg-slate-900 dark:border-slate-800">
                <p className="text-sm font-medium">Session Details</p>
                <div className="mt-2 grid gap-3 md:grid-cols-2">
                  <div className="rounded border p-3 dark:border-slate-700">
                    <p className="text-xs text-gray-500">Session ID</p>
                    <input
                      className="mt-1 w-full rounded border px-2 py-1 text-sm font-mono dark:bg-slate-950 dark:border-slate-700"
                      value={sessionId}
                      onChange={(e) => setSessionId(e.target.value)}
                      disabled={simulatorDisabled}
                    />
                  </div>
                  <div className="rounded border p-3 dark:border-slate-700">
                    <p className="text-xs text-gray-500">Current text path</p>
                    <p className="mt-1 font-mono text-sm">{currentText || "(empty)"}</p>
                  </div>
                </div>
              </div>

              {error ? <div className="rounded border border-red-300 bg-red-50 p-3 text-red-700">{error}</div> : null}

              <div className="rounded border bg-white p-4 dark:bg-slate-900 dark:border-slate-800">
                <p className="mb-3 text-sm font-medium">Conversation Log</p>
                <div className="space-y-3">
                  {history.length === 0 ? (
                    <p className="text-sm text-gray-500">No requests yet. Press Dial to start.</p>
                  ) : (
                    history.map((item, idx) => (
                      <div key={`${idx}-${item.requestText}`} className="rounded border p-3 dark:border-slate-700">
                        <p className="text-xs text-gray-500">
                          Request text: <span className="font-mono">{item.requestText || "(empty)"}</span>
                        </p>
                        <pre className="mt-2 whitespace-pre-wrap break-words text-sm">{item.responseText}</pre>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
