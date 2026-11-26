export type ReadingEnvironment = 'CORE' | 'SANDBOX' | 'UGX_DEMO';
export type UsageDays = 1 | 7 | 30;
export type UsageScope = { id: number; meter_number: string; environment: ReadingEnvironment; days: UsageDays };

const SENSOR = ['OK', 'FAULT', 'UNAVAILABLE'] as const;
const COVERAGE = ['COMPLETE', 'PARTIAL', 'UNAVAILABLE'] as const;
const KINDS = ['MEASURED', 'UPLOAD_GAP', 'DAY_BOUNDARY', 'PERIOD_BOUNDARY', 'RESTART', 'DEVICE_CHANGED',
  'BINDING_CHANGED', 'BASELINE_CHANGED', 'SENSOR_UNAVAILABLE', 'COUNTER_RESET', 'TIME_UNRESOLVED', 'NO_PRIOR_SAMPLE'] as const;

function invalid(): never { throw new Error('The measured consumption response was invalid.'); }
function row(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : invalid();
}
function choice<T extends string>(value: unknown, choices: readonly T[]): T {
  return typeof value === 'string' && choices.includes(value as T) ? value as T : invalid();
}
function text(value: unknown) { return typeof value === 'string' && value.length ? value : invalid(); }
function time(value: unknown) {
  const date = text(value);
  return Number.isFinite(Date.parse(date)) ? date : invalid();
}
function nullableTime(value: unknown) { return value === null ? null : time(value); }
function decimal(value: unknown) {
  return value === null ? null : typeof value === 'string' && /^\d+(\.\d{1,9})?$/.test(value) ? value : invalid();
}
function count(value: unknown) {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 ? value : invalid();
}
function boolean(value: unknown) { return typeof value === 'boolean' ? value : invalid(); }
function array(value: unknown) { return Array.isArray(value) ? value : invalid(); }
function totals(data: Record<string, unknown>) {
  return {
    measured_kwh: decimal(data.measured_kwh), interval_count: count(data.interval_count),
    covered_ms: count(data.covered_ms), window_ms: count(data.window_ms),
    coverage: choice(data.coverage, COVERAGE),
  };
}
function binding(data: Record<string, unknown>) {
  return { device_id: text(data.device_id), binding_epoch: data.binding_epoch === null ? null : count(data.binding_epoch), baseline: text(data.baseline) };
}
function interval(value: unknown) {
  const data = row(value);
  return { ...binding(data), boot_id: text(data.boot_id), sequence: text(data.sequence),
    start_at: nullableTime(data.start_at), measured_at: time(data.measured_at), received_at: time(data.received_at),
    classification: choice(data.classification, KINDS), consumption_kwh: decimal(data.consumption_kwh),
    sensor_state: choice(data.sensor_state, SENSOR) };
}
function latest(value: unknown) {
  const data = row(value);
  return { ...binding(data), measured_at: time(data.measured_at), received_at: time(data.received_at),
    freshness: choice(data.freshness, ['RECENT', 'STALE']), sensor_state: choice(data.sensor_state, SENSOR),
    fault_status: data.fault_status == null ? null : text(data.fault_status),
    voltage_v: decimal(data.voltage_v), current_a: decimal(data.current_a), power_w: decimal(data.power_w),
    cumulative_kwh: decimal(data.cumulative_kwh), remaining_credit_kwh: decimal(data.remaining_credit_kwh),
    output_command: choice(data.output_command, ['ON', 'OFF', 'UNKNOWN']) };
}

export function measuredConsumptionPath(scope: UsageScope): string {
  return `meter/mobile-meters/${scope.id}/measured-consumption/?environment=${scope.environment}&days=${scope.days}`;
}

export function parseMeasuredConsumption(value: unknown, scope: UsageScope) {
  const data = row(value), meter = row(data.meter), period = row(data.period), relay = row(data.relay);
  if (meter.id !== scope.id || meter.meter_number !== scope.meter_number || data.environment !== scope.environment ||
      period.days !== scope.days || period.timezone !== 'UTC' || data.source !== 'AC_LAB_PZEM') {
    throw new Error('The measured consumption response belongs to a different meter or period.');
  }
  const daily = array(data.daily).map(item => {
    const day = row(item), date = text(day.date);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) invalid();
    return { date, ...totals(day) };
  });
  if (daily.length !== scope.days) invalid();
  return {
    scope, as_of: time(data.as_of), stale_after_seconds: count(data.stale_after_seconds),
    device_bound: boolean(data.device_bound),
    latest: data.latest === null ? null : latest(data.latest),
    latest_interval: data.latest_interval === null ? null : interval(data.latest_interval),
    relay: {
      authorized: boolean(relay.authorized), state: choice(relay.state, ['NONE', 'ACTIVE', 'REVOKED', 'EXPIRED']),
      expires_at: nullableTime(relay.expires_at),
      restart_policy: relay.restart_policy === null ? null : choice(relay.restart_policy, ['AUTO', 'MANUAL']),
      contact: choice(relay.contact, ['UNKNOWN']),
    },
    period: { ...totals(period), start_at: time(period.start_at), end_at: time(period.end_at),
      unallocated_kwh: decimal(period.unallocated_kwh), unallocated_interval_count: count(period.unallocated_interval_count) },
    daily, history: array(data.history).map(interval), history_truncated: boolean(data.history_truncated),
  };
}
export type MeasuredConsumption = ReturnType<typeof parseMeasuredConsumption>;

export function sameUsageScope(a: UsageScope, b: UsageScope) {
  return a.id === b.id && a.meter_number === b.meter_number && a.environment === b.environment && a.days === b.days;
}

export function measuredFreshness(data: MeasuredConsumption, now: number) {
  const reading = data.latest;
  if (!reading) return 'UNAVAILABLE';
  const age = Math.max(now - Date.parse(reading.received_at), Math.abs(now - Date.parse(reading.measured_at)));
  return reading.freshness === 'STALE' || age > data.stale_after_seconds * 1000 ? 'STALE' : 'RECENT';
}
