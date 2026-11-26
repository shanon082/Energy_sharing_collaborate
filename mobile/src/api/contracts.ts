export type MeterInfo = {
  id: number;
  meter_number: string;
  label: string;
  architecture: string;
  status: string;
  sandbox_inventory?: boolean;
  ownership_provenance?: "SELF_DECLARED";
  enrolled_at?: string;
  hardware_connection?: "PENDING";
};

export type AllocationStatus = {
  unit: "kWh";
  available_kwh: string;
  pending_kwh: string;
  confirmed_kwh: string;
  last_meter_contact: string | null;
  delivery_environment: "SIMULATOR" | "UNAVAILABLE" | "AC_LAB";
  contact_source?: "SIMULATOR" | "UNAVAILABLE" | "AC_LAB";
  contact_status?: "UNAVAILABLE" | "STALE" | "RECENT";
  simulator_remaining_wh?: string | null;
  meter_reported_remaining_wh?: string | null;
  reported_relay_state?: string | null;
  last_measurement_at?: string | null;
  consumption_reconciliation_required?: boolean;
  lab_environment?: "SANDBOX" | "UGX_DEMO";
  lab_protocol?: "GPAWA_PZEM_V1" | "GPAWA_PZEM_V2";
  lab_remaining_credit_uwh?: string | null;
  lab_consumed_uwh?: string | null;
  lab_uncertain_uwh?: string | null;
  lab_pzem_wh?: string | null;
  lab_interval_usage_wh?: string | null;
  lab_interval_start?: string | null;
  lab_sensor_status?: "OK" | "FAULT" | "UNAVAILABLE";
  lab_received_at?: string | null;
  lab_measurement_state?: "UNINITIALIZED" | "SUSPENDED" | "MIGRATING" | "BASELINED" | "LEGACY_METERED";
  lab_voltage_mv?: string | null;
  lab_current_ma?: string | null;
  lab_power_mw?: string | null;
  lab_frequency_cHz?: string | null;
  lab_power_factor_pct?: string | null;
  lab_output_command?: "ON" | "OFF" | "UNKNOWN";
  lab_fault_status?: "OK" | "SENSOR_UNAVAILABLE" | "ACCOUNTING_HOLD" | "SAFETY_FAULT";
  output_authorized?: boolean;
  output_authorization_state?: "NONE" | "ACTIVE" | "REVOKED" | "EXPIRED";
  output_authorization_expires_at?: string | null;
  output_restart_policy?: "AUTO" | "MANUAL";
};

export type DailyUsage = { date: string; kwh: string; source: string };
export type Telemetry = {
  event_id: string; cumulative_wh: string; measured_at: string;
  received_at: string; classification: string;
};
export type LabTelemetry = {
  boot_id: string; sequence: string; measured_at: string; received_at: string;
  consumed_uwh: string | null; remaining_credit_uwh: string; uncertain_uwh: string;
  sensor_status: "OK" | "FAULT"; pzem_wh: string | null;
  voltage_mv: string | null; current_ma: string | null; power_mw: string | null;
  frequency_cHz: string | null; power_factor_pct: string | null;
  output_command: "ON" | "OFF" | "UNKNOWN"; fault_status: string;
};
export type ConsumptionHistory = {
  meter_no: string; daily_usage: DailyUsage[]; simulator_telemetry: Telemetry[];
  consumer_attribution_available: boolean;
  ac_lab_telemetry: LabTelemetry[];
};

export type Repayment = {
  id: number; status: string; received_ugx: string;
  applied_ugx: string | null; excess_ugx: string | null; paid_at: string;
};
export type Loan = {
  id: number; loan_id: string; status: string;
  amount_approved_ugx: string | null; outstanding_ugx: string | null;
  due_at: string | null; repayments: Repayment[];
};

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Unexpected server response.");
  return value as Record<string, unknown>;
}

function exactDecimal(value: unknown): string {
  if (typeof value !== "string" || !/^\d+(?:\.\d+)?$/.test(value)) throw new Error("Invalid exact amount from server.");
  return value;
}

export function parseMeters(payload: unknown): MeterInfo[] {
  const outer = record(payload);
  if (outer.success !== true) throw new Error("Could not load meters.");
  const data = record(outer.data);
  if (data.has_meter === false) return [];
  if (!Array.isArray(data.meters)) throw new Error("Meter list is unavailable.");
  const identifiers = new Set<number>();
  const numbers = new Set<string>();
  return data.meters.map((item) => {
    const meter = record(item);
    if (typeof meter.id !== "number" || !Number.isSafeInteger(meter.id) || meter.id <= 0 ||
        typeof meter.meter_number !== "string" || !meter.meter_number ||
        typeof meter.architecture !== "string" || typeof meter.status !== "string") {
      throw new Error("Invalid meter record.");
    }
    if (identifiers.has(meter.id) || numbers.has(meter.meter_number)) throw new Error("Duplicate meter identity.");
    identifiers.add(meter.id); numbers.add(meter.meter_number);
    return {
      id: meter.id,
      meter_number: meter.meter_number,
      label: typeof meter.label === "string" && meter.label ? meter.label : meter.meter_number,
      architecture: meter.architecture,
      status: meter.status,
      ...(typeof meter.sandbox_inventory === "boolean" ? { sandbox_inventory: meter.sandbox_inventory } : {}),
      ...(meter.ownership_provenance === "SELF_DECLARED" && meter.sandbox_inventory === true ? {
        ownership_provenance: "SELF_DECLARED" as const,
        ...(typeof meter.enrolled_at === "string" ? { enrolled_at: meter.enrolled_at } : {}),
        ...(meter.hardware_connection === "PENDING" ? { hardware_connection: "PENDING" as const } : {}),
      } : {}),
    };
  });
}

export function selectedMeterStillAssigned(selected: MeterInfo, meters: MeterInfo[]): boolean {
  return meters.some((meter) => meter.id === selected.id && meter.meter_number === selected.meter_number);
}

export function parseMeterDashboard(payload: unknown, selected: MeterInfo): AllocationStatus {
  const data = record(payload);
  const meter = record(data.meter);
  if (meter.id !== selected.id || meter.meter_number !== selected.meter_number) {
    throw new Error("Meter assignment changed. Select an assigned meter again.");
  }
  if (data.quantum_kwh !== "0.01" ||
      !["SIMULATOR", "UNAVAILABLE", "AC_LAB"].includes(String(data.contact_source))) {
    throw new Error("Meter dashboard is unavailable.");
  }
  if (data.lab_environment !== undefined &&
      (!["SANDBOX", "UGX_DEMO"].includes(String(data.lab_environment)) || data.lab_protocol !== (data.lab_environment === "SANDBOX" ? "GPAWA_PZEM_V2" : "GPAWA_PZEM_V1")))
    throw new Error("Meter lab domain is unavailable.");
  const optionalWh = (value: unknown) => value == null ? null :
    typeof value === "string" && /^[0-9]+$/.test(value) ? value : (() => { throw new Error("Invalid meter credit reading."); })();
  const optionalMetric = (value: unknown) => value == null ? null :
    typeof value === "number" && Number.isSafeInteger(value) && value >= 0 ? String(value) :
    typeof value === "string" && /^[0-9]+$/.test(value) ? value :
    (() => { throw new Error("Invalid physical meter measurement."); })();
  return { ...parseAllocation(data), contact_source: data.contact_source as AllocationStatus["contact_source"],
    contact_status: ["UNAVAILABLE", "STALE", "RECENT"].includes(String(data.contact_status))
      ? data.contact_status as AllocationStatus["contact_status"] : "UNAVAILABLE",
    simulator_remaining_wh: optionalWh(data.simulator_remaining_wh),
    meter_reported_remaining_wh: optionalWh(data.meter_reported_remaining_wh),
    reported_relay_state: ["OPEN", "CLOSED", "UNKNOWN"].includes(String(data.reported_relay_state))
      ? String(data.reported_relay_state) : null,
    last_measurement_at: typeof data.last_measurement_at === "string" ? data.last_measurement_at : null,
    consumption_reconciliation_required: data.consumption_reconciliation_required === true,
    ...(data.lab_environment === "SANDBOX" || data.lab_environment === "UGX_DEMO" ? {lab_environment: data.lab_environment, lab_protocol: data.lab_protocol as AllocationStatus["lab_protocol"]} : {}),
    lab_remaining_credit_uwh: optionalWh(data.lab_remaining_credit_uwh),
    lab_consumed_uwh: optionalWh(data.lab_consumed_uwh),
    lab_uncertain_uwh: optionalWh(data.lab_uncertain_uwh),
    lab_pzem_wh: optionalWh(data.lab_pzem_wh),
    lab_interval_usage_wh: optionalWh(data.lab_interval_usage_wh),
    lab_interval_start: typeof data.lab_interval_start === "string" ? data.lab_interval_start : null,
    lab_sensor_status: ["OK", "FAULT", "UNAVAILABLE"].includes(String(data.lab_sensor_status))
      ? data.lab_sensor_status as AllocationStatus["lab_sensor_status"] : "UNAVAILABLE",
    lab_received_at: typeof data.lab_received_at === "string" ? data.lab_received_at : null,
    lab_measurement_state: ["UNINITIALIZED", "SUSPENDED", "MIGRATING", "BASELINED", "LEGACY_METERED"].includes(String(data.lab_measurement_state))
      ? data.lab_measurement_state as AllocationStatus["lab_measurement_state"] : undefined,
    lab_voltage_mv: optionalMetric(data.lab_voltage_mv),
    lab_current_ma: optionalMetric(data.lab_current_ma),
    lab_power_mw: optionalMetric(data.lab_power_mw),
    lab_frequency_cHz: optionalMetric(data.lab_frequency_cHz),
    lab_power_factor_pct: optionalMetric(data.lab_power_factor_pct),
    lab_output_command: ["ON", "OFF", "UNKNOWN"].includes(String(data.lab_output_command))
      ? data.lab_output_command as AllocationStatus["lab_output_command"] : "UNKNOWN",
    lab_fault_status: ["OK", "SENSOR_UNAVAILABLE", "ACCOUNTING_HOLD", "SAFETY_FAULT"].includes(String(data.lab_fault_status))
      ? data.lab_fault_status as AllocationStatus["lab_fault_status"] : "SENSOR_UNAVAILABLE",
    output_authorized: data.output_authorized === true,
    output_authorization_state: ["NONE", "ACTIVE", "REVOKED", "EXPIRED"].includes(String(data.output_authorization_state))
      ? data.output_authorization_state as AllocationStatus["output_authorization_state"] : "NONE",
    output_authorization_expires_at: typeof data.output_authorization_expires_at === "string" &&
      Number.isFinite(Date.parse(data.output_authorization_expires_at)) ? data.output_authorization_expires_at : null,
    output_restart_policy: data.output_restart_policy === "AUTO" || data.output_restart_policy === "MANUAL"
      ? data.output_restart_policy : undefined,
  };
}

export function parseAllocation(payload: unknown): AllocationStatus {
  const data = record(payload);
  if (data.unit !== "kWh" || !["SIMULATOR", "UNAVAILABLE", "AC_LAB"].includes(String(data.delivery_environment))) {
    throw new Error("Allocation status is unavailable.");
  }
  return {
    unit: "kWh",
    available_kwh: exactDecimal(data.available_kwh),
    pending_kwh: exactDecimal(data.pending_kwh),
    confirmed_kwh: exactDecimal(data.confirmed_kwh),
    last_meter_contact: typeof data.last_meter_contact === "string" ? data.last_meter_contact : null,
    delivery_environment: data.delivery_environment as AllocationStatus["delivery_environment"],
  };
}

export function parseConsumption(payload: unknown, selected?: MeterInfo): ConsumptionHistory {
  const data = record(payload);
  if (typeof data.meter_no !== "string" || !Array.isArray(data.daily_usage) ||
      !Array.isArray(data.simulator_telemetry)) throw new Error("Consumption history is unavailable.");
  if (selected) {
    const meter = record(data.meter);
    if (meter.id !== selected.id || data.meter_no !== selected.meter_number ||
        meter.meter_number !== selected.meter_number) throw new Error("Consumption belongs to a different meter.");
  }
  return {
    meter_no: data.meter_no,
    consumer_attribution_available: data.consumer_attribution_available === true,
    daily_usage: data.daily_usage.map((item) => {
      const row = record(item);
      if (typeof row.date !== "string" || typeof row.source !== "string") throw new Error("Invalid usage row.");
      return { date: row.date, kwh: exactDecimal(row.kwh), source: row.source };
    }),
    ac_lab_telemetry: parseLabTelemetry(data.ac_lab_telemetry),
    simulator_telemetry: data.simulator_telemetry.map((item) => {
      const row = record(item);
      const counter = typeof row.cumulative_wh_exact === "string" ? row.cumulative_wh_exact :
        Number.isSafeInteger(row.cumulative_wh) ? String(row.cumulative_wh) : null;
      if (typeof row.event_id !== "string" || counter === null || !/^\d+$/.test(counter) ||
          typeof row.measured_at !== "string" || typeof row.received_at !== "string" ||
          typeof row.classification !== "string") throw new Error("Invalid telemetry row.");
      return { event_id: row.event_id, cumulative_wh: counter, measured_at: row.measured_at,
        received_at: row.received_at, classification: row.classification };
    }),
  };
}

export function parseLoans(payload: unknown): Loan[] {
  const data = record(payload);
  if (!Array.isArray(data.loans)) throw new Error("Loan history is unavailable.");
  return data.loans.map((item) => {
    const loan = record(item);
    if (typeof loan.id !== "number" || typeof loan.loan_id !== "string" ||
        typeof loan.status !== "string" || !Array.isArray(loan.repayments)) {
      throw new Error("Invalid loan record.");
    }
    return {
      id: loan.id, loan_id: loan.loan_id, status: loan.status,
      amount_approved_ugx: loan.amount_approved_ugx == null ? null : exactDecimal(loan.amount_approved_ugx),
      outstanding_ugx: loan.outstanding_ugx == null ? null : exactDecimal(loan.outstanding_ugx),
      due_at: typeof loan.due_at === "string" ? loan.due_at : null,
      repayments: loan.repayments.map((item) => {
        const row = record(item);
        if (typeof row.id !== "number" || typeof row.status !== "string" ||
            typeof row.paid_at !== "string") throw new Error("Invalid repayment record.");
        return {
          id: row.id, status: row.status, received_ugx: exactDecimal(row.received_ugx),
          applied_ugx: row.applied_ugx == null ? null : exactDecimal(row.applied_ugx),
          excess_ugx: row.excess_ugx == null ? null : exactDecimal(row.excess_ugx),
          paid_at: row.paid_at,
        };
      }),
    };
  });
}

function parseLabTelemetry(value: unknown): LabTelemetry[] {
  if (value === undefined) return []; // Compatible with older hosted backend.
  if (!Array.isArray(value)) throw new Error("AC lab history is unavailable.");
  const count = (v: unknown) => {
    if (typeof v !== "string" || !/^[0-9]+$/.test(v)) throw new Error("Invalid lab measurement.");
    return v;
  };
  return value.map(item => {
    const row = record(item);
    if (typeof row.boot_id !== "string" || typeof row.measured_at !== "string" ||
        typeof row.received_at !== "string" || !["OK", "FAULT"].includes(String(row.sensor_status)))
      throw new Error("Invalid lab measurement.");
    const optionalMetric = (v: unknown) => v == null ? null : count(v);
    const outputCommand = ["ON", "OFF", "UNKNOWN"].includes(String(row.output_command))
      ? row.output_command as "ON" | "OFF" | "UNKNOWN" : "UNKNOWN";
    const faultStatus = typeof row.fault_status === "string" ? row.fault_status :
      row.sensor_status === "OK" ? "OK" : "SENSOR_UNAVAILABLE";
    return { boot_id: row.boot_id, sequence: count(row.sequence), measured_at: row.measured_at,
      received_at: row.received_at, consumed_uwh: row.consumed_uwh === null ? null : count(row.consumed_uwh),
      remaining_credit_uwh: count(row.remaining_credit_uwh), uncertain_uwh: count(row.uncertain_uwh),
      pzem_wh: row.pzem_wh === null ? null : count(row.pzem_wh), sensor_status: row.sensor_status as "OK" | "FAULT",
      voltage_mv: optionalMetric(row.voltage_mv), current_ma: optionalMetric(row.current_ma),
      power_mw: optionalMetric(row.power_mw), frequency_cHz: optionalMetric(row.frequency_cHz),
      power_factor_pct: optionalMetric(row.power_factor_pct),
      output_command: outputCommand, fault_status: faultStatus };
  });
}

/** Exact display conversion only: 1 Wh = 1,000,000 microWh. Never authoritative accounting. */
export function microWhDisplay(value: string | null | undefined): string {
  if (value == null || !/^[0-9]+$/.test(value)) return "Unavailable";
  const amount = BigInt(value);
  const fraction = (amount % 1_000_000n).toString().padStart(6, "0").replace(/0+$/, "");
  return `${amount / 1_000_000n}${fraction ? "." + fraction : ""} Wh`;
}

export function labReadingStatus(reading: AllocationStatus, now: number): "RECENT" | "STALE" | "UNAVAILABLE" {
  if (reading.contact_status === "UNAVAILABLE" || !reading.last_measurement_at || !reading.lab_received_at) return "UNAVAILABLE";
  const measured = Date.parse(reading.last_measurement_at), received = Date.parse(reading.lab_received_at);
  if (!Number.isFinite(measured) || !Number.isFinite(received)) return "UNAVAILABLE";
  return reading.contact_status === "STALE" || Math.abs(now - measured) > 90_000 || now - received > 90_000 ? "STALE" : "RECENT";
}
