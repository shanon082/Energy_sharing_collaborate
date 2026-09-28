"use client";

import { Zap, Wifi } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { useSelectedMeter } from "@/contexts/selected-meter-context";
import { cn } from "@/lib/utils";

interface MeterSelectorProps {
  className?: string;
  showWhenSingle?: boolean;
}

export default function MeterSelector({ className, showWhenSingle = true }: MeterSelectorProps) {
  const { meters, selectedMeter, setSelectedMeterNo, isLoading } = useSelectedMeter();

  if (isLoading || meters.length === 0) return null;
  if (!showWhenSingle && meters.length < 2) return null;

  return (
    <div className={cn("space-y-1.5", className)}>
      <Label className="text-sm text-muted-foreground">Active meter</Label>
      <Select
        value={selectedMeter?.meter_number ?? ""}
        onValueChange={setSelectedMeterNo}
      >
        <SelectTrigger className="w-full max-w-sm">
          <SelectValue placeholder="Select meter" />
        </SelectTrigger>
        <SelectContent>
          {meters.map((m) => (
            <SelectItem key={m.meter_number} value={m.meter_number}>
              <span className="flex items-center gap-2">
                {m.architecture === "AMI" ? (
                  <Wifi className="h-3.5 w-3.5 text-blue-500" />
                ) : (
                  <Zap className="h-3.5 w-3.5 text-amber-500" />
                )}
                <span className="font-mono">{m.meter_number}</span>
                {m.label && m.label !== "Home" && (
                  <span className="text-muted-foreground">— {m.label}</span>
                )}
                <span className="text-muted-foreground">({m.architecture})</span>
              </span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
