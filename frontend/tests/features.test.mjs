import test from "node:test";
import assert from "node:assert/strict";
import {
  DISABLED_FEATURES,
  featureForApiPath,
  parseFeatureAvailability,
} from "../src/lib/features.ts";

test("server availability is the only way to expose deferred controls", () => {
  assert.deepEqual(parseFeatureAvailability(null), DISABLED_FEATURES);
  assert.equal(parseFeatureAvailability({ peer_sharing: "true" }).peer_sharing, false);
  assert.equal(parseFeatureAvailability({ peer_sharing: true }).peer_sharing, true);
});

test("optional web action and proxy paths are guarded, including old aliases", () => {
  const expected = {
    "share/receiver-preview/": "peer_sharing",
    "share/share-units/": "peer_sharing",
    "meter/send-units/": "peer_sharing",
    "meter/receive-units/": "peer_sharing",
    "share/transfer-units/": "meter_transfers",
    "/transfer-units/": "meter_transfers",
    "loans/pay-for-someone/": "third_party_repayment",
    "loans/lookup-by-phone/?phone=123": "third_party_repayment",
    "wallet/deposit/": "wallet_deposits",
    "wallet/withdraw/": "wallet_withdrawals",
    "ussd/entry/": "ussd",
    "ussd/phones/": "ussd",
  };
  for (const [path, feature] of Object.entries(expected)) {
    assert.equal(featureForApiPath(path), feature, path);
  }
});

test("required web navigation API paths remain available", () => {
  for (const path of [
    "meter/apply-wallet-units/",
    "meter/generate-token/",
    "meter/load-token/",
    "loans/repay/1/",
    "transactions/history/",
    "wallet/balance/",
    "meter/my-meter/",
    "loans/my-loans/",
  ]) {
    assert.equal(featureForApiPath(path), undefined, path);
  }
});
