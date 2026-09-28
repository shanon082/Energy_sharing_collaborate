"use client";

import { Zap, Wifi } from "lucide-react";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

export type MeterArchitecture = "STS" | "AMI";

interface MeterArchitecturePickerProps {
  value: MeterArchitecture;
  onChange: (arch: MeterArchitecture) => void;
  disabled?: boolean;
}

export default function MeterArchitecturePicker({
  value,
  onChange,
  disabled = false,
}: MeterArchitecturePickerProps) {
  return (
    <div className="space-y-2">
      <Label>
        Meter platform <span className="text-destructive">*</span>
      </Label>
      <p className="text-xs text-muted-foreground">
        Choose the platform that matches your physical meter. You can register multiple meters
        (e.g. rental units) under one login.
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <button
          type="button"
          onClick={() => onChange("STS")}
          disabled={disabled}
          className={cn(
            "rounded-lg border-2 p-4 text-left transition-colors",
            value === "STS"
              ? "border-blue-500 bg-blue-50 dark:bg-blue-950"
              : "border-border hover:border-blue-300"
          )}
        >
          <div className="flex items-center gap-2 mb-1">
            <Zap className="h-4 w-4 text-amber-500" />
            <span className="font-semibold text-sm">STS platform</span>
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Token-based prepaid meter. You must generate a token and enter it on the meter keypad
            to load units.
          </p>
        </button>
        <button
          type="button"
          onClick={() => onChange("AMI")}
          disabled={disabled}
          className={cn(
            "rounded-lg border-2 p-4 text-left transition-colors",
            value === "AMI"
              ? "border-blue-500 bg-blue-50 dark:bg-blue-950"
              : "border-border hover:border-blue-300"
          )}
        >
          <div className="flex items-center gap-2 mb-1">
            <Wifi className="h-4 w-4 text-blue-500" />
            <span className="font-semibold text-sm">AMI platform</span>
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Networked smart meter. Units apply automatically — no token entry required.
          </p>
        </button>
      </div>
    </div>
  );
}
