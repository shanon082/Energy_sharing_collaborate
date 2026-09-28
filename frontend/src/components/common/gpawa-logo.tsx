"use client";

import Image from "next/image";
import Link from "next/link";
import { cn } from "@/lib/utils";

/** Real logo mark from logo.jpeg — transparent PNG, works in light & dark mode */
const LOGO_MARK_SRC = "/gpawa-logo-mark.png";

export const LOGO_SIZES = {
  header: { logoSize: 44, textSize: "xl" as const },
  sidebar: { logoSize: 40, textSize: "lg" as const },
  compact: { logoSize: 36, textSize: "base" as const },
} as const;

interface LogoMarkProps {
  size?: number;
  className?: string;
}

export function GpawaLogoMark({ size = 36, className }: LogoMarkProps) {
  return (
    <Image
      src={LOGO_MARK_SRC}
      alt="gPawa"
      width={size}
      height={size}
      priority
      className={cn("shrink-0 object-contain", className)}
      style={{ width: size, height: size }}
    />
  );
}

interface LogoProps {
  href?: string;
  textSize?: "sm" | "base" | "lg" | "xl";
  showText?: boolean;
  logoSize?: number;
  className?: string;
  /** Shown beside the mark when showText is false (e.g. admin "Administrator") */
  suffix?: string;
  /** Use sidebar tokens so suffix stays readable on admin nav (light & dark) */
  suffixVariant?: "default" | "sidebar";
}

export function GpawaLogo({
  href = "/",
  textSize = "base",
  showText = true,
  logoSize = 36,
  className,
  suffix,
  suffixVariant = "default",
}: LogoProps) {
  const textClass = {
    sm: "text-sm",
    base: "text-base",
    lg: "text-lg",
    xl: "text-xl",
  }[textSize];

  const inner = (
    <span className={cn("flex items-center gap-2.5", className)}>
      <GpawaLogoMark size={logoSize} />
      {showText && (
        <span
          className={cn(
            "font-bold tracking-tight font-[family-name:var(--font-display)]",
            textClass
          )}
        >
          <span className="text-blue-600 dark:text-blue-400">g</span>
          <span className="text-gray-900 dark:text-white">Pawa</span>
        </span>
      )}
      {!showText && suffix && (
        <span
          className={cn(
            "font-semibold tracking-tight",
            textClass,
            suffixVariant === "sidebar"
              ? "gpawa-sidebar-brand"
              : "text-foreground"
          )}
        >
          {suffix}
        </span>
      )}
      {showText && suffix && (
        <span className="text-sm font-medium text-muted-foreground">{suffix}</span>
      )}
    </span>
  );

  return href ? <Link href={href}>{inner}</Link> : inner;
}
