"use client";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { SelectedMeterProvider } from "../../contexts/selected-meter-context";
import { consumerScreen } from "../../lib/consumer-parity";

/** The redesigned workspace must never bootstrap legacy wallet/core balances. */
export function ConsumerMeterBoundary({ children }: { children: ReactNode }) {
  const path = usePathname().replace(/\/$/, "");
  return consumerScreen(path) ? children : <SelectedMeterProvider>{children}</SelectedMeterProvider>;
}
