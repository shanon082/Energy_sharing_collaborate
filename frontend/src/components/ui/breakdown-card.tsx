import { cn } from "@/lib/utils";

interface BreakdownRow {
  label: string;
  value: string;
  muted?: boolean;
}

interface BreakdownCardProps {
  rows: BreakdownRow[];
  totalLabel: string;
  totalValue: string;
  subline?: string;   // e.g. "Estimated yield: 7.84 kWh"
  className?: string;
}

export function BreakdownCard({ rows, totalLabel, totalValue, subline, className }: BreakdownCardProps) {
  return (
    <div className={cn("rounded-xl border border-border bg-card overflow-hidden", className)}>
      <div className="p-4 space-y-2">
        {rows.map((row, i) => (
          <div key={i} className="flex justify-between items-center text-sm">
            <span className={cn("text-muted-foreground", row.muted && "opacity-70")}>{row.label}</span>
            <span className={cn("font-medium tabular-nums", row.muted && "opacity-70")}>{row.value}</span>
          </div>
        ))}
      </div>

      <div className="border-t border-border px-4 py-3 flex justify-between items-center">
        <span className="font-semibold text-sm">{totalLabel}</span>
        <span className="gpawa-gradient-text font-bold text-base tabular-nums">{totalValue}</span>
      </div>

      {subline && (
        <div className="bg-muted/50 px-4 py-2 flex items-center gap-2 text-xs text-muted-foreground">
          <span className="text-primary">ℹ</span>
          {subline}
        </div>
      )}
    </div>
  );
}
