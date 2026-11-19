# Authenticated USB-powered credit testing — 2026-11-19

Active sketch: `C:\Users\USER\OneDrive\Documents\Arduino\GpawaAC`.
This mode needs USB power, configured Wi-Fi, correct time and verified HTTPS to
the existing Django V2 device API. It needs **no AC supply or PZEM measurement**.
It is not the synthetic USB exercise and never accepts local demo keypad codes.

## Confirmed cause and changes

The old network loop required `state.hasMeter && sensorOK` before even starting
a session or sending an ACK. The keypad separately rejected `#` when sensorOK was
false. The pure credit application/journal code and Django session/redeem/ACK
services did not require a sensor reading. Removing measurement from those
specific readiness checks is sufficient; weakening authentication is unnecessary.

`HardwareConfig.h` now explicitly selects:

```cpp
#define GPAWA_WIFI_TEST 0
#define GPAWA_USB_EXERCISE 0
#define GPAWA_AUTH_CREDIT_ONLY 1
#define GPAWA_COMMISSIONED_OUTPUT 0
```

The active sketch already had WIFI_TEST=0; that user change was preserved. Mixing
authenticated credit mode with diagnostics/exercise is a compile error. The
existing unconditional prohibition on physical-output compilation is retained.
No relay GPIO is configured or driven; D displays “Output disabled”.

In authenticated credit-only mode:

- Journal validation, owner/meter/environment/storage/epoch checks and TLS remain
  unchanged. An invalid private configuration fails clearly, never falls back to
  synthetic credit. Existing DeviceConfig.h and NetworkConfig.h are untouched.
- Sessions, keypad redemption and durable ACKs work independently of hasMeter and
  sensorOK. Invalid tokens, identities, TLS, expired network operations and server
  errors never create credit. Readback/CRC persistence precedes the ACK.
- The same command/receipt/counters survive retries and reboot. A lost ACK response
  resends the same receipt; duplicate tokens cannot add another allocation/credit.
- PZEM sampling and consumption deductions are disabled. **No telemetry is sent**:
  no voltage/current/power, baseline, usage or feedback zero is manufactured.
- Every30s, an existing authenticated session request supplies a heartbeat and
  validates the saved counters. ACK recovery takes priority. The backend records
  contact, but that is not a measured sample or proof of load switching.
- The16x2 LCD alternates saved Wh / credit-only status with the two-line message
  “Consumption” / “unavailable”. A, digits,*,C,# and recovery messages are retained.
  D cannot arm output; B does not synthesize usage.

## Persistent measurement state and safe later activation

The NVS namespace `gpawa_sbx2`, key `state`, struct layout and identity are retained.
No namespace is cleared, counter reset, credential rotated, token replayed or
balance converted. Existing valid version2 records are read before any write.
Entering credit-only mode preserves all credit/debit/receipt/baseline fields,
sets reserved byte2 to1, and changes the journal version to3 with a fresh CRC.
Boot counter advancement remains the normal existing recovery operation.

- `hasMeter=false`: measurement state is explicitly **UNINITIALIZED**. The stored
  numeric slot is not a zero baseline and is never sent/interpreted as a reading.
- An existing `hasMeter=true` baseline is preserved as **SUSPENDED**, not current.
- Invalid CRC, held/reconciliation state or changed binding is not bypassed.
- A v2-only binary rejects the version3 journal, preventing an older binary from
  silently debiting the PZEM lifetime total on rollback.
- New firmware with credit-only turned off refuses a paused journal with
  “Baseline review”. The pure observe() function also refuses it without changing
  credit. Sensor reconnection alone never establishes a baseline or deducts usage.

**Metered activation is intentionally blocked in this milestone.** It requires a
separately reviewed operator workflow to establish/reconcile a real baseline,
account for any unmeasured interval and durably authorize the transition. There
is no keypad reset, bit-clearing shortcut or automatic subtraction of lifetime Wh.
Physical output remains forbidden regardless of that future workflow. Never erase
NVS or re-enable ALLOW_FIRST_BOOT to get around a used-binding/reconciliation error.

## Backend and deployment impact

No backend runtime change, new endpoint, schema migration, settings change,
reprovisioning or hosting restart is required **beyond the already deployed
MTN/SANDBOX GPAWA_PZEM_V2 implementation**. The four existing routes and payloads
are unchanged. The backend does not require a PZEM baseline for session/redeem/ACK.
All MTN settlement validation, seven disabled features and relay restrictions stay.

The only backend addition is isolated tests in meter/tests_credit_only.py. Tests
prove owner APIs show ACK-confirmed cloud entitlement separately from unavailable
measurement/physical-balance fields and UNKNOWN output feedback. The last contact
can update without manufacturing a last measurement. Stored pre-existing sensor
readings retain their original times and become stale; a session is not fresh usage.
No new Android/web build is needed for this unchanged read contract.

## Validation and reproduction

```bash
python3 firmware/ac-lab-domain/tests/check.py
python3 firmware/ac-lab-domain/tests/check.py --sketch /mnt/c/Users/USER/OneDrive/Documents/Arduino/GpawaAC
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --sandbox-profile meter.tests_credit_only meter.tests_mtn_device meter.tests_prototype_device backend.tests_feature_flags
```

The C++ tests exercise first sensor-free credit, exact V2 command binding,
wrong-meter rejection, duplicate application, restart before/after ACK, preserved
old baselines/debits, unknown measurement and safe refusal on sensor return.
Compile-time tests retain the output prohibition and mode isolation. The PostgreSQL
tests use synthetic isolated data and mocked providers; no real payment is initiated.

For target compilation, the exact cached FQBN for this sketch was recovered from
Arduino's build.options.json: ESP32S3 Dev Module, Arduino-ESP323.3.12,4MB flash,
default partition,qio,PSRAM disabled,hardware CDC/JTAG,CDC-on-boot disabled,
240MHz,loop/event core1. USB/partition options were not guessed or changed.
Use the same existing IDE board settings and **Verify**, not Upload. Final compile
results/private output path are recorded in CREDIT_ONLY_BUILD.md at the parent
directory. Compiled configured binaries contain the device credential and must
remain private, outside Git and distribution packages.

## Later board check (not performed here)

1. Keep AC/relay/load disconnected; USB power only. Do not clear NVS or reprovision.
2. After an independently authorized flash, observe saved credit and unavailable
   consumption. Wait for Wi-Fi/time/TLS/session readiness, not a PZEM baseline.
3. Enter an existing authorized token for this exact SANDBOX meter; verify credit
   saved, ACK confirmed, same token denied without another credit.
4. Cut/reconnect USB before/after ACK. Receipt/counter/credit must survive and the
   same pending command must recover. Never expose token/secret serial logs.
5. A wrong-meter token must fail. D must not arm output. No PZEM/AC connection or
   payment initiation is required to perform the credit recovery checks.

No deployment, flash, NVS access, provider/board request or relay operation was
performed by this implementation. Host-side tests are not physical durability,
TLS network reliability, keypad or sensor-accuracy evidence.
