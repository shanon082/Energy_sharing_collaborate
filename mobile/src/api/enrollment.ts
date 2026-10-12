export type MeterRequest = {
  id: string; meter_number: string; requested_at: string;
  status: "PENDING" | "LINKED" | "SELF_DECLARED" | "REJECTED" | "ASSIGNMENT_UNAVAILABLE";
  decision_reason?: string | null;
};

export function enrollmentLabel(status: MeterRequest["status"]): string {
  switch (status) {
    case "SELF_DECLARED": return "Linked for prototype testing — self-declared";
    case "LINKED": return "Assigned";
    case "REJECTED": return "Request declined";
    case "ASSIGNMENT_UNAVAILABLE": return "Assignment unavailable — contact staff";
    default: return "Awaiting staff verification";
  }
}
