# Phase 5 hardware and deployment preparation

This is a preparation checklist, not authorization to upload firmware, migrate a
hosted database, change a device binding, or energize AC. The committed-output
configuration and backend output policy remain disabled.

## Export the complete Arduino sketch without private configuration

The complete public sketch source is
[`GpawaAC/`](../GpawaAC/). It contains:

```text
BuzzerCore.h
DeviceConfig.example.h
DeviceDomain.h
Firmware.cpp
GpawaAC.ino
HardwareConfig.h
MeterCore.h
NetworkConfig.example.h
Protocol.h
PzemFrame.h
SafeDiagnostics.h
WifiCheck.cpp
```

In WSL, copy the public source files to a separate Windows Arduino sketch
directory. Replace `<WindowsUser>` and the destination with the real local path:

```bash
mkdir -p "/mnt/c/Users/<WindowsUser>/Documents/Arduino/GpawaAC"
cp firmware/ac-lab-domain/GpawaAC/*.h \
   firmware/ac-lab-domain/GpawaAC/*.cpp \
   firmware/ac-lab-domain/GpawaAC/*.ino \
   "/mnt/c/Users/<WindowsUser>/Documents/Arduino/GpawaAC/"
```

This copies public files only; it does not delete destination files. Keep the
existing private `DeviceConfig.h` and `NetworkConfig.h` in that destination.
Never replace them with the examples, add populated private files to this
repository, or include them in an archive. Confirm that the folder name and
`GpawaAC.ino` basename match. A safe export contains no `DeviceConfig.h`,
`NetworkConfig.h`, credentials, compiled binaries, or NVS image.

For each mode below, use a separate working copy of the public directory and
edit only that copy's `HardwareConfig.h` definitions. Do not change the
repository's disabled-by-default values. The `#ifndef` configuration macros
can also be passed as `compiler.cpp.extra_flags` in Arduino CLI; the standard
Arduino IDE GUI does not expose a general C++ macro editor.

## Arduino IDE libraries and board settings

Required Library Manager libraries:

| Library | Version | Reason |
|---|---:|---|
| ArduinoJson | 7.4.3 | Firmware uses ArduinoJson 7 `JsonDocument`. Do not substitute 6.x. |
| hd44780 (Bill Perry) | 1.3.2 | LCD I2C expander driver. |
| Keypad | 3.1.1 | 4x4 keypad scanning. |

No PZEM library is required: the firmware implements and validates the Modbus
RTU frame itself. Wi-Fi, TLS, HTTP, UART, Preferences, watchdog, and I2C use
Arduino-ESP32/ESP-IDF or Arduino built-ins.

Use the already installed Arduino-ESP32 **3.3.12** core; do not install or
upgrade a WSL toolchain. This version is installed in the Windows Arduino
package and the current full metered/output-disabled source compiled with its
Windows Arduino CLI.

For a new N16R8 bench board, the module's nominal hardware is 16 MB flash and
8 MB octal PSRAM. In Arduino IDE select **ESP32S3 Dev Module**, Flash Size
**16MB**, PSRAM **OPI PSRAM**, Flash Mode **QIO** (the N16 flash is quad SPI),
CPU **240 MHz**, USB Mode **Hardware CDC and JTAG**, CDC/MSC/DFU on boot
**Disabled**, Upload Mode **UART0 / Hardware CDC**, Loop Core **1**, Events
Core **1**, and Upload Speed **921600** if the board connection is stable.
The installed core lists `Huge APP (3MB No OTA/1MB SPIFFS)` for this board;
the firmware uses no filesystem. For a fresh, disposable bench unit, this
gives an ample app slot.

**Existing device partition warning:** the last recorded Windows build for the
existing sketch used `FlashSize=4M`, `PartitionScheme=default`,
`PSRAM=disabled`, QIO, 240 MHz, hardware CDC/JTAG, CDC off, and Loop/Events
Core 1. Its default 4 MB partition has a 1,310,720-byte application slot. That
is a different configuration from the module's nominal N16R8 hardware. The
current code compiled in that existing layout and fits its app slot, but the
actual flashed partition table has not been read back. For **Verify-only**
reproduction, keep the captured `default`/4 MB settings. Before any upload to
the credit-holding device, confirm its existing partition map and flash
settings from trusted build records; do not switch to a 16 MB or different
partition scheme based only on the module marking. Never select full-flash
erase. Matching the application partition does not prove that an upload is
safe for the existing NVS.

### Arduino IDE Verify and upload workflow

1. Install the three pinned libraries above through **Tools → Manage
   Libraries**. Confirm **Tools → Board → esp32 → ESP32S3 Dev Module** and
   enter the board settings for the intended build. A COM port is not required
   for Verify.
2. Open `GpawaAC.ino` from the exported `GpawaAC` folder. Before compiling,
   select exactly one profile by editing only the local copy's macros. Review
   the active `HardwareConfig.h` values; do not rely on stale IDE build output.
3. Choose **Sketch → Verify/Compile** (checkmark). Confirm the console's
   board/core/library versions, flash/partition size, and app/global memory
   totals. A compile does not write to the board.
4. Do not select **Upload** under this authorization. If a separate upload
   authorization is later given, first verify the physical COM port, actual
   chip/partition map, exact installed board options, and that **Erase All
   Flash Before Sketch Upload** is disabled/`none`. The selected upload
   configuration can rewrite bootloader/partition metadata as well as the
   application; if it differs from the existing map, stop. Do not use
   “Erase Flash”, “Erase All Flash”, a merged full-flash image, or any NVS
   reset option. Keep the AC/load disconnected and preserve a private backup
   before an approved maintenance upload.

## Mutually exclusive firmware profiles

Values below are the complete macro set to place in the selected private
working copy's `HardwareConfig.h`. Keep `GPAWA_WIFI_TEST=0` and
`GPAWA_USB_EXERCISE=0` in every profile.

### A. Low-voltage GPIO14 relay diagnostic

```cpp
#define GPAWA_WIFI_TEST 0
#define GPAWA_RELAY_DIAGNOSTIC 1
#define GPAWA_PZEM_DIAGNOSTIC 0
#define GPAWA_AUTH_CREDIT_ONLY 0
#define GPAWA_USB_EXERCISE 0
#define GPAWA_COMMISSIONED_OUTPUT 0
```

Do not define `GPAWA_RELAY_ACTIVE_LEVEL` for this diagnostic. It does not start
Wi-Fi, read or write Preferences/NVS, access the backend, or modify credit. It
sets GPIO14 to input/released at startup and accepts only `H`, `L`, and `Z`.
This mode is not safe evidence about a relay's power-on default or hardware
bias; observe those separately with AC/load disconnected.

### B. Authenticated metered mode, relay output disabled

```cpp
#define GPAWA_WIFI_TEST 0
#define GPAWA_RELAY_DIAGNOSTIC 0
#define GPAWA_PZEM_DIAGNOSTIC 0
#define GPAWA_AUTH_CREDIT_ONLY 0
#define GPAWA_USB_EXERCISE 0
#define GPAWA_COMMISSIONED_OUTPUT 0
```

Do not define an active relay level. This mode reads validated PZEM frames,
authenticates, and performs the existing retry-safe baseline migration when
the firmware, server, and preserved NVS are ready. It reports readings and
telemetry while never driving GPIO14. **Do not upload it to the existing
credit-holding device until the backend rollout and migration window are
separately approved**: migration is intentionally persistent, even though it
does not erase NVS or change binding/credit.

### C. Future commissioned physical-meter mode — not approved or enabled

```cpp
#define GPAWA_WIFI_TEST 0
#define GPAWA_RELAY_DIAGNOSTIC 0
#define GPAWA_PZEM_DIAGNOSTIC 0
#define GPAWA_AUTH_CREDIT_ONLY 0
#define GPAWA_USB_EXERCISE 0
#define GPAWA_COMMISSIONED_OUTPUT 0
#define GPAWA_RELAY_COMMISSIONING_APPROVED 0
// Only after a separately approved commissioning record:
// #define GPAWA_COMMISSIONED_OUTPUT 1
// #define GPAWA_RELAY_COMMISSIONING_APPROVED 1
// #define GPAWA_RELAY_ACTIVE_LEVEL 0  // measured value only; never guess
```

`GPAWA_RELAY_ACTIVE_LEVEL` must be exactly `0` or `1` and must come from the
low-voltage test, not a guess. This profile is documented only; do not build it
for operation or upload it now. Compile-time guards reject conflicting
diagnostic/exercise/credit-only modes and reject a missing/invalid active
level or commissioning approval flag. The backend now implements bounded,
audited, per-device authorization; see
[OUTPUT_AUTHORIZATION.md](./OUTPUT_AUTHORIZATION.md). Compile guards and
backend authorization do not replace physical commissioning or approval.

The guards also allow the repository's existing read-only PZEM diagnostic
profile (the safe source default); it is distinct from profiles A-C.

## Pinout and conflict check

The current source assigns:

| Function | GPIO / address | Source |
|---|---:|---|
| LCD SDA / SCL | 8 / 9 | `HardwareConfig.h` |
| LCD I2C address | `0x27` | `HardwareConfig.h` |
| Keypad rows | 4, 5, 6, 7 | `Firmware.cpp` |
| Keypad columns | 10, 11, 12, 13 | `Firmware.cpp` |
| Relay channel 1 | 14 | `HardwareConfig.h` |
| PZEM RX / TX | 16 / 17 | `HardwareConfig.h` |
| PZEM address | `0x01` | `HardwareConfig.h` |
| Buzzer | 18 | `HardwareConfig.h` |

There are no duplicate assignments among these functions. The source does not
assign GPIO19/20 (native USB) or ESP32-S3 strapping GPIO0/3/45/46 to these
peripherals. Check the exact carrier-board schematic, LCD backpack voltage,
keypad wiring, relay input circuitry, and PZEM isolation before connection;
the chip pin map alone does not establish electrical compatibility. The
relay diagnostic's INPUT/released state is not a guaranteed inactive relay
state if the external input floats.

## Relay diagnostic procedure

1. Keep all mains, AC and load wiring physically disconnected. Verify the
   contacts cannot energize a load. Use only a suitable isolated low-voltage
   supply for the ESP32 and relay module.
2. Verify the relay input is 3.3 V compatible before wiring GPIO14. Do not put
   5 V on the ESP32 GPIO. Leave relay channel 2 disconnected.
3. Build profile A and use **Verify**. Open Serial Monitor at **115200 baud**.
   Startup text is:

   ```text
   RELAY_DIAGNOSTIC ready: AC/load must be disconnected; GPIO14 is released.
   Send H or L to drive GPIO14; observe only K1. Send Z to release. No relay feedback is read.
   ```

4. Record the module's indicator/contact sound while GPIO14 is released at
   boot. This is the observed startup state for that board/driver/supply only;
   the sketch does not assume or guarantee a relay state during reset.
5. Send `H`, record the K1 indicator/click, then send `L` and record it. The
   example serial lines are:

   ```text
   RELAY_DIAGNOSTIC pin=GPIO14 drive=HIGH readback=HIGH k1_feedback=VISUAL_ONLY
   RELAY_DIAGNOSTIC pin=GPIO14 drive=LOW readback=LOW k1_feedback=VISUAL_ONLY
   ```

   The command whose physical low-voltage relay input activates K1 identifies
   active-HIGH (`H`) or active-LOW (`L`) for this exact wiring. GPIO readback is
   only ESP32 pin readback, not relay contact feedback.
6. To identify the inactive driven state, send the opposite command and record
   whether K1 is released. Then send `Z`; this changes GPIO14 to input/released.
7. Test reset with the module still low-voltage powered: reset once from `H`
   and once from `L`, observe K1 during reset and after boot, and record any
   pulse/state change. Serial output restarts with the two startup lines.
8. For power-loss testing, if supplies are separate, remove ESP32 power while
   relay-module power remains and observe K1; restore. Then remove both
   supplies and restore, recording the startup state. The unpowered interval
   cannot report serial data; record observations externally.
9. Send `Z`, close the monitor and remove low-voltage power. Do not connect AC
   or a load for any diagnostic step.

An indicator/click is not proof of contact isolation, contact rating, or
safe switching. Record exact board/module/driver/supply and observations for
startup, inactive, reset, and both power-loss conditions. The documented
procedure is also in [`RELAY_DIAGNOSTIC.md`](RELAY_DIAGNOSTIC.md).

## Watchdog status

The duplicate-initialization path is fixed in the normal authenticated
firmware. On Arduino-ESP32 3.3.12, setup first calls
`esp_task_wdt_reconfigure()`; it calls `esp_task_wdt_init()` only when the
watchdog reports `ESP_ERR_INVALID_STATE` (not initialized). It uses a 5-second
timeout with panic-on-timeout, subscribes all ESP32-S3 idle cores and registers
the current Arduino setup/loop task. If that task was already registered, it
checks `esp_task_wdt_status()` instead of failing on duplicate registration.
The loop services the registered task each iteration. A setup failure latches
the firmware fault and leaves output off; the watchdog is not disabled.

Expected normal startup: no `task_wdt ... already initialized` error and no
watchdog fault message. A watchdog timeout remains a panic/reset, not a
success-shaped fallback. Low-voltage relay diagnostic mode returns before
network/watchdog setup because it is a separate minimal serial-only build; it
does not disable the ESP32 interrupt watchdog.

## Buzzer verification

The current firmware queues non-blocking active-HIGH pulses of 90 ms on and
90 ms off. In normal authenticated metered/credit firmware it requests two
startup pulses, one pulse only after a new credit journal is persistently
saved, and one exhaustion reminder after 120 seconds. It repeats reminders
at 120-second intervals while nonzero historical credit is fully exhausted;
the timer resets when credit returns. Duplicate/invalid tokens do not call the
success beep. An unused meter with no applied credit does not enter the
exhausted-credit reminder state.

Host-side `buzzer.cpp` tests pulse timing, repeated events, credit restoration,
and `millis()` rollover. The diagnostic-only profiles return before normal
startup/buzzer operation and are not the buzzer acceptance build.

## Backend deployment preparation (commands are not authorization)

Migration `meter.0034_prototypemeasurementtransition` depends on
`0033_ac_lab_sandbox_environment`. It adds a protected one-to-one
`PrototypeMeasurementTransition` receipt record with unique transition/receipt
IDs, prior/new baseline, journal counters, credit totals, immutable proposal
payload, and prepare/commit timestamps. It does not rewrite payment, loan,
token, allocation, credit, or device identity rows. The model uses `PROTECT`
and no data migration. Do not edit or reverse-delete the committed receipt.

New routes under `/api/v1/prototype-device/v1/`:

```text
POST measurement/prepare/
POST measurement/commit/
```

Existing `session/`, `redeem/`, `ack/`, and `telemetry/` routes remain in
place. The API requires `X-Device-Id` and `X-Device-Token`, validates existing
binding/environment/storage identity, and returns `output_authorized: false`.
SANDBOX firmware protocol remains `GPAWA_PZEM_V2`; UGX_DEMO remains
`GPAWA_PZEM_V1`. Existing payment/MTN Sandbox settlement services are not
replaced.

The current `session/` contract requires `credited_uwh`, `consumed_uwh`, and
`uncertain_uwh`. The current public Windows sketch includes these fields; do
not assume every older binary does. Confirm the exact deployed firmware
version's request contract before changing only the server. An older client
that omits required fields is not made compatible by the additive database
migration; keep the existing firmware/backend pairing until an approved
matched rollout.

For the current opt-in Alwaysdata sandbox profile:

- `PROTOTYPE_AC_LAB_ENABLED` defaults to `false`; enable it only for an
  approved sandbox test. It is not a production deployment instruction.
- `PROTOTYPE_RELAY_OUTPUT_ENABLED` is a hard-coded `False`, not an environment
  override.
- `PrototypeDevice.output_enabled` defaults to false and the database check
  constraint `ac_lab_output_disabled` requires false.
- Preserve `PROTOTYPE_PAYMENT_PROVIDER=MTN_SANDBOX`, existing MTN sandbox
  credentials/pricing policy, `ENERGY_TOKEN_ISSUANCE_ENABLED`, existing
  `ENERGY_TOKEN_ENCRYPTION_KEYS` and `ENERGY_TOKEN_LOOKUP_KEY`. Do not rotate
  token keys or alter account/payment/debt records as part of this migration.
- Preserve private `SECRET_KEY`, `ALWAYSDATA_HOSTNAME`, `DB_HOST`, `DB_NAME`,
  `DB_USER`, `DB_PASSWORD`, `DB_PORT`, `DB_SSLMODE=require`, email settings,
  CORS/CSRF/origin settings, and existing feature flags. `ALWAYSDATA_ENV_FILE`
  must remain outside the upload with the existing mode/ownership checks.
- Keep `DEBUG=false`, simulator/payment safety flags false as configured, and
  the private environment file untouched except through a separately approved
  deployment change.

Deployment sequence, only after separate approval:

1. Confirm the intended hosted account and database are the existing sandbox
   accounting environment, not production. Read and restore-test private code,
   environment, database, and device-key backups. Preserve payment schedules.
2. Review a no-delete, allowlisted source transfer and migration preview. Do not
   upload `.env`, private device configuration, virtualenv, static/media,
   database files, or firmware binaries.
3. Upload reviewed code only. In the existing host environment, run:

   ```bash
   export ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env
   export DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings
   /home/shanonsimon/energy-venv/bin/python -m pip check
   /home/shanonsimon/energy-venv/bin/python manage.py check_alwaysdata_database
   /home/shanonsimon/energy-venv/bin/python manage.py check --deploy
   /home/shanonsimon/energy-venv/bin/python manage.py showmigrations meter
   /home/shanonsimon/energy-venv/bin/python manage.py migrate --plan
   ```

   Confirm the actual database/TLS identity using the database-check command.
   Stop if `0033` is unexpectedly unapplied, any unrelated migrations are
   pending, the database differs from the intended sandbox, or any check fails.
4. Only after explicit migration authorization and a reviewed plan:

   ```bash
   /home/shanonsimon/energy-venv/bin/python manage.py migrate --noinput
   /home/shanonsimon/energy-venv/bin/python manage.py showmigrations meter
   /home/shanonsimon/energy-venv/bin/python manage.py check --deploy
   /home/shanonsimon/energy-venv/bin/python manage.py collectstatic --noinput
   ```

   Restart the hosted WSGI application only after migrations and static checks
   succeed. Never run these commands against production under this preparation
   task.
5. Read-only HTTP check:

   ```bash
   curl --fail-with-body --silent --show-error \
     https://<approved-host>/api/v1/features/
   ```

   Confirm the intended API/profile flags and no unexpected payment/provider
   effects. There is no special new health URL. An unauthenticated POST with an
   empty body to the existing device `session/` endpoint may be used to confirm
   the expected boundary (`401` when the capability is enabled; `503` when
   disabled); it cannot initialize a device because authentication precedes
   payload processing:

   ```bash
   curl --include --silent --show-error \
     -H 'Content-Type: application/json' --data '{}' \
     https://<approved-host>/api/v1/prototype-device/v1/session/
   ```

6. The authenticated prepare/commit verification is the isolated regression
   command below, or the real firmware's retry-safe flow on an explicitly
   provisioned staging device. Do not hand-craft a proposal or replay a
   migration request against an existing credit-bearing device: it is a
   one-time persistent transition. Check serial request IDs and the durable
   transition row through an authorized operator workflow; never print device
   tokens or private configuration.

Rollback precautions:

- Do not erase device NVS, restore an old journal, change binding/storage IDs,
  or upload a credit-only binary over an INTENT/PREPARED/COMMITTED migration.
- Before firmware writes INTENT, a compatible software rollback can leave the
  paused journal untouched. After INTENT, recover forward using the same
  transition ID/receipt. After backend commit, retain the transition table and
  recover forward with firmware that understands the committed journal.
- Never reverse `0034` by deleting transition receipts. A database restore
  must be coordinated with device journals and payment/accounting records;
  a stale backup is not a routine rollback.

## Existing-credit migration and physical commissioning order

1. Preserve the current private firmware identity, device credential, CA,
   meter/storage/binding/epoch, journal and all receipts/counters. Do not
   initialize or rebind the device.
2. Complete deployment/database checks on the approved non-production target
   with output authorization still false.
3. Keep the AC/load disconnected. Build profile B with the existing private
   configuration. Verify-only first; inspect map/size and compile logs. Do not
   upload without explicit approval.
4. In a separately approved migration window, the firmware authenticates,
   waits for three consecutive valid PZEM frames, persists INTENT, prepares and
   commits the exact proposal, then writes only the new baseline/version fields
   in the existing journal. The PZEM lifetime Wh is a baseline, not prior
   consumption. If interrupted, restore power/network and let the same
   transition ID/receipt retry; never clear NVS.
5. Confirm `COMMITTED`, preserved credit/counter/receipt, new baseline,
   post-baseline whole-Wh accounting, telemetry and reported output `OFF`.
   Keep GPIO14 undriven.
6. Complete the relay low-voltage procedure and record polarity, startup,
   inactive, reset, and power-loss observations. Separately review electrical
   bias, isolation, contact ratings, independent sensor validation, zero-credit
   shutoff, sensor/network faults, and watchdog behavior.
7. A future physical-output release requires a separately approved backend
   design change: the current hard-false setting/model constraint and
   `output_authorized=false` response must not be bypassed by device flags.
   Review its schema/policy, tests, staging behavior, rollback, and operator
   controls before an explicit output commissioning approval. Only then could
   profile C and an independently measured active level be considered.
   Physical AC commissioning is not authorized by this document.

Expected authenticated-mode serial lines include:

```text
MEASUREMENT_TRANSITION status=RECOVERING stage=INTENT baseline_wh=<Wh> output_authorized=NO
MEASUREMENT_TRANSITION status=COMMITTED baseline_wh=<Wh> prior_credit_preserved=YES output_authorized=NO
OUTPUT_STATUS block=OUTPUT_NOT_COMMISSIONED ... gpio14=NOT_DRIVEN
```

Exact recovery/error request IDs vary. A PZEM diagnostic build prints
`PZEM_STATUS status=VALID ...` only for validated measurements and
`PZEM_STATUS status=INVALID reason=...` on validation failure.

## Validation evidence and remaining limits

Completed checks for this source state:

- `python3 firmware/ac-lab-domain/tests/check.py` — passed journal/replay,
  PZEM frame/range/CRC/counter, accounting, diagnostic isolation, relay
  polarity guard, disabled-output guard, and buzzer host tests.
- Current Windows toolchain compile of authenticated metered mode, all
  diagnostics off and output off — passed using Arduino CLI 1.5.1,
  Arduino-ESP32 3.3.12, ArduinoJson 7.4.3, hd44780 1.3.2, and Keypad 3.1.1.
  Settings were the existing recorded FQBN (4 MB/default partition,
  PSRAM disabled); program size 402,198 bytes, 30% of 1,310,720 bytes; globals
  30,256 bytes, 9% of 327,680 bytes. Compile only; no upload.
- The GPIO14 diagnostic profile's Windows target compile was attempted, but
  did not complete in the available CLI session. Its mode/polarity compile-time
  guards and isolated host tests pass; the full-board diagnostic compile and
  all physical relay behavior remain unverified.
- Backend isolated regression:

  ```bash
  cd backend
  HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps \
    venv/bin/python deploy/test-hosting.py --sandbox-profile \
    meter.tests_measurement_transition meter.tests_prototype_device \
    meter.tests_credit_only meter.tests_mtn_device meter.tests_device_diagnostics
  ```

  Result: 48 tests passed; Django system check clean.
- Migration drift:

  ```bash
  cd backend
  HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps \
    venv/bin/python deploy/test-hosting.py --sandbox-profile --check-migrations
  ```

  Result: no model changes detected.
- Mobile regression: `cd mobile && npm test && npm run typecheck` — 91 tests
  passed; no TypeScript diagnostics.
- Web: `cd frontend && npx tsc --noEmit` and
  `cd frontend && npx eslint src/components/consumer/workspace.tsx` — passed.
- `git -c core.whitespace=cr-at-eol diff --check` — passed.

The earlier 46-test backend baseline passed before Phase 4 changes. Full
ESP32-S3 source compilation for the metered mode is now available through the
existing Windows installation; no WSL board packages were downloaded. No
firmware was uploaded, relay hardware was not tested, no AC was energized, no
hosted migration/deployment was run, and no production data was touched.
