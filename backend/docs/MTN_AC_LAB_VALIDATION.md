# Local MTN / AC_LAB validation — 2026-11-18

All PostgreSQL tests used disposable local databases on127.0.0.1:55445, isolated
role gpawa_alwaysdata_test and the guarded deploy/test-hosting.py launcher. It
clears inherited configuration and prohibits external requests.Session HTTP;
individual provider transports are mocked. No hosted DB was queried/migrated and
no actual MTN, ThingsBoard, phone or ESP32 exchange took place.

| Check | Final result |
|---|---|
| alwaysdata consumer profile: MTN, AC_LAB V1/V2, settlement, demo recovery, flags, account pages, owner summary | 127 passed in123.122s |
| Base/core settlement, allocation/simulator, financial and feature-flag regressions | 79 completed:78 passed,1 existing expected failure,388.228s |
| Isolated software bench/token workflow | 17 passed in16.362s |
| Model/migration consistency | No changes detected in meter,loan,transactions |
| Mobile TypeScript and project npm test | Passed |
| Individual mobile test assertions | 73 passed |
| Shared Next.js tests | 29 passed |
| Frontend strict tsc | Passed |
| Vite android-debug bundle, Capacitor sync | Passed |
| Android wrapper offline assembleDebug | Passed,55s,153 tasks (27 executed/126 cached) |
| APK signature, existing local certificate continuity, embedded HTTPS URL | Passed; see mobile/MTN_AC_LAB_BUILD.md |
| Linux public firmware core/contract/mode guards, including headers applied to active sketch | Passed |
| ESP32 board-target compile / flash / physical tests | Not performed |
| Full Next.js production build | Not completed within240s; details below |

The expected failure remains
`FinancialCorrectnessTests.test_completed_loan_stays_closed_when_overdue_clock_advances`:
legacy core debt lacks an immutable closure timestamp. It is not declared fixed.
The core suite also logs existing legacy MeterBalance signal uniqueness warnings
for repeated synthetic meter fixtures; these are not new device-domain failures.
The new domain uses source allocations/deliveries, not those ambiguous balances.

An initial broad invocation incorrectly placed core-only suites under the hosted
sandbox profile. It failed with HTTPS redirects/core financial denials, as that
profile is designed to do. The core and hosted suites were then run under their
proper separate settings above; no HTTPS or financial restrictions were weakened.
The bench fixture now explicitly enables token issuance instead of relying on an
inherited setting; new/demo payment fixture settings remain independent.

## Reproducible commands (repository root unless stated)

The test-only extra path below contains existing project-pinned cryptography and
WhiteNoise dependencies; it is not a source dependency upgrade. The launcher
refuses an unexpected PostgreSQL cluster/role. See ALWAYSDATA_TESTING.md for the
isolated cluster setup; never point these commands at a hosting database.

```bash
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --sandbox-profile meter.tests_mtn_device meter.tests_prototype_device loan.tests_mtn_transition loan.tests_sandbox transactions.tests_demo_payments backend.tests_feature_flags backend.tests_combined_rollout loan.tests_consumer_summary accounts.tests_account_pages
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py meter.tests_allocation_delivery transactions.tests_payment_settlement loan.tests_financial_correctness backend.tests_feature_flags
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --bench-profile meter.tests_energy_tokens
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --sandbox-profile --check-migrations
python3 firmware/ac-lab-domain/tests/check.py
python3 firmware/ac-lab-domain/tests/check.py --sketch /mnt/c/Users/USER/OneDrive/Documents/Arduino/GpawaAC
```

In mobile/: `npm run typecheck`, `npm test`, and
`node --test --test-isolation=none tests/*.test.mjs` all passed. In frontend/:
`npx tsc --noEmit`, `node --test tests/*.test.mjs`, and the same test-isolation=none
invocation passed. The latter exposes individual counts instead of only file totals.

The default Turbopack production build stalled in optimization and was stopped;
its bounded retry exited124 after240s. A separate
`timeout 240 npm run build -- --webpack` compiled successfully (89s), passed its
TypeScript stage and generated49/49 static pages, but exited124 while collecting
build traces. Thus no complete production-build pass is claimed. No type checks,
font fetching, compiler settings or authentication were disabled; the tracing
timeout's root cause is not established. Existing baseline/middleware deprecation
warnings remain. A longer dedicated web-build/tracing investigation is outstanding.

## What the tests establish

Mocked202→PENDING→SUCCESSFUL yields exactly one frozen-price SANDBOX allocation
and one meter-bound token. HTTP200+FAILED/mismatched amount/currency/external ID/
missing transaction identity yields none. Existing timeout/status/backoff,
cross-intent provider replay and same-intent concurrency tests remain passing.
Redemption repeats return the same reserved command; concurrent redemption/ACK,
lost response, reboot before ACK, duplicate ACK and persistent local credit do not
add energy twice. Wrong meter/domain, consumer credentials and revoked device fail.
Telemetry reset/reordering/replay and foreign owner reads fail without minting
credit or application evidence. Existing EUR debt can be repaid with no token or
energy allocation; new EUR lending remains blocked. All seven features stay off.

The host C++ callback tests canonical JSON against fixed Python SHA256 vectors;
it does not independently validate the unchanged mbedtls crypto primitive or real
ESP32 flash durability. Physical TLS/CA, PZEM accuracy, wiring, provider credentials,
gateway/network reliability and actual keypad/phone operation remain untested.

## Active Arduino sketch

Updated seven public files at
`C:\Users\USER\OneDrive\Documents\Arduino\GpawaAC` after approval, preserving
the hd44780 display and WifiCheck diagnostics. Public backup:
`GpawaAC.public-before-sandbox-20261118T194907Z` alongside it. Private DeviceConfig.h
and NetworkConfig.h were checksum-verified unchanged. Repository public sources
match the applied files; no private header is in the repository/patch/upload list.

Sanitized readiness inspection found placeholders for DEVICE_ID, DEVICE_SECRET,
STORAGE_ID and ROOT_CA. Other private values were not displayed and their server
binding was not verified. Public DeviceDomain.h now selects SANDBOX; WIFI_TEST=1
remains diagnostic, USB_EXERCISE=0, output=0 with a compile-time prohibition.
Do not merely flip diagnostic mode and expect operation: complete deployment,
provisioning, matching private configuration and target compilation first. Existing
private settings/old journals must be retained privately, never erased or relabelled.
