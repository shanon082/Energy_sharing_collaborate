import "server-only";
import { API_URL } from "@/common/constants/api";
import {
  DISABLED_FEATURES, Feature, featureDisabledPayload, featureForApiPath,
  parseFeatureAvailability,
} from "./features";

export async function getFeatureAvailability() {
  try {
    const response = await fetch(`${API_URL}/features/`, {
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    if (response.ok) return parseFeatureAvailability((await response.json()).features);
  } catch {
    // An unavailable/older backend must not expose deferred actions.
  }
  return { ...DISABLED_FEATURES };
}

export async function disabledFeature(feature: Feature) {
  return (await getFeatureAvailability())[feature] ? null : featureDisabledPayload(feature);
}

export async function disabledApiFeature(path: string) {
  const feature = featureForApiPath(path);
  return feature ? disabledFeature(feature) : null;
}
