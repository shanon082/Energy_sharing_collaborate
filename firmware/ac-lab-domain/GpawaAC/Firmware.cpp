#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <ArduinoJson.h>
#include <hd44780.h>
#include <hd44780ioClass/hd44780_I2Cexp.h>
#include <Keypad.h>
#include <esp_system.h>
#include <esp_task_wdt.h>
#include <mbedtls/sha256.h>
#include <time.h>
#include <math.h>
#include "BuzzerCore.h"
#include "MeterCore.h"
#include "Protocol.h"
#include "SafeDiagnostics.h"
#include "PzemFrame.h"
#include "RecoveryCore.h"
#include "HardwareConfig.h"
#include "DeviceDomain.h"
#if __has_include("DeviceConfig.h")
#include "DeviceConfig.h"
#else
#include "DeviceConfig.example.h"
#endif
namespace {
using namespace gpawa;
Preferences prefs;
State state{};
hd44780_I2Cexp lcd;
char keypadMap[4][4] = { { '1', '2', '3', 'A' }, { '4', '5', '6', 'B' }, { '7', '8', '9', 'C' }, { '*', '0', '#', 'D' } };
byte rowPins[4] = { 4, 5, 6, 7 }, colPins[4] = { 10, 11, 12, 13 };
Keypad keypad(makeKeymap(keypadMap), rowPins, colPins, 4, 4);
bool displayOK = false, configured = false, storageOK = false, sensorOK = false, sessionReady = false, loadRequested = false, userPaused = false, outputOn = false, outputAuthorized = false, outputAutoRestart = false, busy = false, fatal = false, watchdogReady = false;
char message[48] = "Starting", tokenDigits[16] = {}, bootId[37] = {};
uint8_t tokenLength = 0, good = 0;
uint32_t lastSample = 0, lastUi = 0, lastTelemetry = 0, lastWifiAttempt = 0, nextNetwork = 0, telemetrySequence = 0, retryDelay = 2000, showAt = 0, savedWh = 0;
uint32_t lastSession = 0;
uint32_t outputLeaseUntil = 0;
bool diagnostic = false, startupBeepPending = true;
NonBlockingBuzzer buzzer;
EmptyCreditReminder emptyCreditReminder;
pz::Reading measured{};
pz::MeterMonitor meterMonitor{};
uint32_t lastValidSample = 0, pzemDiagnosticStarted = 0;
bool pzemDiagnosticStaleReported = false;
bool recoveryRequired = true, serverBaselineReady = false, baselineStatusKnown = false;
bool verifiedWhKnown = false, creditCommandPending = false, faultPosted = false;
bool pendingCreditRequiresCheckpoint = false;
uint32_t verifiedWh = 0;
uint32_t safetyEpoch = 1, telemetrySafetyEpoch = 0;
uint64_t verifiedConsumed = 0;
Command pendingCredit{};
struct MeterEvidence {
  pz::Reading reading;
  uint32_t capturedAt;
  uint32_t applicationCounter;
  uint64_t consumedUWh;
  uint32_t crc;
};
MeterEvidence evidence{};
struct CreditCheckpoint {
  char bootId[37];
  char commandId[37];
  uint32_t sequence;
  uint32_t crc;
};
CreditCheckpoint creditCheckpoint{};
enum class JobKind : uint8_t { Session,
                               Redeem,
                               Ack,
                               Telemetry,
                               MeasurementPrepare,
                               MeasurementCommit };
struct MeasurementMigration {
  char transitionId[37];
  char receiptId[37];
  char creditReceiptId[37];
  uint64_t creditedUWh;
  uint64_t availableUWh;
  uint64_t consumedUWh;
  uint64_t uncertainUWh;
  uint32_t applicationCounter;
  uint32_t oldBaselineWh;
  uint32_t baselineWh;
  uint8_t ackPending;
  uint8_t hadBaseline;
  uint8_t stage;
  BaselineSource source; // Former reserved byte. Zero preserves paused records.
  uint32_t crc;
};
constexpr uint8_t MIGRATION_INTENT = 1;
constexpr uint8_t MIGRATION_PREPARED = 2;
MeasurementMigration measurementMigration{};
bool migrationPresent = false;
struct Request {
  JobKind kind;
  uint32_t sentAt;
  bool replay;
  char requestId[37];
  char body[2304];
};
struct Reply {
  JobKind kind;
  uint32_t sentAt;
  int status;
  int httpStatus;
  DiagnosticTransport transport;
  char requestId[37];
  char serverRequestId[37];
  char body[4096];
};
char telemetryOutbox[sizeof(Request::body)] = {};
const Reply* diagnosticReply = nullptr;
const char* diagnosticBackendCode = "NO_SERVER_RESPONSE";
void uuid4(char* out);
const char* operationName(JobKind kind) {
  return kind == JobKind::Session ? "session" : kind == JobKind::Redeem ? "redeem"
                                              : kind == JobKind::Ack    ? "ack"
                                              : kind == JobKind::Telemetry ? "telemetry"
                                              : kind == JobKind::MeasurementPrepare ? "measurement_prepare"
                                                                                   : "measurement_commit";
}
void diagnosticLocal(const char* cause, const char* stage, bool failed = true, JobKind kind = JobKind::Session) {
  char fresh[37];
  if (!diagnosticReply) uuid4(fresh);
  const char* op = diagnosticReply ? operationName(diagnosticReply->kind) : operationName(kind);
  const char* id = diagnosticReply ? diagnosticReply->requestId : fresh;
  const bool ack = diagnosticReply ? diagnosticReply->kind == JobKind::Ack : kind == JobKind::Ack;
  Serial.printf("DEVICE request_id=%s operation=%s http=%d category=%s cause=%s stage=%s code=%s correlation=%s\n",
                diagnosticLogId(id, diagnosticReply ? diagnosticReply->serverRequestId : nullptr), op, diagnosticReply ? diagnosticReply->httpStatus : 0,
                diagnosticCategory(ack, cause, failed), cause, stage, diagnosticReply ? diagnosticBackendCode : "NO_SERVER_RESPONSE",
                diagnosticReply ? diagnosticCorrelation(id, diagnosticReply->serverRequestId) : "not_sent");
}
struct DiagnosticReplyScope {
  DiagnosticReplyScope(const Reply& reply, const char* code) {
    diagnosticReply = &reply;
    diagnosticBackendCode = code;
  }
  ~DiagnosticReplyScope() {
    diagnosticReply = nullptr;
    diagnosticBackendCode = "NO_SERVER_RESPONSE";
  }
};
QueueHandle_t requestQueue = nullptr, replyQueue = nullptr;
void say(const char* msg) {
  snprintf(message, sizeof message, "%s", msg);
  showAt = millis();
}
void eraseToken() {
  memset(tokenDigits, 0, sizeof tokenDigits);
  tokenLength = 0;
}
void switchOff() {
#if GPAWA_COMMISSIONED_OUTPUT && !GPAWA_USB_EXERCISE
  digitalWrite(hw::SWITCH_PIN, hw::RELAY_INACTIVE_LEVEL);
#endif
  outputOn = false;
}
void inhibitForRecovery() {
  ++safetyEpoch;
  recoveryRequired = true;
  outputAuthorized = false;
  outputLeaseUntil = 0;
  loadRequested = false;
  switchOff();
}
bool acceptOutputAuthorization(JsonVariantConst reply, uint32_t sentAt, bool eligible) {
  if (!reply["output_authorized"].is<bool>() ||
      !reply["output_lease_seconds"].is<uint32_t>() ||
      !reply["output_restart_policy"].is<const char*>()) return false;
  const bool authorized = reply["output_authorized"].as<bool>();
  const uint32_t lease = reply["output_lease_seconds"].as<uint32_t>();
  const char* restart = reply["output_restart_policy"].as<const char*>();
  if (lease > 90 || authorized != (lease > 0) ||
      (strcmp(restart, "AUTO") && strcmp(restart, "MANUAL"))) return false;
  outputAutoRestart = !strcmp(restart, "AUTO");
  outputAuthorized = authorized && eligible && leaseLiveAt(millis(), sentAt, lease);
  outputLeaseUntil = outputAuthorized ? sentAt + lease * 1000UL : 0;
  if (!outputAuthorized) {
    switchOff();
    loadRequested = false;
    return true;
  }
#if GPAWA_COMMISSIONED_OUTPUT
  if (outputAutoRestart && storageOK && sensorOK && state.availableUWh &&
      !state.hold && !state.ackPending && state.hasMeter && !measurementPaused(state) &&
      !migrationPresent && !fatal && !userPaused) {
    loadRequested = true;
  }
#endif
  return true;
}
#if GPAWA_RELAY_DIAGNOSTIC
void relayDiagnosticTick() {
  while (Serial.available()) {
    const char command = Serial.read();
    if (command == 'H' || command == 'L') {
      const int level = command == 'H' ? HIGH : LOW;
      digitalWrite(hw::SWITCH_PIN, level);
      pinMode(hw::SWITCH_PIN, OUTPUT);
      Serial.printf("RELAY_DIAGNOSTIC pin=GPIO14 drive=%s readback=%s k1_feedback=VISUAL_ONLY\n",
                    command == 'H' ? "HIGH" : "LOW", digitalRead(hw::SWITCH_PIN) == HIGH ? "HIGH" : "LOW");
    } else if (command == 'Z' || command == 'z') {
      pinMode(hw::SWITCH_PIN, INPUT);
      Serial.printf("RELAY_DIAGNOSTIC pin=GPIO14 drive=RELEASED readback=%s k1_feedback=VISUAL_ONLY\n",
                    digitalRead(hw::SWITCH_PIN) == HIGH ? "HIGH" : "LOW");
    } else if (command != '\r' && command != '\n') {
      Serial.println("Send H, L, or Z (release GPIO14).");
    }
  }
}
#endif


// Active-HIGH buzzer: a queued beep is a 90 ms ON pulse followed by 90 ms OFF.
void beep(uint8_t n) {
  buzzer.start(n, millis());
}
void tickSound() {
  const uint32_t now = millis();
  digitalWrite(hw::BEEP, buzzer.tick(now) ? HIGH : LOW);
  const bool depleted = storageOK && !fatal && state.creditedUWh > 0 && state.availableUWh == 0;
  if (emptyCreditReminder.tick(now, depleted, buzzer.active())) beep(1);
}
void latch(const char* why) {
  switchOff();
  loadRequested = false;
  fatal = true;
  say(why);
  Serial.println(why);
}
bool persist(State next) {
  seal(next);
  if (!valid(next)) {
    diagnosticLocal("PERSISTENT_STORAGE_FAILURE", "journal_validation");
    latch("Invalid state - service");
    return false;
  }
  if (prefs.putBytes("state", &next, sizeof next) != sizeof next) {
    diagnosticLocal("PERSISTENT_STORAGE_FAILURE", "storage_write");
    latch("Save failed");
    return false;
  }
  State verify{};
  if (prefs.getBytesLength("state") != sizeof verify || prefs.getBytes("state", &verify, sizeof verify) != sizeof verify || memcmp(&next, &verify, sizeof next) || !valid(verify)) {
    diagnosticLocal("PERSISTENT_STORAGE_FAILURE", "storage_verify");
    latch("Save check failed");
    return false;
  }
  state = next;
  savedWh = next.meterWh;
  return true;
}
template <class Record>
bool storedRecordValid(const Record& item) {
  return item.crc == crc32(&item, offsetof(Record, crc));
}
template <class Record>
bool saveRecord(const char* key, Record& item) {
  item.crc = crc32(&item, offsetof(Record, crc));
  Record verify{};
  if (prefs.putBytes(key, &item, sizeof item) != sizeof item ||
      prefs.getBytes(key, &verify, sizeof verify) != sizeof verify ||
      memcmp(&item, &verify, sizeof item)) {
    diagnosticLocal("PERSISTENT_STORAGE_FAILURE", "recovery_write");
    latch("Recovery save failed");
    return false;
  }
  return true;
}
bool evidenceMatchesJournal() {
  return evidence.capturedAt && evidence.reading.wh == state.meterWh &&
         evidence.applicationCounter == state.applicationCounter &&
         evidence.consumedUWh == state.consumedUWh;
}
bool checkpointMatchesCommand() {
  return storedRecordValid(creditCheckpoint) && creditCheckpoint.sequence &&
         terminated(creditCheckpoint.bootId, sizeof creditCheckpoint.bootId) && uuid(creditCheckpoint.bootId) &&
         terminated(creditCheckpoint.commandId, sizeof creditCheckpoint.commandId) &&
         !strcmp(creditCheckpoint.commandId, state.lastCommand.id);
}
void sealMigration(MeasurementMigration& migration) {
  migration.crc = crc32(&migration, offsetof(MeasurementMigration, crc));
}
bool validMigration(const MeasurementMigration& migration) {
  if (migration.crc != crc32(&migration, offsetof(MeasurementMigration, crc)) ||
      !terminated(migration.transitionId, sizeof migration.transitionId) || !uuid(migration.transitionId) ||
      !terminated(migration.receiptId, sizeof migration.receiptId) ||
      !terminated(migration.creditReceiptId, sizeof migration.creditReceiptId) ||
      (migration.stage != MIGRATION_INTENT && migration.stage != MIGRATION_PREPARED) ||
      migration.hadBaseline > 1 || migration.ackPending > 1 || !baselineSourceName(migration.source))
    return false;
  if (migration.creditReceiptId[0] && !uuid(migration.creditReceiptId)) return false;
  if (migration.stage == MIGRATION_INTENT && migration.receiptId[0]) return false;
  if (migration.stage == MIGRATION_PREPARED && !uuid(migration.receiptId)) return false;
  return true;
}
bool migrationMatchesJournal() {
  const bool sourceMatches = measurementMigration.source == BaselineSource::Paused ? measurementPaused(state) :
      !measurementPaused(state) && (state.hasMeter == (measurementMigration.source == BaselineSource::Legacy)) &&
      (!state.hasMeter || state.meterWh == measurementMigration.oldBaselineWh);
  return migrationPresent && sourceMatches &&
         measurementMigration.applicationCounter == state.applicationCounter &&
         measurementMigration.creditedUWh == state.creditedUWh &&
         measurementMigration.availableUWh == state.availableUWh &&
         measurementMigration.consumedUWh == state.consumedUWh &&
         measurementMigration.uncertainUWh == state.uncertainUWh &&
         measurementMigration.ackPending == state.ackPending &&
         !strcmp(measurementMigration.creditReceiptId, state.receiptId);
}
bool persistMigration() {
  sealMigration(measurementMigration);
  if (!validMigration(measurementMigration) ||
      prefs.putBytes("migration", &measurementMigration, sizeof measurementMigration) != sizeof measurementMigration) {
    diagnosticLocal("PERSISTENT_STORAGE_FAILURE", "migration_write");
    latch("Migration save failed");
    return false;
  }
  MeasurementMigration verify{};
  if (prefs.getBytesLength("migration") != sizeof verify ||
      prefs.getBytes("migration", &verify, sizeof verify) != sizeof verify ||
      memcmp(&measurementMigration, &verify, sizeof verify) || !validMigration(verify)) {
    diagnosticLocal("PERSISTENT_STORAGE_FAILURE", "migration_verify");
    latch("Migration check failed");
    return false;
  }
  migrationPresent = true;
  return true;
}
bool removeMigration() {
  if (prefs.isKey("migration") && !prefs.remove("migration")) {
    diagnosticLocal("PERSISTENT_STORAGE_FAILURE", "migration_remove");
    latch("Migration cleanup failed");
    return false;
  }
  migrationPresent = prefs.isKey("migration");
  if (migrationPresent) {
    diagnosticLocal("PERSISTENT_STORAGE_FAILURE", "migration_remove_verify");
    latch("Migration cleanup failed");
    return false;
  }
  memset(&measurementMigration, 0, sizeof measurementMigration);
  return true;
}
bool beginMeasurementMigration(uint32_t baselineWh, BaselineSource source) {
  if (migrationPresent || !sensorOK || state.ackPending || state.hold) return false;
  memset(&measurementMigration, 0, sizeof measurementMigration);
  uuid4(measurementMigration.transitionId);
  memcpy(measurementMigration.creditReceiptId, state.receiptId, sizeof measurementMigration.creditReceiptId);
  measurementMigration.creditedUWh = state.creditedUWh;
  measurementMigration.availableUWh = state.availableUWh;
  measurementMigration.consumedUWh = state.consumedUWh;
  measurementMigration.uncertainUWh = state.uncertainUWh;
  measurementMigration.applicationCounter = state.applicationCounter;
  measurementMigration.oldBaselineWh = state.meterWh;
  measurementMigration.baselineWh = baselineWh;
  measurementMigration.ackPending = state.ackPending;
  measurementMigration.hadBaseline = state.hasMeter;
  measurementMigration.stage = MIGRATION_INTENT;
  measurementMigration.source = source;
  return persistMigration();
}
void uuid4(char* out) {
  uint8_t b[16];
  esp_fill_random(b, sizeof b);
  b[6] = (b[6] & 15) | 0x40;
  b[8] = (b[8] & 63) | 0x80;
  snprintf(out, 37, "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
           b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7], b[8], b[9], b[10], b[11], b[12], b[13], b[14], b[15]);
}
bool clockValid() {
  time_t t = time(nullptr);
  return t >= 1790812800LL && t < 4102444800LL;
}
void timestamp(char* out, size_t size) {
  time_t t = time(nullptr);
  struct tm utc {};
  gmtime_r(&t, &utc);
  strftime(out, size, "%Y-%m-%dT%H:%M:%SZ", &utc);
}
bool probe(uint8_t address) {
  Wire.beginTransmission(address);
  return Wire.endTransmission() == 0;
}
class BoundedBody : public Stream {
public:
  char value[4096]{};
  size_t count = 0;
  bool overflow = false;
  size_t write(uint8_t b) override {
    return write(&b, 1);
  }
  size_t write(const uint8_t* b, size_t n) override {
    if (n > sizeof(value) - 1 - count) {
      overflow = true;
      return 0;
    }
    memcpy(value + count, b, n);
    count += n;
    value[count] = 0;
    return n;
  }
  int available() override {
    return 0;
  }
  int read() override {
    return -1;
  }
  int peek() override {
    return -1;
  }
  void flush() override {}
};
const char* route(JobKind k) {
  switch (k) {
    case JobKind::Session: return "/prototype-device/v1/session/";
    case JobKind::Redeem: return "/prototype-device/v1/redeem/";
    case JobKind::Ack: return "/prototype-device/v1/ack/";
    case JobKind::Telemetry: return "/prototype-device/v1/telemetry/";
    case JobKind::MeasurementPrepare: return "/prototype-device/v1/measurement/prepare/";
    case JobKind::MeasurementCommit: return "/prototype-device/v1/measurement/commit/";
  }
  return "/prototype-device/v1/telemetry/";
}
void networkWorker(void*) {
  Request req{};
  for (;;) {
    if (xQueueReceive(requestQueue, &req, portMAX_DELAY) != pdTRUE) continue;
    Reply response{};
    response.kind = req.kind;
    response.sentAt = req.sentAt;
    response.status = -1;
    response.transport = DiagnosticTransport::Connection;
    memcpy(response.requestId, req.requestId, sizeof response.requestId);
    if (WiFi.status() == WL_CONNECTED && !clockValid()) response.transport = DiagnosticTransport::Clock;
    if (WiFi.status() == WL_CONNECTED && clockValid()) {
      WiFiClientSecure tls;
      tls.setCACert(cfg::ROOT_CA);
      tls.setHandshakeTimeout(8);
      HTTPClient http;
      http.setConnectTimeout(5000);
      http.setTimeout(5000);
      http.setFollowRedirects(HTTPC_DISABLE_FOLLOW_REDIRECTS);
      response.transport = DiagnosticTransport::HttpBegin;
      if (http.begin(tls, String(cfg::API_BASE) + route(req.kind))) {
        const char* headers[] = { "X-Request-ID" };
        http.collectHeaders(headers, 1);
        http.addHeader("X-Request-ID", req.requestId);
        http.addHeader("Content-Type", "application/json");
        if (req.replay) http.addHeader("X-Gpawa-Telemetry-Replay", "1");
        http.addHeader("X-Device-Id", cfg::DEVICE_ID);
        http.addHeader("X-Device-Token", cfg::DEVICE_SECRET);
        response.status = http.POST((uint8_t*)req.body, strlen(req.body));
        if (response.status > 0) {
          response.httpStatus = response.status;
          response.transport = DiagnosticTransport::Ok;
          String returned = http.header("X-Request-ID");
          if (diagnosticId(returned.c_str())) memcpy(response.serverRequestId, returned.c_str(), 37);
          BoundedBody body;
          if (http.getSize() > 4095) {
            response.status = -2;
            response.transport = DiagnosticTransport::BodyLimit;
          } else if (http.writeToStream(&body) < 0 || body.overflow) {
            response.status = -2;
            response.transport = body.overflow ? DiagnosticTransport::BodyLimit : DiagnosticTransport::BodyRead;
          } else memcpy(response.body, body.value, body.count + 1);
        } else {
          char discarded[96];
          int tlsError = tls.lastError(discarded, sizeof discarded);
          // ESP32's -1 covers TCP failures AND some handshake timeouts. Do not invent a narrower cause.
          response.transport = tlsError < -1 ? DiagnosticTransport::TLS : DiagnosticTransport::ConnectionTLS;
          memset(discarded, 0, sizeof discarded);
        }
        http.end();
      }
    }
    // No request/response bodies or credentials are printed.
    volatile char* p = req.body;
    for (size_t i = 0; i < sizeof req.body; ++i) p[i] = 0;
    xQueueSend(replyQueue, &response, portMAX_DELAY);
  }
}
bool enqueueBody(JobKind kind, const char* body, bool replay = false) {
  if (busy || !requestQueue || WiFi.status() != WL_CONNECTED || !clockValid()) {
    diagnosticLocal(WiFi.status() != WL_CONNECTED ? "CONNECTION_FAILURE" : !clockValid() ? "CLOCK_UNAVAILABLE"
                                                                                         : "REQUEST_NOT_SENT",
                    "enqueue", true, kind);
    return false;
  }
  Request r{};
  r.kind = kind;
  r.sentAt = millis();
  r.replay = replay;
  uuid4(r.requestId);
  if (strlen(body) >= sizeof r.body) {
    diagnosticLocal("REQUEST_NOT_SENT", "request_size", true, kind);
    latch("Request too large");
    return false;
  }
  memcpy(r.body, body, strlen(body) + 1);
  if (xQueueSend(requestQueue, &r, 0) != pdTRUE) {
    diagnosticLocal("REQUEST_NOT_SENT", "queue", true, kind);
    return false;
  }
  volatile char* p = r.body;
  for (size_t i = 0; i < sizeof r.body; ++i) p[i] = 0;
  busy = true;
  return true;
}
bool enqueue(JobKind kind, JsonDocument& doc) {
  char body[sizeof(Request::body)] = {};
  if (measureJson(doc) >= sizeof body) {
    latch("Request too large");
    return false;
  }
  serializeJson(doc, body, sizeof body);
  const bool queued = enqueueBody(kind, body);
  volatile char* bytes = body;
  for (size_t i = 0; i < sizeof body; ++i) bytes[i] = 0;
  return queued;
}
void identity(JsonDocument& j) {
  j["protocol"] = deviceProtocol(state);
  j["device_id"] = cfg::DEVICE_ID;
  j["meter_number"] = cfg::METER_NUMBER;
  j["storage_id"] = state.storageId;
  j["binding_epoch"] = state.bindingEpoch;
  j["environment"] = accountingEnvironment(state);
  j["hardware_class"] = "AC_LAB";
}
void reportRelayProfile(JsonDocument& j) {
#if GPAWA_COMMISSIONED_OUTPUT
  j["relay_active_level"] = hw::RELAY_ACTIVE_LEVEL == HIGH ? "HIGH" : "LOW";
#else
  j["relay_active_level"] = nullptr;
#endif
}
bool matching(JsonVariantConst j) {
  return matchingIdentity(j, state);
}

void sendSession() {
  JsonDocument j;
  identity(j);
  reportRelayProfile(j);
  j["boot_id"] = bootId;
  j["boot_counter"] = state.bootCounter;
  j["application_counter"] = state.applicationCounter;
  j["initialize"] = state.reservedBytes[0] == 0;
  j["ack_pending"] = state.ackPending != 0;
  if (state.applicationCounter) {
    j["last_command_id"] = state.lastCommand.id;
    j["last_payload_digest"] = state.lastCommand.digest;
    j["last_receipt_id"] = state.receiptId;
  }
  j["credited_uwh"] = state.creditedUWh;
  j["consumed_uwh"] = state.consumedUWh;
  j["uncertain_uwh"] = state.uncertainUWh;
  if (!GPAWA_AUTH_CREDIT_ONLY) {
    j["accounting_protocol"] = RECOVERY_PROTOCOL;
    j["journal_mode"] = measurementPaused(state) ? "PAUSED" : state.hasMeter ? "METERED" : "FRESH";
    if (state.hasMeter && !measurementPaused(state)) j["journal_counter_wh"] = state.meterWh;
  }
  if (enqueue(JobKind::Session, j)) lastSession = millis();
}
void sendAck() {
  JsonDocument j;
  identity(j);
  j["command_id"] = state.lastCommand.id;
  j["command_sequence"] = state.lastCommand.sequence;
  j["payload_digest"] = state.lastCommand.digest;
  j["credit_wh"] = state.lastCommand.creditWh;
  j["receipt_id"] = state.receiptId;
  j["applied_at"] = state.appliedAt;
  j["type"] = "AC_LAB_APPLIED";
  // Include frozen command so Django can check allocation/delivery bindings.
  JsonDocument original;
  if (deserializeJson(original, state.lastCommand.canonical)) {
    diagnosticLocal("COMMAND_VALIDATION_FAILURE", "ack_journal", true, JobKind::Ack);
    latch("ACK journal bad");
    return;
  }
  j["allocation_id"] = original["allocation_id"];
  j["delivery_id"] = original["delivery_id"];
  if (checkpointMatchesCommand()) {
    j["credit_checkpoint"]["boot_id"] = creditCheckpoint.bootId;
    j["credit_checkpoint"]["sequence"] = creditCheckpoint.sequence;
  }
  enqueue(JobKind::Ack, j);
}
void sendMeasurementPrepare() {
  if (!migrationMatchesJournal() || measurementMigration.stage != MIGRATION_INTENT ||
      measurementMigration.ackPending || !sensorOK || !sessionReady) return;
  JsonDocument j;
  identity(j);
  j["transition_id"] = measurementMigration.transitionId;
  j["transition_protocol"] = "GPAWA_BASELINE_V1";
  j["source_state"] = baselineSourceName(measurementMigration.source);
  j["had_baseline"] = measurementMigration.hadBaseline != 0;
  if (measurementMigration.hadBaseline) j["old_baseline_wh"] = measurementMigration.oldBaselineWh;
  else j["old_baseline_wh"] = nullptr;
  j["baseline_wh"] = measurementMigration.baselineWh;
  j["application_counter"] = measurementMigration.applicationCounter;
  j["ack_pending"] = measurementMigration.ackPending != 0;
  if (measurementMigration.applicationCounter) {
    j["last_command_id"] = state.lastCommand.id;
    j["last_payload_digest"] = state.lastCommand.digest;
    j["last_receipt_id"] = measurementMigration.creditReceiptId;
  }
  j["credited_uwh"] = measurementMigration.creditedUWh;
  j["consumed_uwh"] = measurementMigration.consumedUWh;
  j["uncertain_uwh"] = measurementMigration.uncertainUWh;
  enqueue(JobKind::MeasurementPrepare, j);
}
void sendMeasurementCommit() {
  if (!migrationMatchesJournal() || measurementMigration.stage != MIGRATION_PREPARED ||
      !sessionReady) return;
  JsonDocument j;
  identity(j);
  j["transition_id"] = measurementMigration.transitionId;
  j["receipt_id"] = measurementMigration.receiptId;
  enqueue(JobKind::MeasurementCommit, j);
}
bool sendPendingTelemetry(bool replay = true) {
  return telemetryOutbox[0] && enqueueBody(JobKind::Telemetry, telemetryOutbox, replay);
}
bool clearTelemetryOutbox() {
  if (!prefs.remove("telemetry") || prefs.isKey("telemetry")) {
    latch("Telemetry cleanup failed");
    return false;
  }
  telemetryOutbox[0] = 0;
  return true;
}
void sendTelemetry() {
  if (GPAWA_AUTH_CREDIT_ONLY || telemetryOutbox[0] || !serverBaselineReady) return;
  const bool healthy = sensorOK && lastValidSample && millis() - lastValidSample <= 3000 && evidenceMatchesJournal();
  const bool outstanding = !verifiedWhKnown || state.meterWh != verifiedWh || state.consumedUWh != verifiedConsumed;
  const bool readingAvailable = healthy || (outstanding && evidenceMatchesJournal());
  // A fault is not accounting evidence. Keep the unpaid proof pending until
  // the saved observation can be sent or a new valid reading is acquired.
  if (outstanding && !readingAvailable) return;
  if (telemetrySequence == UINT32_MAX) {
    latch("Sequence exhausted");
    return;
  }
  JsonDocument j;
  identity(j);
  reportRelayProfile(j);
  j["accounting_protocol"] = RECOVERY_PROTOCOL;
  j["boot_id"] = bootId;
  j["boot_counter"] = state.bootCounter;
  j["sequence"] = ++telemetrySequence;
  char at[25];
  if (readingAvailable) {
    time_t captured = evidence.capturedAt;
    struct tm utc {};
    gmtime_r(&captured, &utc);
    strftime(at, sizeof at, "%Y-%m-%dT%H:%M:%SZ", &utc);
  } else timestamp(at, sizeof at);
  j["measured_at"] = at;
  j["clock_status"] = "NETWORK_TIME";
  j["application_counter"] = state.applicationCounter;
  j["credited_uwh"] = state.creditedUWh;
  j["consumed_uwh"] = state.consumedUWh;
  j["uncertain_uwh"] = state.uncertainUWh;
  j["remaining_credit_uwh"] = state.availableUWh;
  if (readingAvailable) {
    j["voltage_mv"] = evidence.reading.mv;
    j["current_ma"] = evidence.reading.ma;
    j["power_mw"] = evidence.reading.mw;
    j["pzem_wh"] = state.meterWh;
    j["frequency_cHz"] = evidence.reading.frequency_cHz;
    j["power_factor_pct"] = evidence.reading.powerFactorPct;
  } else {
    j["voltage_mv"] = nullptr;
    j["current_ma"] = nullptr;
    j["power_mw"] = nullptr;
    j["pzem_wh"] = nullptr;
    j["frequency_cHz"] = nullptr;
    j["power_factor_pct"] = nullptr;
  }
  j["output_requested"] = outputOn;
  j["output_feedback"] = "UNKNOWN";
  j["sensor_status"] = readingAvailable ? "OK" : "FAULT";
  j["fault_status"] = state.hold ? "ACCOUNTING_HOLD" : fatal ? "SAFETY_FAULT" :
                      healthy ? "OK" : "SENSOR_UNAVAILABLE";
  // Commit the balance before making the snapshot retryable. A restart can
  // never restore a balance older than a transmitted snapshot.
  if ((savedWh != state.meterWh) && !persist(state)) return;
  if (measureJson(j) >= sizeof telemetryOutbox) {
    latch("Telemetry too large");
    return;
  }
  serializeJson(j, telemetryOutbox, sizeof telemetryOutbox);
  const size_t length = strlen(telemetryOutbox);
  char verify[sizeof telemetryOutbox] = {};
  if (prefs.putString("telemetry", telemetryOutbox) != length ||
      prefs.getString("telemetry", verify, sizeof verify) != length + 1 ||
      strcmp(verify, telemetryOutbox)) {
    latch("Telemetry save failed");
    return;
  }
  lastTelemetry = millis();
  telemetrySafetyEpoch = safetyEpoch;
  sendPendingTelemetry(false);
}
void commandSha(const uint8_t* bytes, size_t n, uint8_t* out) {
  mbedtls_sha256(bytes, n, out, 0);
}
bool parseCommand(JsonVariantConst row, Command& out) {
  return parseCreditCommand(row, state, out, commandSha);
}
bool applyPendingCredit(const char* sampleBoot = nullptr, uint32_t sampleSequence = 0) {
  if (pendingCreditRequiresCheckpoint) {
    if (!sampleBoot || !sampleSequence) return false;
    creditCheckpoint = {};
    memcpy(creditCheckpoint.bootId, sampleBoot, sizeof creditCheckpoint.bootId);
    memcpy(creditCheckpoint.commandId, pendingCredit.id, sizeof creditCheckpoint.commandId);
    creditCheckpoint.sequence = sampleSequence;
    if (!saveRecord("creditProof", creditCheckpoint)) return false;
  }
  char receipt[37], at[25];
  uuid4(receipt);
  timestamp(at, sizeof at);
  State next = state;
  const auto result = apply(next, pendingCredit, receipt, at);
  if (result == Apply::New) {
    if (!persist(next)) return false;
    diagnosticLocal("CREDIT_SAVED", "persisted", false);
    beep(1);
    say("Credit saved");
  } else if (result == Apply::Duplicate) {
    say("Already stored - recovering");
  } else {
    latch("Credit conflict");
    return false;
  }
  creditCommandPending = false;
  pendingCredit = {};
  return true;
}
bool stageCredit(JsonVariantConst row, bool checkpointRequired) {
  if (!clockValid() || !parseCommand(row, pendingCredit)) return false;
  creditCommandPending = true;
  pendingCreditRequiresCheckpoint = checkpointRequired;
  if (!GPAWA_AUTH_CREDIT_ONLY) inhibitForRecovery();
  return checkpointRequired || applyPendingCredit();
}
void meterTick(bool force = false);
void handleReply() {
  Reply r{};
  if (xQueueReceive(replyQueue, &r, 0) != pdTRUE) return;
  busy = false;
  JsonDocument diagnostic;
  const bool jsonValid = !deserializeJson(diagnostic, r.body) && diagnostic.is<JsonObject>();
  // Header-stripping proxies may still preserve the safe error-envelope ID.
  if (!r.serverRequestId[0] && r.httpStatus >= 400 && diagnostic["request_id"].is<const char*>() && diagnosticId(diagnostic["request_id"]))
    memcpy(r.serverRequestId, diagnostic["request_id"].as<const char*>(), 37);
  const char* code = diagnosticCode(diagnostic.as<JsonVariantConst>(), r.httpStatus);
  DiagnosticReplyScope trace(r, code);
  if (r.transport != DiagnosticTransport::Ok) diagnosticLocal(transportCause(r.transport), "transport");
  else if (r.status < 200 || r.status >= 300) diagnosticLocal("HTTP_REJECTION", "http_rejection");
  else diagnosticLocal("HTTP_RESPONSE", "response_received", false);
  if (r.status == 401 || r.status == 403) {
    outputAuthorized = false;
    outputLeaseUntil = 0;
    switchOff();
    loadRequested = false;

    sessionReady = false;
    latch("Device access denied");
    return;
  }
  if (r.status < 200 || r.status >= 300) {
    if (!GPAWA_AUTH_CREDIT_ONLY && (r.kind != JobKind::Redeem || r.status <= 0 || r.status >= 500)) {
      inhibitForRecovery();
      sessionReady = false;
    }
    nextNetwork = millis() + retryDelay;
    retryDelay = retryDelay < 30000 ? retryDelay * 2 : 60000;
    if (r.status == 409 && r.kind != JobKind::Redeem) {
      outputAuthorized = false;
      outputLeaseUntil = 0;
      switchOff();
      loadRequested = false;

      sessionReady = false;
      latch("Reconciliation required");
      return;
    }
    if (r.kind == JobKind::Redeem) {
      if (r.status == 400 || r.status == 404 || r.status == 409) say(rejectionMessage(code));
      else if (r.status == 503) say("Device API unavailable");
      else say(r.transport == DiagnosticTransport::BodyRead || r.transport == DiagnosticTransport::BodyLimit ? "API reply failed" : r.transport == DiagnosticTransport::TLS   ? "TLS failed"
                                                                                                                                  : r.transport == DiagnosticTransport::Clock ? "Clock not ready"
                                                                                                                                                                              : "No API response");
    } else say(r.kind == JobKind::Ack ? "ACK retry pending" : r.status == 503 ? "API unavailable"
                                                                              : "Retry pending");
    return;
  }
  if (!jsonValid) {
    diagnosticLocal("INVALID_JSON", "response_json");
    latch("Bad server JSON");
    return;
  }
  JsonDocument& j = diagnostic;
  if (!matching(j.as<JsonVariantConst>())) {
    diagnosticLocal("COMMAND_VALIDATION_FAILURE", "response_binding");
    latch("Wrong reply bind");
    return;
  }
  retryDelay = 2000;
  nextNetwork = millis() + 1000;
  if (r.kind == JobKind::Session) {
    if (!j["status"].is<const char*>() || strcmp(j["status"], "READY") ||
        !acceptOutputAuthorization(j.as<JsonVariantConst>(), r.sentAt, false)) {
      diagnosticLocal("COMMAND_VALIDATION_FAILURE", "session_status");
      latch("Bad session reply");
      return;
    }
    State next = state;
    next.reservedBytes[0] = 1;
    if (!persist(next)) return;
    sessionReady = true;
    if (!GPAWA_AUTH_CREDIT_ONLY) {
      const char* baseline = j["measurement_baseline"] | "";
      if ((strcmp(baseline, "REQUIRED") && strcmp(baseline, "PREPARED") && strcmp(baseline, "COMMITTED")) ||
          !j["verified_consumed_uwh"].is<uint64_t>()) {
        latch("Bad recovery session");
        return;
      }
      serverBaselineReady = !strcmp(baseline, "COMMITTED");
      if ((serverBaselineReady && !j["verified_counter_wh"].is<uint32_t>()) ||
          (!strcmp(baseline, "PREPARED") && !migrationPresent) ||
          (serverBaselineReady && (!state.hasMeter || measurementPaused(state)) && !migrationPresent)) {
        latch("Baseline needs review");
        return;
      }
      baselineStatusKnown = true;
      verifiedConsumed = j["verified_consumed_uwh"].as<uint64_t>();
      verifiedWhKnown = serverBaselineReady;
      verifiedWh = j["verified_counter_wh"].as<uint32_t>();
      faultPosted = false;
      if (!j["pending_credit_command"].isNull() &&
          (!j["credit_checkpoint_required"].is<bool>() ||
           !stageCredit(j["pending_credit_command"], j["credit_checkpoint_required"].as<bool>()))) {
        latch("Bad pending credit");
        return;
      }
    }
    say(state.ackPending ? "Recovering receipt" : GPAWA_AUTH_CREDIT_ONLY ? "Credit API ready"
                                                                         : "Ready: D to arm");
  } else if (r.kind == JobKind::Redeem) {
    if ((!GPAWA_AUTH_CREDIT_ONLY && !j["credit_checkpoint_required"].is<bool>()) ||
        !stageCredit(j["command"], !GPAWA_AUTH_CREDIT_ONLY && j["credit_checkpoint_required"].as<bool>())) {
      diagnosticLocal("COMMAND_VALIDATION_FAILURE", "command_validation");
      latch("Bad credit cmd");
      return;
    }
  } else if (r.kind == JobKind::Ack) {
    if (!j["status"].is<const char*>() || strcmp(j["status"], "APPLIED") || !j["command_id"].is<const char*>() || !j["receipt_id"].is<const char*>() || !j["command_sequence"].is<uint32_t>() || j["command_sequence"].as<uint32_t>() != state.applicationCounter || !j["payload_digest"].is<const char*>() || strcmp(j["payload_digest"], state.lastCommand.digest)) {
      diagnosticLocal("COMMAND_VALIDATION_FAILURE", "ack_response");
      latch("ACK reply bad");
      return;
    }
    State next = state;
    if (!acknowledge(next, j["command_id"], j["receipt_id"])) {
      diagnosticLocal("COMMAND_VALIDATION_FAILURE", "ack_binding");
      latch("ACK mismatch");
      return;
    }
    if (persist(next)) {
      diagnosticLocal("ACK_CONFIRMED", "ack_saved", false);
      say("Credit confirmed");
      if (!GPAWA_AUTH_CREDIT_ONLY) {
        inhibitForRecovery();
        if (!serverBaselineReady) {
          sessionReady = false; // Re-evaluate a legacy anchor after its final ACK.
          baselineStatusKnown = false;
        }
      }
    }
  } else if (r.kind == JobKind::MeasurementPrepare) {
    const char* status = j["status"].is<const char*>() ? j["status"].as<const char*>() : "";
    if ((strcmp(status, "PREPARED") && strcmp(status, "COMMITTED")) ||
        !j["transition_id"].is<const char*>() ||
        strcmp(j["transition_id"], measurementMigration.transitionId) ||
        !j["receipt_id"].is<const char*>() || !uuid(j["receipt_id"]) ||
        !j["baseline_wh"].is<uint32_t>() ||
        j["baseline_wh"].as<uint32_t>() != measurementMigration.baselineWh ||
        j["output_authorized"] != false) {
      diagnosticLocal("COMMAND_VALIDATION_FAILURE", "measurement_prepare_response");
      latch("Baseline reply bad");
      return;
    }
    memcpy(measurementMigration.receiptId, j["receipt_id"].as<const char*>(), 37);
    measurementMigration.stage = MIGRATION_PREPARED;
    if (persistMigration()) say("Baseline prepared");
  } else if (r.kind == JobKind::MeasurementCommit) {
    if (!j["status"].is<const char*>() || strcmp(j["status"], "COMMITTED") ||
        !j["transition_id"].is<const char*>() ||
        strcmp(j["transition_id"], measurementMigration.transitionId) ||
        !j["receipt_id"].is<const char*>() ||
        strcmp(j["receipt_id"], measurementMigration.receiptId) ||
        !j["baseline_wh"].is<uint32_t>() ||
        j["baseline_wh"].as<uint32_t>() != measurementMigration.baselineWh ||
        j["output_authorized"] != false) {
      diagnosticLocal("COMMAND_VALIDATION_FAILURE", "measurement_commit_response");
      latch("Baseline commit bad");
      return;
    }
    State next = state;
    next.version = VERSION;
    next.reservedBytes[2] = 0;
    next.hasMeter = 1;
    next.meterWh = measurementMigration.baselineWh;
    if (persist(next) && removeMigration()) {
      outputAuthorized = false;
      outputLeaseUntil = 0;
      outputAutoRestart = false;
      loadRequested = false;
      switchOff();
      serverBaselineReady = true;
      verifiedWhKnown = true;
      verifiedWh = state.meterWh;
      verifiedConsumed = state.consumedUWh;
      say("Meter baseline ready");
      Serial.printf("MEASUREMENT_TRANSITION status=COMMITTED baseline_wh=%lu prior_credit_preserved=YES output_authorized=NO\n",
                    (unsigned long)state.meterWh);
    }
  } else {
    JsonDocument sent;
    if (deserializeJson(sent, telemetryOutbox)) {
      latch("Telemetry journal bad");
      return;
    }
    const char* sampleBoot = sent["boot_id"] | "";
    const uint32_t sampleSequence = sent["sequence"].as<uint32_t>();
    if (!j["status"].is<const char*>() || strcmp(j["status"], "ACCEPTED") ||
        !j["boot_id"].is<const char*>() || strcmp(j["boot_id"], sampleBoot) ||
        !j["sequence"].is<uint32_t>() || j["sequence"].as<uint32_t>() != sampleSequence ||
        !j["recovery_pending"].is<bool>()) {
      diagnosticLocal("COMMAND_VALIDATION_FAILURE", "telemetry_response");
      latch("Telemetry bad");
      return;
    }
    if (!clearTelemetryOutbox()) return;
    const bool current = !strcmp(sampleBoot, bootId) && sessionReady && WiFi.status() == WL_CONNECTED && clockValid();
    const bool afterInhibit = telemetrySafetyEpoch == safetyEpoch;
    const bool validReading = sent["pzem_wh"].is<uint32_t>();
    if (validReading) {
      verifiedWhKnown = true;
      verifiedWh = sent["pzem_wh"].as<uint32_t>();
      verifiedConsumed = sent["consumed_uwh"].as<uint64_t>();
    }
    const bool postedHealthy = validReading && sent["fault_status"] == "OK";
    const bool caughtUp = postedHealthy && !j["recovery_pending"].as<bool>() &&
                          verifiedWh == state.meterWh && verifiedConsumed == state.consumedUWh &&
                          sent["application_counter"].as<uint32_t>() == state.applicationCounter;
    if (current) faultPosted = !validReading;
    // A retained observation can close the ledger during a fault, but only a
    // fresh healthy observation from this session can clear recovery.
    const bool sensorReady = sensorOK && lastValidSample && millis() - lastValidSample <= 3000;
    if (current && afterInhibit && sensorReady && caughtUp) {
      if (creditCommandPending && !applyPendingCredit(sampleBoot, sampleSequence)) return;
      else if (!state.ackPending) recoveryRequired = false;
    }
    if (!acceptOutputAuthorization(j.as<JsonVariantConst>(), r.sentAt,
          current && afterInhibit && sensorReady && !j["recovery_pending"].as<bool>() &&
          !recoveryRequired && !creditCommandPending && !state.ackPending)) {
      latch("Telemetry lease bad");
      return;
    }
  }
}
constexpr size_t PZEM_DIAGNOSTIC_RAW_LIMIT = 64;
constexpr uint32_t PZEM_DIAGNOSTIC_TIMEOUT_MS = 500;
constexpr uint32_t PZEM_DIAGNOSTIC_QUIET_MS = 20;
enum class PzemRxEnd : uint8_t { QuietGap, TotalTimeout };
struct PzemUartErrors {
  uint16_t frame = 0;
  uint16_t parity = 0;
  uint16_t fifoOverflow = 0;
  uint16_t bufferFull = 0;
  uint16_t breakSignal = 0;
};
volatile uint16_t pzemFrameErrors = 0;
volatile uint16_t pzemParityErrors = 0;
volatile uint16_t pzemFifoOverflows = 0;
volatile uint16_t pzemBufferFullErrors = 0;
volatile uint16_t pzemBreakErrors = 0;
void pzemOnReceiveError(hardwareSerial_error_t error) {
  switch (error) {
    case UART_FRAME_ERROR: if (pzemFrameErrors != UINT16_MAX) ++pzemFrameErrors; break;
    case UART_PARITY_ERROR: if (pzemParityErrors != UINT16_MAX) ++pzemParityErrors; break;
    case UART_FIFO_OVF_ERROR: if (pzemFifoOverflows != UINT16_MAX) ++pzemFifoOverflows; break;
    case UART_BUFFER_FULL_ERROR: if (pzemBufferFullErrors != UINT16_MAX) ++pzemBufferFullErrors; break;
    case UART_BREAK_ERROR: if (pzemBreakErrors != UINT16_MAX) ++pzemBreakErrors; break;
    default: break;
  }
}
void resetPzemUartErrors() {
  pzemFrameErrors = 0;
  pzemParityErrors = 0;
  pzemFifoOverflows = 0;
  pzemBufferFullErrors = 0;
  pzemBreakErrors = 0;
}
PzemUartErrors snapshotPzemUartErrors() {
  return {pzemFrameErrors, pzemParityErrors, pzemFifoOverflows,
          pzemBufferFullErrors, pzemBreakErrors};
}
struct PzemRxDiagnostics {
  uint16_t received = 0;
  uint16_t responseBytes = 0;
  uint16_t discardedBeforeRequest = 0;
  uint8_t raw[PZEM_DIAGNOSTIC_RAW_LIMIT] = {};
  uint8_t rawStored = 0;
  uint32_t elapsedMs = 0;
  uint32_t firstByteUs = UINT32_MAX;
  uint32_t lastByteUs = UINT32_MAX;
  uint32_t maxObservedByteReadGapUs = 0;
  PzemRxEnd end = PzemRxEnd::TotalTimeout;
  bool quietGapObserved = false;
  bool requestEcho = false;
  PzemUartErrors uartErrors{};
};
void pzemRequest(uint8_t (&request)[8]) {
  request[0] = hw::PZEM_ADDR;
  request[1] = 4;
  request[2] = 0;
  request[3] = 0;
  request[4] = 0;
  request[5] = 10;
  const uint16_t checksum = pz::crc(request, 6);
  request[6] = uint8_t(checksum);
  request[7] = uint8_t(checksum >> 8);
}
void beginPzemUart() {
  Serial1.setRxBufferSize(256);
  Serial1.begin(9600, SERIAL_8N1, hw::RX, hw::TX);
  Serial1.setRxTimeout(3);
  Serial1.setRxFIFOFull(1);
  Serial1.onReceiveError(pzemOnReceiveError);
}
struct MeterPoll {
  uint8_t request[8];
  uint8_t frame[PZEM_DIAGNOSTIC_RAW_LIMIT];
  size_t count;
  uint32_t started;
  uint32_t lastByte;
  bool active;
};
MeterPoll meterPoll{};
void startMeterPoll(uint32_t now) {
  meterPoll = {};
  // Bounded even with a continuously noisy input.
  for (int i = 0; i < 256 && Serial1.available(); ++i) Serial1.read();
  pzemRequest(meterPoll.request);
  resetPzemUartErrors();
  Serial1.write(meterPoll.request, sizeof meterPoll.request);
  meterPoll.started = meterPoll.lastByte = now;
  meterPoll.active = true;
}
bool takeMeterPoll(uint32_t now, pz::DecodeError& error) {
  for (size_t i = 0; i <= sizeof meterPoll.frame && Serial1.available(); ++i) {
    const int byte = Serial1.read();
    if (meterPoll.count == sizeof meterPoll.frame) {
      error = pz::DecodeError::ExtraBytes;
      meterPoll.active = false;
      return true;
    }
    meterPoll.frame[meterPoll.count++] = uint8_t(byte);
    meterPoll.lastByte = now;
  }
  const size_t echo = pz::hasRequestEcho(meterPoll.frame, meterPoll.count, meterPoll.request)
      ? pz::READ_REQUEST_BYTES : 0;
  if (now - meterPoll.started < PZEM_DIAGNOSTIC_TIMEOUT_MS &&
      (meterPoll.count < echo + pz::READ_RESPONSE_BYTES ||
       now - meterPoll.lastByte < PZEM_DIAGNOSTIC_QUIET_MS)) return false;
  meterPoll.active = false;
  error = pz::decodeChecked(meterPoll.frame + echo, meterPoll.count - echo, hw::PZEM_ADDR, measured);
  const auto uart = snapshotPzemUartErrors();
  if (error == pz::DecodeError::None &&
      (uart.frame || uart.parity || uart.fifoOverflow || uart.bufferFull || uart.breakSignal))
    error = pz::DecodeError::Uart;
  return true;
}
bool sample(pz::DecodeError* error = nullptr, PzemRxDiagnostics* rx = nullptr,
            uint32_t timeoutMs = 180, uint32_t quietMs = 0) {
#if GPAWA_USB_EXERCISE
  if (error) *error = pz::DecodeError::None;
  measured.wh = prefs.getUInt("mockWh", 0);
  return true;
#else
  if (rx) *rx = {};
  // PZEM v3 TTL, single instrument, read-only function 04. No counter reset.
  auto& u = Serial1;
  uint16_t discarded = 0;
  while (u.available()) {
    u.read();
    if (discarded != UINT16_MAX) ++discarded;
  }
  if (rx) rx->discardedBeforeRequest = discarded;
  uint8_t req[8] = {};
  pzemRequest(req);
  if (rx) resetPzemUartErrors();
  u.write(req, 8);
  u.flush();
  uint8_t b[PZEM_DIAGNOSTIC_RAW_LIMIT] = {};
  uint16_t n = 0;
  const uint32_t startUs = micros();
  uint32_t lastObservedByteReadUs = startUs;
  bool seenRx = false;
  bool completeAfterEcho = false;
  const uint32_t timeoutUs = timeoutMs * 1000UL;
  while (uint32_t(micros() - startUs) < timeoutUs) {
    const int available = u.available();
    if (available > 0) {
      seenRx = true;
      while (u.available()) {
        const uint8_t value = uint8_t(u.read());
        const uint32_t byteReadAtUs = micros();
        if (rx) {
          if (n == 0) rx->firstByteUs = uint32_t(byteReadAtUs - startUs);
          else {
            const uint32_t gap = uint32_t(byteReadAtUs - lastObservedByteReadUs);
            if (gap > rx->maxObservedByteReadGapUs)
              rx->maxObservedByteReadGapUs = gap;
          }
          rx->lastByteUs = uint32_t(byteReadAtUs - startUs);
        }
        lastObservedByteReadUs = byteReadAtUs;
        if (n < sizeof b) b[n] = value;
        if (rx && rx->rawStored < sizeof rx->raw) rx->raw[rx->rawStored++] = value;
        if (n != UINT16_MAX) ++n;
      }
      const size_t echoBytes = pz::hasRequestEcho(b, n, req) ? pz::READ_REQUEST_BYTES : 0;
      completeAfterEcho = n >= echoBytes + pz::READ_RESPONSE_BYTES;
      continue;
    }
    if (seenRx && uint32_t(micros() - lastObservedByteReadUs) >= quietMs * 1000UL) {
      if (rx) rx->quietGapObserved = true;
      if (!completeAfterEcho) {
        delay(1);
        continue;
      }
      if (rx) rx->end = PzemRxEnd::QuietGap;
      break;
    }
    delay(1);
  }
  if (rx) {
    rx->received = n;
    rx->elapsedMs = uint32_t(micros() - startUs) / 1000;
    if (!rx->quietGapObserved || !completeAfterEcho)
      rx->end = PzemRxEnd::TotalTimeout;
    rx->requestEcho = pz::hasRequestEcho(b, n, req);
    rx->responseBytes = n >= (rx->requestEcho ? pz::READ_REQUEST_BYTES : 0)
                            ? n - (rx->requestEcho ? pz::READ_REQUEST_BYTES : 0)
                            : 0;
    rx->uartErrors = snapshotPzemUartErrors();
  }
  const size_t echoBytes = pz::hasRequestEcho(b, n, req) ? pz::READ_REQUEST_BYTES : 0;
  const size_t responseBytes = n >= echoBytes ? n - echoBytes : 0;
  if (rx) rx->responseBytes = responseBytes > UINT16_MAX ? UINT16_MAX : uint16_t(responseBytes);
  const pz::DecodeError result = pz::decodeChecked(b + echoBytes, responseBytes, hw::PZEM_ADDR, measured);
  if (error) *error = result;
  return result == pz::DecodeError::None;
#endif
}
void printPzemInvalid(pz::DecodeError error, const PzemRxDiagnostics& rx) {
  Serial.printf("PZEM_STATUS status=INVALID reason=%s end=%s rx_bytes=%u response_bytes=%u pre_request_discarded=%u elapsed_ms=%lu first_byte_us=",
                pz::errorName(error),
                rx.end == PzemRxEnd::QuietGap ? "INTER_BYTE_QUIET" : "TOTAL_TIMEOUT",
                unsigned(rx.received), unsigned(rx.responseBytes), unsigned(rx.discardedBeforeRequest),
                (unsigned long)rx.elapsedMs);
  if (rx.firstByteUs == UINT32_MAX) Serial.print("NONE");
  else Serial.print((unsigned long)rx.firstByteUs);
  Serial.print(" last_byte_read_us=");
  if (rx.lastByteUs == UINT32_MAX) Serial.print("NONE");
  else Serial.print((unsigned long)rx.lastByteUs);
  Serial.printf(" rx_span_us=%lu max_observed_byte_read_gap_us=%lu quiet_gap_observed=%s request_echo=%s uart_frame=%u uart_parity=%u uart_fifo_overflow=%u uart_buffer_full=%u uart_break=%u raw=",
                rx.firstByteUs == UINT32_MAX || rx.lastByteUs == UINT32_MAX
                    ? 0UL : (unsigned long)(rx.lastByteUs - rx.firstByteUs),
                (unsigned long)rx.maxObservedByteReadGapUs,
                rx.quietGapObserved ? "YES" : "NO",
                rx.requestEcho ? "YES" : "NO", unsigned(rx.uartErrors.frame),
                unsigned(rx.uartErrors.parity), unsigned(rx.uartErrors.fifoOverflow),
                unsigned(rx.uartErrors.bufferFull), unsigned(rx.uartErrors.breakSignal));
  const uint8_t shown = rx.rawStored;
  if (!shown) Serial.print("[]");
  else {
    Serial.print('[');
    for (uint8_t i = 0; i < shown; ++i) {
      if (i) Serial.print(' ');
      if (rx.raw[i] < 16) Serial.print('0');
      Serial.print(rx.raw[i], HEX);
    }
    Serial.print(']');
  }
  if (rx.received > rx.rawStored) Serial.printf(" truncated=%u", unsigned(rx.received - rx.rawStored));
  Serial.println();
}
void printPzemValidTiming(const PzemRxDiagnostics& rx) {
  Serial.printf("PZEM_RX end=%s rx_bytes=%u response_bytes=%u first_byte_us=",
                rx.end == PzemRxEnd::QuietGap ? "INTER_BYTE_QUIET" : "TOTAL_TIMEOUT",
                unsigned(rx.received), unsigned(rx.responseBytes));
  if (rx.firstByteUs == UINT32_MAX) Serial.print("NONE");
  else Serial.print((unsigned long)rx.firstByteUs);
  Serial.printf(" last_byte_read_us=%lu rx_span_us=%lu max_observed_byte_read_gap_us=%lu elapsed_ms=%lu request_echo=%s uart_frame=%u uart_parity=%u uart_fifo_overflow=%u uart_buffer_full=%u uart_break=%u\n",
                (unsigned long)rx.lastByteUs,
                rx.firstByteUs == UINT32_MAX || rx.lastByteUs == UINT32_MAX
                    ? 0UL : (unsigned long)(rx.lastByteUs - rx.firstByteUs),
                (unsigned long)rx.maxObservedByteReadGapUs, (unsigned long)rx.elapsedMs,
                rx.requestEcho ? "YES" : "NO", unsigned(rx.uartErrors.frame),
                unsigned(rx.uartErrors.parity), unsigned(rx.uartErrors.fifoOverflow),
                unsigned(rx.uartErrors.bufferFull), unsigned(rx.uartErrors.breakSignal));
}
void sensorUnavailable() {
  if (sensorOK || good) {
    inhibitForRecovery();
    faultPosted = false;
    if (evidenceMatchesJournal() && (!verifiedWhKnown || verifiedWh != state.meterWh ||
        verifiedConsumed != state.consumedUWh)) {
      if (!saveRecord("meterProof", evidence)) return;
      if (savedWh != state.meterWh && !persist(state)) return;
    }
  }
  sensorOK = false;
  good = 0;
}
void meterTick(bool force) {
  if (GPAWA_AUTH_CREDIT_ONLY) {
    sensorOK = false;
    good = 0;
    return;
  }
  uint32_t now = millis();
  if (sensorOK && now - lastValidSample > 3000) {
    sensorUnavailable();
    say("Meter stale");
  }
  pz::DecodeError sampleError = pz::DecodeError::None;
  if (GPAWA_USB_EXERCISE) {
    if (!force && now - lastSample < hw::SAMPLE_MS) return;
    lastSample = now;
    sample(&sampleError);
  } else {
    if (!meterPoll.active) {
      if (!force && now - lastSample < hw::SAMPLE_MS) return;
      lastSample = now;
      startMeterPoll(now);
    }
    if (!takeMeterPoll(now, sampleError)) return;
  }
  if (sampleError != pz::DecodeError::None) {
    Serial.printf("PZEM_STATUS status=INVALID reason=%s\n", pz::errorName(sampleError));
    sensorUnavailable();
    return;
  }
  if (!GPAWA_USB_EXERCISE) {
    const pz::CounterStatus counter = meterMonitor.accept(
        measured.wh, now, state.hasMeter != 0, state.meterWh);
    if (counter == pz::CounterStatus::Regression ||
        counter == pz::CounterStatus::ImplausibleJump) {
      State next = state;
      next.hold = 1;
      switchOff();
      loadRequested = false;
      persist(next);
      latch(counter == pz::CounterStatus::Regression ?
                "Counter reversed" : "Meter jump review");
      return;
    }
  }
  lastValidSample = now;
  static uint8_t ignoredOff = 0;
  if (!GPAWA_USB_EXERCISE && GPAWA_COMMISSIONED_OUTPUT && !outputOn && measured.ma > 100) {
    if (++ignoredOff >= 5) {
      State n = state;
      n.hold = 1;
      switchOff();
      persist(n);
      latch("Load while OFF");
      return;
    }
  } else ignoredOff = 0;
  if (good < 3) ++good;
  if (good == 3 && !sensorOK) faultPosted = false;
  sensorOK = good >= 3;
  if (!GPAWA_USB_EXERCISE && (measurementPaused(state) || !serverBaselineReady || migrationPresent)) {
    switchOff();
    loadRequested = false;
    if (sensorOK && sessionReady && baselineStatusKnown && !serverBaselineReady &&
        !migrationPresent && !state.ackPending && !creditCommandPending) {
      const auto source = measurementPaused(state) ? BaselineSource::Paused :
          state.hasMeter ? BaselineSource::Legacy : BaselineSource::Fresh;
      beginMeasurementMigration(source == BaselineSource::Legacy ? state.meterWh : measured.wh, source);
    }
    return;
  }
  auto next = state;
  const auto before = state.availableUWh;
  auto result = observe(next, measured.wh);
  if (result == Reading::BaselineRequired) {
    switchOff();
    loadRequested = false;
    return;
  }
  if (result == Reading::Fault) {
    switchOff();
    persist(next);
    latch("Counter reversed");
    return;
  }
  if (!next.availableUWh) {
    switchOff();
    loadRequested = false;
  }
  if (result == Reading::First || (before && !next.availableUWh) || next.meterWh - savedWh >= 32) {
    if (!persist(next)) return;
  } else {
    seal(next);
    state = next;
  }
  if (!GPAWA_USB_EXERCISE && clockValid()) {
    evidence = {measured, uint32_t(time(nullptr)), state.applicationCounter, state.consumedUWh, 0};
  }
}
void outputTick() {
  const uint32_t now = millis();
  const bool leaseLive = outputAuthorized &&
      static_cast<int32_t>(outputLeaseUntil - now) > 0;
  if (outputAuthorized && !leaseLive) {
    outputAuthorized = false;
    outputLeaseUntil = 0;
    switchOff();
    loadRequested = false;
  }
  const bool permit = !GPAWA_AUTH_CREDIT_ONLY && (GPAWA_USB_EXERCISE || GPAWA_COMMISSIONED_OUTPUT) &&
                      storageOK && sensorOK && lastValidSample && millis() - lastValidSample <= 3000 &&
                      !fatal && loadRequested && !state.hold && state.hasMeter && !measurementPaused(state) &&
                      !migrationPresent && !recoveryRequired && !creditCommandPending && state.availableUWh &&
                      !state.ackPending && state.reservedBytes[0] &&
                      leaseLive &&
                      (GPAWA_USB_EXERCISE || (sessionReady && WiFi.status() == WL_CONNECTED && clockValid()));
  static uint32_t lastDiagnostic = 0;
  static char lastBlock[32] = {};
  const char* block = GPAWA_AUTH_CREDIT_ONLY ? "AUTH_CREDIT_ONLY" :
                      (!GPAWA_USB_EXERCISE && !GPAWA_COMMISSIONED_OUTPUT) ? "OUTPUT_NOT_COMMISSIONED" :
                      !storageOK ? "STORAGE_UNAVAILABLE" : fatal ? "FAULT_LATCHED" : state.hold ? "METER_HOLD" :
                      measurementPaused(state) || migrationPresent ? "BASELINE_MIGRATION" :
                      !state.hasMeter ? "NO_METER_BASELINE" : !sensorOK ? "SENSOR_NOT_READY" :
                      !state.availableUWh ? "CREDIT_EMPTY" : state.ackPending ? "ACK_PENDING" :
                      recoveryRequired || creditCommandPending ? "METER_RECOVERY_PENDING" :
                      !leaseLive ? "OUTPUT_NOT_AUTHORIZED" :
                      !sessionReady ? "SESSION_NOT_READY" :
                      (!GPAWA_USB_EXERCISE && WiFi.status() != WL_CONNECTED) ? "NETWORK_OFFLINE" :
                      (!GPAWA_USB_EXERCISE && !clockValid()) ? "CLOCK_UNAVAILABLE" :
                      !loadRequested ? "NOT_ARMED" : "AUTHORIZED";
  if (strcmp(lastBlock, block) || now - lastDiagnostic >= 5000) {
    snprintf(lastBlock, sizeof lastBlock, "%s", block);
    lastDiagnostic = now;
    Serial.printf("OUTPUT_STATUS block=%s mode=%s storage=%s sensor=%s credit=%s ack_pending=%s session=%s wifi=%s armed=%s fault=%s hold=%s measurement=%s gpio14=%s\n",
                  block, GPAWA_AUTH_CREDIT_ONLY ? "AUTH_CREDIT_ONLY" : "METERED",
                  storageOK ? "READY" : "UNAVAILABLE",
                  GPAWA_AUTH_CREDIT_ONLY ? "DISABLED_BY_MODE" : sensorOK ? "HEALTHY" : "MISSING_OR_INVALID",
                  state.availableUWh ? "AVAILABLE" : "ZERO", state.ackPending ? "YES" : "NO",
                  sessionReady ? "READY" : "NOT_READY", WiFi.status() == WL_CONNECTED ? "CONNECTED" : "OFFLINE",
                  loadRequested ? "YES" : "NO", fatal ? "YES" : "NO", state.hold ? "YES" : "NO",
                  measurementState(state), GPAWA_COMMISSIONED_OUTPUT ? "CONTROLLED" : "NOT_DRIVEN");
  }
  if (!permit) {
    switchOff();
    if (fatal || state.hold || !storageOK || !sensorOK || !sessionReady ||
        !outputAuthorized || !state.availableUWh || !state.hasMeter || measurementPaused(state))
      loadRequested = false;
    return;
  }
#if GPAWA_COMMISSIONED_OUTPUT && !GPAWA_USB_EXERCISE
  digitalWrite(hw::SWITCH_PIN, hw::RELAY_ACTIVE_LEVEL);
  outputOn = true;
#elif GPAWA_USB_EXERCISE
  outputOn = true;  // logical indicator; no relay GPIO written
#else
  outputOn = false;
#endif
}
bool viewingMeter = false;
uint32_t meterShownAt = 0;
void handleKey() {
  char k = keypad.getKey();
  if (!k) return;
  if (k == 'A') {
    viewingMeter = !viewingMeter;
    meterShownAt = millis();
    return;
  }
  if (viewingMeter) {
    viewingMeter = false;
    if (k < '0' || k > '9') return;
  }
  if (tokenLength && (k == 'D' || k == 'B')) return;
  if (k >= '0' && k <= '9') {
    if (tokenLength < 15) {
      tokenDigits[tokenLength++] = k;
      tokenDigits[tokenLength] = 0;
    }
    return;
  }
  if (k == '*') {
    if (tokenLength) tokenDigits[--tokenLength] = 0;
    return;
  }
  if (k == 'C') {
    eraseToken();
    say("Entry cleared");
    return;
  }
#if !GPAWA_USB_EXERCISE
  if (k == 'B') {
    say(state.ackPending ? "Credit ACK pending" : "Balance available");
    return;
  }
#endif
  if (k == 'D') {
    if (GPAWA_AUTH_CREDIT_ONLY) {
      loadRequested = false;
      switchOff();
      say("Output disabled");
      return;
    }
    if (!GPAWA_COMMISSIONED_OUTPUT || !outputAuthorized || recoveryRequired || creditCommandPending) {
      loadRequested = false;
      switchOff();
      say("Output not authorized");
      return;
    }
    if (loadRequested) {
      loadRequested = false;
      userPaused = true;
      switchOff();
      say("Paused");
    } else if (sensorOK && state.availableUWh && sessionReady && WiFi.status() == WL_CONNECTED && clockValid() && !fatal && !state.hold) {
      userPaused = false;
      loadRequested = true;
      say("Meter armed");
    } else say(!state.availableUWh ? "Credit empty" : !sensorOK ? "Check meter" : "Check API/safety");
    return;
  }
#if GPAWA_USB_EXERCISE
  if (k == 'B') {
    if (outputOn && state.availableUWh) {
      auto reading = prefs.getUInt("mockWh", 0);
      if (reading == UINT32_MAX || prefs.putUInt("mockWh", reading + 1) != 4) {
        latch("Mock meter fault");
        return;
      }
      meterTick(true);
      outputTick();
    }
    return;
  }
#endif
  if (k != '#') return;
  if (!digits(tokenDigits, 15)) {
    say("Need 15 digits");
    return;
  }
  if (!creditTransportReady(state, GPAWA_AUTH_CREDIT_ONLY, sensorOK)) {
    say("Check meter");
    return;
  }
#if GPAWA_USB_EXERCISE
  const bool second = state.applicationCounter == 1 && !strcmp(tokenDigits, "222222222222222");
  if (!second && (state.applicationCounter != 0 || strcmp(tokenDigits, "111111111111111"))) {
    eraseToken();
    say("Invalid or used");
    return;
  }
  Command c{};
  strcpy(c.id, "00000000-0000-4000-8000-000000000003");
  memset(c.digest, 'a', 64);
  strcpy(c.canonical, "EXERCISE");
  c.sequence = second ? 2 : 1;
  c.creditWh = 10;
  if (second) {
    c.id[35] = '5';
    strcpy(c.canonical, "EXERCISE2");
  }
  State next = state;
  if (apply(next, c, second ? "00000000-0000-4000-8000-000000000006" : "00000000-0000-4000-8000-000000000004", "2026-01-01T00:00:00Z") != Apply::New) {
    latch("Exercise fault");
    return;
  }
  next.ackPending = 0;
  if (persist(next)) {
    beep(1);
    say("10 test Wh saved");
  }
  eraseToken();
#else
  if (!sessionReady || WiFi.status() != WL_CONNECTED || !clockValid()) {
    diagnosticLocal(WiFi.status() != WL_CONNECTED ? "CONNECTION_FAILURE" : !clockValid() ? "CLOCK_UNAVAILABLE"
                                                                                         : "SESSION_NOT_READY",
                    "request_not_sent", true, JobKind::Redeem);
    say("Need device API");
    return;
  }
  if (!GPAWA_AUTH_CREDIT_ONLY && (!serverBaselineReady || recoveryRequired || creditCommandPending)) {
    say("Meter sync pending");
    return;
  }
  if (busy || state.ackPending || telemetryOutbox[0]) {
    diagnosticLocal(state.ackPending ? "PENDING_ACK" : "REQUEST_PENDING", "request_not_sent", true, JobKind::Redeem);
    say(state.ackPending ? "ACK pending" : "Request pending");
    return;
  }
  JsonDocument j;
  identity(j);
  j["token"] = tokenDigits;
  j["application_counter"] = state.applicationCounter;
  if (!GPAWA_AUTH_CREDIT_ONLY) {
    j["accounting_protocol"] = RECOVERY_PROTOCOL;
    // Close the old credit epoch with output inhibited. The command is
    // applied only after the server accepts a subsequent meter checkpoint.
    inhibitForRecovery();
  }
  if (enqueue(JobKind::Redeem, j)) {
    eraseToken();
    say("Checking token");
  }
#endif
}
void row(int n, const char* s) {
  char a[17];
  snprintf(a, sizeof a, "%-16.16s", s);
  lcd.setCursor(0, n);
  lcd.print(a);
}
// Energy balance is stored as micro-watt-hours (uWh); 1 kWh = 1,000,000,000 uWh.
// Integer conversion truncates to two decimals so the LCD NEVER displays more
// spendable credit than the persistent accounting journal actually contains.
void formatKWh(char* dest, size_t capacity, uint64_t uwh) {
  const uint64_t hundredths = uwh / 10000000ULL;
  snprintf(dest, capacity, "%llu.%02llu", (unsigned long long)(hundredths / 100ULL),
           (unsigned long long)(hundredths % 100ULL));
}
void draw() {
  if (!displayOK || millis() - lastUi < hw::UI_MS) return;
  lastUi = millis();
  char value[24], line[40];
  if (fatal) {
    row(0, "OFF: needs check");
    row(1, message);
    return;
  }
  if (viewingMeter && millis() - meterShownAt >= 5000) viewingMeter = false;
  if (viewingMeter) {
    row(0, "Meter number");
    row(1, state.meterNumber);
    return;
  }
  if (tokenLength) {
    row(0, tokenDigits);
    row(1, "# Send  * Delete");
    return;
  }
  formatKWh(value, sizeof value, state.availableUWh);
  snprintf(line, sizeof line, "Units: %skWh", value);
  row(0, line);
  if (millis() - showAt < 2000) {
    row(1, message);
  } else if (sensorOK && lastValidSample && millis() - lastValidSample <= 3000 &&
             (millis() / 2500) % 2 == 1) {
    snprintf(line, sizeof line, "%luV %luW",
             (unsigned long)(measured.mv / 1000),
             (unsigned long)(measured.mw / 1000));
    row(1, line);
  } else {
    row(1, outputOn ? "Output command ON" : "Output command OFF");
  }
}
bool configValid() {
  return (environmentCode(commissioning::ENVIRONMENT) == 1 || environmentCode(commissioning::ENVIRONMENT) == 2) && String(cfg::WIFI_SSID).indexOf("REPLACE") < 0 && strlen(cfg::WIFI_SSID) > 0 && String(cfg::WIFI_PASSWORD).indexOf("REPLACE") < 0 && uuid(cfg::DEVICE_ID) && uuid(cfg::STORAGE_ID) && digits(cfg::METER_NUMBER, 11) && strcmp(cfg::METER_NUMBER, "00000000000") && cfg::BINDING_EPOCH > 0 && strlen(cfg::DEVICE_SECRET) >= 32 && String(cfg::DEVICE_SECRET).indexOf("REPLACE") < 0 && !strncmp(cfg::API_BASE, "https://", 8) && String(cfg::API_BASE).indexOf("REPLACE") < 0 && strlen(cfg::API_BASE) > 15 && String(cfg::API_BASE).endsWith("/api/v1") && !strchr(cfg::API_BASE, '@') && !strchr(cfg::API_BASE, '?') && !strchr(cfg::API_BASE, '#') && String(cfg::ROOT_CA).indexOf("BEGIN CERTIFICATE") >= 0 && String(cfg::ROOT_CA).indexOf("REPLACE") < 0;
}
}
void wifiCheckSetup();
void wifiCheckLoop();
void firmwareSetup() {
#if GPAWA_PZEM_DIAGNOSTIC
  Serial.begin(115200);
  beginPzemUart();
  meterMonitor = {};
  pzemDiagnosticStarted = millis();
  lastSample = pzemDiagnosticStarted;
  Serial.println("PZEM_DIAGNOSTIC read-only: no relay, NVS, credit, or network access.");
  Serial.printf("PZEM_CONFIG baud=9600 format=8N1 rx_gpio=%d tx_gpio=%d address=0x%02X function=04 rx_timeout_symbols=3 fifo_threshold=1 timeout_ms=%lu quiet_ms=%lu\n",
                hw::RX, hw::TX, unsigned(hw::PZEM_ADDR),
                (unsigned long)PZEM_DIAGNOSTIC_TIMEOUT_MS,
                (unsigned long)PZEM_DIAGNOSTIC_QUIET_MS);
  uint8_t req[8] = {};
  pzemRequest(req);
  Serial.print("PZEM_REQUEST bytes=");
  for (uint8_t i = 0; i < sizeof req; ++i) {
    if (i) Serial.print(' ');
    if (req[i] < 16) Serial.print('0');
    Serial.print(req[i], HEX);
  }
  Serial.println();
  Serial.println("PZEM_EXPECTED_RESPONSE length=25 address=01 function=04 byte_count=14 data=20_bytes crc=2_bytes_low_first");
  return;
#endif
#if GPAWA_RELAY_DIAGNOSTIC
  Serial.begin(115200);
  pinMode(hw::SWITCH_PIN, INPUT);
  Serial.println("RELAY_DIAGNOSTIC ready: AC/load must be disconnected; GPIO14 is released.");
  Serial.println("Send H or L to drive GPIO14; observe only K1. Send Z to release. No relay feedback is read.");
  return;
#endif
#if GPAWA_WIFI_TEST
  wifiCheckSetup();
  return;
#endif
#if !GPAWA_USB_EXERCISE && GPAWA_COMMISSIONED_OUTPUT
  digitalWrite(hw::SWITCH_PIN, hw::RELAY_INACTIVE_LEVEL);
  pinMode(hw::SWITCH_PIN, OUTPUT);
  switchOff();
#endif
  Serial.begin(115200);
  pinMode(hw::BEEP, OUTPUT);
  digitalWrite(hw::BEEP, LOW);
  Wire.begin(hw::SDA_PIN, hw::SCL_PIN);
  Wire.setTimeOut(50);
  displayOK = probe(hw::LCD_ADDR);
  if (!displayOK) {
    latch("LCD not found");
    return;
  }
  lcd.init();
  lcd.backlight();
  // Some LCD libraries re-initialize Wire. Reapply the chosen S3 pins if changing defaults.
  const bool usb = GPAWA_USB_EXERCISE;
  configured = usb || configValid();
  if (!configured) {
    if (GPAWA_AUTH_CREDIT_ONLY) {
      latch("Check DeviceConfig");
      return;
    }
    if (GPAWA_COMMISSIONED_OUTPUT) {
      latch("Set DeviceConfig");
      return;
    }
    diagnostic = true;
    beginPzemUart();
    row(0, "PZEM read only");
    row(1, "Waiting for data");
    return;
  }
  const char* dev = usb ? "00000000-0000-4000-8000-000000000001" : cfg::DEVICE_ID;
  const char* id = usb ? "00000000-0000-4000-8000-000000000002" : cfg::STORAGE_ID;
  const char* met = usb ? "00000000001" : cfg::METER_NUMBER;
  unsigned epoch = usb ? 1 : cfg::BINDING_EPOCH;
  const char* domain = usb ? "USB_EXERCISE" : commissioning::ENVIRONMENT;
  if (!prefs.begin(usb ? "gpawa_ex2" : (!strcmp(domain, "SANDBOX") ? "gpawa_sbx2" : "gpawa_ac1"), false)) {
    diagnosticLocal("PERSISTENT_STORAGE_FAILURE", "nvs_open");
    latch("NVS unavailable");
    return;
  }
  if (prefs.isKey("state")) {
    if (prefs.getBytesLength("state") != sizeof state || prefs.getBytes("state", &state, sizeof state) != sizeof state || !valid(state)) {
      diagnosticLocal("PERSISTENT_STORAGE_FAILURE", "journal_read");
      latch("Invalid journal");
      return;
    }
    if (strcmp(dev, state.deviceId) || strcmp(id, state.storageId) || strcmp(met, state.meterNumber) || epoch != state.bindingEpoch || strcmp(domain, accountingEnvironment(state))) {
      latch("Identity/domain changed");
      return;
    }
  } else {
    if (!usb && !cfg::ALLOW_FIRST_BOOT) {
      latch("Provision first");
      return;
    }
    state = {};
    state.magic = MAGIC;
    state.version = VERSION;
    state.bindingEpoch = epoch;
    state.reservedBytes[1] = environmentCode(domain);
    strcpy(state.deviceId, dev);
    strcpy(state.storageId, id);
    strcpy(state.meterNumber, met);
    if (usb) state.reservedBytes[0] = 1;
    seal(state);
  }
  if (state.hold) {
    latch("Meter needs check");
    return;
  }
  if (GPAWA_AUTH_CREDIT_ONLY) {
    if (!enterAuthenticatedCreditOnly(state)) {
      latch("Credit mode invalid");
      return;
    }
  }
  if (prefs.isKey("meterProof")) {
    if (prefs.getBytesLength("meterProof") != sizeof evidence ||
        prefs.getBytes("meterProof", &evidence, sizeof evidence) != sizeof evidence ||
        !storedRecordValid(evidence)) {
      latch("Invalid meter proof");
      return;
    }
    if (!GPAWA_AUTH_CREDIT_ONLY && !measurementPaused(state) && state.hasMeter &&
        evidence.applicationCounter == state.applicationCounter && evidence.reading.wh > state.meterWh) {
      State recovered = state;
      if (observe(recovered, evidence.reading.wh) != Reading::Advanced ||
          recovered.consumedUWh != evidence.consumedUWh) {
        latch("Meter proof conflict");
        return;
      }
      state = recovered;
    }
  }
  if (state.ackPending && prefs.isKey("creditProof") &&
      (prefs.getBytesLength("creditProof") != sizeof creditCheckpoint ||
       prefs.getBytes("creditProof", &creditCheckpoint, sizeof creditCheckpoint) != sizeof creditCheckpoint ||
       !storedRecordValid(creditCheckpoint))) {
    latch("Invalid credit proof");
    return;
  }
  if (prefs.isKey("telemetry")) {
    const size_t length = prefs.getString("telemetry", telemetryOutbox, sizeof telemetryOutbox);
    JsonDocument saved;
    if (GPAWA_AUTH_CREDIT_ONLY || length <= 1 || deserializeJson(saved, telemetryOutbox) ||
        !matching(saved.as<JsonVariantConst>()) ||
        saved["accounting_protocol"] != RECOVERY_PROTOCOL ||
        !saved["boot_counter"].is<uint32_t>() ||
        saved["boot_counter"].as<uint32_t>() > state.bootCounter ||
        !saved["sequence"].is<uint32_t>() ||
        !saved["boot_id"].is<const char*>() || !uuid(saved["boot_id"].as<const char*>())) {
      latch("Invalid telemetry journal");
      return;
    }
  }
  if (!bootRecover(state)) {
    diagnosticLocal("PERSISTENT_STORAGE_FAILURE", "journal_read");
    latch("Invalid journal");
    return;
  }
  if (!persist(state)) return;
  storageOK = true;
  if (prefs.isKey("migration")) {
    if (prefs.getBytesLength("migration") != sizeof measurementMigration ||
        prefs.getBytes("migration", &measurementMigration, sizeof measurementMigration) != sizeof measurementMigration ||
        !validMigration(measurementMigration)) {
      diagnosticLocal("PERSISTENT_STORAGE_FAILURE", "migration_read");
      latch("Invalid migration");
      return;
    }
    migrationPresent = true;
    if (measurementMigration.source != BaselineSource::Legacy && !measurementPaused(state) && state.hasMeter &&
        state.version == VERSION && state.meterWh == measurementMigration.baselineWh) {
      if (!removeMigration()) return;
    } else if (!migrationMatchesJournal()) {
      diagnosticLocal("PERSISTENT_STORAGE_FAILURE", "migration_binding");
      latch("Migration review");
      return;
    } else {
      Serial.printf("MEASUREMENT_TRANSITION status=RECOVERING stage=%s baseline_wh=%lu output_authorized=NO\n",
                    measurementMigration.stage == MIGRATION_PREPARED ? "PREPARED" : "INTENT",
                    (unsigned long)measurementMigration.baselineWh);
    }
  }
#if !GPAWA_USB_EXERCISE
  if (!GPAWA_AUTH_CREDIT_ONLY) beginPzemUart();
  uuid4(bootId);
  requestQueue = xQueueCreate(1, sizeof(Request));
  replyQueue = xQueueCreate(1, sizeof(Reply));
  if (!requestQueue || !replyQueue || xTaskCreate(networkWorker, "gpawa_net", 32768, nullptr, 1, nullptr) != pdPASS) {
    latch("Net task fault");
    return;
  }
  esp_task_wdt_config_t wdt = {};
  wdt.timeout_ms = 5000;
  wdt.idle_core_mask = (1U << portNUM_PROCESSORS) - 1U;
  wdt.trigger_panic = true;
  esp_err_t err = esp_task_wdt_reconfigure(&wdt);
  if (err == ESP_ERR_INVALID_STATE) err = esp_task_wdt_init(&wdt);
  if (err != ESP_OK) {
    latch("Watchdog fault");
    return;
  }
  err = esp_task_wdt_add(nullptr);
  watchdogReady = err == ESP_OK ||
                  (err == ESP_ERR_INVALID_STATE && esp_task_wdt_status(nullptr) == ESP_OK);
  if (!watchdogReady) {
    latch("Watchdog fault");
    return;
  }
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(cfg::WIFI_SSID, cfg::WIFI_PASSWORD);
  configTime(0, 0, "pool.ntp.org", "time.cloudflare.com");
#else
  sessionReady = true;
#endif
  if (GPAWA_AUTH_CREDIT_ONLY) Serial.println("Authenticated balance display mode; physical output remains disabled.");
  else if (usb) Serial.println("BUILD_PROFILE USB_EXERCISE");
  else Serial.printf("BUILD_PROFILE %s accounting=%s polarity=%s\n",
                     GPAWA_COMMISSIONED_OUTPUT ? "COMMISSIONED_OUTPUT" : "METERED_INHIBITED",
                     RECOVERY_PROTOCOL,
#if GPAWA_COMMISSIONED_OUTPUT
                     hw::RELAY_ACTIVE_LEVEL == HIGH ? "HIGH" : "LOW"
#else
                     "NOT_DRIVEN"
#endif
  );
  say(usb ? "USB exercise" : GPAWA_AUTH_CREDIT_ONLY ? "Checking credit"
                                                    : "Checking meter");
  meterTick(true);
}
void firmwareLoop() {
#if GPAWA_PZEM_DIAGNOSTIC
  const uint32_t now = millis();
  if (now - lastSample >= hw::SAMPLE_MS) {
    lastSample = now;
    pz::DecodeError error = pz::DecodeError::None;
    PzemRxDiagnostics rx{};
    if (!sample(&error, &rx, PZEM_DIAGNOSTIC_TIMEOUT_MS, PZEM_DIAGNOSTIC_QUIET_MS)) {
      printPzemInvalid(error, rx);
    } else {
      const pz::CounterStatus status = meterMonitor.accept(measured.wh, now, false, 0);
      if (status == pz::CounterStatus::Regression) {
        Serial.println("PZEM_STATUS status=FAULT reason=COUNTER_REGRESSION");
      } else if (status == pz::CounterStatus::ImplausibleJump) {
        Serial.println("PZEM_STATUS status=FAULT reason=ENERGY_JUMP");
      } else {
        pzemDiagnosticStaleReported = false;
        Serial.printf("PZEM_STATUS status=VALID voltage_mv=%lu current_ma=%lu power_mw=%lu energy_wh=%lu\n",
                      (unsigned long)measured.mv, (unsigned long)measured.ma,
                      (unsigned long)measured.mw, (unsigned long)measured.wh);
        printPzemValidTiming(rx);
      }
    }
  }
  const uint32_t lastGood = meterMonitor.initialized ? meterMonitor.previousAt : pzemDiagnosticStarted;
  if (meterMonitor.stale(now, lastGood, 3000) && !pzemDiagnosticStaleReported) {
    Serial.println("PZEM_STATUS status=STALE reason=NO_RECENT_VALID_SAMPLE");
    pzemDiagnosticStaleReported = true;
  }
  delay(2);
  return;
#endif
#if GPAWA_RELAY_DIAGNOSTIC
  relayDiagnosticTick();
  delay(5);
  return;
#endif
#if GPAWA_WIFI_TEST
  wifiCheckLoop();
  return;
#endif
  if (diagnostic) {
    if (millis() - lastSample >= 1000) {
      lastSample = millis();
      char a[32];
      if (sample()) {
        snprintf(a, sizeof a, "%lu V  %lu W", (unsigned long)(measured.mv / 1000), (unsigned long)(measured.mw / 1000));
        row(0, a);
        snprintf(a, sizeof a, "%lu Wh total", (unsigned long)measured.wh);
        row(1, a);
        Serial.printf("PZEM: %lu mV, %lu mA, %lu mW, %lu Wh\n", (unsigned long)measured.mv, (unsigned long)measured.ma, (unsigned long)measured.mw, (unsigned long)measured.wh);
      } else {
        row(0, "PZEM read only");
        row(1, "No valid reading");
      }
    }
    delay(2);
    return;
  }
  if (startupBeepPending) {
    beep(2);
    startupBeepPending = false;
  }
  if (watchdogReady) esp_task_wdt_reset();
  tickSound();
  if (!configured || !storageOK || fatal) {
    draw();
    delay(3);
    return;
  }
  meterTick();
  if (fatal) {
    draw();
    return;
  }
#if !GPAWA_USB_EXERCISE
  handleReply();
  if (fatal) {
    draw();
    return;
  }
  if (WiFi.status() != WL_CONNECTED) {
    if (sessionReady || outputAuthorized) inhibitForRecovery();
    sessionReady = false;
    if (millis() - lastWifiAttempt >= 15000) {
      lastWifiAttempt = millis();
      WiFi.reconnect();
    }
  } else if (clockValid() && !busy && (int32_t)(millis() - nextNetwork) >= 0) {
    if (telemetryOutbox[0]) sendPendingTelemetry(); // Its original boot still owns the sequence.
    else if (!sessionReady) sendSession();
    else if (state.ackPending) sendAck();
    else if (migrationPresent && measurementMigration.stage == MIGRATION_INTENT) sendMeasurementPrepare();
    else if (migrationPresent && measurementMigration.stage == MIGRATION_PREPARED) sendMeasurementCommit();
    else if (GPAWA_AUTH_CREDIT_ONLY) {
      if (millis() - lastSession >= hw::TELEMETRY_MS) sendSession();
    } else if (serverBaselineReady &&
               ((recoveryRequired && (!faultPosted || sensorOK)) || creditCommandPending ||
                millis() - lastTelemetry >= hw::TELEMETRY_MS)) sendTelemetry();
  }
#endif
  handleKey();
  outputTick();
  draw();
  delay(2);
}
