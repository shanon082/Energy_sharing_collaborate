# Persistent AUTO commissioning rollout

For operation on saved credit during an internet outage, see the
[offline prepaid rollout](OFFLINE_PREPAID_ROLLOUT.md). This document records
the preceding online-only persistent release and its build.

Migration `meter.0037` adds persistent commissioning without converting existing
records. Existing grants are temporary and keep their original expiry and audit
history. An administrator can promote a previously reviewed binding. The server
copies its stored evidence, keeps the temporary grant as history, and records
the administrator, reason and source grant in a `PROMOTED` event. Persistent
commissioning remains in force until revocation or binding replacement.

The firmware still needs a fresh authenticated lease of at most 90 seconds. It
uses its existing accounting journal, baseline, recovery and credit ACK rules.
At boot it commands the inactive relay level first. It resumes automatically
with an AUTO lease after reconciliation and switches off when credit, metering,
storage, the session or local safety conditions fail. Keypad D is ignored.

## Alwaysdata order

1. Use the existing Alwaysdata SSH authentication. Verify the deployed revision,
   migration history, sandbox environment and database identity. Back up the
   database, source and private configuration as described in the [measured
   consumption handoff](MEASURED_CONSUMPTION_HANDOFF.md#live-rollout-preflight).
   Keep a rollback reference. Use this targeted list when the deployed baseline
   already includes the matching backend through `0036`.

   ```bash
   ssh -o BatchMode=yes -o StrictHostKeyChecking=yes shanonsimon@ssh-shanonsimon.alwaysdata.net
   python3 backend/deploy/preview_combined_migrations.py
   manifest=backend/deploy/persistent-output.files
   rsync -avnc --files-from="$manifest" backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
   ```

   Verify the migration plan and code diff. If the server still lacks earlier
   prerequisites, use the earlier rollout allowlists in the handoff and merge
   this list into the reviewed upload. Confirm the global relay gate and keep
   the controlled load physically isolated during rollout. The private config
   and MTN setup are outside the upload list.

2. After the backup and dry run, upload the reviewed files and apply the schema
   during the maintenance window before restarting the current WSGI site.

   ```bash
   rsync -avc --files-from="$manifest" backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
   ssh shanonsimon@ssh-shanonsimon.alwaysdata.net
   cd /home/shanonsimon/energy-sharing
   export ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env
   export DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings
   django=/home/shanonsimon/energy-venv/bin/python
   "$django" manage.py check_alwaysdata_database
   "$django" manage.py check --deploy
   "$django" manage.py migrate meter 0037 --plan
   "$django" manage.py migrate meter 0037 --noinput
   "$django" manage.py showmigrations meter
   ```

   Restart **Web → Sites → shanonsimon.alwaysdata.net → Restart**. Confirm
   existing mobile, measured and telemetry reads still work. The backend can be
   released before the new firmware. For the updated shared authorization label,
   deploy the matching frontend from its existing Vercel project and rebuild
   mobile using its existing configuration during the next client release.

3. Before promotion, confirm the running firmware and verified relay setup with
   the load isolated, including a valid authenticated PZEM sample, settled
   recovery and a matching recorded polarity. Check the selected device as an
   Admin. Credentials belong in a private curl config file. In particular, the
   server setting `PROTOTYPE_RELAY_OUTPUT_ENABLED` must be enabled for the
   reviewed operation to succeed.

   ```bash
   url=https://shanonsimon.alwaysdata.net/api/v1/admin/prototype-devices/be9f868b-33f0-49d4-b39f-38d08313ce51/output-authorization
   curl -fsS --config "$GPAWA_ADMIN_CURL_CONFIG" "$url/" |
     jq '{authorization_id, authorization_state, mode, restart_policy, output_authorized, output_reason}'
   ```

   For this binding the explicit Admin operation is the following. Run it only
   after reviewing the stored evidence and the device's operating conditions.
   An existing AUTO-capable commissioned firmware can act on its next eligible
   reply after this operation.

   ```bash
   curl -fsS --config "$GPAWA_ADMIN_CURL_CONFIG" -H 'Content-Type: application/json' \
     --data '{"reason":"Approve ongoing AUTO operation for this previously reviewed binding"}' "$url/persistent/"
   ```

   Expect `201` with `mode: PERSISTENT`, `restart_policy: AUTO` and
   `expires_at: null`. A duplicate request for the active record returns `200`
   with the same authorization ID. A missing, revoked, or unverifiable source
   record requires review. The operation does not accept new evidence in its
   request. Check `PROMOTED` and the recorded source authorization in the staff
   history. Firmware `OUTPUT_LEASE` logs the server reason, local result and mode.

## Rollback and revocation

Set `PROTOTYPE_RELAY_OUTPUT_ENABLED=false` in the existing private environment
and restart the service to inhibit all new leases. To disable only this binding,
use the authenticated revoke route. An already issued lease expires within its
remaining lifetime. A received denial or local fault switches the output off
earlier. The firmware does not persist leases across restart.

```bash
curl -fsS --config "$GPAWA_ADMIN_CURL_CONFIG" -H 'Content-Type: application/json' \
  --data '{"reason":"Suspend persistent commissioning during rollback"}' "$url/revoke/"
```

Before any persistent record has been created, the database change can be
reversed during maintenance with `"$django" manage.py migrate meter 0036 --plan`
and then `"$django" manage.py migrate meter 0036 --noinput`, followed by restoring
the backed-up code and restarting. After any persistent record exists, keep
`0037` and its schema-aware readers to preserve the commissioning history. The
migration blocks reversal in that case. Use the global inhibit and revocation
for operational rollback and retain the existing accounting records.

## Firmware acceptance

Use the staged `C:\Users\USER\OneDrive\Documents\Arduino\GpawaAC\GpawaAC.ino`
and its existing `build_opt.h`. The current IDE build record selects ESP32S3 Dev
Module, 4 MB flash, QIO at 80 MHz, default partitions, PSRAM disabled, 240 MHz
CPU, hardware USB CDC/JTAG and no full erase. The file selects commissioned
active-LOW output. Confirm the live partition and booted app slot before any
upload and review an app-only write that preserves NVS and the partition map.
The application image contains the local private configuration and should stay
in the device operator's private Windows build directory.

Compile with the existing Windows Arduino IDE CLI and its configured libraries.
The installed core uses the staged `build_opt.h` and encodes the internal DIO
image header for this QIO board setting. This command compiles locally.

```powershell
$cli = 'C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe'
$sketch = 'C:\Users\USER\OneDrive\Documents\Arduino\GpawaAC'
$fqbn = 'esp32:esp32:esp32s3:UploadSpeed=921600,USBMode=hwcdc,CDCOnBoot=default,MSCOnBoot=default,DFUOnBoot=default,UploadMode=default,CPUFreq=240,FlashMode=qio,FlashSize=4M,PartitionScheme=default,DebugLevel=none,PSRAM=disabled,LoopCore=1,EventsCore=1,EraseFlash=none,JTAGAdapter=default,ZigbeeMode=default'
$build = Join-Path $env:LOCALAPPDATA ('Temp\gpawa-persistent-' + [guid]::NewGuid())
& $cli --config-file "$env:USERPROFILE\.arduinoIDE\arduino-cli.yaml" compile --fqbn $fqbn --build-path $build $sketch
Get-FileHash -Algorithm SHA256 (Join-Path $build 'GpawaAC.ino.bin')
```

The verified application image is
`C:\Users\USER\AppData\Local\Temp\gpawa-persistent-reviewed-6b81otnn\GpawaAC.ino.bin`.
It is `1103408` bytes, SHA-256
`fd9283f354eea250f1bc165a1de3a65f688bbd3e8fc1cd7eff27a4f4889389f9`.
The Arduino CLI invocation through WSL timed out. The delivered image was
compiled from a frozen copy of all three reviewed sketch translation units and
linked with the matching IDE core and library objects. The recorded 4 MB
partition files matched byte for byte and the image fits the recorded app slot.
The final source matches the active sketch, including its local build assertions.

The original public files are backed up in
`C:\Users\USER\OneDrive\Documents\Arduino\GpawaAC-persistent-auto-backup-nlnky9y6`.
A concurrent edit that removed runtime lease enforcement was backed up in
`C:\Users\USER\OneDrive\Documents\Arduino\GpawaAC-concurrent-edit-backup-f3nxmxdd`.
The intermediate image produced with that edit was quarantined. Use only the
verified image identified by the hash above.

1. With the load isolated, observe an inactive startup command, storage and
   binding readiness, authentication, a healthy PZEM reading and baseline resume.
2. Verify that restart or reconnect inhibits output during recovery, then
   correlate `OUTPUT_LEASE ... server_reason=LEASE_GRANTED local=ACCEPTED ...
   mode=PERSISTENT` with a fresh post-recovery telemetry acknowledgement.
3. In the reviewed test setup, confirm acknowledged positive credit permits
   output, zero credit inhibits it, a duplicate token has no effect, a valid top-up
   resumes after its ACK and fresh reading, and D does not change the command.
4. Confirm sensor fault, stale readings and revoked or expired runtime leases
   inhibit the output. Reconnect and verify the expected balance and boot ID.
   Match the PZEM counter delta to consumption across restart and verify the
   baseline does not debit historical lifetime energy. Verify relay contacts
   separately on the reviewed equipment.
