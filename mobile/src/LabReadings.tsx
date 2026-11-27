import { useEffect, useState } from "react";
import { labReadingStatus, microWhDisplay, type AllocationStatus } from "./api/contracts.ts";
import { dateTime } from "./format.ts";

function scaled(value: string | null | undefined, divisor: number, precision: number, unit: string) {
  if (value == null || !/^[0-9]+$/.test(value)) return "Unavailable";
  return `${(Number(value) / divisor).toFixed(precision)} ${unit}`;
}

/** Periodic device attestations, never evidence that a load is energized. */
export function LabReadings({ reading, stale }: { reading: AllocationStatus; stale: boolean }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(timer);
  }, []);
  const status = stale ? "STALE" : labReadingStatus(reading, now);
  return <section className="panel"><h2>AC lab meter</h2>
    {reading.lab_environment && <p className="muted small">{reading.lab_environment} energy · {reading.lab_protocol}. This is device evidence, not utility verification.</p>}
    <p className="muted small">Physical PZEM readings · {status.toLowerCase()} · measurement {reading.lab_measurement_state ?? "unknown"}.</p>
    <div className="detail-grid"><div><span>Usage since previous stored sample</span><strong>{reading.lab_interval_usage_wh == null ? "Unavailable" : `${reading.lab_interval_usage_wh} Wh`}</strong></div><div><span>Device-reported credit</span><strong>{microWhDisplay(reading.lab_remaining_credit_uwh)}</strong></div></div>
    <p className="muted small">PZEM cumulative energy: {reading.lab_pzem_wh == null ? "Unavailable" : `${reading.lab_pzem_wh} Wh`}. Credit debited: {microWhDisplay(reading.lab_consumed_uwh)}.</p>
    <div className="detail-grid">
      <div><span>Voltage</span><strong>{scaled(reading.lab_voltage_mv, 1000, 2, "V")}</strong></div>
      <div><span>Current</span><strong>{scaled(reading.lab_current_ma, 1000, 3, "A")}</strong></div>
      <div><span>Active power</span><strong>{scaled(reading.lab_power_mw, 1000, 2, "W")}</strong></div>
      <div><span>Frequency</span><strong>{scaled(reading.lab_frequency_cHz, 100, 2, "Hz")}</strong></div>
      <div><span>Power factor</span><strong>{reading.lab_power_factor_pct == null ? "Unavailable" : `${reading.lab_power_factor_pct}%`}</strong></div>
      <div><span>Device output command</span><strong>{reading.lab_output_command ?? "UNKNOWN"}</strong></div>
    </div>
    <p className="muted small">{reading.output_offline_allowed ? "Offline operation permitted" : `Online output permission ${reading.output_authorized ? "authorized" : "unavailable"}`} · {reading.output_authorization_state ?? "NONE"} · {reading.output_restart_policy ?? "MANUAL"} restart · {reading.output_commissioning_mode === "PERSISTENT" ? "Persistent commissioning" : `Expires ${dateTime(reading.output_authorization_expires_at)}`}. Physical relay contact unknown.</p>
    {reading.lab_interval_start && <p className="muted small">Usage interval begins {dateTime(reading.lab_interval_start)}; missing samples are not interpolated.</p>}
    <p>Last measurement: {dateTime(reading.last_measurement_at)} · Last contact: {dateTime(reading.last_meter_contact)}</p>
    {reading.lab_sensor_status !== "OK" && <p role="status">Sensor reading unavailable · {reading.lab_fault_status ?? "SENSOR_UNAVAILABLE"}.</p>}
    {status === "STALE" && <p role="status">Stored readings are stale; refresh to check contact.</p>}
    {status === "UNAVAILABLE" && <p role="status">No measured reading available.</p>}
    {reading.lab_uncertain_uwh && reading.lab_uncertain_uwh !== "0" && <p>Credit withheld for uncertainty: {microWhDisplay(reading.lab_uncertain_uwh)}. Reconciliation required.</p>}
  </section>;
}
