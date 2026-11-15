"use client";
import { useEffect, useState, type FormEvent } from "react";
import SandboxConsumer from "./sandbox-consumer";
import { sandboxCapabilities, type SandboxCapabilities, type SandboxClient, type TestMeter } from "../lib/sandbox";
import { normalizePrototypeMeterNumber, parsePrototypeEnrollment, PROTOTYPE_OWNERSHIP_NOTICE } from "../lib/meter-enrollment";
import { get, post } from "../lib/fetch-client";
import { getApiErrorMessage } from "../lib/api-response";
import ConsumerWallet from "./sandbox-wallet";
import type { ConsumerFinanceView } from "./sandbox-mobile-view";

async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = body === undefined ? await get<T>(path) : await post<T>(path, body);
  if (response.error) {
    throw new Error(getApiErrorMessage(response.error, `Request failed (${response.status}).`));
  }
  if (response.data === undefined) throw new Error("The API returned an empty response.");
  return response.data;
}
const client: SandboxClient = { get: request, post: (path, body) => request(path, body) };
export default function SandboxWeb({ view = "purchase" }: { view?: ConsumerFinanceView | "wallet" }) {
  const [owner, setOwner] = useState<number | null>(null);
  const [meters, setMeters] = useState<TestMeter[]>([]);
  const [selected, setSelected] = useState("");
  const [capabilities, setCapabilities] = useState<SandboxCapabilities | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [number, setNumber] = useState("");
  const [enrolling, setEnrolling] = useState(false);
  const [enrollmentAvailable, setEnrollmentAvailable] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [addingMeter, setAddingMeter] = useState(false);
  const [loadAttempt, setLoadAttempt] = useState(0);
  useEffect(() => {
    let current = true;
    setError(null);
    setOwner(null);
    setMeters([]);
    setSelected("");
    setCapabilities(null);
    void Promise.all([client.get<{ sandbox: unknown }>("features/"), client.get<{ id: number }>("auth/mobile-account/"),
      client.get<{ meters: TestMeter[]; sandbox_self_enrollment?: boolean }>("meter/mobile-onboarding/")]).then(([flags, account, onboarding]) => {
      if (current) {
        if (!Array.isArray(onboarding.meters)) throw new Error("Could not load your meters.");
        const linked = onboarding.meters;
        const selectable = linked.filter(meter => meter.sandbox_inventory);
        setCapabilities(sandboxCapabilities(flags.sandbox));
        setOwner(account.id);
        setMeters(linked);
        setEnrollmentAvailable(onboarding.sandbox_self_enrollment === true);
        setSelected(previous => selectable.some(meter => String(meter.id) === previous)
          ? previous : selectable.length === 1 ? String(selectable[0].id) : "");
      }
    }).catch(cause => { if (current) setError(cause instanceof Error ? cause.message : "Could not read sandbox availability."); });
    return () => { current = false; };
  }, [loadAttempt]);
  const enroll = async (event: FormEvent) => {
    event.preventDefault(); setError(null); setNotice(null); setEnrolling(true);
    try {
      const normalized = normalizePrototypeMeterNumber(number);
      const linked = parsePrototypeEnrollment(await client.post("meter/sandbox-meter-enrollment/", { meter_no: normalized }), normalized);
      setMeters(old => [...old.filter(meter => meter.id !== linked.meter.id), linked.meter]);
      setSelected(String(linked.meter.id)); setNumber(""); setNotice(linked.message); setAddingMeter(false);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not confirm enrollment. Retrying the same number is safe."); }
    finally { setEnrolling(false); }
  };
  if (error && !capabilities && view !== "wallet") return <p role="alert">{error} <button className="underline" onClick={() => setLoadAttempt(value => value + 1)}>Retry</button></p>;
  if (owner === null) return error
    ? <p role="alert">{error} <button className="underline" onClick={() => setLoadAttempt(value => value + 1)}>Retry</button></p>
    : <p role="status">Loading your account…</p>;
  const activeEnvironment = capabilities?.enabled ? capabilities.environment! : "CORE";
  if (view === "wallet") return <ConsumerWallet key={owner} client={client} meters={meters} environment={activeEnvironment} />;
  if (!capabilities?.enabled) return <p>This sandbox workflow is unavailable.</p>;
  const testMeters = meters.filter(meter => meter.sandbox_inventory);
  const selectedMeter = testMeters.find(meter => String(meter.id) === selected) ?? null;
  return <div className="sandbox-web">
    {addingMeter && enrollmentAvailable && <form className="panel form-panel" onSubmit={event => void enroll(event)}>
      <h2>Add your meter</h2><p>{PROTOTYPE_OWNERSHIP_NOTICE}</p>
      <label>Meter number <input value={number} maxLength={11} inputMode="numeric" pattern="[0-9]{11}" autoComplete="off" required disabled={enrolling} onChange={event => setNumber(event.target.value)} /></label>
      <button type="submit" disabled={enrolling}>{enrolling ? "Linking…" : "Add your meter"}</button>
      <p>Leading zeros are preserved. Hardware connection is pending.</p>
      <button type="button" className="secondary" disabled={enrolling} onClick={() => setAddingMeter(false)}>Cancel</button>
    </form>}
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    <SandboxConsumer key={`${owner}:${capabilities.provider ?? "MTN_SANDBOX"}:${view}`} client={client} owner={owner} meters={meters}
      selectedMeter={selectedMeter} capabilities={capabilities} view={view} surface="web" onSelectMeter={setSelected}
      onAddMeter={() => enrollmentAvailable ? setAddingMeter(true) : setError("Meter enrollment is unavailable. Contact support to link an assigned meter.")} />
  </div>;
}
