#include "../GpawaAC/Protocol.h"
#include "protocol-vectors.h"
#include <cassert>
#include <cstdio>

// Fixed Python SHA256 vectors test canonical serialization across languages.
// Firmware uses mbedtls_sha256; this does not claim to test the crypto primitive.
void vectorDigest(const uint8_t* input, size_t count, uint8_t* output) {
  memset(output, 0, 32);
  for (const auto& row : vectors) {
    if (strlen(row.canonical) != count || memcmp(input, row.canonical, count)) continue;
    for (int i=0; i<32; ++i) { unsigned byte; sscanf(row.digest+2*i, "%2x", &byte); output[i]=uint8_t(byte); }
  }
}
gpawa::State initial(uint8_t domain) {
  gpawa::State state{}; state.magic=gpawa::MAGIC; state.version=gpawa::VERSION; state.bindingEpoch=1;
  strcpy(state.deviceId,"00000000-0000-4000-8000-000000000001");
  strcpy(state.storageId,"00000000-0000-4000-8000-000000000002"); strcpy(state.meterNumber,"00000001234");
  state.reservedBytes[1]=domain; gpawa::seal(state); return state;
}
int main() {
  for (const auto& row: vectors) {
    auto state=initial(gpawa::environmentCode(row.environment));
    assert(gpawa::valid(state));
    JsonDocument document; assert(!deserializeJson(document,row.payload));
    gpawa::Command command{};
    assert(gpawa::parseCreditCommand(document.as<JsonVariantConst>(),state,command,vectorDigest));
    assert(!strcmp(command.canonical,row.canonical));
    assert(gpawa::apply(state,command,"00000000-0000-4000-8000-000000000004","2026-11-18T10:00:00Z")==gpawa::Apply::New);
    gpawa::State durable{}; memcpy(&durable,&state,sizeof state);
    assert(gpawa::bootRecover(durable)); assert(durable.ackPending);
    assert(gpawa::apply(durable,command,"00000000-0000-4000-8000-000000000004","2026-11-18T10:00:00Z")==gpawa::Apply::Duplicate);
    assert(durable.creditedUWh==2000*gpawa::UWH_PER_WH);
    assert(!strcmp(gpawa::accountingEnvironment(durable),row.environment));
    assert(gpawa::acknowledge(durable,command.id,durable.receiptId));
    assert(gpawa::bootRecover(durable)); assert(!durable.ackPending);
    document["environment"]=!strcmp(row.environment,"SANDBOX")?"UGX_DEMO":"SANDBOX";
    assert(!gpawa::parseCreditCommand(document.as<JsonVariantConst>(),durable,command,vectorDigest));
  }
  auto sandbox=initial(2); JsonDocument doc; deserializeJson(doc,vectors[1].payload);
  doc["protocol"]="GPAWA_PZEM_V1"; gpawa::Command command{};
  assert(!gpawa::parseCreditCommand(doc.as<JsonVariantConst>(),sandbox,command,vectorDigest));
  deserializeJson(doc,vectors[1].payload); doc["meter_number"]="00000009999";
  assert(!gpawa::parseCreditCommand(doc.as<JsonVariantConst>(),sandbox,command,vectorDigest));
  auto legacy=initial(0); assert(gpawa::valid(legacy)); assert(!strcmp(gpawa::accountingEnvironment(legacy),"UGX_DEMO"));
  auto exercise=initial(3); assert(gpawa::valid(exercise)); deserializeJson(doc,vectors[1].payload);
  assert(!gpawa::matchingIdentity(doc.as<JsonVariantConst>(),exercise));
  auto invalid=initial(255); assert(!gpawa::valid(invalid));
  puts("PASS: V1/V2 exact command digest vectors, domain/meter/protocol isolation, journal reboot, lost ACK and no duplicate credit");
}
