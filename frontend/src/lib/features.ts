/** Public availability is supplied by Django; this module contains no overrides. */
export const DISABLED_FEATURES = {
  peer_sharing: false,
  meter_transfers: false,
  third_party_repayment: false,
  ussd: false,
  wallet_deposits: false,
  wallet_withdrawals: false,
  external_crb: false,
};

export type Feature = keyof typeof DISABLED_FEATURES;
export type FeatureAvailability = Record<Feature, boolean>;

export function parseFeatureAvailability(value: unknown): FeatureAvailability {
  const values = value && typeof value === "object" ? value as Record<string, unknown> : {};
  return Object.fromEntries(
    Object.keys(DISABLED_FEATURES).map((key) => [key, values[key] === true]),
  ) as FeatureAvailability;
}

export function featureDisabledPayload(feature: Feature) {
  return {
    code: "FEATURE_DISABLED" as const,
    feature,
    message: "This feature is currently disabled. Existing records remain available.",
  };
}

/** Only new optional entry points. History, settlement and own-meter loads stay open. */
export function featureForApiPath(path: string): Feature | undefined {
  const normalized = path.split(/[?#]/)[0].replace(/^\/+|\/+$/g, "").replace(/^api\/v1\//, "");
  if (normalized === "ussd" || normalized.startsWith("ussd/")) return "ussd";
  const paths: Record<string, Feature> = {
    "share/share-units": "peer_sharing",
    "share/receiver-preview": "peer_sharing",
    "meter/send-units": "peer_sharing",
    "meter/receive-units": "peer_sharing",
    "share/transfer-units": "meter_transfers",
    "transfer-units": "meter_transfers", // old frontend alias
    "loans/pay-for-someone": "third_party_repayment",
    "loans/lookup-by-phone": "third_party_repayment",
    "wallet/deposit": "wallet_deposits",
    "wallet/withdraw": "wallet_withdrawals",
  };
  return paths[normalized];
}
