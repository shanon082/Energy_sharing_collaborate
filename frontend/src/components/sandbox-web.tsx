"use client";
import { useEffect, useState, type FormEvent } from "react";
import SandboxConsumer from "./sandbox-consumer";
import { sandboxCapabilities, type SandboxCapabilities, type SandboxClient, type TestMeter } from "../lib/sandbox";
import { normalizePrototypeMeterNumber, parsePrototypeEnrollment, PROTOTYPE_OWNERSHIP_NOTICE } from "../lib/meter-enrollment";

async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/proxy/${path}`, { method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body), cache: "no-store" });
  const data: unknown = await response.json();
  if (!response.ok) {
    const row = data && typeof data === "object" ? data as Record<string, unknown> : {};
    throw new Error(typeof row.message === "string" ? row.message : typeof row.detail === "string" ? row.detail : `Request failed (${response.status}).`);
  }
  return data as T;
}
const client: SandboxClient = { get: request, post: (path, body) => request(path, body) };
export default function SandboxWeb() {
  const [owner, setOwner] = useState<number | null>(null);
  const [meters, setMeters] = useState<TestMeter[]>([]);
  const [selected, setSelected] = useState("");
  const [capabilities, setCapabilities] = useState<SandboxCapabilities | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [number, setNumber] = useState("");
  const [enrolling, setEnrolling] = useState(false);
  const [enrollmentAvailable, setEnrollmentAvailable] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  useEffect(() => {
    let current = true;
    void Promise.all([client.get<{ sandbox: unknown }>("features/"), client.get<{ id: number }>("auth/mobile-account/"),
      client.get<{ meters: TestMeter[]; sandbox_self_enrollment?: boolean }>("meter/mobile-onboarding/")]).then(([flags, account, onboarding]) => {
      if (current) { setCapabilities(sandboxCapabilities(flags.sandbox)); setOwner(account.id); setMeters(onboarding.meters); setEnrollmentAvailable(onboarding.sandbox_self_enrollment === true); }
    }).catch(cause => { if (current) setError(cause instanceof Error ? cause.message : "Could not read sandbox availability."); });
    return () => { current = false; };
  }, []);
  const enroll = async (event: FormEvent) => {
    event.preventDefault(); setError(null); setNotice(null); setEnrolling(true);
    try {
      const normalized = normalizePrototypeMeterNumber(number);
      const linked = parsePrototypeEnrollment(await client.post("meter/sandbox-meter-enrollment/", { meter_no: normalized }), normalized);
      setMeters(old => [...old.filter(meter => meter.id !== linked.meter.id), linked.meter]);
      setSelected(String(linked.meter.id)); setNumber(""); setNotice(linked.message);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not confirm enrollment. Retrying the same number is safe."); }
    finally { setEnrolling(false); }
  };
  if (error && !capabilities) return <p role="alert">{error}</p>;
  if (!capabilities || owner === null) return <p>Checking server sandbox availability…</p>;
  if (!capabilities.enabled) return <p>This deployment has no sandbox workflow. Existing web functions remain available.</p>;
  return <div className="sandbox-web">
    {enrollmentAvailable && <form className="panel form-panel" onSubmit={event => void enroll(event)}>
      <h2>Add your meter</h2><p>{PROTOTYPE_OWNERSHIP_NOTICE}</p>
      <label>Meter number <input value={number} maxLength={100} autoComplete="off" required disabled={enrolling} onChange={event => setNumber(event.target.value)} /></label>
      <button type="submit" disabled={enrolling}>{enrolling ? "Linking…" : "Add your meter"}</button>
      <p>Leading zeros are preserved. Hardware connection is pending.</p>
    </form>}
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    <label>Explicit test meter <select value={selected} onChange={event => setSelected(event.target.value)}>
    <option value="">Choose a linked prototype meter</option>{meters.filter(meter => meter.sandbox_inventory).map(meter => <option key={meter.id} value={meter.id}>{meter.meter_number}</option>)}
  </select></label><SandboxConsumer key={owner} client={client} owner={owner} meters={meters}
    selectedMeter={meters.find(meter => String(meter.id) === selected) ?? null} capabilities={capabilities} /></div>;
}
