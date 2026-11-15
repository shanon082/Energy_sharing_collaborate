import test from "node:test";
import assert from "node:assert/strict";
import { exactDifference, exactSum, formatEnergy, formatMoney, meterReadEnvironment } from "../src/lib/sandbox-presentation.ts";

test("loan applied repayments and outstanding preserve server precision", () => {
  const principal = "5000.00";
  const totalDue = "5250.00";
  const applied = "2500.00";
  const outstanding = exactDifference(totalDue, applied);

  assert.equal(principal, "5000.00");
  assert.equal(outstanding, "2750");
  assert.equal(formatMoney(outstanding, "UGX"), "UGX 2,750");
  assert.equal(exactDifference("10.55", "2.50"), "8.05");
  assert.equal(exactDifference("1.00", "1.01"), null);
});

test("successful empty totals are distinct from invalid or missing values", () => {
  assert.equal(exactSum([]), "0");
  assert.equal(exactSum(["2500", "0.25"]), "2500.25");
  assert.equal(exactSum(["2500", null]), null);
  assert.equal(formatMoney(null, "UGX"), "Unavailable");
});

test("energy values are formatted without inventing missing readings", () => {
  assert.equal(formatEnergy("8.95"), "8.95 kWh");
  assert.equal(formatEnergy("8"), "8.00 kWh");
  assert.equal(formatEnergy(null), "Unavailable");
});

test("meter balance reads use the API's allocation environment names", () => {
  assert.equal(meterReadEnvironment("UGX_DEMO"), "UGX_DEMO");
  assert.equal(meterReadEnvironment("MTN_SANDBOX"), "SANDBOX");
  assert.equal(meterReadEnvironment("CORE"), "CORE");
});
