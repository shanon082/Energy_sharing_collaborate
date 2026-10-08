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
const browser = await chromium.launch({ headless: true, channel: "chromium" });
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
    else if (path.endsWith("auth/mobile-profile/")) body = { values: {}, choices: {}, complete_for_scoring: false };
    else if (path.endsWith("auth/account-details/")) body = { account_number: null, address: null, energy_preference: null, payment_method: null };
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
  checks++;

  await page.getByRole("button", { name: "Back to sign in" }).click();
  await page.getByRole("button", { name: "Forgot password?" }).click();
  await layout("forgot-password");
  await page.getByRole("button", { name: "Already have a reset link?" }).click();
  await layout("reset-password");
  await page.getByRole("button", { name: "Back to welcome" }).click();
  const beforePreview = calls.length;
  await page.getByRole("button", { name: "Explore the app preview" }).click();
  await page.getByRole("heading", { name: "Hello, Alex." }).waitFor();
  await layout("dashboard");
  assert.deepEqual(await page.getByRole("navigation").getByRole("button").allTextContents(), ["Home", "Meters", "Usage", "Credit", "Activity", "Account"]);
  assert.equal(await page.getByRole("button", { name: /share|transfer|withdraw|deposit|pay.for.someone|ussd/i }).count(), 0);
  checks++;

  await tab("Meters");
  await page.getByRole("button", { name: /Shop meter Small business/ }).click();
  await layout("meters");
  await tab("Home");
  await page.getByRole("button", { name: "Buy electricity" }).click();
  assert.equal(await page.getByLabel("Your meter").inputValue(), "1");
  await page.getByRole("button", { name: "UGX 5,000", exact: true }).click();
  await page.getByLabel("Mobile Money phone").fill("+256700000000");
  await layout("purchase");
  await page.getByRole("button", { name: "Review request" }).click();
  await page.getByText("Shop meter · SAMPLE-M002", { exact: true }).waitFor();
  await layout("purchase-review");
  await page.getByRole("button", { name: "About this preview" }).click();
  await page.getByRole("dialog").waitFor();
  assert.equal(await page.getByRole("button", { name: "Got it" }).evaluate((button) => button === document.activeElement), true);
  await page.keyboard.press("Escape");
  assert.equal(await page.getByRole("dialog").count(), 0);
  checks++;

  await tab("Meters");
  await page.getByRole("button", { name: "Preview meter loading" }).click();
  await page.getByLabel("Energy amount (kWh)").fill("0.001");
  await page.getByRole("button", { name: "Review load" }).click();
  await page.getByRole("alert").filter({ hasText: "0.01 kWh" }).waitFor();
  await page.getByLabel("Energy amount (kWh)").fill("4.61");
  await page.getByRole("button", { name: "Review load" }).click();
  await page.getByRole("alert").filter({ hasText: "available entitlement" }).waitFor();
  await page.getByLabel("Energy amount (kWh)").fill("1.20");
  await page.getByRole("button", { name: "Review load" }).click();
  await layout("load-review");
  checks++;

  await tab("Credit");
  await layout("credit");
  await page.getByRole("button", { name: "View loan" }).click();
  await page.getByText("SAMPLE-M001", { exact: true }).waitFor();
  await layout("loan-detail");
  await page.getByRole("button", { name: "Preview self-repayment" }).click();
  assert.equal(await page.getByLabel("Loan meter").inputValue(), "0", "Loan stays bound to its source meter");
  await page.getByLabel("Amount (whole UGX)").fill("8000");
  await page.getByLabel("Mobile Money phone").fill("+256700000000");
  await page.getByRole("button", { name: "Review repayment" }).click();
  await page.getByRole("alert").waitFor();
  await page.getByLabel("Amount (whole UGX)").fill("2500");
  await page.getByRole("button", { name: "Review repayment" }).click();
  await page.getByText("Home meter · SAMPLE-M001", { exact: true }).waitFor();
  await layout("repayment-review");
  await tab("Credit");
  await page.getByRole("button", { name: "Preview a credit request" }).click();
  await page.getByLabel("Amount (whole UGX)").fill("10000");
  await page.getByRole("button", { name: "Review request" }).click();
  await layout("application-review");
  checks++;

  await tab("Usage"); await layout("usage");
  await tab("Activity"); await layout("activity");
  await page.getByRole("button", { name: /Electricity purchase.*5,000/ }).click();
  await page.getByText("SAMPLE-M001", { exact: true }).waitFor();
  await layout("receipt");
  await page.getByRole("button", { name: "Preview notifications" }).click();
  await layout("notifications");
  await page.getByRole("button", { name: "Mark sample alerts as read" }).click();
  checks++;

  await tab("Account"); await layout("account");
  await page.getByRole("button", { name: /Personal details/ }).click();
  await page.getByLabel("First name").fill("Changed");
  await page.getByRole("button", { name: "Save sample details" }).click();
  await page.getByRole("button", { name: "Got it" }).click();
  await layout("profile");
  await tab("Account");
  await page.getByRole("button", { name: /Account security/ }).click(); await layout("security");
  await tab("Account");
  await page.getByRole("button", { name: /Help/ }).click(); await layout("help");
  assert.equal(calls.length, beforePreview, "Entire design preview makes no API calls");
  checks++;

  await tab("Home");
  await page.getByText("Preview display states", { exact: true }).click();
  await page.getByRole("button", { name: "Empty account" }).click();
  await page.getByRole("heading", { name: "Nothing here yet" }).waitFor();
  await layout("empty");
  await page.getByRole("button", { name: "Offline / stale" }).click();
  await page.getByRole("status").filter({ hasText: "stale" }).waitFor();
  await layout("offline");
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  for (const width of [320, 768]) {
    await page.setViewportSize({ width, height: 844 });
    for (const name of ["Home", "Meters", "Usage", "Credit", "Activity", "Account"]) {
      await tab(name); await layout(`${name.toLowerCase()}-${width}`);
    }
  }
  checks++;

  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Exit preview", exact: true }).click();
  await page.getByRole("heading", { name: "Your power. Your possibilities." }).waitFor();
  loginAccepted = true;
  await page.getByRole("button", { name: /Already have an account/ }).click();
  await page.getByLabel("Email address").fill(user.email);
  await page.locator('input[type="password"]').fill("isolated-test-only");
  await page.locator('form button[type="submit"]').click();
  await page.getByRole("heading", { name: "Hello, UI." }).waitFor();
  await page.getByRole("navigation").getByRole("button", { name: "Account", exact: true }).click();
  await page.getByRole("button", { name: "Log out", exact: true }).click();
  await page.getByRole("heading", { name: "Your power. Your possibilities." }).waitFor();
  assert.equal(await page.getByText("ui@example.invalid", { exact: true }).count(), 0, "Logout removes private account data");
  assert.deepEqual(errors, [], "No browser runtime errors");
  checks++;
  console.log(`${checks} browser scenarios passed: authentication, preview isolation, meter binding, forms, navigation, states, responsive layouts and logout.`);
  await context.close();
} finally { await browser.close(); }
