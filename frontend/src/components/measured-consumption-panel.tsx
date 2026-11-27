'use client';

import { useEffect, useState } from 'react';
import { measuredFreshness, type MeasuredConsumption, type UsageDays } from '../lib/measured-consumption';

const reasons = {
  MEASURED: 'Measured', UPLOAD_GAP: 'Upload gap', DAY_BOUNDARY: 'Crosses midnight UTC',
  PERIOD_BOUNDARY: 'Crosses period start', RESTART: 'Device restart', DEVICE_CHANGED: 'Device replaced',
  BINDING_CHANGED: 'Meter binding changed', BASELINE_CHANGED: 'Measurement baseline changed',
  SENSOR_UNAVAILABLE: 'Sensor unavailable', COUNTER_RESET: 'Counter reset',
  TIME_UNRESOLVED: 'Sample time unresolved', NO_PRIOR_SAMPLE: 'First sample',
};
const display = (amount: string | null | undefined, unit: string) => amount == null ? 'Unavailable' : `${amount} ${unit}`;
const date = (value: string | null | undefined) => value ? new Date(value).toLocaleString() : 'Unavailable';

export function MeasuredConsumptionPanel({ data, loading, error, onRefresh, compact = false, days, onDays } : {
  data: MeasuredConsumption | null;
  loading?: boolean;
  error?: string | null;
  onRefresh?: () => void;
  compact?: boolean;
  days: UsageDays;
  onDays: (days: UsageDays) => void;
}) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 10_000);
    return () => clearInterval(timer);
  }, []);
  const sample = data?.latest, relay = data?.relay, period = data?.period;
  const freshness = data ? measuredFreshness(data, now) : 'UNAVAILABLE';
  const sensorFault = sample?.sensor_state === 'FAULT';
  const daily = data?.daily ?? [];
  const max = Math.max(0, ...daily.map(day => Number(day.measured_kwh)));
  const allowDisplay = sample?.sensor_state === 'OK';
  const authorized = relay?.authorized && freshness === 'RECENT' && !sensorFault && !error &&
    (!relay.expires_at || Date.parse(relay.expires_at) > now);
  return <section className="measured-consumption" aria-label="Physical meter consumption">
    <h3>Physical meter consumption</h3>
    {!compact && data?.device_bound !== false && <label>Usage period (UTC) <select value={days} onChange={event => onDays(Number(event.currentTarget.value) as UsageDays)}>
      <option value={1}>Today</option><option value={7}>7 calendar days</option><option value={30}>30 calendar days</option>
    </select></label>}
    {error && <p role="alert">Could not refresh measured consumption. {onRefresh && <button type="button" onClick={onRefresh}>Retry</button>}</p>}
    {loading && !data && <p role="status">Loading measured consumption…</p>}
    {data && !data.device_bound && <p role="status">No physical meter is bound to this meter in {data.scope.environment}.</p>}
    {data?.device_bound && <p role="status">{sensorFault ? 'Sensor unavailable.' : !sample ? 'No measured readings yet.' :
      freshness === 'STALE' ? 'Stored readings are stale.' : 'Recent PZEM reading.'}{sensorFault && freshness === 'STALE' ? ' Fault report is stale.' : ''}
      {error && sample ? ' Showing the last stored reading.' : ''}</p>}
    {data?.device_bound && <>
      <dl className="detail-grid">
        <div><dt>{freshness === 'STALE' || error ? 'Last stored power' : 'Current power'}</dt><dd>{display(allowDisplay ? sample?.power_w : null, 'W')}</dd></div>
        <div><dt>Voltage</dt><dd>{display(allowDisplay ? sample?.voltage_v : null, 'V')}</dd></div>
        <div><dt>Current</dt><dd>{display(allowDisplay ? sample?.current_a : null, 'A')}</dd></div>
        <div><dt>PZEM cumulative counter</dt><dd>{display(allowDisplay ? sample?.cumulative_kwh : null, 'kWh')}</dd></div>
        <div><dt>Latest observed interval</dt><dd>{display(data.latest_interval?.consumption_kwh, 'kWh')}</dd></div>
        <div><dt>Last reported remaining credit</dt><dd>{display(sample?.remaining_credit_kwh, 'kWh')}</dd></div>
      </dl>
      {data.latest_interval && data.latest_interval.classification !== 'MEASURED' &&
        <p>Interval coverage: {reasons[data.latest_interval.classification]}.</p>}
      <p>Last measurement {date(sample?.measured_at)} · Received {date(sample?.received_at)}</p>
      <p>Last reported relay command {sample?.output_command ?? 'Unknown'} · {relay?.offline_allowed ? 'Offline operation permitted' : `Online permission ${authorized ? 'authorized' : 'unavailable or inhibited'}`} · Physical contact unknown</p>
      {relay && relay.state !== 'NONE' && <p>Authorization {relay.state.toLowerCase()} · {relay.restart_policy?.toLowerCase() ?? 'Unknown'} restart · {relay.mode === 'PERSISTENT' ? 'Persistent commissioning' : `Expires ${date(relay.expires_at)}`}</p>}
      {!compact && <>
        <p>Measured energy in covered intervals <strong>{display(period?.measured_kwh, 'kWh')}</strong></p>
        <p>{period?.coverage === 'UNAVAILABLE' ? 'No covered intervals in this period.' :
          period?.coverage === 'PARTIAL' ? 'Partial coverage. Missing intervals are excluded.' : 'Complete coverage.'}</p>
        {period?.unallocated_kwh != null && <p>{period.unallocated_kwh} kWh observed across {period.unallocated_interval_count} interval(s) with a time gap or boundary, excluded from chart totals.</p>}
        <ol className="measured-day-chart" aria-label="Daily measured kWh in UTC">
          {daily.map(day => <li key={day.date}>
            <span>{day.date}</span>
            <meter aria-label={`${day.date} measured energy`} min={0} max={max || 1}
              hidden={day.measured_kwh === null} value={Number(day.measured_kwh)} />
            <span>{display(day.measured_kwh, 'kWh')}{day.coverage === 'PARTIAL' ? ' · partial' : ''}</span>
          </li>)}
        </ol>
        <details><summary>Measured interval history</summary>
          {data.history_truncated && <p>Showing the latest 120 observations. Totals include the entire selected period.</p>}
          {data.history.length ? <ul>{data.history.map(entry => <li key={`${entry.device_id}:${entry.boot_id}:${entry.sequence}`}>
            {entry.start_at ? `${date(entry.start_at)} – ` : ''}{date(entry.measured_at)} · {display(entry.consumption_kwh, 'kWh')} · {reasons[entry.classification]}
            <small> · Received {date(entry.received_at)}</small>
          </li>)}</ul> : <p>No observations in this period.</p>}
        </details>
      </>}
    </>}
  </section>;
}
