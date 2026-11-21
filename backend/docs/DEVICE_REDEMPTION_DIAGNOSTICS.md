# One-attempt ESP32 redemption diagnostics — 21 November 2026

Diagnostics implemented locally. **The hosted token rejection is not reproduced
or confirmed fixed.** No token reset, NVS erase, re-provisioning, replacement
credit, payment, deployment or flash was performed. Unrelated feature work is
paused. No Android/frontend change or APK rebuild is needed for this patch.

## What changes

Runtime backend changes are limited to four files:

- `meter/diagnostics.py`: request-scoped UUID correlation, fixed stage/code logs,
  dedicated metadata-only INFO stream (including successful replies), sanitized
  stack locations/type only. No request object, bodies, exception message, source
  lines or local variables enter diagnostic records. Existing custom handlers
  are respected; if one is configured, ensure only meter.device permits INFO.
- `meter/api/prototype_views.py`: echo X-Request-ID, add request_id to errors only,
  generic/redacted errors including unexpected handler/serialization failures.
  Success JSON and signed command payloads remain unchanged. Unknown input IDs
  are regenerated, never echoed. Missing and other-meter tokens have identical
  public rejection status/code/message; operator stages distinguish them.
- `meter/prototype_device.py`: stage observations at existing guards; no new
  business mutations, allocations, commands, checks bypasses or retries.
- `backend/hosting_middleware.py`: correlate a blocked/missing device route only;
  preserve the exact capability/route restrictions. Ordinary routes unchanged.

Firmware changes are only public `Firmware.cpp` and `SafeDiagnostics.h` in the
existing active sketch. Request IDs live in RAM and HTTP metadata, never NVS,
receipt identity, token text, signed JSON or credit state. Each HTTP attempt gets
an independent UUID; existing command/receipt identities drive idempotency.
Header-stripping proxies can use the validated error-envelope ID as fallback.
Only canonical UUID4 values and fixed code literals may enter logs.

Firmware separates connection/TLS, HTTP rejection, malformed JSON, invalid
identity/command, persistent write/verify and ACK failures. A 2xx HTTP response
is recorded separately from CREDIT_SAVED and ACK_CONFIRMED. It is never proof of
load switching. ESP32's generic TLS error -1 is ambiguous between TCP connection
and certain handshake timeouts: it is honestly labelled
CONNECTION_OR_TLS_FAILURE, not asserted to be a certificate error. More specific
TLS-stack errors are labelled TLS_FAILURE; raw TLS text is discarded.

## Smallest safe backend upload

**Do not upload the whole dirty checkout or the previous loan/payment package.**
Those contain unrelated work. Two diagnostic-only patch variants preserve either
known baseline's own business code, including its current loan/policy behavior.
The committed-base patch does not introduce the uncommitted UGX lending branch.
Both variants update only the four runtime files above. Each has been dry-run,
applied and syntax-checked against its exact preimage in a temporary directory;
reapplication is refused and service business-mutation call sequences are unchanged.

A single matched patch is sufficient. The small allowlist uploads both choices
plus their checksums/preimage manifest so the correct choice can be identified:

```text
deploy/device-diagnostics-head.patch
deploy/device-diagnostics-prior-release.patch
deploy/device-diagnostics-bases.json
```

From the existing repository, first upload dry-run (no secrets, env, keys,
virtualenv, databases, firmware binaries or generated files in this allowlist):

```bash
rsync -avni --files-from=backend/deploy/device-diagnostics.files backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/.local/device-diagnostics/
# Review the list. Create the private staging directory on the host if needed:
ssh shanonsimon@ssh-shanonsimon.alwaysdata.net 'umask 077; mkdir -p /home/shanonsimon/.local/device-diagnostics'
rsync -avi --files-from=backend/deploy/device-diagnostics.files backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/.local/device-diagnostics/
```

On the host, identify the exact source baseline without importing Django or
connecting to a database (file hashes only, no credential files):

```bash
cd /home/shanonsimon/energy-sharing
/home/shanonsimon/energy-venv/bin/python - <<'PY_CHECK'
import hashlib,json
from pathlib import Path
known=json.loads(Path('/home/shanonsimon/.local/device-diagnostics/deploy/device-diagnostics-bases.json').read_text())
for variant,entry in known.items():
    def matches(expected):
        return all((hashlib.sha256(Path(p).read_bytes()).hexdigest() if Path(p).is_file() else None)==digest for p,digest in expected.items())
    print(variant, 'MATCH' if matches(entry['before']) else 'ALREADY_INSTALLED' if matches(entry['after']) else 'NO_MATCH')
PY_CHECK
```

Proceed only with exactly one MATCH. ALREADY_INSTALLED means do not apply again.
If neither matches, stop and report only the mismatching filenames; a new patch
must preserve that host's changes. Do not reset code, choose an approximate
version, or use patch fuzz to force installation.

Back up only these source files privately, then preview/apply the matched patch:

```bash
umask 077
export GPAWA_DIAG_BACKUP="/home/shanonsimon/.local/backups/device-diagnostics/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$GPAWA_DIAG_BACKUP"
cp --parents -p meter/api/prototype_views.py meter/prototype_device.py backend/hosting_middleware.py "$GPAWA_DIAG_BACKUP/"
if test -f meter/diagnostics.py; then cp --parents -p meter/diagnostics.py "$GPAWA_DIAG_BACKUP/"; fi
# Set this to the variant printed MATCH; this example is not an assumption:
GPAWA_DIAG_VARIANT=prior-release
GPAWA_DIAG_PATCH="/home/shanonsimon/.local/device-diagnostics/deploy/device-diagnostics-$GPAWA_DIAG_VARIANT.patch"
patch --dry-run --batch --forward --fuzz=0 -p1 < "$GPAWA_DIAG_PATCH"
# Review. If the exact dry-run succeeds:
patch --batch --forward --fuzz=0 -p1 < "$GPAWA_DIAG_PATCH"
/home/shanonsimon/energy-venv/bin/python -m py_compile meter/diagnostics.py meter/api/prototype_views.py meter/prototype_device.py backend/hosting_middleware.py
```

There are **no migrations, dependency installs or environment changes**. Keep the
existing private environment, MTN mode/keys, all seven deferred features, email
schedule, device binding and physical-output prohibition unchanged. Restart only
the existing shanonsimon.alwaysdata.net WSGI site via alwaysdata Web → Sites →
select that site → Restart. No global service restart or worker is required.

Optional credential-free readiness check after restart:

```bash
GPAWA_TRACE_ID="$(python3 -c 'import uuid; print(uuid.uuid4())')"
curl --silent --show-error --include --request POST https://shanonsimon.alwaysdata.net/api/v1/prototype-device/v1/session/ --header "X-Request-ID: $GPAWA_TRACE_ID" --header 'Content-Type: application/json' --data '{}'
```

Expect401 DEVICE_UNAUTHORIZED with matching X-Request-ID/request_id when the lab
is enabled. If the existing profile blocks it, expect503 and hosting_policy in
operator logs; this task does not enable it. No device credential/token is used
and this does not grant credit. A missing route is request_routing, not a token
failure. If neither header nor body ID arrives, confirm this code/site was
reloaded before changing networking or authentication.

## Firmware build and later operator upload

Active sketch: `C:\Users\USER\OneDrive\Documents\Arduino\GpawaAC`.
The two public files have already been updated there. Do not reapply the public
patch a second time or replace private headers. `request-correlation.patch` is
for review/another exact baseline only. Existing journal/state layout, namespace,
counters, binding, credentials, hd44780 and keypad remain unchanged. Compiled
modes remain authenticated credit-only; no AC/PZEM is required and output is
compile-prohibited. The build contains the existing device credential, so keep
its binaries/compiler logs private and outside Git/upload packages.

Exact ESP32-S3 target compile passed using existing CLI1.5.1/core3.3.12:

- Sketch uses 1083513 bytes (82%) of program storage space. Maximum is 1310720 bytes.
- Global variables use 49880 bytes (15%) of dynamic memory, leaving 277800 bytes for local variables. Maximum is 327680 bytes.
- Private application: `C:\Users\USER\AppData\Local\Temp\gpawa-request-trace-20261120T231452Z\artifacts\GpawaAC.ino.bin`.
- Size:1,083,664bytes; SHA256:`ec21b064173809657e4096ab764f9b8db5d13676a382d9fce6b23ed609cd41db`.
- DeviceConfig.h and NetworkConfig.h checksum-verified unchanged.
- Full preserved FQBN: `esp32:esp32:esp32s3:UploadSpeed=921600,USBMode=hwcdc,CDCOnBoot=default,MSCOnBoot=default,DFUOnBoot=default,UploadMode=default,CPUFreq=240,FlashMode=qio,FlashSize=4M,PartitionScheme=default,DebugLevel=none,PSRAM=disabled,LoopCore=1,EventsCore=1,EraseFlash=none,JTAGAdapter=default,ZigbeeMode=default`.

For operator upload **later**, use the existing Arduino IDE sketch/board/port,
EraseFlash=none and the same partition layout. Keep relay/load disconnected and
use USB only. Verify, then Upload to the already-provisioned board; never erase
all flash/NVS or generate a new identity. Alternatively, after substituting the
existing board's actual port, the equivalent PowerShell command is:

```powershell
$gpawaPort = 'REPLACE_WITH_EXISTING_COM_PORT'
& 'C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe' upload --fqbn 'esp32:esp32:esp32s3:UploadSpeed=921600,USBMode=hwcdc,CDCOnBoot=default,MSCOnBoot=default,DFUOnBoot=default,UploadMode=default,CPUFreq=240,FlashMode=qio,FlashSize=4M,PartitionScheme=default,DebugLevel=none,PSRAM=disabled,LoopCore=1,EventsCore=1,EraseFlash=none,JTAGAdapter=default,ZigbeeMode=default' --port $gpawaPort --input-dir 'C:\Users\USER\AppData\Local\Temp\gpawa-request-trace-20261120T231452Z\artifacts' 'C:\Users\USER\OneDrive\Documents\Arduino\GpawaAC'
```

This upload command has **not** been executed. No board/provider/phone testing
is claimed. The compiled credential-bearing binary is not in the public bundle.

## Reproduce once and share only safe lines

1. Open Serial Monitor at115200 after the backend restart and firmware upload.
   Confirm this is authenticated credit-only mode, not Wi-Fi-only diagnostics.
2. Enter the **existing** purchased15-digit token once on its bound meter, keeping
   leading zeros. Press # once. Do not buy again, reset tokens/NVS or re-provision.
3. Copy only the failing `DEVICE request_id=...` Serial line(s). The firmware uses
   the safe server ID when available; correlation=matched/mismatch/missing reports
   the metadata match. A missing header can fall back to a valid error-envelope ID.
4. Retrieve matching operator lines, e.g. on the host (if this account's standard
   log directory exists; otherwise use the site's WSGI error-log viewer):

```bash
GPAWA_TRACE_ID='PASTE_ONLY_THE_UUID_FROM_THE_DEVICE_LINE'
rg --no-heading --no-filename --fixed-strings "DEVICE request_id=$GPAWA_TRACE_ID operation=" /home/shanonsimon/admin/logs
```

Example of one correlated failure (illustrative UUID; no token/credential):

```text
DEVICE request_id=10000000-0000-4000-8000-000000000001 operation=redeem http=404 category=HTTP_REJECTION cause=HTTP_REJECTION stage=http_rejection code=TOKEN_UNAVAILABLE correlation=matched
DEVICE request_id=10000000-0000-4000-8000-000000000001 operation=redeem http=404 stage=token_lookup code=TOKEN_LOOKUP_MISS
```

The first is safe device output; the second is the private operator distinction.
Wrong-meter/environment rejection gives the same public token response but an
operator stage=meter_environment_mismatch. Source, already-used, pending and
conflicting-command failures have their own stages. Unexpected errors return
INTERNAL_ERROR plus UUID; the operator event has exception type/stack locations,
never message/source lines/local variables/request bodies.

For connection/TLS/clock/readiness failures there may be no Django request;
category/stage and http=0 identify the local boundary. For valid HTTP200 followed
by INVALID_JSON/COMMAND_VALIDATION_FAILURE, the matching server INFO event is
retained and the device's local stage identifies the rejection. ACK_FAILURE has
its own request ID and a fixed cause such as HTTP_REJECTION or INVALID_JSON.
CREDIT_SAVED means durable journal write/verify succeeded; ACK_CONFIRMED means
Django accepted its receipt. Neither means the relay/load was switched on.

Share only those safe DEVICE lines and the short LCD message. Do not share token
digits, credential headers, private configuration, complete responses or compiler
logs. Keep an uncertain pending command intact for diagnosis. No retry is allowed
to mint another allocation/credit; normal existing retry/durable recovery is unchanged.

## Local verification and limits

- 60 focused PostgreSQL device/credit/feature regression tests passed with mocked
  external I/O; a final12-case database-free diagnostic suite verifies the final
  logger/renderer/redaction behavior. These counts overlap, not72 unique cases.
- Repository and active-sketch host C++ suites test classification, UUID validation,
  arbitrary-code/header redaction, persistent credit, duplicate/restart/lost-ACK
  recovery, exact signed command vectors and compile-time output prohibition.
- Both diagnostic-only patch variants dry-run/apply/syntax-check exactly; repeated
  application is refused and source business-mutation call sequences match before.
- Actual ESP32-S3 compile passed; private headers unchanged. No schema changes,
  operational DB access, hosted install, flash, new payment or physical test.
- An initial old regression assertion expected the previous log string without
  stage; its format assertion was corrected, with no credit behavior change.

The root cause of the hosted token rejection remains **unconfirmed** until the
single correlated attempt is collected. This release supplies the evidence path;
it does not infer that token, key, owner or environment is wrong.

Exact local commands (isolated test launcher blocks external HTTP; no hosted DB):

```bash
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --sandbox-profile --slow-test-cleanup meter.tests_device_diagnostics meter.tests_mtn_device meter.tests_credit_only meter.tests_prototype_device backend.tests_feature_flags loan.tests_ugx_lab.UGXLabTests.test_token_lookup_diagnostics_preserve_leading_zeros_and_do_not_log_them
HOSTING_TEST_EXTRA_PATH=/tmp/gpawa-alwaysdata-deps backend/venv/bin/python backend/deploy/test-hosting.py --sandbox-profile meter.tests_device_diagnostics.DeviceDiagnosticTests
python3 firmware/ac-lab-domain/tests/check.py
python3 firmware/ac-lab-domain/tests/check.py --sketch /mnt/c/Users/USER/OneDrive/Documents/Arduino/GpawaAC
```

The test-only cleanup allowance changes isolated DB lifecycle timeouts, not
financial-query or hosted request timeouts. No tests use live providers/devices.
To undo later, use the private source backup or an exact reverse dry-run of the
matched patch, then restart that WSGI site. There is no data migration to reverse.
