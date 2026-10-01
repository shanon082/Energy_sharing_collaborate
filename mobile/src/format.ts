export function energy(value: string | null | undefined): string {
  return value == null ? "Unavailable" : `${value} kWh`;
}

export function ugx(value: string | null | undefined): string {
  return value == null ? "Unavailable" : `UGX ${value}`;
}

export function dateTime(value: string | null | undefined): string {
  if (!value) return "Unavailable";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Unavailable" : date.toLocaleString();
}
