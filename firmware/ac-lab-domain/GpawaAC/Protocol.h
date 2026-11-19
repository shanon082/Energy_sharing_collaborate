#pragma once
#include <ArduinoJson.h>
#include "MeterCore.h"
namespace gpawa {
inline bool matchingIdentity(JsonVariantConst j, const gpawa::State& state) {
  return accountingEnvironment(state) && state.reservedBytes[1] != 3 && j["protocol"].is<const char*>() && !strcmp(j["protocol"], deviceProtocol(state)) && j["device_id"].is<const char*>() && !strcmp(j["device_id"], state.deviceId) && j["meter_number"].is<const char*>() && !strcmp(j["meter_number"], state.meterNumber) && j["storage_id"].is<const char*>() && !strcmp(j["storage_id"], state.storageId) && j["binding_epoch"].is<uint32_t>() && j["binding_epoch"].as<uint32_t>() == state.bindingEpoch && j["environment"].is<const char*>() && !strcmp(j["environment"], accountingEnvironment(state)) && j["hardware_class"].is<const char*>() && !strcmp(j["hardware_class"], "AC_LAB");
}
inline bool parseCreditCommand(JsonVariantConst row, const gpawa::State& state, gpawa::Command& out, void (*sha)(const uint8_t*, size_t, uint8_t*)) {
  if (!row.is<JsonObjectConst>() || row.size() != 14 || !matchingIdentity(row, state) || !row["type"].is<const char*>() || strcmp(row["type"], "AC_LAB_CREDIT") || !row["command_id"].is<const char*>() || !gpawa::uuid(row["command_id"]) || !row["command_sequence"].is<uint32_t>() || !row["command_sequence"].as<uint32_t>() || !row["credit_wh"].is<uint64_t>() || !row["credit_wh"].as<uint64_t>() || row["credit_wh"].as<uint64_t>() > gpawa::MAX_CREDIT_WH || row["credit_wh"].as<uint64_t>() % 10 || !row["allocation_id"].is<uint64_t>() || !row["delivery_id"].is<uint64_t>() || !row["allocation_id"].as<uint64_t>() || !row["delivery_id"].as<uint64_t>() || row["allocation_id"].as<uint64_t>() > 9007199254740991ULL || row["delivery_id"].as<uint64_t>() > 9007199254740991ULL || !row["payload_digest"].is<const char*>() || strlen(row["payload_digest"]) != 64) return false;
  out = {};
  strcpy(out.id, row["command_id"]);
  strcpy(out.digest, row["payload_digest"]);
  out.sequence = row["command_sequence"];
  out.creditWh = row["credit_wh"];
  // Insert keys in lexical order. Fixed ASCII identifiers and integers only.
  // Matches Python json.dumps(fields,sort_keys=True,separators=(',',':')).
  JsonDocument canon;
  const char* keys[] = { "allocation_id", "binding_epoch", "command_id", "command_sequence", "credit_wh", "delivery_id",
                         "device_id", "environment", "hardware_class", "meter_number", "protocol", "storage_id", "type" };
  for (auto key : keys) canon[key] = row[key];
  if (measureJson(canon) >= sizeof out.canonical) return false;
  serializeJson(canon, out.canonical, sizeof out.canonical);
  uint8_t hash[32];
  sha((const uint8_t*)out.canonical, strlen(out.canonical), hash);
  char hex[65];
  for (int i = 0; i < 32; ++i) snprintf(hex + 2 * i, 3, "%02x", hash[i]);
  return !strcmp(hex, out.digest);
}
}
