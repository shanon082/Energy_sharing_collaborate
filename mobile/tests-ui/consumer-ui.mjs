// Run against the local Vite server. All API traffic is intercepted; no Django,
// provider, account or physical device is contacted. Playwright can be installed
// separately and supplied via PLAYWRIGHT_MODULE without changing web packages.
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || "playwright");
const base = process.env.MOBILE_UI_URL || "http://127.0.0.1:5173";
assert.ok(["127.0.0.1", "localhost"].includes(new URL(base).hostname), "Use a local test server");
const shots = process.env.MOBILE_UI_SCREENSHOTS;
if (shots) await mkdir(shots, { recursive: true });
const browser = await chromium.launch({ headless: true,
  ...(process.env.PLAYWRIGHT_EXECUTABLE_PATH ? { executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH } : {}) });
let checks = 0;
try {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, deviceScaleFactor: 1 });
  const page = await context.newPage();
  page.setDefaultTimeout(30000);
  const errors = [];
  const calls = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const user = { id: 9001, email: "ui@example.invalid", first_name: "UI", last_name: "Test", user_role: "CLIENT", email_verified: true };
  let loginAccepted = false;
  const homeMeter = { id: 7, meter_number: "UI-METER-7", label: "Home meter", architecture: "AMI", status: "ACTIVE" };
  const shopMeter = { id: 8, meter_number: "UI-METER-8", label: "Shop meter", architecture: "STS", status: "SUSPENDED" };
  let liveMeters = [homeMeter, shopMeter];
  let selfEnrollment = false;
  let failProfile = false;
  let detailsAvailable = true;
  let detailsValues = { account_number: "EN-TEST", address: null, energy_preference: null, payment_method: null };
  const detailsChoices = { energy_preference: [{ value: "HYDRO", label: "Hydro" }], payment_method: [{ value: "MOBILE_MONEY", label: "Mobile Money" }] };
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    calls.push({ path, method: route.request().method() });
    let status = 200;
    let body = {};
    if (path.endsWith("auth/login/")) {
      assert.equal(route.request().method(), "POST");
      body = loginAccepted ? { access: "ui-test-access", refresh: "ui-test-refresh", user } : { detail: "Invalid credentials." };
      if (!loginAccepted) status = 401;
    } else if (path.endsWith("auth/mobile-account/")) body = user;
    else if (path.endsWith("auth/mobile-profile/")) {
      if (failProfile) { await route.abort("failed"); return; }
      body = { values: { monthly_income: null }, choices: { monthly_income: [{ value: "TEST", label: "Test category" }] }, complete_for_scoring: false };
    } else if (path.endsWith("auth/mobile-account-details/")) {
      if (failProfile) { await route.abort("failed"); return; }
      if (route.request().method() === "PATCH") {
        const update = route.request().postDataJSON();
        assert.deepEqual(Object.keys(update).sort(), ["address", "energy_preference", "payment_method"]);
        detailsValues = { ...detailsValues, ...update };
      }
      body = { details_available: detailsAvailable, values: detailsAvailable ? detailsValues : null, choices: detailsChoices };
    } else if (path.endsWith("meter/mobile-onboarding/")) {
      body = { needs_meter: !liveMeters.length, meters: liveMeters, requests: [], phone_ownership_verified: false,
        sandbox_self_enrollment: selfEnrollment };
    } else if (path.endsWith("meter/sandbox-meter-enrollment/")) {
      assert.equal(route.request().method(), "POST");
      const input = route.request().postDataJSON();
      assert.deepEqual(input, { meter_no: "000245" });
      const declared = { id: 24, meter_number: input.meter_no, label: "Prototype meter", architecture: "AMI", status: "ACTIVE",
        sandbox_inventory: true, ownership_provenance: "SELF_DECLARED", enrolled_at: "2026-10-13T00:00:00Z", hardware_connection: "PENDING" };
      liveMeters = [declared];
      body = { success: true, status: "SELF_DECLARED", meter: declared,
        message: "Meter linked for prototype testing. Ownership and live readings are not verified with the electricity provider." };
      status = 201;
    } else if (path.endsWith("meter/mobile-meter-requests/")) {
      assert.equal(route.request().method(), "POST");
      assert.deepEqual(Object.keys(route.request().postDataJSON()), ["meter_no"]);
      body = { success: true, status: "PENDING", request_id: "ui-pending-request", message: "Request recorded; staff verification is required." }; status = 202;
    } else if (path.endsWith("transactions/mobile-payment-recovery/")) {
      body = { pending: false, receipt: null, provider_polled: false, status_source: "STORED_VERIFIED_SETTLEMENT" };
    } else if (path.endsWith("meter/mobile-meters/")) {
      body = { success: true, data: { has_meter: Boolean(liveMeters.length), meters: liveMeters } };
    } else if (/meter\/mobile-meters\/\d+\/$/.test(path)) {
      const id = Number(path.split("/").at(-2));
      const selected = liveMeters.find((meter) => meter.id === id);
      if (!selected) { status = 404; body = { detail: "Not found." }; }
      else body = { meter: selected, unit: "kWh", quantum_kwh: "0.01", available_kwh: id === 7 ? "1.50" : "2.50",
        pending_kwh: "0.31", confirmed_kwh: "0.20", delivery_environment: "UNAVAILABLE", contact_source: "UNAVAILABLE", last_meter_contact: null };
    } else if (path.endsWith("loans/mobile-overview/")) body = { loans: [] };
    else if (path.endsWith("meter/mobile-consumption/")) body = { meter: liveMeters.find((row) => row.id === Number(new URL(route.request().url()).searchParams.get("meter_id"))), meter_no: new URL(route.request().url()).searchParams.get("meter_no"), daily_usage: [], simulator_telemetry: [], consumer_attribution_available: false };
    else if (path.endsWith("meter/mobile-deliveries/")) body = { meter: liveMeters.find((row) => row.id === Number(new URL(route.request().url()).searchParams.get("meter_id"))), meter_no: new URL(route.request().url()).searchParams.get("meter_no"), deliveries: [], pagination: { has_more: false, next_before_id: null } };
    else if (path.endsWith("transactions/mobile-receipts/")) body = { receipts: [], pagination: { has_more: false, next_before_id: null } };
    else if (path.endsWith("transactions/mobile-history/")) body = { transactions: [], pagination: { has_more: false, next_before_id: null } };
    else if (path.endsWith("meter/mobile-notifications/")) body = { notifications: [], pagination: { has_more: false, next_before_id: null }, unread_count: 0 };
    else if (path.endsWith("auth/register/")) {
      const input = route.request().postDataJSON();
      assert.equal(input.gender, "FEMALE");
      assert.equal(input.password, input.confirm_password);
      body = { message: "Check your email" }; status = 201;
    } else if (path.endsWith("features/")) body = { features: {}, mobile_actions: {} };
    else if (path.endsWith("auth/mobile-logout/")) status = 204;
    else body = [];
    await route.fulfill({ status, contentType: "application/json", body: status === 204 ? "" : JSON.stringify(body) });
  });
  async function shot(name) {
    if (shots) await page.screenshot({ path: `${shots}/${name}.png`, fullPage: true });
  }
  async function layout(name) {
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    assert.equal(overflow, false, `${name}: no horizontal overflow`);
    await shot(name);
  }
  async function tab(name) {
    await page.getByRole("navigation").getByRole("button", { name, exact: true }).click();
  }
  await page.goto(base);
  await page.getByRole("heading", { name: "Your power. Your possibilities." }).waitFor();
  await layout("welcome");
  assert.equal(calls.length, 0, "Welcome works without account/API requests");
  checks++;

  await page.getByRole("button", { name: /Already have an account/ }).click();
  await page.getByLabel("Email address").fill(user.email);
  await page.locator('input[type="password"]').fill("isolated-test-only");
  await page.getByRole("button", { name: "Show password" }).click();
  assert.equal(await page.locator('input[autocomplete="current-password"]').getAttribute("type"), "text");
  await page.getByRole("button", { name: "Hide password" }).click();
  await layout("login");
  await page.locator('form button[type="submit"]').click();
  await page.getByRole("alert").filter({ hasText: "Invalid credentials." }).waitFor();
  assert.equal(calls.filter((call) => call.path.endsWith("auth/login/")).length, 1);
  checks++;

  await page.getByRole("button", { name: "Create account", exact: true }).click();
  assert.equal(await page.locator('input[autocomplete="new-password"]').first().inputValue(), "", "Mode changes clear passwords");
  await page.getByLabel("First name").fill("UI");
  await page.getByLabel("Last name").fill("Test");
  await page.getByLabel("Phone number").fill("+256700000000");
  await page.getByLabel("Gender").selectOption("FEMALE");
  await page.locator('input[autocomplete="new-password"]').nth(0).fill("isolated-test-only");
  await page.getByLabel("Confirm password").fill("different");
  await layout("register");
  await page.locator('form button[type="submit"]').click();
  await page.getByRole("alert").filter({ hasText: "Passwords do not match." }).waitFor();
  assert.equal(calls.filter((call) => call.path.endsWith("auth/register/")).length, 0);
  await page.getByLabel("Confirm password").fill("isolated-test-only");
  await page.locator('form button[type="submit"]').click();
  await page.getByRole("heading", { name: "Check your inbox." }).waitFor();
  await layout("verification");
  const browserAccountPages = await page.getByText(/Open the link from your email in your phone’s browser/).count() > 0;
  if (browserAccountPages) {
    assert.equal(await page.getByLabel("Email link", { exact: true }).count(), 0);
    assert.equal(await page.locator('form button[type="submit"]').count(), 0);
    assert.equal(calls.filter((call) => call.path.endsWith("auth/verify-email/")).length, 0);
  }
  checks++;

  await page.getByRole("button", { name: "Back to sign in" }).click();
  await page.getByRole("button", { name: "Forgot password?" }).click();
  await layout("forgot-password");
  await page.getByRole("button", { name: browserAccountPages ? "Check reset email" : "Already have a reset link?" }).click();
  await layout("reset-password");
  if (browserAccountPages) {
    await page.getByText(/Choose your new password on the page/).waitFor();
    assert.equal(await page.locator('input[type="password"]').count(), 0);
    assert.equal(await page.locator('form button[type="submit"]').count(), 0);
    assert.equal(calls.filter((call) => call.path.endsWith("auth/reset-password/")).length, 0);
  }
  await page.getByRole("button", { name: "Back to welcome" }).click();
  assert.equal(await page.getByRole("button", { name: "Explore the app preview" }).count(), 0,
    "Welcome has no unauthenticated preview entry");
  assert.equal(await page.getByText("Preview uses sample data. No account needed.").count(), 0);
  checks++;

  loginAccepted = true;
  await page.getByRole("button", { name: /Already have an account/ }).click();
  await page.getByLabel("Email address").fill(user.email);
  await page.locator('input[type="password"]').fill("isolated-test-only");
  await page.locator('form button[type="submit"]').click();
  await page.getByRole("heading", { name: "Hello, UI" }).waitFor();
  await page.getByRole("heading", { name: "Start with your meter", exact: true }).waitFor();
  await tab("Meters");
  await page.getByRole("button", { name: /Home meter.*UI-METER-7/ }).click();
  await tab("Home");
  await page.getByText("1.50 kWh", { exact: true }).waitFor();
  await page.getByText("0.31 kWh", { exact: true }).waitFor();
  await tab("Meters");
  await page.getByRole("button", { name: /Shop meter.*UI-METER-8/ }).click();
  await tab("Home");
  await page.getByText("2.50 kWh", { exact: true }).waitFor();
  assert.equal(await page.getByText("1.50 kWh", { exact: true }).count(), 0);
  checks++;

  await tab("Account");
  await page.getByRole("button", { name: /Personal details/ }).click();
  await page.getByLabel("Address", { exact: true }).fill("Synthetic profile address");
  await page.getByLabel("Energy preference").selectOption("HYDRO");
  await page.getByRole("button", { name: "Save details", exact: true }).click();
  await page.getByText("Account details saved.", { exact: true }).waitFor();
  failProfile = true;
  await page.getByRole("button", { name: "Refresh account details", exact: true }).click();
  await page.getByRole("alert").filter({ hasText: "Account details:" }).waitFor();
  assert.equal(await page.getByRole("button", { name: "Save details", exact: true }).isDisabled(), true);
  await page.getByText(/Stale — last fetched/).first().waitFor();
  failProfile = false; detailsAvailable = false;
  await page.getByRole("button", { name: "Refresh account details", exact: true }).click();
  await page.getByRole("heading", { name: "Account details unavailable" }).waitFor();
  assert.equal(await page.getByRole("button", { name: "Save details", exact: true }).count(), 0);
  checks++;

  liveMeters = [{ ...shopMeter, id: 18 }]; // Same displayed number, different physical-record identity.
  await page.getByRole("button", { name: "Refresh account", exact: true }).click();
  await page.getByRole("status").filter({ hasText: /Your meter assignment changed|This meter is no longer assigned/ }).waitFor();
  await tab("Home");
  assert.equal(await page.getByText("2.50 kWh", { exact: true }).count(), 0);
  await page.getByRole("heading", { name: "Start with your meter", exact: true }).waitFor();
  liveMeters = [];
  await page.getByRole("button", { name: "Refresh account", exact: true }).click();
  await tab("Meters");
  await page.getByRole("heading", { name: "Add your meter", exact: true }).waitFor();
  assert.equal(calls.some((call) => call.path.endsWith("auth/account-details/") || call.path.endsWith("meter/my-meter/")), false);
  assert.equal(calls.some((call) => /share|send-units|transfer-units/.test(call.path)), false);
  checks++;
  selfEnrollment = true;
  await page.getByRole("button", { name: "Refresh meters", exact: true }).click();
  await page.getByRole("button", { name: "Add your meter", exact: true }).waitFor();
  await page.getByLabel("Meter number", { exact: true }).fill(" 000245 ");
  await page.getByRole("button", { name: "Add your meter", exact: true }).click();
  await page.getByRole("button", { name: /Prototype meter.*000245/ }).waitFor();
  await tab("Home");
  await page.getByRole("heading", { name: "Hello, UI", exact: true }).waitFor();
  await page.getByText("Hardware contact unavailable", { exact: true }).waitFor();
  assert.equal(calls.some(call => call.path.endsWith("meter/sandbox-meter-enrollment/") && call.method === "POST"), true);
  checks++;
  for (const width of [320, 768]) {
    await page.setViewportSize({ width, height: 844 });
    for (const name of ["Home", "Meters", "Loans", "Buy Units", "Account"]) {
      await tab(name); await layout(`${name.toLowerCase()}-${width}`);
    }
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await tab("Account");
  await page.getByRole("button", { name: "Log out", exact: true }).click();
  await page.getByRole("heading", { name: "Your power. Your possibilities." }).waitFor();
  assert.equal(await page.getByText("ui@example.invalid", { exact: true }).count(), 0, "Logout removes private account data");
  assert.deepEqual(errors, [], "No browser runtime errors");
  checks++;
  console.log(`${checks} browser scenarios passed: authentication, hidden preview, meter binding, forms, navigation, states and logout.`);
  await context.close();
} finally { await browser.close(); }
