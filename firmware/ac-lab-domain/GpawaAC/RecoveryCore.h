#pragma once
#include <stdint.h>

namespace gpawa {
constexpr char RECOVERY_PROTOCOL[] = "GPAWA_RECOVERY_V1";

// The server evaluates the lease after this request left the loop. Anchoring
// to enqueue time conservatively charges all queue and network delay to it.
inline bool leaseLiveAt(uint32_t now, uint32_t sentAt, uint32_t seconds) {
  return seconds && seconds <= 90 && (uint32_t)(now - sentAt) < seconds * 1000UL;
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
