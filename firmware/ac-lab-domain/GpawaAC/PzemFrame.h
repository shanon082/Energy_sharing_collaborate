#pragma once
#include <stdint.h>
#include <stddef.h>

namespace pz {
constexpr uint32_t MAX_VOLTAGE_MV = 260000;
constexpr uint32_t MAX_CURRENT_MA = 100000;
constexpr uint32_t MAX_POWER_MW = 26000000;
constexpr uint32_t MAX_POWER_W = MAX_POWER_MW / 1000;
constexpr uint32_t ENERGY_TOLERANCE_WH = 1;
constexpr size_t READ_REQUEST_BYTES = 8;
constexpr size_t READ_RESPONSE_BYTES = 25;

inline bool hasRequestEcho(const uint8_t* bytes, size_t count, const uint8_t* request) {
  if (!bytes || !request || count < READ_REQUEST_BYTES) return false;
  for (size_t i = 0; i < READ_REQUEST_BYTES; ++i)
    if (bytes[i] != request[i]) return false;
  return true;
}

inline uint16_t crc(const uint8_t* bytes, size_t count) {
  uint16_t value = 65535;
  while (count--) {
    value ^= *bytes++;
    for (int bit = 0; bit < 8; ++bit)
      value = (value & 1) ? (value >> 1) ^ 0xa001 : value >> 1;
  }
  return value;
}

struct Reading {
  uint32_t mv, ma, mw, wh, frequency_cHz, powerFactorPct;
};

enum class DecodeError : uint8_t {
  None,
  Length,
  Address,
  Function,
  ByteCount,
  Crc,
  Voltage,
  Current,
  Power,
  ApparentPower,
  Frequency,
  PowerFactor,
  Alarm,
  NoResponse,
  IncompleteFrame,
  ExtraBytes,
  Uart
};

inline const char* errorName(DecodeError error) {
  switch (error) {
    case DecodeError::None: return "OK";
    case DecodeError::Length: return "LENGTH";
    case DecodeError::Address: return "ADDRESS";
    case DecodeError::Function: return "FUNCTION";
    case DecodeError::ByteCount: return "BYTE_COUNT";
    case DecodeError::Crc: return "CRC";
    case DecodeError::Voltage: return "VOLTAGE_RANGE";
    case DecodeError::Current: return "CURRENT_RANGE";
    case DecodeError::Power: return "POWER_RANGE";
    case DecodeError::ApparentPower: return "POWER_EXCEEDS_APPARENT";
    case DecodeError::Frequency: return "FREQUENCY_RANGE";
    case DecodeError::PowerFactor: return "POWER_FACTOR_RANGE";
    case DecodeError::Alarm: return "PZEM_ALARM";
    case DecodeError::NoResponse: return "NO_RESPONSE_TIMEOUT";
    case DecodeError::IncompleteFrame: return "INCOMPLETE_FRAME";
    case DecodeError::ExtraBytes: return "EXTRA_OR_NOISY_BYTES";
    case DecodeError::Uart: return "UART_ERROR";
  }
  return "UNKNOWN";
}

inline DecodeError responseLengthError(size_t count) {
  if (!count) return DecodeError::NoResponse;
  if (count < READ_RESPONSE_BYTES) return DecodeError::IncompleteFrame;
  if (count > READ_RESPONSE_BYTES) return DecodeError::ExtraBytes;
  return DecodeError::None;
}

inline DecodeError decodeChecked(const uint8_t* bytes, size_t count, uint8_t address, Reading& out) {
  if (!bytes) return DecodeError::Length;
  const DecodeError lengthError = responseLengthError(count);
  if (lengthError != DecodeError::None) return lengthError;
  if (bytes[0] != address) return DecodeError::Address;
  if (bytes[1] != 4) return DecodeError::Function;
  if (bytes[2] != 20) return DecodeError::ByteCount;
  if (crc(bytes, READ_RESPONSE_BYTES - 2) !=
      (bytes[READ_RESPONSE_BYTES - 2] | (uint16_t(bytes[READ_RESPONSE_BYTES - 1]) << 8)))
    return DecodeError::Crc;

  auto reg = [&](int index) -> uint32_t {
    return (uint32_t(bytes[3 + index * 2]) << 8) | bytes[4 + index * 2];
  };
  const uint64_t activePowerMw = uint64_t((reg(4) << 16) | reg(3)) * 100;
  if (activePowerMw > MAX_POWER_MW) return DecodeError::Power;
  const Reading candidate = {
    reg(0) * 100,
    (reg(2) << 16) | reg(1),
    uint32_t(activePowerMw),
    (reg(6) << 16) | reg(5),
    reg(7) * 10,
    reg(8)
  };

  if (candidate.mv < 80000 || candidate.mv > MAX_VOLTAGE_MV) return DecodeError::Voltage;
  if (candidate.ma > MAX_CURRENT_MA) return DecodeError::Current;
  if (candidate.mw > MAX_POWER_MW) return DecodeError::Power;
  if (reg(7) < 450 || reg(7) > 650) return DecodeError::Frequency;
  if (reg(8) > 100) return DecodeError::PowerFactor;
  if (reg(9) != 0) return DecodeError::Alarm;
  const uint64_t apparentPowerMw = uint64_t(candidate.mv) * candidate.ma / 1000;
  if (candidate.mw > apparentPowerMw + 1000) return DecodeError::ApparentPower;

  out = candidate;
  return DecodeError::None;
}

inline bool decode(const uint8_t* bytes, size_t count, uint8_t address, Reading& out) {
  return decodeChecked(bytes, count, address, out) == DecodeError::None;
}

inline bool plausibleAdvance(uint32_t previousWh, uint32_t currentWh, uint32_t elapsedMs) {
  if (currentWh < previousWh) return false;
  const uint64_t deltaWh = uint64_t(currentWh) - previousWh;
  const uint64_t maxWh = (uint64_t(MAX_POWER_W) * elapsedMs + 3599999ULL) / 3600000ULL +
                         ENERGY_TOLERANCE_WH;
  return deltaWh <= maxWh;
}

enum class CounterStatus : uint8_t { First, Valid, Regression, ImplausibleJump };

struct MeterMonitor {
  bool initialized = false;
  uint32_t previousWh = 0;
  uint32_t previousAt = 0;

  CounterStatus accept(uint32_t readingWh, uint32_t nowMs, bool hasPersistentBaseline,
                       uint32_t persistentWh) {
    if (initialized) {
      if (readingWh < previousWh) return CounterStatus::Regression;
      if (!plausibleAdvance(previousWh, readingWh, nowMs - previousAt))
        return CounterStatus::ImplausibleJump;
      previousWh = readingWh;
      previousAt = nowMs;
      return CounterStatus::Valid;
    }
    if (hasPersistentBaseline && readingWh < persistentWh) return CounterStatus::Regression;
    initialized = true;
    previousWh = readingWh;
    previousAt = nowMs;
    return CounterStatus::First;
  }

  bool stale(uint32_t nowMs, uint32_t lastValidMs, uint32_t maxAgeMs) const {
    return !initialized || nowMs - lastValidMs > maxAgeMs;
  }
};
}
