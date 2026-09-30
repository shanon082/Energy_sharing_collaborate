"use client";

import { createContext, useContext, ReactNode } from "react";
import { DISABLED_FEATURES, FeatureAvailability } from "@/lib/features";

const FeaturesContext = createContext<FeatureAvailability>(DISABLED_FEATURES);

export function FeaturesProvider({ features, children }: {
  features: FeatureAvailability;
  children: ReactNode;
}) {
  return <FeaturesContext.Provider value={features}>{children}</FeaturesContext.Provider>;
}

export const useFeatures = () => useContext(FeaturesContext);
