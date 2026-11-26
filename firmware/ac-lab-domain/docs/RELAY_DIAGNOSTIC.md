# GPIO14 / K1 low-voltage diagnostic

The normal authenticated firmware is intentionally output-disabled. This
diagnostic is a separate build that does not start Wi-Fi, access Preferences/NVS,
read or write the credit journal, call Django, redeem tokens, or change balances.
It only accepts serial commands for GPIO14. It never configures Channel 2.

## Build isolation

Use the existing board/toolchain configuration and Verify only:

```text
GPAWA_AUTH_CREDIT_ONLY=0
GPAWA_WIFI_TEST=0
GPAWA_USB_EXERCISE=0
GPAWA_COMMISSIONED_OUTPUT=0
GPAWA_RELAY_DIAGNOSTIC=1
```

The repository `HardwareConfig.h` defaults to the separate read-only PZEM
diagnostic. To select this GPIO14 diagnostic, explicitly set
`GPAWA_PZEM_DIAGNOSTIC=0`, `GPAWA_RELAY_DIAGNOSTIC=1`, and
`GPAWA_AUTH_CREDIT_ONLY=0`. It defaults authenticated credit to `0` while either
diagnostic is selected. For normal authenticated-credit firmware, explicitly set
both diagnostic flags to `0` and `GPAWA_AUTH_CREDIT_ONLY=1`; do not combine
either diagnostic with authenticated credit.

The diagnostic guard rejects authenticated-credit, Wi-Fi-test, exercise, and
commissioned-output builds. Physical output is disabled by default; the
commissioned mode requires an explicit measured relay level and cannot be
combined with diagnostic modes.

## Bench procedure

1. Disconnect mains, every AC/load wire, and any external source that could
   energize the relay contacts. Verify the contacts are de-energized. Power the
   ESP32 and relay module only from a suitable isolated low-voltage bench supply.
2. Before connecting GPIO14, confirm the relay module's input voltage and that
   its K1 input is compatible with the ESP32-S3's 3.3 V GPIO. Do not connect
   5 V to the ESP32 pin. Leave Channel 2 disconnected.
3. Open serial at 115200 baud. On startup GPIO14 is set to INPUT (released);
   no automatic relay pulse is commanded. Observe and record K1's startup
   indicator/state; it is module/driver-dependent and is not presumed inactive.
4. Send `H`, then `L`, and observe the K1 indicator/click for each state. Either
   state may activate K1: relay polarity is not inferred by firmware. The log
   reports the GPIO level read back by the ESP32, not relay-contact feedback.
5. Test reset behavior with the relay module still powered: send `H`, reset the
   ESP32, observe K1 during reset and after boot; repeat from `L`. Record any
   activation or release. Then send `Z`.
6. If the relay module has a separate low-voltage supply, test loss of ESP32
   power while that supply remains on, observing K1; restore power and repeat
   with both supplies removed before restoring them. Record the observed state
   during loss and startup. Do not infer this from GPIO readback.
7. Send `Z` to return GPIO14 to INPUT before disconnecting. Remove power and
   inspect wiring before any later test. Do not connect AC during this procedure.

An indicator/click only confirms the relay board's low-voltage response. This
does not verify contact isolation, contact rating, external driver behavior,
or safe operation with a load. The reset and power-loss observations are
specific to the exact ESP32, relay module, driver, wiring, and supply tested;
they are required commissioning evidence, not assurances supplied by this
diagnostic firmware.

## Later physical-output commissioning

Physical output remains disabled in firmware configuration and server policy.
The guarded code path must not be enabled until all of these are verified:

- measured/verified active polarity for the exact board and driver, and an
  explicit active-level setting; the output code has no assumed polarity;
- verified reset/brownout hardware bias that keeps K1 de-energized, safe GPIO
  electrical compatibility, isolation and contact ratings;
- a completed authenticated prepare/commit baseline transition as documented
  in [MEASUREMENT_TRANSITION.md](MEASUREMENT_TRANSITION.md);
- a fresh sensor-validity and consumption test, including promptly switching
  OFF at zero credit and on sensor/session faults; and
- an independent authorized review and controlled commissioning procedure.

The baseline transition consumes the version-3 measurement-paused journal
without clearing or recreating it. Preserve NVS during upgrade and follow the
recovery procedure if the device reports a transition hold.
