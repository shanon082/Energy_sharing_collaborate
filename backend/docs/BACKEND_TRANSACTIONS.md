# gPawa Backend — Transactions & Meter Flows

This document describes what happens on the Django backend when users buy electricity units, and how **STS** vs **AMI** meters are handled differently.

### API base URLs

| Environment | Base URL |
|---|---|
| **Production** | `https://energy-share.sun.ac.ug/api/v1/` |
| **Local dev** | `http://localhost:8000/api/v1/` |

Meter endpoints documented below use the prefix **`/api/v1/meter/`** — append to the base URL above.

**Example (production buy units):**  
`POST https://energy-share.sun.ac.ug/api/v1/meter/buy-units/`

**Authentication:** All endpoints require a logged-in user (`Authorization: Bearer <JWT>`, or httpOnly session cookie via the Next.js `/api/proxy/` route on the web app).

---

## 1. Architecture overview

### Meter types

| Type | Code | How units reach the physical meter |
|------|------|-----------------------------------|
| **STS** | `STS` | User buys kWh → **unit wallet** → generates a **keypad token** → enters token on meter |
| **AMI** | `AMI` | User buys kWh → **unit wallet** → user clicks **Apply** → server pushes balance over the network (no token) |

A single login can register **multiple meters** (landlords / sub-meters). Each meter has its own `architecture` (`STS` or `AMI`).

### Wallets & ledgers (important)

The backend uses **three separate balance concepts**:

| Store | Model | What it holds |
|-------|-------|---------------|
| **Unit wallet** | `wallet.models.Wallet` (`UnitWallet` in code) | kWh purchased but not yet applied to a meter |
| **MoMo payment ledger** | `transactions.models.Transaction` | UGX mobile-money payment status (`PENDING` / `COMPLETED` / `FAILED`) |
| **Unit purchase ledger** | `transactions.models.UnitTransaction` | kWh self-credits from purchases (`sender=user`, `receiver=user`, `direction=IN`) |
| **Unified meter ledger** | `meter.models.Transaction` | Audit trail of kWh/UGX movements per meter (`TYPE_PURCHASE`, etc.) |
| **Meter balance** | `meter.models.Meter.units` | kWh delivered to ThingsBoard (AMI ledger) |
| **AMI pending delivery** | `meter.models.Meter.pending_units` | AMI: kWh queued when ThingsBoard unreachable; STS: awaiting token |

**Purchases never push directly to the meter.** Units always land in the **unit wallet** first. The user then either generates an STS token or **loads** to an AMI meter (`apply-wallet-units`).

---

## 2. ERA billing (unit calculation)

All buy/estimate flows use `utils/billing.py` with the ERA domestic tariff (`DOM-10.1-2026Q1`).

### Tiered monthly blocks (cumulative kWh purchased this calendar month)

| Block | Range (kWh/month) | Rate (UGX/kWh) |
|-------|-------------------|----------------|
| Lifeline | 0–15 | 250 |
| Normal | 16–80 | 756.2 |
| Cooking | 81–150 | 412.0 |
| Super normal | 151+ | 756.0 |

### Fixed charges

- **Service charge:** UGX 3,360 — charged **once per calendar month** on the first purchase only.
- **VAT:** 18% on (energy cost + service charge).

### Monthly tracking

`get_monthly_units_consumed(user)` sums completed `UnitTransaction` self-purchases plus `meter.models.Transaction` purchases (`amount_kwh`) for the current month. This drives:

1. Whether service charge applies on the next purchase.
2. Which tariff tier the next kWh are priced at.

---

## 3. End-to-end flows

### 3.1 STS meter — full journey

```
┌─────────────┐    POST buy-units     ┌──────────────┐    MoMo (sandbox)    ┌─────────────┐
│   Client    │ ───────────────────►  │   Backend    │ ──────────────────► │ Unit wallet │
│  (Buy UGX)  │                       │  ERA billing │                     │  +kWh       │
└─────────────┘                       └──────────────┘                     └──────┬──────┘
                                                                                 │
                    POST generate-token                                          │
┌─────────────┐ ◄──────────────────────────────────────────────────────────────┘
│  Keypad     │   debits wallet, returns 10-digit token
│  entry      │
└─────────────┘
```

### 3.2 AMI meter — full journey

```
┌─────────────┐    POST buy-units     ┌──────────────┐    MoMo (sandbox)    ┌─────────────┐
│   Client    │ ───────────────────►  │   Backend    │ ──────────────────► │ Unit wallet │
│  (Buy UGX)  │                       │  ERA billing │                     │  +kWh       │
└─────────────┘                       └──────────────┘                     └──────┬──────┘
                                                                                 │
              POST apply-wallet-units                                            │
┌─────────────┐ ◄──────────────────────────────────────────────────────────────┘
│ AMI Delivery│   debits wallet → credit_ami_meter() → TB telemetry + attribute
│ Engine      │   success → meter.units += kWh | fail → meter.pending_units += kWh
└─────────────┘   Celery retries pending every 5 min + on Check Units
```

### 3.3 AMI delivery (`meter/ami_delivery.py` + `utils/ami_gateway.py`)

`apply_units_to_meter(meter, units)` branches on architecture:

- **STS:** adds to `meter.pending_units` (token still required separately).
- **AMI:** calls `credit_ami_meter()` which:
  1. Pushes telemetry via `push_units_to_thingsboard()`.
  2. Increments `remaining_units` shared attribute via tenant REST API.
  3. On success → `meter.units += amount` (ledger).
  4. On failure → `meter.pending_units += amount` (queued; wallet already debited on load).

| Setting | Gateway | Behaviour |
|---------|---------|-----------|
| `AMI_GATEWAY=utils.ami_gateway.MockAMIGateway` (default) | Mock | Logs success; no real network call (pilot) |
| `AMI_GATEWAY=utils.ami_gateway.ThingsBoardAMIGateway` | ThingsBoard | Push + attribute sync; pending queue on failure |

**Celery:** `meter.tasks.retry_pending_ami_deliveries` runs every **5 minutes** (requires worker + beat).

`get_ami_gateway().get_status(meter)` powers the AMI status card. Live kWh on refresh uses `GET /meter/check-units/` (ThingsBoard `remaining_units`). Check-units also retries pending delivery inline.

### 3.4 Ledger vs live balance (AMI)

| Balance | Source | When it changes |
|---------|--------|-----------------|
| **Ledger** (`meter.units`) | gPAWA DB | Load/share delivered to ThingsBoard |
| **Pending delivery** (`meter.pending_units`) | gPAWA DB | Load/share when meter offline / TB rejects |
| **Live** (`remaining_units`) | ThingsBoard | Consumption on device; gPAWA writes on delivery |

---

## 4. API reference — POST bodies & responses

### 4.1 Register meter

**`POST /api/v1/meter/register/`**

**Request body (JSON):**

```json
{
  "meter_no": "1236784560",
  "architecture": "AMI",
  "static_ip": "192.168.1.100",
  "label": "Home",
  "iot_device_token": "pCqLl8iPI1UKIMCA8w2Z"
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `meter_no` | Yes | Unique meter identifier |
| `architecture` | Yes | `"STS"` or `"AMI"` |
| `static_ip` | AMI only | Required when `architecture` is `AMI`; ignored for STS |
| `iot_device_token` | AMI only | ThingsBoard **device access token**; use `dev-*` for local stub |
| `label` | No | Display name (e.g. "Shop", "Tenant A") |

**Success (201):**

```json
{
  "success": true,
  "message": "Meter registered successfully",
  "data": {
    "meter_no": "1236784560",
    "static_ip": "192.168.1.100",
    "units": "0.00",
    "architecture": "AMI",
    "label": "Home"
  }
}
```

---

### 4.2 Estimate units (no side effects)

**`GET /api/v1/meter/estimate-units/?amount=5000`**

Query only — no POST body. Returns projected kWh before payment.

**Success (200):**

```json
{
  "estimated_units": 3.51,
  "tariff": "DOM-10.1-2026Q1",
  "gross_amount": 5000.0,
  "deductions": 0.0,
  "net_amount": 5000.0,
  "service_charge": 3360.0,
  "vat": 762.71,
  "energy_cost": 877.28,
  "total_bill": 4999.99,
  "insufficient_amount": false,
  "minimum_payment": 3967.75,
  "service_charge_included": true,
  "monthly_units_consumed": 0.0,
  "lifeline_remaining_kwh": 15.0,
  "current_tier_band": "lifeline"
}
```

On a **second purchase** in the same month, `service_charge` is `0`, `service_charge_included` is `false`, and `estimated_units` is higher because the full payment goes to energy.

---

### 4.3 Buy units (MoMo payment)

**`POST https://energy-share.sun.ac.ug/api/v1/meter/buy-units/`** (production)  
**`POST http://localhost:8000/api/v1/meter/buy-units/`** (local)

**Request body (JSON):**

```json
{
  "amount": 5000,
  "phone_number": "+256773443684"
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `amount` | Yes | UGX payment amount (number) |
| `phone_number` | Yes | E.164 format, e.g. `+2567XXXXXXXX` |

**Pre-checks (400 if failed):**

- User has no blocking loan (`LoanApplication` not in `COMPLETED` / `REJECTED`).
- User has at least one registered meter.
- Amount is a positive number.

**Sandbox mode** (`MTN_MOMO_CONFIG.ENVIRONMENT=sandbox`):

**Immediate response (200):**

```json
{
  "status": "PENDING",
  "message": "Simulating sandbox payment - Please wait...",
  "external_id": "uuid-string",
  "transaction_id": 42,
  "user_prompt": "Sandbox mode: Payment will auto-complete in 2 seconds",
  "estimated_units": 3.51,
  "tariff_applied": "DOM-10.1-2026Q1",
  "loan_outstanding_deduction": 0
}
```

**Background processing** (`_simulate_sandbox_payment`, ~10 seconds later):

1. Auto-repay any **disbursed loan** balance from the payment first.
2. Calculate kWh from remaining UGX via ERA billing.
3. Credit `wallet.models.Wallet` (unit wallet).
4. Mark `transactions.models.Transaction` as `COMPLETED`.
5. Create `UnitTransaction` (self-purchase, `direction=IN`, `status=COMPLETED`).
6. Create `meter.models.Transaction` ledger row (`TYPE_PURCHASE`, `amount_kwh`, `amount_ugx`).

**Units are NOT pushed to the meter at this step** (STS or AMI).

---

### 4.4 Check payment status

**`POST /api/v1/meter/check-payment-status/`**

**Request body (JSON):**

```json
{
  "transaction_id": 42
}
```

**Success — completed (200):**

```json
{
  "status": "SUCCESS",
  "message": "Payment completed successfully",
  "units_purchased": 3.51,
  "token": null,
  "transaction": {
    "id": 42,
    "amount": 5000.0,
    "units": 3.51,
    "timestamp": "2026-06-20T10:29:12.123456+00:00"
  }
}
```

**Still processing (200):**

```json
{
  "status": "PENDING",
  "message": "Payment still processing"
}
```

---

### 4.5 AMI — Apply wallet units to meter

**`POST /api/v1/meter/apply-wallet-units/`**

This is the AMI-specific step after buying units. **STS users must use `generate-token` instead.**

**Request body (JSON):**

```json
{
  "amount": 10.5,
  "meter_no": "1236784560"
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `amount` | Yes | kWh to debit from unit wallet (positive number) |
| `meter_no` | Conditional | Required if user has **multiple** AMI meters; optional if only one AMI meter |

**Server-side steps (atomic transaction):**

1. Resolve meter — must be owned by user, `architecture=AMI`.
2. Lock unit wallet (`select_for_update`).
3. Verify `wallet.balance >= amount`.
4. Debit unit wallet: `balance -= amount`.
5. Call `apply_units_to_meter(meter, amount)` via `credit_ami_meter()`:
   - Push telemetry + sync `remaining_units` attribute.
   - On success: `meter.units += amount`.
   - On failure: `meter.pending_units += amount` (queued for auto-retry).
6. Return updated balances and delivery status.

**Success — delivered (200):**

```json
{
  "success": true,
  "units_applied": 10.5,
  "meter_balance": 10.5,
  "pending_delivery_kwh": 0.0,
  "remaining_wallet_balance": 2.01,
  "message": "10.50 kWh sent to your AMI meter. No token entry is required."
}
```

**Success — queued for delivery (200):**

```json
{
  "success": true,
  "units_applied": 10.5,
  "meter_balance": 0.0,
  "pending_delivery_kwh": 10.5,
  "remaining_wallet_balance": 2.01,
  "message": "10.50 kWh queued for delivery to your meter. Units will be sent automatically when the meter is reachable."
}
```

**Error examples:**

| Status | Condition | Response |
|--------|-----------|----------|
| 400 | STS meter | `"This action is for AMI meters only..."` |
| 400 | Insufficient wallet | `"Insufficient wallet balance. Available: X.XX kWh."` |
| 409 | STS meter selected | `"architecture": "STS"` |

---

### 4.6 AMI — Meter status (GET, not POST)

**`GET /api/v1/meter/ami-status/?meter_no=1236784560`**

**Success (200):**

```json
{
  "success": true,
  "is_online": true,
  "last_seen": "2026-06-20T10:07:55.123456+00:00",
  "meter_no": "1236784560",
  "current_balance_kwh": 10.5,
  "wallet_balance": 2.01
}
```

---

### 4.7 AMI — Check units (ThingsBoard live read)

**`GET /api/v1/meter/check-units/?meter_no=1236784560`**

Reads ThingsBoard shared attribute `remaining_units`. Retries pending AMI delivery first. AMI meters only.

**Success (200):**

```json
{
  "success": true,
  "meter_no": "1236784560",
  "units_kwh": 4.5,
  "queried_at": "2026-06-22T14:30:00+03:00",
  "ledger_balance_kwh": 10.0,
  "pending_delivery_kwh": 0.0,
  "pending_retry": {
    "delivered_kwh": 0.0,
    "remaining_pending_kwh": 0.0,
    "message": "No pending delivery."
  },
  "source": "thingsboard"
}
```

Web AMI card refresh and USSD `6*2` use this endpoint / same service.

---

### 4.8 Meter notifications (low-units alerts)

**`GET /api/v1/meter/notifications/`** — list alerts (`?unread=true` optional)

**`PATCH /api/v1/meter/notifications/`** — `{ "all": true }` or `{ "ids": [1,2] }`

Created by `POST /webhooks/thingsboard/low-units` (ThingsBoard rule chain). Web notification bell polls GET.

---

### 4.9 STS — Generate token from wallet

**`POST /api/v1/meter/generate-token/`**

**Request body (JSON):**

```json
{
  "amount": 5.0,
  "meter_no": "9876543210"
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `amount` | Yes | kWh to debit from unit wallet |
| `meter_no` | Conditional | Required if user has multiple STS meters |

**Server-side steps:**

1. Verify STS meter (reject AMI with 409).
2. Debit unit wallet.
3. Create `MeterToken` with a 10-digit numeric token.
4. User enters token on physical meter keypad.

**Success (200):**

```json
{
  "success": true,
  "token": "1234567890",
  "units": 5.0,
  "remaining_balance": 8.51,
  "message": "Enter this token on your meter keypad to load 5.00 kWh."
}
```

---

## 5. AMI transaction process — detailed sequence

```
Client                          Backend                              AMI Gateway
  │                                │                                      │
  │  POST /buy-units/              │                                      │
  │  { amount: 5000,               │                                      │
  │    phone_number: "+256..." }   │                                      │
  │ ─────────────────────────────► │                                      │
  │                                │  Create MoMo tx (PENDING)            │
  │  ◄── PENDING + transaction_id  │                                      │
  │                                │                                      │
  │  (poll check-payment-status)   │  [sandbox: sleep 10s]                │
  │                                │  ERA billing → units_purchased       │
  │                                │  unit_wallet.balance += kWh          │
  │                                │  UnitTransaction + meter ledger      │
  │  ◄── SUCCESS, units_purchased  │                                      │
  │                                │                                      │
  │  POST /apply-wallet-units/     │                                      │
  │  { amount: 10.5,               │                                      │
  │    meter_no: "1236784560" }    │                                      │
  │ ─────────────────────────────► │                                      │
  │                                │  unit_wallet.balance -= 10.5         │
  │                                │  credit_ami_meter() ────────────────►│
  │                                │                                      │ telemetry + attribute
  │                                │  ◄──────────────────────────────── │ OK or queued
  │                                │  meter.units += 10.5 OR              │
  │                                │  meter.pending_units += 10.5         │
  │  ◄── success, balances         │                                      │
  │                                │                                      │
  │  GET /check-units/?meter_no=   │  retry_pending + read remaining    │
  │ ─────────────────────────────► │  units from ThingsBoard              │
  │  ◄── live + ledger + pending   │                                      │
```

### Production ThingsBoard delivery

A real ThingsBoard deployment pushes telemetry and updates the shared attribute using:

- `meter.iot_device_token` or `THINGSBOARD_ACCESS_TOKEN`
- `meter.static_ip` / device ID
- kWh amount as a telemetry attribute

---

## 6. Loan interaction on purchase

If the user has a **disbursed** loan with outstanding balance:

1. Incoming UGX first repays the loan (`LoanRepayment` created).
2. Only the **remainder** is used for kWh calculation.
3. Users with **pending / approved / disbursed** (non-completed) loans are **blocked** from buying units entirely.

---

## 7. Key source files

| Area | Path |
|------|------|
| Meter API views | `meter/api/views.py` |
| Meter URL routes | `meter/api/urls.py` |
| Meter model | `meter/models.py` |
| ERA billing engine | `utils/billing.py` |
| AMI gateway | `utils/ami_gateway.py` |
| Unit wallet | `wallet/models.py` |
| Unit transactions | `transactions/models.py` |
| MoMo payment tx | `transactions/models.py` → `Transaction` |
| Billing verification | `loan/management/commands/verify_era_billing.py` |

---

## 8. Sandbox vs production

| Mode | Buy-units behaviour |
|------|---------------------|
| **Sandbox** | Auto-completes payment in background thread (~10 s); no real MoMo call |
| **Production** | `BuyUnitsView.post` production branch (real `MTNMoMoService`) — must also credit unit wallet and create the same ledger rows |

---

## 9. Quick reference — which POST when?

| User action | Endpoint | Body |
|-------------|----------|------|
| Pay for units | `POST /buy-units/` | `{ amount, phone_number }` |
| Poll payment | `POST /check-payment-status/` | `{ transaction_id }` |
| AMI: load meter | `POST /apply-wallet-units/` | `{ amount, meter_no? }` |
| STS: get keypad token | `POST /generate-token/` | `{ amount, meter_no? }` |
| Register meter | `POST /register/` | `{ meter_no, architecture, static_ip?, label? }` |

---

*Last updated: June 2026 — reflects current pilot implementation (wallet-first purchase, AMI apply step, ERA DOM-10.1-2026Q1 tariff).*
