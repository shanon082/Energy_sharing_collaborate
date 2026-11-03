"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { get } from "@/lib/fetch-client";
import { sandboxCapabilities } from "@/lib/sandbox";
import { loanSummary } from "@/lib/dashboard-loan-summary";
import LoanOverview from "./loan-overview";

type View = { kind: "loading" | "unavailable" | "core" } |
  { kind: "summary"; data: ReturnType<typeof loanSummary> };

export default function DashboardLoans() {
  const [view, setView] = useState<View>({kind: "loading"});
  const [attempt, retry] = useState(0);
  useEffect(() => {
    let mounted = true, version = 0;
    async function refresh() {
      const current = ++version;
      function publish(next: View) { if (mounted && current === version) setView(next); }
      try {
        const flags = await get<{sandbox?: {enabled?: boolean}}>("features/");
        if (flags.error || !flags.data?.sandbox) throw Error();
        if (flags.data.sandbox.enabled === false) { publish({kind:"core"}); return; }
        const sandbox = sandboxCapabilities(flags.data.sandbox);
        if (!sandbox.enabled) throw Error();
        const records = await get<unknown>("sandbox/loans/");
        if (records.error) throw Error();
        publish({kind:"summary",data:loanSummary(records.data, sandbox.provider === "LOCAL_DEMO" ? "UGX_DEMO" : "MTN_SANDBOX")});
      } catch { publish({kind:"unavailable"}); }
    }
    void refresh();
    window.addEventListener("focus", refresh);
    return () => {mounted = false; window.removeEventListener("focus",refresh);};
  },[attempt]);
  if (view.kind === "core") return <LoanOverview />;
  if (view.kind === "loading") return <p role="status">Loading loan balances…</p>;
  if (view.kind !== "summary") return <p role="alert">Loan balances are unavailable.{" "}
    <button className="underline" onClick={() => {setView({kind:"loading"}); retry(n => n+1);}}>Retry</button></p>;
  const s = view.data;
  const money = (n: number) => new Intl.NumberFormat("en-UG", {style:"currency",currency:s.currency,
    minimumFractionDigits:s.currency === "UGX" ? 0 : 2, maximumFractionDigits:s.currency === "UGX" ? 0 : 2}).format(n);
  return <section aria-label="Loan summary" className="space-y-3">
    <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="text-lg font-semibold">Your loans</h2>
      <Link href="/dashboard/loans" className="text-sm underline">View loans and repayments</Link></div>
    <p className="text-sm text-muted-foreground">{s.currency === "UGX" ? "UGX demo" : "EUR test"} · All your meters
      {s.limited && " · Based on the latest 100 account loan records only"}</p>
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {[[ "Active loans", s.active ],["Principal borrowed", money(s.borrowed)],["Repayments applied",money(s.repaid)],
        ["Outstanding balance",money(s.outstanding)]].map(([label,value]) =>
        <Card key={label}><CardHeader><CardDescription>{label}</CardDescription>
          <CardTitle className="text-2xl">{value}</CardTitle></CardHeader></Card>)}
    </div>
  </section>;
}
