"use client";
import { useEffect, useState } from "react";
import type { SandboxClient } from "../lib/sandbox";
import { ALLOCATION_LEDGERS, readLedgerBalance } from "../lib/allocation-ledgers";

/** Read-only projections of existing allocations; no ledger or wallet conversion. */
export function AllocationLedgers({ client, owner, meterId }: { client: SandboxClient; owner: number; meterId: number }) {
  const [open, setOpen] = useState(false);
  return <details className="info-disclosure panel" onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>Balances by allocation ledger</summary>
    <p className="muted small">Cloud energy stays in its original ledger. These are not physical meter credit or converted money.</p>
    {open && <LedgerRead key={`${owner}:${meterId}`} client={client} meterId={meterId} />}
  </details>;
}
function LedgerRead({ client, meterId }: { client: SandboxClient; meterId: number }) {
  const [version, setVersion] = useState(0);
  const [result, setResult] = useState<{ rows: { environment: string; value: ReturnType<typeof readLedgerBalance> | null }[]; at: string } | null>(null);
  const [busy, setBusy] = useState(true);
  useEffect(() => {
    let active = true;
    void Promise.allSettled(ALLOCATION_LEDGERS.map(async environment => ({ environment,
      value: readLedgerBalance(await client.get(`meter/mobile-meters/${meterId}/?environment=${environment}`), meterId) })))
      .then(results => { if (active) setResult({ at: new Date().toISOString(), rows: results.map((row, index) =>
        row.status === "fulfilled" ? row.value : { environment: ALLOCATION_LEDGERS[index], value: null }) }); })
      .finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [client, meterId, version]);
  return <>
    {busy && <p role="status">Loading ledger balances…</p>}
    {result && <><p className="muted small">Stored snapshot · fetched {new Date(result.at).toLocaleString()}. Refresh after reconnecting.</p>
      {result.rows.map(row => <section key={row.environment}><strong>{row.environment === "SANDBOX" ? "EUR TEST allocations" : row.environment === "UGX_DEMO" ? "UGX DEMO allocations" : "CORE allocations"}</strong>
        {row.value ? <p>Available {row.value.available} kWh · reserved/unresolved {row.value.pending} kWh · confirmed applied {row.value.confirmed} kWh</p> : <p role="status">Unavailable. No zero balance has been assumed.</p>}
      </section>)}</>}
    <button type="button" className="secondary" disabled={busy} onClick={() => { setBusy(true); setVersion(value => value + 1); }}>Refresh ledger balances</button>
  </>;
}
