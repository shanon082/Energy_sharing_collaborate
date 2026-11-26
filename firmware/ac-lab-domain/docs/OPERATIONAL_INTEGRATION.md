# Operational firmware integration

`firmware/ac-lab-domain/GpawaAC` is the canonical public source. The external Arduino sketch currently defaults to authenticated credit-only and hard-rejects commissioned output. Its private configuration and its older public code are independent of this repository. Compare the public files before switching source. Keep the existing `DeviceConfig.h`, `NetworkConfig.h` (if present), credentials, TLS root, binding and journal identity.

When the build input can be changed, copy the canonical public files listed by `git ls-files firmware/ac-lab-domain/GpawaAC` and include the new public headers `BuzzerCore.h` and `RecoveryCore.h`. Review any other public files added to the canonical sketch. Use a private staging folder named `GpawaAC` for a side-by-side comparison, copy the existing private files into it unchanged, and verify their hashes locally. Use the reviewed staging folder as the Arduino sketch or replace only those identified public files in the external folder. Avoid mirroring or deleting the external folder. Preserve the existing Arduino board options and confirm the actual partition table and application slot before preparing any future upload. Build metadata for a local diagnostic artifact cannot establish the device's partition layout.

Use the compile-only profile runner with the recorded full FQBN and compatible installed libraries (ESP32 Arduino 3.x, ArduinoJson 7, Keypad and hd44780). For example, from the repository:

```sh
python3 firmware/ac-lab-domain/build_profile.py metered --flags-only
python3 firmware/ac-lab-domain/build_profile.py metered \
  --fqbn "$GPAWA_CONFIRMED_FQBN" --sketch "$GPAWA_PRIVATE_SKETCH" \
  --build-path "$GPAWA_SCRATCH_BUILD"
```

For Windows Arduino CLI from WSL, pass the existing executable with `--cli` and add `--windows-paths`. Each profile prints its explicit effective defines. The metered build has PZEM diagnostics and authenticated credit-only both disabled. No relay GPIO is driven. The commissioned profile needs the measured polarity via `--relay-active-level` and is for use only with the existing physical commissioning checks. Its compile flags express the operator's choice of commissioned profile, while operation still requires the backend lease and local interlocks. The diagnostic profiles are separate. Relay diagnostics drives only the controller input on explicit serial commands and is for the disconnected contact test.

| Profile | Mode | PZEM diagnostic | Relay diagnostic | Credit-only | Commissioned output | Approval |
|---|---|---:|---:|---:|---:|---:|
| `pzem-diagnostic` | Read-only UART evidence | 1 | 0 | 0 | 0 | 0 |
| `relay-diagnostic` | Isolated contact diagnostic | 0 | 1 | 0 | 0 | 0 |
| `metered` | PZEM, display, keypad, private journal, HTTPS and telemetry | 0 | 0 | 0 | 0 | 0 |
| `commissioned` | Metered operation with commissioned GPIO control | 0 | 0 | 0 | 1 | 1 |

All four set Wi-Fi diagnostic and USB exercise flags to 0. The default sketch without flags remains PZEM diagnostic. The actual relay polarity and flash options are deployment inputs. Test binaries with example configuration or fixture polarity are compile evidence only.

## Recovery contract

- Operational firmware advertises `GPAWA_RECOVERY_V1` over the existing authenticated device protocol. Apply the server migration through `0036` before using a matching firmware build. Once a binding opts in, a legacy session cannot update its ledger. A session returns the last verified ledger position and denies output. Its reported counter and debit are recovery targets that can hold output off until verified by telemetry. Pending commands are recovered from that session, while ACK retries retain the original persisted receipt.
- A fresh journal establishes an authenticated baseline with zero debit. A paused journal uses its preserved credit and the prepare/commit receipt, and starts measuring at a new PZEM counter value. Legacy metered journals can continue from compatible server telemetry. An unanchored legacy journal with zero accumulated debit can preserve its local baseline, which permits accounting for subsequent deltas. Incompatible or unverifiable historical debit requires operator review.
- The NVS `state` layout and namespace stay unchanged. The existing `migration` record uses its former reserved byte for baseline source, with zero still meaning paused. `telemetry` holds one immutable payload until acknowledged. It replays before a new boot session, so an accepted request whose reply was lost produces one row. A retry header inhibits lease issuance even if the original upload never arrived. The counter and debit are checkpointed before an outbox write. The independent PZEM counter bridges a restart before a checkpoint. `meterProof` saves a validated observation at a sensor fault when an unsent delta remains, and can bridge a restart during the fault. Missing evidence keeps recovery pending until it can be measured.
- A top-up keeps output inhibited while the old epoch is closed. The old epoch's valid sample and sequence must be accepted before the local credit is applied. `creditProof` stores that reference before the credit journal write. The ACK verifies the stored reference and any duplicate must match the original receipt and checkpoint. An advance beyond zero credit stays measured Wh without being charged later to the new epoch.
- Only a newly accepted healthy sample from the current boot can renew the server lease. A retained old observation can settle its counter delta during a fault while output remains inhibited. The firmware measures relative permission from request enqueue, charges queue and transport delay against it and discards replies from an earlier local safety state. The UART poll uses the diagnostic RX settings and 500 ms/20 ms framing, with bounded per-loop reads and no wait for a frame on the control loop.
