"use client";
import { useCallback, useEffect, useState } from "react";
import { parseEnergyTokens, tokenLoadingLabel, type EnergyToken } from "../lib/energy-token";
import type { SandboxClient } from "../lib/sandbox";

/** Secret values stay in component memory/authorized DOM; never storage or URLs. */
export function EnergyTokenCard({ client, owner, allocationId, meterId, compact = false }: {
  client: SandboxClient; owner: number; allocationId?: number | null; meterId?: number; compact?: boolean;
}) {
  if (allocationId === null || (allocationId === undefined && meterId === undefined)) return null;
  return <TokenDetails key={`${owner}:${allocationId ?? ""}:${meterId ?? ""}`} client={client} owner={owner} allocationId={allocationId} meterId={meterId} compact={compact} />;
}

function TokenDetails({ client, owner, allocationId, meterId, compact }: {
  client: SandboxClient; owner: number; allocationId?: number; meterId?: number; compact: boolean;
}) {
  const context = `${owner}:${allocationId ?? ""}:${meterId ?? ""}`;
  const [result, setResult] = useState<{ context: string; tokens: EnergyToken[] } | null>(null);
  const tokens = result?.context === context ? result.tokens : null;
  const [error, setError] = useState("");
  const [copyNotice, setCopyNotice] = useState("");
  const [version, setVersion] = useState(0);
  const [busy, setBusy] = useState(true);
  const refresh = useCallback(() => {
    setBusy(true); setError(""); setCopyNotice(""); setVersion(value => value + 1);
  }, []);
  useEffect(() => {
    let active = true;
    const query = allocationId !== undefined ? `?allocation_id=${allocationId}` : meterId ? `?meter_id=${meterId}` : "";
    void client.get<unknown>(`meter/energy-tokens/${query}`).then(value => {
      if (active) setResult({ context, tokens: parseEnergyTokens(value, allocationId ?? undefined) });
    }).catch(() => { if (active) setError("Electricity tokens could not be retrieved. Reconnect and refresh; do not repeat the payment."); })
      .finally(() => { if (active) setBusy(false); });
    return () => { active = false; };
  }, [client, owner, allocationId, meterId, version, context]);
  useEffect(() => {
    if (!tokens?.some(row => row.state === "DELIVERY_PENDING")) return;
    const timer = setInterval(() => { if (document.visibilityState === "visible") refresh(); }, 15000);
    return () => clearInterval(timer);
  }, [tokens, refresh]);
  return <section className="energy-token-card" aria-label="Electricity tokens">
    {busy && <p role="status">Loading electricity token…</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {tokens?.length === 0 && <p className="muted small">Token unavailable for this historical transaction.</p>}
    {tokens?.map(row => <div key={row.id} className="token-detail">
      <p><strong>{row.environment === "SANDBOX" ? "EUR test allocation — token issued; incompatible with the current AC lab device." : row.source === "PURCHASE" ? "Payment confirmed — token issued." : "Loan disbursed — token issued."}</strong></p>
      <label>15-digit electricity token<input className="energy-token-value" readOnly type="text" inputMode="numeric" value={row.token} aria-label="15-digit electricity token" /></label>
      <p className="small">Meter {row.meter_number} · {row.energy_kwh} kWh</p>
      <p className="reference small">{row.source === "PURCHASE" ? "Purchase" : "Loan"} reference: {row.source_reference}</p>
      <p role="status">{tokenLoadingLabel(row)}</p>
      {row.state === "APPLIED" && <p className="small">Token already used.</p>}
      <button type="button" className="secondary" onClick={() => {
        setCopyNotice("");
        if (!navigator.clipboard?.writeText) { setCopyNotice("Select the token text and copy it manually."); return; }
        void navigator.clipboard.writeText(row.token).then(() => setCopyNotice("Token copied. Paste only where intended.")).catch(() => setCopyNotice("Select the token text and copy it manually."));
      }}>Copy Token</button>
      {row.environment === "SANDBOX" ? <p className="muted small">EUR test tokens are retained for history or the isolated software bench. AC_LAB accepts UGX_DEMO only. No credit saved on the physical device is implied.</p> : compact ? <><p className="muted small">Enter all 15 digits on the meter keypad. Application needs a commissioned device.</p><details><summary>Meter connection</summary><p>Internet is needed to validate a new token. This is a prototype token for commissioned lab devices or the isolated software bench. It is not an STS token or proof of load switching.</p></details></> : <p className="muted small">Enter all 15 digits on the meter keypad. Internet is needed to validate a new token. Prototype lab token; this is not an STS token or proof of load switching.</p>}
    </div>)}
    {copyNotice && <p role="status">{copyNotice}</p>}
    <button type="button" className="secondary" disabled={busy} onClick={refresh}>Refresh loading status</button>
  </section>;
}
