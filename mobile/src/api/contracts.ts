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
  delivery_environment: "SIMULATOR" | "UNAVAILABLE";
  contact_source?: "SIMULATOR" | "UNAVAILABLE";
  contact_status?: "UNAVAILABLE" | "STALE" | "RECENT";
  simulator_remaining_wh?: string | null;
  meter_reported_remaining_wh?: string | null;
  reported_relay_state?: string | null;
  last_measurement_at?: string | null;
  consumption_reconciliation_required?: boolean;
};

export type DailyUsage = { date: string; kwh: string; source: string };
export type Telemetry = {
  event_id: string; cumulative_wh: string; measured_at: string;
  received_at: string; classification: string;
};
export type ConsumptionHistory = {
  meter_no: string; daily_usage: DailyUsage[]; simulator_telemetry: Telemetry[];
  consumer_attribution_available: boolean;
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
      !["SIMULATOR", "UNAVAILABLE"].includes(String(data.contact_source))) {
    throw new Error("Meter dashboard is unavailable.");
  }
  const optionalWh = (value: unknown) => value == null ? null :
    typeof value === "string" && /^[0-9]+$/.test(value) ? value : (() => { throw new Error("Invalid meter credit reading."); })();
  return { ...parseAllocation(data), contact_source: data.contact_source as AllocationStatus["contact_source"],
    contact_status: ["UNAVAILABLE", "STALE", "RECENT"].includes(String(data.contact_status))
      ? data.contact_status as AllocationStatus["contact_status"] : "UNAVAILABLE",
    simulator_remaining_wh: optionalWh(data.simulator_remaining_wh),
    meter_reported_remaining_wh: optionalWh(data.meter_reported_remaining_wh),
    reported_relay_state: ["OPEN", "CLOSED", "UNKNOWN"].includes(String(data.reported_relay_state))
      ? String(data.reported_relay_state) : null,
    last_measurement_at: typeof data.last_measurement_at === "string" ? data.last_measurement_at : null,
    consumption_reconciliation_required: data.consumption_reconciliation_required === true,
  };
}

export function parseAllocation(payload: unknown): AllocationStatus {
  const data = record(payload);
  if (data.unit !== "kWh" || !["SIMULATOR", "UNAVAILABLE"].includes(String(data.delivery_environment))) {
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
