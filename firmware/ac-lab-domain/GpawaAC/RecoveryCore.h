#pragma once
#include <stdint.h>
#include "MeterCore.h"

namespace gpawa {
constexpr char RECOVERY_PROTOCOL[] = "GPAWA_RECOVERY_V1";

// The server evaluates the lease after this request left the loop. Anchoring
// to enqueue time conservatively charges all queue and network delay to it.
inline bool leaseLiveAt(uint32_t now, uint32_t sentAt, uint32_t seconds) {
  return seconds && seconds <= 90 && (uint32_t)(now - sentAt) < seconds * 1000UL;
}

struct OfflineApproval {
  char deviceId[37];
  char storageId[37];
  char meterNumber[12];
  uint32_t bindingEpoch;
  uint32_t confirmedCommand;
  uint32_t checkpointWh;
  uint8_t environment;
  uint8_t relayActiveLevel;
  uint32_t crc;
};

inline OfflineApproval offlineApprovalFor(const State& state, uint8_t relayActiveLevel) {
  OfflineApproval approval{};
  memcpy(approval.deviceId, state.deviceId, sizeof approval.deviceId);
  memcpy(approval.storageId, state.storageId, sizeof approval.storageId);
  memcpy(approval.meterNumber, state.meterNumber, sizeof approval.meterNumber);
  approval.bindingEpoch = state.bindingEpoch;
  approval.confirmedCommand = state.applicationCounter;
  approval.checkpointWh = state.meterWh;
  approval.environment = state.reservedBytes[1];
  approval.relayActiveLevel = relayActiveLevel;
  approval.crc = crc32(&approval, offsetof(OfflineApproval, crc));
  return approval;
}

inline bool matchesOfflineApproval(const OfflineApproval& approval, const State& state, uint8_t relayActiveLevel) {
  return approval.crc == crc32(&approval, offsetof(OfflineApproval, crc)) &&
         state.hasMeter && !measurementPaused(state) && state.reservedBytes[0] &&
         approval.bindingEpoch == state.bindingEpoch && approval.environment == state.reservedBytes[1] &&
         approval.relayActiveLevel == relayActiveLevel && approval.confirmedCommand <= state.applicationCounter &&
         approval.checkpointWh <= state.meterWh &&
         !memcmp(approval.deviceId, state.deviceId, sizeof approval.deviceId) &&
         !memcmp(approval.storageId, state.storageId, sizeof approval.storageId) &&
         !memcmp(approval.meterNumber, state.meterNumber, sizeof approval.meterNumber);
}

constexpr uint32_t METER_CHECKPOINT_WH = 32;
// The reviewed offline installation drops the load on controller power loss.
// Allow the unsaved checkpoint slice and the last three seconds of readings
// before cutoff, plus the meter's whole-Wh resolution. Larger jumps need review.
constexpr uint32_t OFFLINE_RESTART_LIMIT_WH = METER_CHECKPOINT_WH + (26000UL * 3 + 3599) / 3600 + 2;
inline bool offlineCounterRestorable(uint32_t checkpointWh, uint32_t actualWh) {
  return actualWh >= checkpointWh && actualWh - checkpointWh <= OFFLINE_RESTART_LIMIT_WH;
}

struct OutputConditions {
  bool creditOnly, profileEnabled, storageReady, fatal, hold;
  bool migrating, baselineReady, sensorReady, hasCredit, ackPending;
  bool recoveryPending, sessionReady, networkReady, clockReady, leaseLive;
  bool offlineApproved = false;
};

inline const char* outputInhibit(const OutputConditions& state) {
  if (state.creditOnly) return "AUTH_CREDIT_ONLY";
  if (!state.profileEnabled) return "OUTPUT_NOT_COMMISSIONED";
  if (!state.storageReady) return "STORAGE_UNAVAILABLE";
  if (state.fatal) return "FAULT_LATCHED";
  if (state.hold) return "METER_HOLD";
  if (state.migrating) return "BASELINE_MIGRATION";
  if (!state.baselineReady) return "NO_METER_BASELINE";
  if (!state.sensorReady) return "SENSOR_NOT_READY";
  if (!state.hasCredit) return "CREDIT_EMPTY";
  if (state.ackPending) return "ACK_PENDING";
  if (state.offlineApproved) return nullptr;
  if (state.recoveryPending) return "METER_RECOVERY_PENDING";
  if (!state.sessionReady) return "SESSION_NOT_READY";
  if (!state.networkReady) return "NETWORK_OFFLINE";
  if (!state.clockReady) return "CLOCK_UNAVAILABLE";
  if (!state.leaseLive) return "OUTPUT_NOT_AUTHORIZED";
  return nullptr;
}

enum class BaselineSource : uint8_t { Paused = 0, Fresh = 1, Legacy = 2 };
inline const char* baselineSourceName(BaselineSource source) {
  switch (source) {
    case BaselineSource::Paused: return "AUTH_CREDIT_ONLY_V3";
    case BaselineSource::Fresh: return "FRESH_METERED";
    case BaselineSource::Legacy: return "LEGACY_METERED";
  }
  return nullptr;
}
}
