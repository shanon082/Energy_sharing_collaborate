# Token diagnostics target build — 2026-11-20

**ESP32-S3 compile passed. No upload, flash, hosted deployment or board test.**

The active sketch is `C:\Users\USER\OneDrive\Documents\Arduino\GpawaAC`.
Only public Firmware.cpp and SafeDiagnostics.h changed in this diagnostic step.
DeviceConfig.h and NetworkConfig.h were checksum-verified unchanged. Existing
NVS/journal structures, storage namespace, credentials/binding/counters, keypad,
hd44780, TLS and credit-only mode remain intact. Do not reapply the patch to this
already updated sketch or reprovision the existing device.

- Arduino CLI1.5.1, Arduino-ESP323.3.12; existing exact board options.
- Target: ESP32S3 Dev Module;4MB flash/default partition/qio/noPSRAM.
- Sketch uses 1079989 bytes (82%) of program storage space. Maximum is 1310720 bytes.
- Global variables use 49864 bytes (15%) of dynamic memory, leaving 277816 bytes for local variables. Maximum is 327680 bytes.
- Application binary:1,080,144bytes, SHA256:`832af53d73eb9837891a1f7edd9eb7feab08bee42c5051e9824c6df43f2b8eec`.
- Private Windows artifact:`C:\Users\USER\AppData\Local\Temp\gpawa-diagnostics-20261120T073121Z\artifacts\GpawaAC.ino.bin`.
- Private WSL artifact:`/mnt/c/Users/USER/AppData/Local/Temp/gpawa-diagnostics-20261120T073121Z/artifacts/GpawaAC.ino.bin`.
- Public-source backup:`/mnt/c/Users/USER/OneDrive/Documents/Arduino/GpawaAC.public-before-diagnostics-20261120T073121Z`.
- Firmware binary/compiler log contain or may reference the existing credential;
  they are **not** copied into Git or the public release archive.

## Reproduce Verify only (not Upload)

```powershell
& 'C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe' compile --fqbn 'esp32:esp32:esp32s3:UploadSpeed=921600,USBMode=hwcdc,CDCOnBoot=default,MSCOnBoot=default,DFUOnBoot=default,UploadMode=default,CPUFreq=240,FlashMode=qio,FlashSize=4M,PartitionScheme=default,DebugLevel=none,PSRAM=disabled,LoopCore=1,EventsCore=1,EraseFlash=none,JTAGAdapter=default,ZigbeeMode=default' --jobs 2 --build-path 'C:\Users\USER\AppData\Local\Temp\gpawa-diagnostics-20261120T073121Z' --output-dir 'C:\Users\USER\AppData\Local\Temp\gpawa-diagnostics-20261120T073121Z\artifacts' 'C:\Users\USER\OneDrive\Documents\Arduino\GpawaAC'
```

For operator-authorized upload later, use the existing Arduino IDE board and port
with these exact options. Keep EraseFlash=none, the same partition layout/private
headers and output0. Do not erase all flash/NVS or upload a replacement identity.
Disconnect the relay/load and use USB power only for this milestone. The current
source prohibits mains/output even if a client asks for it.

## Actual software evidence versus physical work

Both repository and active-sketch host C++ suites passed all5 groups: persistent
credit/CRC, V1/V2 exact digest/domain vectors, duplicate/lost-ACK/reboot recovery,
sensor-free authenticated credit and fixed-code diagnostic privacy. Compile-time
attempts to enable relay/exercise in authenticated credit mode fail as required.
These emulate journal recovery; they are **not** a real NVS/power-cut test.

After the backend and diagnostic firmware are deployed by the operator, obtain
one sanitized normal `redeem` line such as
`DEVICE operation=redeem http=404 code=TOKEN_LOOKUP_MISS`. Never send token digits,
credentials, headers or full response bodies. The existing purchased token's
specific rejection remains unconfirmed until that evidence/read-only audit is
available. Do not buy again, clear the token or reset credit to diagnose it.

See [the coordinated handoff](../../backend/docs/UGX_LENDING_AND_TOKEN_DIAGNOSTICS.md)
for the read-only audit, exact backend rollout and ordered demonstration checks.
