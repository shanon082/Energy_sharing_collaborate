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
