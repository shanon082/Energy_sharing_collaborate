**Latest change:** fixed-code token diagnostics added to the active sketch. No token rejection cause is yet confirmed from hosted evidence. See [the diagnostic/lending handoff](../../backend/docs/UGX_LENDING_AND_TOKEN_DIAGNOSTICS.md). Earlier build/mode notes below retain their dates; do not reapply old patches.

# AC_LAB SANDBOX integration sources

**Current milestone (2026-11-19):** see [authenticated USB-powered credit testing](docs/USB_CREDIT_ONLY.md).
The active sketch and this public snapshot now use WIFI_TEST=0,
AUTH_CREDIT_ONLY=1, USB_EXERCISE=0 and output=0. Existing private credentials,
binding and NVS are preserved. No PZEM/AC measurement is required for credit.
The earlier mode/default/source-application notes below describe the2026-11-18
milestone; do not reapply its old patch to the updated active sketch. The new
`authenticated-credit-only.patch` is against the separately recorded current
baseline, and is retained for review/reproduction, not for double application.

These are the public source changes for the **active** sketch:
`C:\Users\USER\OneDrive\Documents\Arduino\GpawaAC` (WSL:
`/mnt/c/Users/USER/OneDrive/Documents/Arduino/GpawaAC`).

The previous `gPawa-S3-Keypad-Update/docs/API_CONTRACT.md` was inspected for the
wire specification. The active sketch has additional hd44780 display and Wi-Fi
diagnostic changes. Those changes are preserved here, including `WifiCheck.cpp`.
Neither private `DeviceConfig.h` nor private `NetworkConfig.h` is included.

The seven reviewed public files were applied to that corrected active sketch on
2026-11-18 after approval. Public backup:
`C:\Users\USER\OneDrive\Documents\Arduino\GpawaAC.public-before-sandbox-20261118T194907Z`.
Private headers were checksum-verified unchanged; diagnostic mode remains1.
The patch is retained for review/reproduction, **not for reapplying to this copy**.

`public-firmware.patch` applies to the flat active sketch directory. Its baseline
public-file hashes are in `UPSTREAM_SHA256.json`. Do not apply it to the older
package folder. Review changes if any baseline public file has changed since
inspection. No board firmware has been built, uploaded or flashed by this work.

## Manual source application, after reviewing/backing up public files

```bash
cd /mnt/c/Users/USER/OneDrive/Documents/Arduino/GpawaAC
patch --dry-run -p1 < /home/shanon/projects/next_projects/Energy-sharing-project/firmware/ac-lab-domain/public-firmware.patch
# Only after reviewing the dry-run and backing up the public files:
patch -p1 < /home/shanon/projects/next_projects/Energy-sharing-project/firmware/ac-lab-domain/public-firmware.patch
```

Do not overwrite private headers or erase NVS. Do not apply the patch a second
time to an already updated sketch. Updating source does not change a flashed
board. Arduino target compilation and physical-board tests remain required.

## Explicit mode and commissioning

- `GPAWA_WIFI_TEST=1` remains the active sketch's diagnostic default. It uses
  private `NetworkConfig.h`, tests Wi-Fi/keypad/PZEM only, and does not call Django,
  write credit or accept tokens. The placeholder example is a safe compile fallback.
- Authenticated operation requires explicit `GPAWA_WIFI_TEST=0`,
  `GPAWA_USB_EXERCISE=0`, `GPAWA_COMMISSIONED_OUTPUT=0`, reviewed provisioning and
  private `DeviceConfig.h`. The display retains hd44780. Physical output enablement
  causes a compile error; the relay/load supply must also remain disconnected.
- Public `DeviceDomain.h` selects `commissioning::ENVIRONMENT="SANDBOX"`.
  The private header does not need a newly invented ENVIRONMENT member. Retain its
  unique credential, meter/device/storage/epoch values and verified CA; make them
  match a new explicit SANDBOX binding, not an existing UGX identity.
- `API_BASE` is `https://shanonsimon.alwaysdata.net/api/v1`; no duplicate suffix,
  disabled certificate verification or redirect following.
- `ALLOW_FIRST_BOOT=true` is only for an unused, newly provisioned identity.
  After commissioning set it false. A used server binding refuses erased-storage
  initialization. Do not turn it on to clear a reconciliation error.
- SANDBOX journal: `gpawa_sbx2`; legacy UGX: `gpawa_ac1`; explicit USB exercise:
  `gpawa_ex2`. Previous journals are preserved. No currency/balance migration.

## Host-side validation (no board or provider access)

```bash
python3 firmware/ac-lab-domain/tests/check.py
# Test the public headers actually applied to the active sketch too:
python3 firmware/ac-lab-domain/tests/check.py --sketch /mnt/c/Users/USER/OneDrive/Documents/Arduino/GpawaAC
```

Requires Linux g++ and the existing ArduinoJson headers (the script accepts
`--arduinojson /path/to/ArduinoJson/src`). It exercises the existing credit/reboot/
CRC/PZEM core, V1/V2 canonical SHA256 command vectors, wrong-domain/meter rejection,
lost ACK, duplicate command persistence and compile-time output prohibition.
Digest vectors test canonical JSON against Python SHA256; the firmware's unchanged
mbedtls crypto primitive is not independently tested by that callback.

The Windows Arduino CLI exists (version1.5.1), but approval to query its installed
cores was declined, so **no ESP32 target compile is claimed**. After source/private
configuration review, use the existing IDE board settings (ESP32S3 Dev Module,
installed Arduino-ESP323.x and existing partition/USB settings), Verify only first.
Dependencies: ArduinoJson, hd44780, Keypad, plus ESP32 built-ins. Do not install or
upgrade toolchains just to obtain a passing result; report exact compiler errors.

See [the device contract](docs/API_CONTRACT.md) and
[backend rollout](../../backend/docs/MTN_AC_LAB_SANDBOX.md) for protocol examples,
server provisioning and the separately authorized real sandbox/board test.
