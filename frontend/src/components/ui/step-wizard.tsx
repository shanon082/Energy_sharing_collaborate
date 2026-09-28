"use client";

import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface Step {
  label: string;
}

interface StepWizardProps {
  steps: Step[];
  currentStep: number; // 0-indexed
  className?: string;
}

export function StepWizard({ steps, currentStep, className }: StepWizardProps) {
  return (
    <div className={cn("flex items-center w-full", className)}>
      {steps.map((step, i) => {
        const isCompleted = i < currentStep;
        const isActive = i === currentStep;

        return (
          <div key={i} className="flex items-center flex-1">
            {/* Circle */}
            <div className="flex flex-col items-center gap-1 shrink-0">
              <div
                className={cn(
                  "w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold transition-all",
                  isCompleted && "gpawa-gradient text-white",
                  isActive && "border-2 border-primary text-primary bg-primary/10",
                  !isCompleted && !isActive && "border-2 border-border text-muted-foreground bg-background"
                )}
              >
                {isCompleted ? <Check className="w-4 h-4" /> : <span>{i + 1}</span>}
              </div>
              <span
                className={cn(
                  "text-[11px] font-medium text-center leading-tight max-w-[60px]",
                  isActive ? "text-primary" : isCompleted ? "text-foreground" : "text-muted-foreground"
                )}
              >
                {step.label}
              </span>
            </div>

            {/* Connector line */}
            {i < steps.length - 1 && (
              <div
                className={cn(
                  "flex-1 h-[2px] mx-2 mt-[-14px] rounded-full transition-all",
                  isCompleted ? "gpawa-gradient" : "bg-border"
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
