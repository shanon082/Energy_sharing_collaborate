#include "../GpawaAC/Protocol.h"
#include "protocol-vectors.h"
#include <cassert>
#include <cstdio>

void vectorDigest(const uint8_t* input, size_t count, uint8_t* output) {
  memset(output,0,32);
  for(const auto& row:vectors){
    if(strlen(row.canonical)!=count || memcmp(input,row.canonical,count))continue;
    for(int i=0;i<32;++i){unsigned byte;sscanf(row.digest+2*i,"%2x",&byte);output[i]=uint8_t(byte);}
  }
}
gpawa::State initial(){
  gpawa::State s{};s.magic=gpawa::MAGIC;s.version=gpawa::VERSION;s.bindingEpoch=1;
  strcpy(s.deviceId,"00000000-0000-4000-8000-000000000001");
  strcpy(s.storageId,"00000000-0000-4000-8000-000000000002");strcpy(s.meterNumber,"00000001234");
  s.reservedBytes[0]=1;s.reservedBytes[1]=2;gpawa::seal(s);return s;
}
int main(){
  using namespace gpawa;
  State s=initial();assert(valid(s));
  State held=s;held.hold=1;seal(held);const State heldBefore=held;
  assert(!enterAuthenticatedCreditOnly(held));assert(!memcmp(&heldBefore,&held,sizeof held));
  assert(!creditTransportReady(s,false,false));
  assert(enterAuthenticatedCreditOnly(s));assert(valid(s));
  assert(s.version==3 && s.hasMeter==0 && s.meterWh==0);
  assert(!strcmp(measurementState(s),"UNINITIALIZED"));
  assert(creditTransportReady(s,true,false));
  assert(!creditTransportReady(s,false,true));
  // Read the actual V2 wire command. A wrong meter cannot be accepted.
  JsonDocument payload;assert(!deserializeJson(payload,vectors[1].payload));
  Command command{};assert(parseCreditCommand(payload.as<JsonVariantConst>(),s,command,vectorDigest));
  payload["meter_number"]="00000009999";
  assert(!parseCreditCommand(payload.as<JsonVariantConst>(),s,command,vectorDigest));
  assert(!deserializeJson(payload,vectors[1].payload));
  assert(parseCreditCommand(payload.as<JsonVariantConst>(),s,command,vectorDigest));
  const char* receipt="00000000-0000-4000-8000-000000000004";
  const char* at="2026-11-19T10:00:00Z";
  assert(apply(s,command,receipt,at)==Apply::New);assert(valid(s));
  const auto credit=s.creditedUWh;
  assert(credit==2000*UWH_PER_WH && s.availableUWh==credit && s.consumedUWh==0);
  assert(apply(s,command,receipt,at)==Apply::Duplicate);assert(s.creditedUWh==credit);
  // NVS snapshot/readback before ACK; boot recovery must keep the same receipt.
  State stored{};memcpy(&stored,&s,sizeof s);assert(bootRecover(stored));
  assert(stored.ackPending && !strcmp(stored.receiptId,receipt));
  assert(creditTransportReady(stored,true,false));
  assert(apply(stored,command,receipt,at)==Apply::Duplicate);assert(stored.creditedUWh==credit);
  assert(acknowledge(stored,command.id,receipt));assert(valid(stored));
  assert(acknowledge(stored,command.id,receipt));
  assert(bootRecover(stored));assert(!stored.ackPending && stored.applicationCounter==1);
  assert(stored.creditedUWh==credit && stored.consumedUWh==0 && !stored.hasMeter);
  // Sensor return cannot treat a lifetime total as usage or create a baseline.
  const State before=stored;
  assert(observe(stored,7654321)==Reading::BaselineRequired);
  assert(!memcmp(&before,&stored,sizeof stored));
  assert(enterAuthenticatedCreditOnly(stored));assert(creditTransportReady(stored,true,false));
  // Existing baselined credit/debit history also survives entering the mode.
  State old=initial();assert(observe(old,15000)==Reading::First);seal(old);
  assert(apply(old,command,receipt,at)==Apply::New);
  assert(observe(old,15003)==Reading::Advanced);seal(old);
  const State legacy=old;assert(enterAuthenticatedCreditOnly(old));
  assert(old.hasMeter && old.meterWh==legacy.meterWh && old.applicationCounter==legacy.applicationCounter);
  assert(old.creditedUWh==legacy.creditedUWh && old.availableUWh==legacy.availableUWh && old.consumedUWh==legacy.consumedUWh);
  State expected=legacy;expected.version=CREDIT_ONLY_VERSION;expected.reservedBytes[2]=1;seal(expected);
  assert(!memcmp(&expected,&old,sizeof old));
  assert(!strcmp(measurementState(old),"SUSPENDED"));
  assert(observe(old,18000)==Reading::BaselineRequired);assert(old.availableUWh==legacy.availableUWh);
  assert(old.version!=VERSION); // Old v2-only firmware rejects the new journal.
  old.reservedBytes[2]=0;seal(old);assert(!valid(old)); // No implicit resume by clearing a bit.
  puts("PASS: sensor-free authenticated credit, exact V2 binding, duplicate/restart/ACK recovery, preserved journals and blocked baseline activation");
}
