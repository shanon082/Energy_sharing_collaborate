export type MeterInfo = {
  meter_number: string;
  label: string;
  architecture: string;
  status: string;
};

export type AllocationStatus = {
  unit: "kWh";
  available_kwh: string;
  pending_kwh: string;
  confirmed_kwh: string;
  last_meter_contact: string | null;
  delivery_environment: "SIMULATOR" | "UNAVAILABLE";
};

export type DailyUsage = { date: string; kwh: string; source: string };
export type Telemetry = {
  event_id: string; cumulative_wh: number; measured_at: string;
  received_at: string; classification: string;
};
export type ConsumptionHistory = {
  meter_no: string; daily_usage: DailyUsage[]; simulator_telemetry: Telemetry[];
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
  return data.meters.map((item) => {
    const meter = record(item);
    if (typeof meter.meter_number !== "string" || !meter.meter_number ||
        typeof meter.architecture !== "string" || typeof meter.status !== "string") {
      throw new Error("Invalid meter record.");
    }
    return {
      meter_number: meter.meter_number,
      label: typeof meter.label === "string" && meter.label ? meter.label : meter.meter_number,
      architecture: meter.architecture,
      status: meter.status,
    };
  });
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

export function parseConsumption(payload: unknown): ConsumptionHistory {
  const data = record(payload);
  if (typeof data.meter_no !== "string" || !Array.isArray(data.daily_usage) ||
      !Array.isArray(data.simulator_telemetry)) throw new Error("Consumption history is unavailable.");
  return {
    meter_no: data.meter_no,
    daily_usage: data.daily_usage.map((item) => {
      const row = record(item);
      if (typeof row.date !== "string" || typeof row.source !== "string") throw new Error("Invalid usage row.");
      return { date: row.date, kwh: exactDecimal(row.kwh), source: row.source };
    }),
    simulator_telemetry: data.simulator_telemetry.map((item) => {
      const row = record(item);
      if (typeof row.event_id !== "string" || typeof row.cumulative_wh !== "number" ||
          typeof row.measured_at !== "string" || typeof row.received_at !== "string" ||
          typeof row.classification !== "string") throw new Error("Invalid telemetry row.");
      return row as Telemetry;
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
