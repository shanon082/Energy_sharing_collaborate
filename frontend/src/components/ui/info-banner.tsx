import { Info } from "lucide-react";
import { cn } from "@/lib/utils";

interface InfoBannerProps {
  children: React.ReactNode;
  variant?: "info" | "warning";
  className?: string;
}

export function InfoBanner({ children, variant = "info", className }: InfoBannerProps) {
  return (
    <div
      className={cn(
        "flex items-start gap-2 rounded-lg px-3 py-2.5 text-sm",
        variant === "info" && "bg-primary/8 text-primary border border-primary/20",
        variant === "warning" && "bg-amber-50 text-amber-800 border border-amber-200 dark:bg-amber-950/30 dark:text-amber-300 dark:border-amber-800/40",
        className
      )}
    >
      <Info className="w-4 h-4 mt-0.5 shrink-0" />
      <span>{children}</span>
    </div>
  );
}
