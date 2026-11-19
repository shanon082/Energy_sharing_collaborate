# Authenticated USB-powered credit build — 2026-11-19

**Target compilation passed. No flash, deploy, payment or physical test performed.**

The corrected active sketch at `C:\Users\USER\OneDrive\Documents\Arduino\GpawaAC`
now matches the repository's three reviewed public files: Firmware.cpp, MeterCore.h
and HardwareConfig.h. DeviceConfig.h and NetworkConfig.h were checksum-verified
unchanged before and after compilation; device/meter/storage/environment/epoch
configuration was not replaced. Existing unrelated repository changes were retained.

- Arduino CLI:1.5.1; existing installed Arduino-ESP32 core:3.3.12.
- Target: ESP32S3 Dev Module with its exact cached board options below.
- Sketch uses 1078073 bytes (82%) of program storage space. Maximum is 1310720 bytes.
- Global variables use 49864 bytes (15%) of dynamic memory, leaving 277816 bytes for local variables. Maximum is 327680 bytes.
- Exported application binary:1,078,224bytes.
- Application SHA256:`b208194f355f266d15cb092f4b348ece0c94efd163bf432ea15d9082c144812b`.
- Private Windows build directory:`C:\Users\USER\AppData\Local\Temp\gpawa-auth-credit-only-20261119T090719Z`.
- Application:`C:\Users\USER\AppData\Local\Temp\gpawa-auth-credit-only-20261119T090719Z\artifacts\GpawaAC.ino.bin`.
- WSL application:`/mnt/c/Users/USER/AppData/Local/Temp/gpawa-auth-credit-only-20261119T090719Z/artifacts/GpawaAC.ino.bin`.
- Public-source backup:`/mnt/c/Users/USER/OneDrive/Documents/Arduino/GpawaAC.public-before-auth-credit-only-20261119T090719Z`.

Configured binaries and the private compiler log remain outside Git. They contain
or may reference the existing device credential; keep them private. No private
header, filled configuration or firmware binary was copied into the repository.

## Actual compile command (PowerShell reproduction, no upload)

```powershell
& 'C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe' compile --fqbn 'esp32:esp32:esp32s3:UploadSpeed=921600,USBMode=hwcdc,CDCOnBoot=default,MSCOnBoot=default,DFUOnBoot=default,UploadMode=default,CPUFreq=240,FlashMode=qio,FlashSize=4M,PartitionScheme=default,DebugLevel=none,PSRAM=disabled,LoopCore=1,EventsCore=1,EraseFlash=none,JTAGAdapter=default,ZigbeeMode=default' --jobs 2 --build-path 'C:\Users\USER\AppData\Local\Temp\gpawa-auth-credit-only-20261119T090719Z' --output-dir 'C:\Users\USER\AppData\Local\Temp\gpawa-auth-credit-only-20261119T090719Z\artifacts' 'C:\Users\USER\OneDrive\Documents\Arduino\GpawaAC'
```

The full FQBN came from the active sketch's cached build.options.json. Flash4MB,
default partitions,qio,disabled PSRAM,hardware USB CDC/JTAG,CDC-on-boot disabled,
240MHz and erase-none were retained. No core/library upgrade was installed.
The first sandboxed Windows-tool call could not bind WSL's interop socket; the
approved invocation outside that sandbox compiled successfully.

No --upload, --port, monitor, NVS-read/reset, provider request or relay operation
was used. A future separately authorized upload must preserve NVS and erase-none;
do not use full-flash erase or write the generated merged image across NVS.

## Mode and behavior

AUTH_CREDIT_ONLY=1, WIFI_TEST=0, USB_EXERCISE=0, output=0. USB supplies power;
Wi-Fi, time and verified HTTPS are still required. Real V2 token redemption and
ACK use the existing binding. There are no local synthetic token shortcuts.
The LCD alternates saved credit and “Consumption / unavailable”; D cannot arm.
Session heartbeats replace telemetry in this mode. No PZEM value is fabricated.

The journal upgrades in place from2 to3 while retaining layout,NVS key,identity,
balances,receipts and counters. The marker prevents older binaries from accepting
a paused baseline. Turning credit-only off or reconnecting PZEM cannot deduct
lifetime energy: metered activation is blocked until explicit baseline reconciliation
is implemented. This limitation is intentional; no baseline was invented.

## Local checks

- `python3 firmware/ac-lab-domain/tests/check.py`: passed.
- Same command with `--sketch /mnt/c/Users/USER/OneDrive/Documents/Arduino/GpawaAC`:
  passed against the actual applied headers. Pure credit/reboot/CRC/PZEM regression,
  V1/V2 digest/domain tests, new sensor-free recovery tests and compile-time output/
  mode prohibition all passed. Digest vectors test serialization against Python;
  they are not an independent test of the unchanged mbedtls implementation.
- Isolated PostgreSQL: **45 tests passed in113.577s**, including sensor-free first
  redemption, duplicate/wrong-meter token, repeated heartbeat, reboot before/after
  ACK, lost ACK response, owner-only reads and existing MTN/feature-flag regressions.
  Providers/devices were mocked and inherited operational configuration was cleared.
- `git diff --check`: passed.

Backend command:

```bash
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --sandbox-profile meter.tests_credit_only meter.tests_mtn_device meter.tests_prototype_device backend.tests_feature_flags
```

The backend addition is tests only; no runtime/API/schema change, hosting restart,
reprovisioning or new migration is needed for this mode. The existing MTN/SANDBOX
V2 deployment is assumed, as confirmed by the operator. No hosted records were
inspected. Seven disabled features, relay/payment restrictions and prior work remain.
No web/mobile source changed in this phase; no new APK was built.

Actual USB board,Wi-Fi/TLS,keypad and physical journal durability testing remains
outstanding. See [USB_CREDIT_ONLY.md](docs/USB_CREDIT_ONLY.md) for the later board
checklist and the explicit measurement/baseline restriction.
