export type MeterArchitecture = "STS" | "AMI";

export interface UserMeter {
  meter_number: string;
  static_ip: string | null;
  units: number;
  architecture: MeterArchitecture;
  pending_units: number;
  status: string;
  label: string;
  has_iot_token?: boolean;
}
