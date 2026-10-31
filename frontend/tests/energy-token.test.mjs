import test from "node:test";
import assert from "node:assert/strict";
import { parseEnergyTokens } from "../src/lib/energy-token.ts";

const token = (value) => ({
  id: "token-1",
  allocation_id: 5,
  token: value,
  meter_number: "00000001234",
  energy_wh: "10000",
  energy_kwh: "10.00",
  environment: "UGX_DEMO",
  source: "PURCHASE",
  source_reference: "receipt-1",
  state: "ISSUED",
  application_environment: "UNCONFIRMED",
  created_at: "2026-10-25T00:00:00Z",
});

test("web token parser accepts exactly 15 digits for the matching allocation", () => {
  assert.equal(parseEnergyTokens({ tokens: [token("123456789012345")] }, 5)[0].token.length, 15);
  assert.throws(() => parseEnergyTokens({ tokens: [token("12345678901234")] }, 5), /Invalid electricity token/);
  assert.throws(() => parseEnergyTokens({ tokens: [token("1234567890123456")] }, 5), /Invalid electricity token/);
  assert.throws(() => parseEnergyTokens({ tokens: [token("123456789012345")] }, 6), /Invalid electricity token/);
});
