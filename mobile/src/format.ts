/** Display formatting only. Financial calculations stay on the server. */
function decimalText(value: string | null | undefined): string | null {
  if (value == null || !/^-?\d+(?:\.\d+)?$/.test(value.trim())) return null;
  const [whole, fraction] = value.trim().split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return grouped + (fraction && /[1-9]/.test(fraction) ? `.${fraction}` : "");
}
export function energy(value: string | null | undefined): string {
  const formatted = decimalText(value);
  return formatted == null ? "Unavailable" : `${formatted.includes(".") ? formatted : `${formatted}.00`} kWh`;
}
export function ugx(value: string | null | undefined): string {
  const formatted = decimalText(value);
  return formatted == null ? "Unavailable" : `UGX ${formatted}`;
}
export function dateTime(value: string | null | undefined): string {
  if (!value) return "Unavailable";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Unavailable" : date.toLocaleString();
}
