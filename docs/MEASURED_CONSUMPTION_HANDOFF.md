# Physical measured consumption handoff

## Read contract and coverage

`GET /api/v1/meter/mobile-meters/<meter_id>/measured-consumption/?environment=SANDBOX&days=7`
requires the consumer's authentication and current meter assignment. `environment`
is explicit (`SANDBOX`, `UGX_DEMO`, or `CORE`). The response identifies the meter,
energy environment and physical source. It contains recent voltage, current, power,
PZEM cumulative kWh, last reported remaining credit in a separate field, both
measurement timestamps, interval history, and output permission. The last relay
command is a controller report. Physical contact feedback is `UNKNOWN`.

Periods are 1, 7 or 30 UTC calendar dates through the current instant. Daily
buckets use UTC midnight. Totals are exact sums of whole-Wh counter differences
reported as decimal kWh. Consecutive valid samples must have matching device,
binding and baseline, the same boot and consecutive sequence, a positive time
span at most 90 seconds, a nondecreasing counter, and both endpoints within the
same day and requested period. Compatible deltas across midnight, a restart or
an upload gap appear in interval history and in the separate unallocated total
if both endpoints are in the period. An interval crossing period start is shown
in history and excluded from both period totals. A fault, reset, device change,
binding change or baseline transition breaks the chain. The first observation in
a chain does not imply any consumption. Coverage is the duration of included
intervals divided by the observed part of the window. A missing total is `null`.
A valid unchanged counter contributes zero. No interpolation or time allocation
is applied. `history_truncated` indicates when more than 120 observations were
used. Credit, entitlement, balance snapshots and simulator history do not enter
the totals. A retained valid observation sent while the sensor is faulty can
settle its historical counter delta, but the live metrics are marked unavailable.

## Later deployment order

1. Review the deployed revision, existing private settings, bindings and the
   database target. Use the private source, config and PostgreSQL backup
   procedure in [the combined rollout, step 3](../backend/docs/COMBINED_AC_MTN_ROLLOUT.md).
   The following local commands create a reviewed allowlist and preview the
   upload for a host on the AC-lab rollout. Review missing prerequisites if the
   host is older.

   ```bash
   manifest=$(mktemp /tmp/gpawa-measured-files.XXXXXX)
   cat backend/deploy/mtn-ac-lab-domain.files backend/deploy/measured-consumption.files | sort -u > "$manifest"
   rsync -avnc --files-from="$manifest" backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
   ```

2. After review and backup, upload that same allowlist and apply the reviewed
   migrations. Preserve the private file and existing binding and token keys.
   Keep server output unavailable for the first sensor-only acceptance. Verify
   the effective running configuration and keep the lab capability enabled in
   the intended sandbox domain.

   ```bash
   rsync -avc --files-from="$manifest" backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
   ssh shanonsimon@ssh-shanonsimon.alwaysdata.net
   cd /home/shanonsimon/energy-sharing
   export ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env
   export DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings
   django=/home/shanonsimon/energy-venv/bin/python
   "$django" manage.py check_alwaysdata_database
   "$django" manage.py check --deploy
   "$django" manage.py showmigrations meter
   "$django" manage.py migrate --plan
   # After reviewing the plan, including meter 0034, 0035 and 0036 if pending:
   "$django" manage.py migrate --noinput
   "$django" manage.py collectstatic --noinput
   "$django" manage.py showmigrations meter
   ```

   Use **Web → Sites → shanonsimon.alwaysdata.net → Restart** for the existing
   sandbox WSGI site. Check the authenticated response before either client is
   released. Keep any authentication header in a private curl config file.

   ```bash
   curl -fsS --config "$GPAWA_OWNER_CURL_CONFIG" \
     "https://shanonsimon.alwaysdata.net/api/v1/meter/mobile-meters/${GPAWA_METER_ID}/measured-consumption/?environment=SANDBOX&days=7"
   ```

3. Configure `API_URL=https://shanonsimon.alwaysdata.net/api/v1` on the intended
   Vercel project's Production environment. From a checkout linked to that project:

   ```bash
   cd frontend
   npx vercel env ls production
   npx vercel deploy --prod
   ```

   Check **Dashboard → My Meters → Physical meter consumption** with the same
   meter. The older AMI report remains a separate source. For Android, verify
   the installed application's signing certificate is compatible before using
   the replacement command. A mismatch needs review before installation.

   ```bash
   adb devices
   adb install -r /home/shanon/projects/next_projects/Energy-sharing-project/mobile/artifacts/gpawa-measured-1.1.0-debug.apk
   ```

4. The actual Arduino upload folder has been staged. For future revisions, run
   the comparison first, then apply the public-only sync if its plan matches.
   The helper backs up differing public files outside the sketch and verifies
   the byte contents of preserved files. Open the exact Windows sketch path
   `C:\Users\USER\OneDrive\Documents\Arduino\GpawaAC\GpawaAC.ino`.

   ```bash
   sketch=/mnt/c/Users/USER/OneDrive/Documents/Arduino/GpawaAC
   PYTHONDONTWRITEBYTECODE=1 python3 firmware/ac-lab-domain/sync_arduino.py "$sketch"
   PYTHONDONTWRITEBYTECODE=1 python3 firmware/ac-lab-domain/sync_arduino.py "$sketch" --apply
   ```

   Select `ESP32S3 Dev Module` in Arduino IDE. Match the actual flash, PSRAM,
   partition, USB and core options to read-only evidence before preparing an
   upload. The synchronized `build_opt.h` makes IDE builds metered with GPIO14
   undriven. Arduino-ESP32 3.3.12 passes that file to the C++ compiler. The
   repository profile runner passes an equivalent, explicit set of options for
   staged validation builds, and takes a separate, full FQBN:

   ```bash
   python3 firmware/ac-lab-domain/build_profile.py metered --flags-only
   python3 firmware/ac-lab-domain/build_profile.py metered --fqbn "$GPAWA_CONFIRMED_FQBN" --build-path "$GPAWA_SCRATCH_BUILD"
   ```

   The local archived build in the actual upload folder used QIO, 4 MB flash,
   default partitions, disabled PSRAM, 240 MHz, hardware USB CDC/JTAG and no
   full-flash erase. Those settings describe that **archive**, not the board.
   A separately archived diagnostic used 16 MB and OPI PSRAM. Record the live
   application identity, confirmed board/flash settings, actual partition table
   and active app slot, journal state and binding. Confirm the upload recipe
   preserves the existing bootloader, partition table and NVS before any write.
   Validation binaries use example configuration and cannot be used on the board.

5. After a separately authorized, reviewed upload, keep the controlled load
   physically isolated. If the existing safe setup powers the PZEM measurement
   side independently of the isolated load, it can provide voltage and idle
   current, power and counter readings without closing the relay. If that
   isolation arrangement cannot power the sensor safely, stop at UART and mode
   evidence until the hardware test setup is reviewed. Relay contact state is
   independent of successful TLS or valid metering. Capture serial at 115200 baud.

   ```bash
   python3 -m serial.tools.miniterm "$GPAWA_PORT" 115200 --dtr 0 --rts 0
   ```

   Expect `BUILD_PROFILE METERED_INHIBITED`, `OUTPUT_STATUS` with GPIO14
   `NOT_DRIVEN`, and a successful `session` followed by a baseline status. For a
   fresh or paused journal, check `measurement_prepare`, `measurement_commit`
   and `MEASUREMENT_TRANSITION status=COMMITTED`. A compatible existing baseline
   should resume instead of resetting credit. Check `telemetry` HTTP 200 and
   correlate `request_id` to the server log. Two valid idle counter observations
   in the same UTC day can establish zero measured consumption. Restart while
   still isolated and confirm the expected boot change, the same binding and
   credit, replay or resumption without a second debit, and current idle readings
   again. Check both UIs against the owner API. A subsequent positive consumption
   test requires actual commissioning and the normal controlled relay path.

## Staged acceptance

Record the firmware profile, request ID, device and binding epoch, boot ID,
sequence, measurement time, receive time and PZEM Wh for each observation.
Capture the two clients with the same meter, energy environment and UTC period.
Use approved test equipment and test credit for the load and depletion cases.

| Stage | Device and API evidence | Web and mobile |
| --- | --- | --- |
| Metered profile, load isolated | `BUILD_PROFILE METERED_INHIBITED` and `gpio14=NOT_DRIVEN`. An authenticated session establishes or resumes the baseline. An acknowledged idle sample reports valid current and power as measured. A later valid sample with the same Wh counter gives a 0 kWh interval. | A valid zero is displayed numerically. The period stays unavailable until it has a covered interval. Output stays inhibited and contact state stays unknown. |
| Sensor failure and recovery, load isolated | Sensor loss inhibits output. An accepted fault report has unavailable live metrics. Retained valid Wh can settle historical usage before a fresh valid observation clears the recovery gate. | Live readings become unavailable. A delayed measurement becomes stale once it ages out. Earlier covered history stays available. |
| Restart or network loss and reconnection, load isolated | The restart has a new boot ID. The same baseline and binding resume. An unacknowledged observation can be replayed with its original identity. Confirm `ACCEPTED`, one stored telemetry row and one accounted change. Output remains inhibited during recovery. | A request failure is distinct from stale telemetry. Fresh data returns after reconnection. Restart and upload-gap intervals are labelled and excluded from the daily chart. |
| Commissioned operation, after physical evidence and authorization | Valid acknowledged credit, fresh sensor data and all existing interlocks are required. Confirm the commanded state and separately verify the relay contact on test equipment. An approved test load causes positive power and an increasing PZEM counter. Confirm one credit deduction for the validated change. | Recent power appears in W. The measured kWh delta and remaining credit appear separately. Relay command and server permission are shown with physical contact unknown. |
| Credit depletion, after commissioning | At zero credit the controller commands off. Confirm cutoff on lab test equipment. Replaying a delivery or telemetry acknowledgement produces no second credit or consumption event. | Confirm reported remaining credit falls to zero and the most recent relay command is off. Measured history and covered totals retain the earlier load usage. |
| Period and access checks | A wrong owner receives 404. An empty day returns `null`. A compatible counter delta across midnight UTC is shown as unallocated when both endpoints are in the period. A binding or baseline change starts a new chain. | Switch rapidly between two meters while one request is delayed. Only the current meter's readings and history appear. Missing buckets remain unavailable. |

## APK identity

- Local artifact `mobile/artifacts/gpawa-measured-1.1.0-debug.apk`
- Package `org.gpawa.consumer.prototype`, version `1.1.0-measured`, versionCode `2`
- SHA-256 `ddc1b31dfeadb93bde617516f4e2c3d3f005ecfdcda820b0ffed971cf4559e00`
- Embedded API `https://shanonsimon.alwaysdata.net/api/v1`
- Signing certificate SHA-256 `e9fb53040e78b6a525b67462cc5cc72a656de66ebe6c55061714e785eae86b4c`, verified equal to the preceding local debug APK. The installed phone certificate was not checked.

The source backup associated with the sync is
`/mnt/c/Users/USER/OneDrive/Documents/Arduino/GpawaAC-public-backup-20261126T064555Z-_ywse4y5`.

## Firmware validation artifacts

Both Arduino CLI profile runs timed out on the Windows/WSL build path. The
fallback recompiled the current sketch, linked it with the installed Espressif
compiler and the archived matching 3.3.12 core and library objects, and converted
each linked ELF to an ESP32-S3 application image. The commissioned validation
used `LOW` as a compile fixture. The actual staged IDE profile has commissioned
output and approval disabled, with no relay active level defined.

The validation directory is
`/mnt/c/Users/USER/AppData/Local/Temp/gpawa-firmware-linked-validation-l5emoiyp`.
Both `metered/` and `commissioned/` contain `GpawaAC.validation.elf` and
`GpawaAC.validation.app.bin`. These builds use example device configuration and
archived board options. Build again for the live device after reviewing its
settings and upload recipe.

The archived upload-folder FQBN, used as the validation reference only, is

```text
esp32:esp32:esp32s3:UploadSpeed=921600,USBMode=hwcdc,CDCOnBoot=default,MSCOnBoot=default,DFUOnBoot=default,UploadMode=default,CPUFreq=240,FlashMode=qio,FlashSize=4M,PartitionScheme=default,DebugLevel=none,PSRAM=disabled,LoopCore=1,EventsCore=1,EraseFlash=none,JTAGAdapter=default,ZigbeeMode=default
```

## Live rollout preflight

Release source is commit `75032da137f500cb5dab6455bffb85ef1fbdc79d`. On 26 November 2026, the public feature endpoint returned 200 and advertised MTN Sandbox with the AC lab in `SANDBOX` using `GPAWA_PZEM_V2`. The existing mobile meter list returned 401 to an unauthenticated request, and the measured-consumption path returned an HTML 404. The Vercel meter page redirected to sign-in. Alwaysdata rejected noninteractive SSH authentication, so the deployed source, migration state and private configuration could not be inspected. No production state was changed.

1. Restore existing SSH authentication in the shell performing the rollout. Use strict host-key checking. Inspect the host's code reference before backup. If the deployment is an rsync tree, retain a source archive and compare representative path hashes instead of expecting Git revision metadata.

   ```bash
   ssh -o BatchMode=yes -o StrictHostKeyChecking=yes shanonsimon@ssh-shanonsimon.alwaysdata.net
   ```

   On the server:

   ```bash
   cd /home/shanonsimon/energy-sharing
   git rev-parse --verify HEAD || sha256sum backend/alwaysdata_sandbox_settings.py meter/api/urls.py meter/prototype_device.py
   export ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env
   export DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings
   django=/home/shanonsimon/energy-venv/bin/python
   "$django" manage.py check_alwaysdata_database
   "$django" manage.py showmigrations meter
   "$django" manage.py shell -c 'from django.conf import settings; from meter.prototype_device import permitted_environment; print("AC lab:", getattr(settings, "PROTOTYPE_AC_LAB_ENABLED", False), "environment:", permitted_environment(), "relay server gate:", getattr(settings, "PROTOTYPE_RELAY_OUTPUT_ENABLED", False))'
   ```

2. Run `python3 backend/deploy/preview_combined_migrations.py` locally and review the read-only PostgreSQL plan. Follow deployment steps 1–2 above for the rsync preview and the private source/config/DB backup. Validate the created dump with `pg_restore --list "$GPAWA_ROLLOUT_BACKUP/database-before.dump" > /dev/null` before upload. If the existing deployment differs from the AC-lab baseline, review the actual diff and prerequisites before applying the allowlist. The target revision defaults the server relay gate to true when its environment variable is absent. For a sensor-only rollout, verify the effective gate and use an explicit `PROTOTYPE_RELAY_OUTPUT_ENABLED=false` in the private host configuration before activating the new code. Preserve the other settings and review any existing active grants before the transition. Issue no grants. Apply the reviewed plan through `meter.0036`; for a plan confined to that dependency chain the apply command is `"$django" manage.py migrate meter 0036 --noinput`. Restart the existing WSGI site and confirm the applied migrations and effective sandbox settings.

3. Run the protected endpoint checks before deploying the web client. Use existing authorized test accounts and private curl config files. The second consumer must not own the selected meter. Store the owner response privately and print only the contract checks below.

   ```bash
   umask 077
   route="https://shanonsimon.alwaysdata.net/api/v1/meter/mobile-meters/${GPAWA_METER_ID}/measured-consumption/?environment=SANDBOX&days=7"
   curl -sS -o /dev/null -w 'unauthenticated HTTP %{http_code}\n' "$route"
   curl -fsS --config "$GPAWA_OWNER_CURL_CONFIG" -o gpawa-owner-read.json -w 'owner HTTP %{http_code}\n' "$route"
   curl -sS --config "$GPAWA_OTHER_OWNER_CURL_CONFIG" -o /dev/null -w 'other owner HTTP %{http_code}\n' "$route"
   python3 -c 'import json; d=json.load(open("gpawa-owner-read.json")); assert d["environment"]=="SANDBOX" and d["source"]=="AC_LAB_PZEM" and d["period"]["timezone"]=="UTC" and d["relay"]["contact"]=="UNKNOWN" and not d["relay"]["authorized"]; print("Contract OK. Bound:",d["device_bound"],"Sample present:",d["latest"] is not None,"Coverage:",d["period"]["coverage"])'
   ```

   Expect 401, 200 and 404 respectively. A 200 with `latest: null` verifies access and contract only. An existing sample must be correlated to its device and timestamps to demonstrate real-device telemetry in the acceptance run.

4. Authenticate the existing Vercel account, then link the checkout to the **existing** project serving `energy-sharing-collaborate.vercel.app`. Confirm the project and its Root Directory before deploying. Record the previous production deployment ID from `vercel inspect`. Verify the existing production `API_URL` privately and retain the other variables.

   ```bash
   cd frontend
   npx vercel whoami
   npx vercel link
   npx vercel inspect https://energy-sharing-collaborate.vercel.app
   npx vercel env ls production
   npx vercel env run -e production -- node -e 'if (process.env.API_URL !== "https://shanonsimon.alwaysdata.net/api/v1") process.exit(1)'
   npx vercel deploy --prod
   ```

   If the API check fails, stop and review the production target. If the value is missing or confirmed outdated, set only that key in the existing project with `npx vercel env add API_URL production` or `npx vercel env update API_URL production` as appropriate, enter `https://shanonsimon.alwaysdata.net/api/v1`, and repeat the check. Use `npx vercel rollback "$GPAWA_PREVIOUS_DEPLOYMENT"` if a reviewed web rollback is needed. The server source backup is its rollback reference. Retain the DB backup and evaluate transactions since backup before any decision to restore it.

## Windows Android update

The verified APK is staged at `C:\Users\USER\Downloads\gpawa-measured-1.1.0-debug.apk`. Connect the phone with USB debugging enabled and authorize it in the phone prompt. Run these in PowerShell with Android platform-tools and `apksigner.bat` available:

```powershell
$apk = "$env:USERPROFILE\Downloads\gpawa-measured-1.1.0-debug.apk"
$pkg = 'org.gpawa.consumer.prototype'
Get-FileHash -Algorithm SHA256 $apk
adb.exe devices
adb.exe shell dumpsys package $pkg | Select-String 'versionCode=|versionName='
$installed = adb.exe shell pm path $pkg | Where-Object { $_ -match '/base\.apk\s*$' } | Select-Object -First 1
if (-not $installed) { throw 'Existing application was not found. Check the selected phone and package.' }
$base = Join-Path $env:TEMP ('gpawa-installed-' + [guid]::NewGuid() + '.apk')
adb.exe pull ($installed.Trim() -replace '^package:','') $base
if ($LASTEXITCODE) { throw 'Could not inspect the existing package.' }
apksigner.bat verify --print-certs $base
apksigner.bat verify --print-certs $apk
```

Verify both commands succeed and report certificate SHA-256 `e9fb53040e78b6a525b67462cc5cc72a656de66ebe6c55061714e785eae86b4c`. With the matching installed package, a compatible installed version code, and exactly one authorized phone, run `adb.exe install -r $apk`. Stop on a signature mismatch or downgrade error and retain the original app and its data.

## Review before a device-specific build and upload

Windows enumerated no matching serial device and ADB listed no phone during preflight. The local core is Arduino-ESP32 3.3.12 and its build recipe consumes the synchronized `build_opt.h`. Open the exact Arduino sketch path above and use only **Verify** when board settings have been established.

1. With the load physically isolated, identify the COM port in Windows. Collect existing serial logs at 115200 with DTR and RTS disabled where available. Record the running firmware identification, booted app offset, startup PSRAM/flash details, and any journal/binding status already reported. Opening some USB serial bridges can toggle control lines. If the adapter cannot guarantee passive attachment, review reset behavior first. Boot logs and the app's firmware identity are evidence of the previously running image; a bootable partition entry alone is insufficient.
2. If physical capacity or the table is still unknown, a separate read-only inspection can enter the ROM loader. Entering it resets and interrupts the application, and leaving it starts the application again. Record that before any attempt and keep the load physically isolated. After manually entering the loader, `esptool.exe --chip esp32s3 --port COMx --before no-reset --after no-reset --no-stub flash-id` checks physical capacity and `get-security-info` with the same options checks secure boot and encryption state. With the confirmed table offset, read only its 4 KiB sector (`read-flash <confirmed-table-offset> 0x1000 <private-table-file>`, adding the permitted RAM stub only if needed). Decode the table with the installed `gen_esp32part.exe`. Share the parsed labels, offsets and sizes. Do not dump NVS or raw journal records. If the boot log is insufficient, inspect only verified app-slot metadata and the documented boot selection before choosing a destination. Stop if read protection or the active slot is unresolved.
3. Match the full FQBN to the verified capacity, PSRAM, flash mode and frequency, partition layout, USB/runtime options and core. For a custom table, use `partitions.csv` in a private copy of the sketch folder with the existing private headers and profile file. Run the metered profile from the repository root using `python3 firmware/ac-lab-domain/build_profile.py metered --cli "$GPAWA_CLI" --windows-paths --sketch "$GPAWA_ARDUINO_SKETCH" --fqbn "$GPAWA_CONFIRMED_FQBN" --build-path "$GPAWA_SCRATCH_BUILD"`, or compile in the configured Windows IDE. `GPAWA_CLI` is the installed Windows Arduino CLI executable as a WSL path, and the fresh build directory must also be accessible from Windows. Do not distribute the resulting private application image. Inspect its fit in the verified app partition, including the sector-rounded write range, and compare its metadata and profile with the build log.
4. The installed core's normal ESP32-S3 upload passes the bootloader at `0x0`, table at `0x8000`, `boot_app0.bin` at `0xe000`, and application at `0x10000`. Its fast-flash wrapper still writes the OTA selection file unconditionally. It can overwrite the existing table and OTA selection even when full erase is disabled. The recipe for subsequent review is a single `write-flash` address/image pair to the verified booted application slot, preserving flash mode, frequency and size. Confirm the security and boot rollback state permits that method, and confirm the entire write is inside the app partition. No bootloader, table, OTA metadata, NVS or merged image is included. A different OTA slot would require separate review of how it is selected. There is no device-specific upload command until the live offsets and image match, and no upload is part of this phase.
