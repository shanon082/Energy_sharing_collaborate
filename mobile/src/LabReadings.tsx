import { useEffect, useState } from "react";
import { labReadingStatus, microWhDisplay, type AllocationStatus } from "./api/contracts.ts";
import { dateTime } from "./format.ts";

/** Periodic device attestations, never evidence that a load is energized. */
export function LabReadings({ reading, stale }: { reading: AllocationStatus; stale: boolean }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(timer);
  }, []);
  const status = stale ? "STALE" : labReadingStatus(reading, now);
  return <section className="panel"><h2>AC lab meter</h2>
    <p className="muted small">Periodic PZEM readings · {status.toLowerCase()} · relay output disabled. Load feedback unknown.</p>
    <div className="detail-grid"><div><span>Usage since previous stored sample</span><strong>{reading.lab_interval_usage_wh == null ? "Unavailable" : `${reading.lab_interval_usage_wh} Wh`}</strong></div><div><span>Device-reported credit</span><strong>{microWhDisplay(reading.lab_remaining_credit_uwh)}</strong></div></div>
    <p className="muted small">PZEM cumulative energy: {reading.lab_pzem_wh == null ? "Unavailable" : `${reading.lab_pzem_wh} Wh`}. Credit debited: {microWhDisplay(reading.lab_consumed_uwh)}.</p>
    {reading.lab_interval_start && <p className="muted small">Usage interval begins {dateTime(reading.lab_interval_start)}; missing samples are not interpolated.</p>}
    <p>Last measurement: {dateTime(reading.last_measurement_at)} · Last contact: {dateTime(reading.last_meter_contact)}</p>
    {reading.lab_sensor_status !== "OK" && <p role="status">Sensor reading unavailable.</p>}
    {status === "STALE" && <p role="status">Stored readings are stale; refresh to check contact.</p>}
    {status === "UNAVAILABLE" && <p role="status">No measured reading available.</p>}
    {reading.lab_uncertain_uwh && reading.lab_uncertain_uwh !== "0" && <p>Credit withheld for uncertainty: {microWhDisplay(reading.lab_uncertain_uwh)}. Reconciliation required.</p>}
  </section>;
}
