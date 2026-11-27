# Offline prepaid operation

Offline operation is an explicit per-device policy on persistent AUTO
commissioning. Temporary grants and existing persistent grants keep their
online behavior unless an administrator enables offline operation. An
authenticated, healthy, reconciled telemetry exchange establishes the device's
initial approval. The firmware stores it in NVS under `offlineOutput`, bound
to the device, storage identity, meter, environment, binding epoch and relay
polarity. The existing accounting journal retains its layout and credit.

| Event | Meter behavior |
| --- | --- |
| Internet drops while the controller stays powered | Continues supplying and deducting from saved, verified credit with a healthy sensor and journal. |
| Controller power is interrupted | Recording stops. The installation must have a verified fail-off relay path when the controller loses power. |
| Controller restarts without internet | Starts with an off command, restores the saved journal and approval, reconciles the fresh PZEM counter against the saved checkpoint, then resumes when credit remains. A counter regression or an implausible restart advance inhibits output. |
| Credit reaches zero or the sensor or storage becomes unsafe | Interrupts output locally, including during an internet outage. |
| A top-up is interrupted | The pending top-up is excluded from the LCD balance. Output remains inhibited through the pending credit checkpoint and ACK. New top-ups still require the backend. |
| Internet returns | Replays the durable telemetry outbox before the new session, then reconciles the cumulative PZEM delta once. A newer server denial, credential revocation, or binding rejection inhibits output and clears the local approval. |

A disconnected device cannot learn about a new server-side revocation or global
inhibit. The change takes effect on its next authenticated contact. A connected
device with a temporary or online-only grant continues to use its runtime lease.
The hardware contact state requires independent verification in both modes.

## Deployment and enrollment

1. Verify and back up the deployed Alwaysdata code, private configuration, and
   PostgreSQL database using the [existing rollout preflight](MEASURED_CONSUMPTION_HANDOFF.md#live-rollout-preflight).
   If the server is on the matching `0037` release, review the targeted dry run.
   Otherwise merge in the prior release allowlist and validate all prerequisites.

   ```bash
   manifest=backend/deploy/offline-output.files
   rsync -avnc --files-from="$manifest" backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
   python3 backend/deploy/preview_combined_migrations.py
   ```

2. After backup and review, upload without changing private settings. Apply the
   migration during the maintenance window and restart the existing WSGI site.

   ```bash
   rsync -avc --files-from="$manifest" backend/ shanonsimon@ssh-shanonsimon.alwaysdata.net:/home/shanonsimon/energy-sharing/
   ssh shanonsimon@ssh-shanonsimon.alwaysdata.net
   cd /home/shanonsimon/energy-sharing
   export ALWAYSDATA_ENV_FILE=/home/shanonsimon/.config/energy-sharing/backend.env
   export DJANGO_SETTINGS_MODULE=backend.alwaysdata_sandbox_settings
   django=/home/shanonsimon/energy-venv/bin/python
   "$django" manage.py check_alwaysdata_database
   "$django" manage.py migrate meter 0038 --plan
   "$django" manage.py migrate meter 0038 --noinput
   "$django" manage.py showmigrations meter
   ```

   Update both clients before enabling offline mode. The updated measured history
   accepts an unknown capture time on durable offline evidence. It shows receipt
   time separately and keeps intervals with upload gaps or unresolved timing out
   of the UTC daily chart. After an offline reboot the device can send a retained
   PZEM observation without claiming a measurement timestamp, even if the sensor
   faults before reconnection. A fresh timed sample restores live metrics.

3. Review the active sketch at `C:\Users\USER\OneDrive\Documents\Arduino\GpawaAC\GpawaAC.ino`.
   Its private configuration and active-LOW build profile are preserved. The
   [persistent rollout](PERSISTENT_OUTPUT_ROLLOUT.md#firmware-acceptance) records
   the existing full IDE FQBN and explains how to verify the live partition and
   active app slot before any reviewed application-only upload.

   The verified offline-capable image is
   `C:\Users\USER\AppData\Local\Temp\gpawa-offline-reviewed-njd0jn7f\GpawaAC.ino.bin`.
   It is `1105488` bytes, SHA-256
   `b3623f474ed17c526f2cbac3dc36213445a58836068a20276120750df90af1d1`.
   The build used a frozen sketch and private configuration with the recorded IDE
   settings. The previous public files are backed up in
   `C:\Users\USER\OneDrive\Documents\Arduino\GpawaAC-offline-backup-8ve4px5y`.
   The application image contains the device configuration. Keep it private.

4. Keep the load isolated while verifying the controller's fail-off behavior,
   the existing commissioning evidence, and the first online acceptance. An
   administrator can then enable this policy for the reviewed device when the
   server's `PROTOTYPE_RELAY_OUTPUT_ENABLED` setting permits output. Configure
   the authentication outside the command in a private curl config file.

   ```bash
   url=https://shanonsimon.alwaysdata.net/api/v1/admin/prototype-devices/be9f868b-33f0-49d4-b39f-38d08313ce51/output-authorization
   curl -fsS --config "$GPAWA_ADMIN_CURL_CONFIG" -H 'Content-Type: application/json' \
     --data '{"reason":"Enable reviewed local prepaid operation during an internet outage","offline":true}' "$url/persistent/"
   ```

   Expect `mode=PERSISTENT`, `restart_policy=AUTO`, `offline_enabled=true`, and a
   `PROMOTED` audit event that references the previous authorization. Wait for
   an eligible authenticated sample and `OUTPUT_LEASE ... offline=STORED` before
   testing without internet. A device that has never stored this approval needs
   that first successful exchange.

## Acceptance and rollback

1. Record the acknowledged kWh and PZEM counter. Disconnect the network while
   keeping the controller and sensor powered. Expect `AUTHORIZED_OFFLINE` and
   local deductions with a healthy load in the approved test setup.
2. Restart the controller with the network still disconnected. Confirm the
   initial off command and the safe relay contact behavior during power loss.
   After fresh, valid samples, verify the restored balance. An example test uses
   a 3.020 kWh saved checkpoint and a 0.020 kWh counter advance, so the restored
   display is 3.00 kWh. A repeat restart without further usage keeps that balance.
3. Verify zero-credit cutoff, an invalid sensor reading, and a counter reset
   hold. Reconnect and compare the single accepted PZEM delta, the remaining
   credit, and the gap in both clients. Verify retrying the upload cannot change
   the accounting a second time.
4. To return a device to online-only commissioning, repeat the admin operation
   with `"offline":false` and confirm the device has contacted the server, stopped
   using the cached offline policy, and completed any outstanding recovery. For
   a full output inhibit use the existing revoke route or global switch, and
   likewise verify the device has received the decision. Physical isolation is
   needed for an immediate cutoff on a disconnected device.

Migration `0038` can be reversed before an offline grant exists. After an
offline grant exists, retain the migration and schema-aware backend so historic
authorizations and offline telemetry can be read and reconciled. The migration
guards against discarding that policy history. Use the online-only policy or
revocation as the operational rollback.
