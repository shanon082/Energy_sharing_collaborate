"use client";

import { Lock } from "lucide-react";
import { Input } from "@/components/ui/input";

export const PIN_LENGTH = 4;

interface PinInputProps {
  value: string;
  onChange: (pin: string) => void;
  disabled?: boolean;
  label?: string;
  hint?: string;
  id?: string;
  autoFocus?: boolean;
  onEnter?: () => void;
}

/**
 * Reusable transaction-PIN field used as the final authentication step before
 * buying, sharing, or requesting a loan. Numeric, masked, fixed length.
 */
export function PinInput({
  value,
  onChange,
  disabled,
  label = "Transaction PIN",
  hint = "Enter your 4-digit PIN to authorise this action.",
  id = "transaction-pin",
  autoFocus,
  onEnter,
}: PinInputProps) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium flex items-center gap-2" htmlFor={id}>
        <Lock className="h-3.5 w-3.5" />
        {label}
      </label>
      <Input
        id={id}
        type="password"
        inputMode="numeric"
        autoComplete="off"
        placeholder="••••"
        maxLength={PIN_LENGTH}
        value={value}
        disabled={disabled}
        autoFocus={autoFocus}
        onChange={(e) => onChange(e.target.value.replace(/\D/g, "").slice(0, PIN_LENGTH))}
        onKeyDown={(e) => {
          if (e.key === "Enter" && onEnter && value.length === PIN_LENGTH) {
            e.preventDefault();
            onEnter();
          }
        }}
        className="text-center text-2xl tracking-[0.6em] font-mono"
      />
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}
