"use client";

import { cn } from "@/lib/utils";

interface SegmentedOption {
  label: string;
  value: string;
  disabled?: boolean;
}

interface SegmentedSelectorProps {
  options: SegmentedOption[];
  value: string;
  onChange: (value: string) => void;
  className?: string;
}

export function SegmentedSelector({ options, value, onChange, className }: SegmentedSelectorProps) {
  return (
    <div className={cn("flex gap-2 flex-wrap", className)}>
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          disabled={opt.disabled}
          onClick={() => !opt.disabled && onChange(opt.value)}
          className={cn(
            "px-4 py-1.5 rounded-full text-sm font-medium border transition-all",
            value === opt.value
              ? "bg-primary text-primary-foreground border-primary shadow-sm"
              : "bg-background text-foreground border-border hover:border-primary/60 hover:text-primary",
            opt.disabled && "opacity-40 cursor-not-allowed"
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
