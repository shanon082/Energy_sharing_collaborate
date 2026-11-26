# PZEM read-only validation and paused-journal reconciliation

## Read-only diagnostic

The default `GPAWA_PZEM_DIAGNOSTIC=1` build is isolated from relay diagnostics,
authenticated-credit mode, Wi-Fi tests and USB exercise mode. To build explicitly:

```text
GPAWA_RELAY_DIAGNOSTIC=0
GPAWA_PZEM_DIAGNOSTIC=1
GPAWA_AUTH_CREDIT_ONLY=0
GPAWA_WIFI_TEST=0
GPAWA_USB_EXERCISE=0
GPAWA_COMMISSIONED_OUTPUT=0
```

It initializes only Serial and PZEM Serial1 (RX GPIO16, TX GPIO17). It does not
initialize GPIO14, LCD/keypad/buzzer, Wi-Fi, Preferences/NVS, the credit journal,
or Django requests. It uses Modbus function 04 only; it never resets the PZEM
counter. Output consists of fixed status/reason labels and validated measurements.

UART is configured for 9600 baud, 8N1, with the verified PZEM device address `0x01`. The request is
`01 04 00 00 00 0A 70 0D` (read ten input registers; CRC low byte first).
In the ESP32-S3 diagnostic, RX buffer capacity is 256 bytes, FIFO transfer
threshold is one byte and UART RX timeout is three symbols (about 3.1 ms).
These settings make short frames visible promptly to the bounded collector and
do not alter the Modbus request or accounting path.
The prior 180 ms deadline is longer than the approximately 26 ms on-wire time
for a 25-byte response at 9600 baud, so it is not inherently too short for the
frame itself; however, it may not cover device/adapter turnaround delays. The
isolated diagnostic therefore allows up to 500 ms and ends collection after a
20 ms inter-byte quiet period only after a complete response (optionally preceded
by an exact echoed request). If a partial frame goes quiet, the collector records
that gap but keeps listening to the 500 ms total deadline so a delayed remainder
is not discarded. This is bounded and diagnostic-only; normal metered sampling
retains its existing 180 ms timeout.

The bounded collector stores at most 64 bytes while counting the total received.
It reports time to first/last byte read by the application, the span and maximum
gap between successive byte reads, total elapsed time, whether a quiet gap was
seen, and whether reception ended at the quiet gap or total deadline. These
per-read times are software observation timestamps: buffered bytes drained in
one burst do not reveal their individual wire arrival times. UART event callbacks
report frame, parity, FIFO overflow, receive-buffer-full and break errors when
Arduino-ESP32 exposes them. Neither the timestamps nor zero error counts prove
the signal is electrically clean.

Incomplete/error logs include received and response byte counts, pre-request
discarded-byte count and up to 64 raw bytes. `NO_RESPONSE_TIMEOUT` means no
response bytes (request echo excluded) by the 500 ms deadline; `INCOMPLETE_FRAME`
means 1-24 response bytes; `EXTRA_OR_NOISY_BYTES` means more than 25 response
bytes were collected. An exact first 8-byte echo of the transmitted request is
identified and excluded only for response validation; original raw bytes remain
in diagnostics. Other validation failures such as CRC retain the received count
and bounded raw bytes. This distinguishes no response, truncated data, echo and
extra/noisy traffic without logging credentials or backend data.

Repeated bytes such as `FF C7 E0 C0` or `FE 1C C0 E0`, especially alongside
hardware UART frame/parity errors, are not explained by a longer software
timeout. They suggest checking the physical UART path: PZEM TX-to-ESP32 RX
(GPIO16), ESP32 TX-to-PZEM RX (GPIO17), shared ground, correct TTL pins rather
than RS-485/AC terminals, secure connections, and the exact PZEM model's logic
voltage. A PZEM TTL board powered from 5 V may present a 5 V TX-high level;
ESP32-S3 GPIOs are not 5 V tolerant, so verify the board's output level and use
a suitable level shifter/divider on PZEM-TX to ESP32-RX if required. Do not
connect a 5 V UART output directly to GPIO16 unless the exact interface is
verified 3.3 V safe. The PZEM's 5 V supply alone does not establish UART logic
compatibility. Verify baud/address and signal quality with suitable instruments;
do not probe or alter mains wiring while energized.

The reported `FE C7 C0 C0 C0 EE FF` is seven bytes, not a valid response or the
expected request echo: a response must begin `01 04 14`, while the transmitted
request is exactly `01 04 00 00 00 0A 64 64`. Seven bytes are too few to validate
a CRC or infer measurement registers. Bitwise inversion also does not produce
the expected response header. The bytes are consistent with corrupted UART
sampling, wrong polarity/logic levels, baud/ground/wiring problems, or unrelated
line activity, but software alone cannot identify which. In particular,
`elapsed_ms=21-22` with a 500 ms setting is characteristic of the earlier
collector stopping on its 20 ms quiet gap; it is not evidence that a 500 ms
collector timed out. With the updated collector, a partial seven-byte frame
must remain buffered until the total 500 ms deadline and should log
`end=TOTAL_TIMEOUT`, `rx_bytes=7`, and `quiet_gap_observed=YES` unless more bytes
arrive.

The decoder requires the expected 25-byte response, address, function, register
count and CRC, then checks voltage (80-260 V), current (at most 100 A), active
power (at most 26 kW and no greater than apparent power), frequency (45-65 Hz),
power factor (0-100), and a clear PZEM alarm register. It assigns a reading only
after every check passes. The energy monitor rejects counter regression and
inter-sample increases above the configured 26 kW ceiling plus 1 Wh tolerance.
No prior reading is fabricated; after three seconds without a valid sample it
reports stale. These numeric limits are conservative software checks for a
100 A PZEM-004T configuration, not verification of the exact meter, CT or
installation.

In normal metered firmware, invalid frames disable sensor authorization and
request OFF. Runtime counter regression or an implausible inter-sample jump
persists a journal hold and requires service/reconciliation. The persistent
baseline is also checked for regression. The first reading after boot is not
bounded by elapsed time because the journal contains no trustworthy timestamp
for the last durable meter sample.

## Paused version-3 journal: no automatic transition

The authenticated-credit-only journal remains version 3 with
`reservedBytes[2] == 1`. It preserves identity, credit, counters, receipts and
the historical meter baseline, but `observe()` returns `BaselineRequired`
without mutation. Returning to a metered build currently stops at `Baseline
review`; do not clear the pause bit, rewrite the baseline, erase NVS, or enable
first-boot provisioning.

The current Django device API has no audited, idempotent operation/receipt that
binds a suspended-period accounting decision to old and new PZEM baselines.
Its existing session and telemetry checks do not authorize a baseline change.
Therefore an automatic migration cannot prove that energy used while metering
was paused is accounted for, and no migration is implemented.

Before a future migration, an operator-approved accounting policy must state
how suspended-period energy is treated and provide independently reviewable
evidence. Acceptable policy cannot be inferred by firmware. A safe future
protocol needs:

1. A versioned journal extension that preserves all existing identity, credit,
   command/receipt/counter fields and the old baseline, and stores a unique
   transition ID, proposed baseline, policy/evidence digest and durable stage.
2. A backend prepare/commit operation idempotently bound to device, storage ID,
   meter, environment, binding epoch, existing counters/receipts, old baseline,
   proposed baseline, policy and evidence. The backend must return a durable
   audit receipt; existing session/telemetry endpoints are not substitutes.
3. Ordered local writes with readback verification: persist the immutable
   proposal first, obtain/verify the backend decision, then commit the approved
   accounting adjustment and baseline. Keep output disabled throughout.
4. Crash recovery that retries only the same transition ID and byte-identical
   proposal, never repeats a credit grant or consumption debit, and remains
   held/OFF if local and server stages cannot be reconciled.
5. Explicit tests for power loss at every stage, duplicate prepare/commit,
   backend ACK loss, conflicting evidence, and unchanged credit/receipts.

This design is a prerequisite, not authorization to migrate. Production physical
output remains compile-time prohibited. A separate commissioning review must
also verify the exact relay polarity, startup/reset electrical bias, isolation,
contact ratings and behavior with the PZEM before any output-enable change.
