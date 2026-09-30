import { ReactNode } from "react";
import { disabledFeature } from "@/lib/features-server";
import FeatureUnavailable from "@/components/common/feature-unavailable";

export default async function UssdLayout({ children }: { children: ReactNode }) {
  if (await disabledFeature("ussd")) return <FeatureUnavailable />;
  return children;
}
