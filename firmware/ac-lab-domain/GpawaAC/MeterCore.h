#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <limits.h>

// Pure logic shared by the ESP32 sketch and host regression tests.
namespace gpawa {
constexpr uint32_t MAGIC = 0x47505741;
constexpr uint32_t VERSION = 2;
// Same layout/NVS key; v3 marks authenticated credit without active measurement.
// A v2-only binary must reject this journal instead of debiting a stale baseline.
constexpr uint32_t CREDIT_ONLY_VERSION = 3;
constexpr uint64_t UWH_PER_WH = 1000000ULL;
constexpr uint64_t MAX_CREDIT_WH = 1000000ULL;
constexpr uint64_t MAX_TOTAL_UWH = 9000000000000000ULL;  // below JSON's 2^53
constexpr uint64_t RESERVE_UWH = UWH_PER_WH;             // 1 Wh maximum uncheckpointed slice
constexpr size_t COMMAND_JSON_BYTES = 1024;
struct Command {
  char id[37];
  char digest[65];
  uint32_t sequence;
  uint64_t creditWh;
  char canonical[COMMAND_JSON_BYTES];
};
struct State {
  uint32_t magic;
  uint32_t version;
  char deviceId[37];
  char meterNumber[12];
  char storageId[37];
  uint32_t bindingEpoch;
  uint32_t bootCounter;
  uint32_t applicationCounter;
  uint8_t ackPending;
  uint8_t reservedBytes[3];
  uint64_t creditedUWh;
  uint64_t availableUWh;
  uint64_t reservedUWh;
  uint64_t consumedUWh;
  uint64_t uncertainUWh;
  Command lastCommand;
  char receiptId[37];
  char appliedAt[25];
  uint32_t meterWh;
  uint8_t hasMeter, hold;
  uint32_t crc;
};
// Byte 1 was reserved/zero in legacy v2 UGX journals. Preserve its layout/CRC.
// New journals bind their domain explicitly; old zero remains UGX only.
inline const char* accountingEnvironment(const State& s) {
  switch (s.reservedBytes[1]) {
    case 0: case 1: return "UGX_DEMO";
    case 2: return "SANDBOX";
    case 3: return "USB_EXERCISE";
    default: return nullptr;
  }
}
inline uint8_t environmentCode(const char* name) {
  return name && !strcmp(name,"UGX_DEMO") ? 1 : name && !strcmp(name,"SANDBOX") ? 2 : name && !strcmp(name,"USB_EXERCISE") ? 3 : 255;
}
inline const char* deviceProtocol(const State& s) {
  return s.reservedBytes[1] == 2 ? "GPAWA_PZEM_V2" : s.reservedBytes[1] <= 1 ? "GPAWA_PZEM_V1" : "USB_EXERCISE_ONLY";
}
inline bool measurementPaused(const State& s) {
  return s.version == CREDIT_ONLY_VERSION && s.reservedBytes[2] == 1;
}
inline const char* measurementState(const State& s) {
  return !s.hasMeter ? "UNINITIALIZED" : measurementPaused(s) ? "SUSPENDED" : "BASELINED";
}
inline bool creditTransportReady(const State& s, bool creditOnly, bool sensorReady) {
  return !s.hold && (creditOnly || (!measurementPaused(s) && s.hasMeter && sensorReady));
}
inline uint32_t crc32(const void* p, size_t n) {
  const uint8_t* b = static_cast<const uint8_t*>(p);
  uint32_t c = 0xffffffffU;
  for (size_t i = 0; i < n; ++i) {
    c ^= b[i];
    for (int j = 0; j < 8; ++j) c = (c >> 1) ^ ((c & 1) ? 0xedb88320U : 0);
  }
  return ~c;
}
inline void seal(State& s) {
  s.crc = crc32(&s, offsetof(State, crc));
}
inline bool digits(const char* p, size_t count) {
  if (!p || strlen(p) != count) return false;
  for (size_t i = 0; i < count; ++i)
    if (p[i] < '0' || p[i] > '9') return false;
  return true;
}
inline bool uuid(const char* p) {
  if (!p || strlen(p) != 36) return false;
  for (size_t i = 0; i < 36; ++i) {
    if (i == 8 || i == 13 || i == 18 || i == 23) {
      if (p[i] != '-') return false;
    } else if (!((p[i] >= '0' && p[i] <= '9') || (p[i] >= 'a' && p[i] <= 'f'))) return false;
  }
  return true;
}
inline bool terminated(const char* p, size_t size) {
  return memchr(p, 0, size) != nullptr;
}
inline bool invariant(const State& s) {
  if (s.creditedUWh > MAX_TOTAL_UWH || s.availableUWh > s.creditedUWh || s.reservedUWh > RESERVE_UWH || s.consumedUWh > s.creditedUWh || s.uncertainUWh > s.creditedUWh || s.ackPending > 1 || s.hold > 1 || s.hasMeter > 1 || s.reservedUWh || s.uncertainUWh) return false;
  return s.creditedUWh == s.availableUWh + s.reservedUWh + s.consumedUWh + s.uncertainUWh;
}
inline bool valid(const State& s) {
  const bool versionOK = (s.version == VERSION && s.reservedBytes[2] == 0) || measurementPaused(s);
  if (!accountingEnvironment(s) || s.magic != MAGIC || !versionOK || s.crc != crc32(&s, offsetof(State, crc)) || !invariant(s)) return false;
  if (!terminated(s.deviceId, sizeof s.deviceId) || !uuid(s.deviceId) || !terminated(s.storageId, sizeof s.storageId) || !uuid(s.storageId) || !terminated(s.meterNumber, sizeof s.meterNumber) || !digits(s.meterNumber, 11) || s.bindingEpoch == 0) return false;
  if (s.applicationCounter) {
    if (!terminated(s.lastCommand.id, sizeof s.lastCommand.id) || !uuid(s.lastCommand.id) || !terminated(s.receiptId, sizeof s.receiptId) || !uuid(s.receiptId) || !terminated(s.lastCommand.digest, sizeof s.lastCommand.digest) || strlen(s.lastCommand.digest) != 64 || !terminated(s.lastCommand.canonical, sizeof s.lastCommand.canonical) || !terminated(s.appliedAt, sizeof s.appliedAt) || s.lastCommand.sequence != s.applicationCounter) return false;
  } else if (s.ackPending || s.creditedUWh) return false;
  return true;
}
inline bool enterAuthenticatedCreditOnly(State& s) {
  if (!valid(s) || s.hold || strcmp(accountingEnvironment(s), "SANDBOX")) return false;
  // Do not change hasMeter, baseline, identity, credit, receipts or counters.
  s.version = CREDIT_ONLY_VERSION;
  s.reservedBytes[2] = 1;
  seal(s);
  return true;
}
inline bool bootRecover(State& s) {
  if (!valid(s) || s.bootCounter == UINT32_MAX) return false;
  // A crash cannot silently return a previously reserved slice to spendable credit.
  s.uncertainUWh += s.reservedUWh;
  s.reservedUWh = 0;
  ++s.bootCounter;
  seal(s);
  return invariant(s);
}
enum class Apply { New,
                   Duplicate,
                   Conflict,
                   Busy,
                   Invalid };
inline Apply apply(State& s, const Command& c, const char* receipt, const char* at) {
  if (!terminated(c.id, sizeof c.id) || !uuid(c.id) || !terminated(c.digest, sizeof c.digest) || strlen(c.digest) != 64 || !terminated(c.canonical, sizeof c.canonical) || !c.canonical[0] || !uuid(receipt) || !at || strlen(at) != 20 || !c.creditWh || c.creditWh > MAX_CREDIT_WH || c.creditWh % 10) return Apply::Invalid;
  if (s.applicationCounter && !strcmp(s.lastCommand.id, c.id)) {
    return c.sequence == s.lastCommand.sequence && c.creditWh == s.lastCommand.creditWh && !strcmp(c.digest, s.lastCommand.digest) && !strcmp(c.canonical, s.lastCommand.canonical)
             ? Apply::Duplicate
             : Apply::Conflict;
  }
  if (s.ackPending) return Apply::Busy;
  if (s.applicationCounter == UINT32_MAX || c.sequence != s.applicationCounter + 1) return Apply::Conflict;
  uint64_t add = c.creditWh * UWH_PER_WH;
  if (add > MAX_TOTAL_UWH - s.creditedUWh) return Apply::Invalid;
  s.creditedUWh += add;
  s.availableUWh += add;
  s.lastCommand = c;
  s.applicationCounter = c.sequence;
  s.ackPending = 1;
  memcpy(s.receiptId, receipt, 37);
  memset(s.appliedAt, 0, sizeof s.appliedAt);
  memcpy(s.appliedAt, at, 20);
  seal(s);
  return Apply::New;
}
inline bool acknowledge(State& s, const char* command, const char* receipt) {
  if (!s.applicationCounter || strcmp(s.lastCommand.id, command) || strcmp(s.receiptId, receipt)) return false;
  s.ackPending = 0;
  seal(s);
  return true;
}

// Account for differences, never for the full meter lifetime reading.
enum class Reading { Same, Advanced, First, Fault, BaselineRequired };
inline Reading observe(State &s, uint32_t reading){
 if(s.hold) return Reading::Fault;
 if(measurementPaused(s)) return Reading::BaselineRequired;
 if(!s.hasMeter){
   if(s.applicationCounter || s.availableUWh || s.consumedUWh){s.hold=1;return Reading::Fault;}
   s.hasMeter=1;s.meterWh=reading;return Reading::First;
 }
 if(reading<s.meterWh){s.hold=1;return Reading::Fault;}
 const uint64_t delta=uint64_t(reading-s.meterWh)*UWH_PER_WH;
 if(!delta)return Reading::Same;
 s.meterWh=reading;
 const uint64_t billed=delta<s.availableUWh?delta:s.availableUWh;
 s.availableUWh-=billed;s.consumedUWh+=billed;
 return Reading::Advanced;
}
}
