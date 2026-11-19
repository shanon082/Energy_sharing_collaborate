#include "../GpawaAC/MeterCore.h"
#include "../GpawaAC/PzemFrame.h"
#include <cassert>
#include <cstdio>
using namespace gpawa;
int main(){
 State s{};s.magic=MAGIC;s.version=VERSION;s.bindingEpoch=1;strcpy(s.deviceId,"00000000-0000-4000-8000-000000000001");strcpy(s.storageId,"00000000-0000-4000-8000-000000000002");strcpy(s.meterNumber,"00000000001");
 assert(observe(s,1200)==Reading::First);seal(s);assert(valid(s));
 Command c{};c.sequence=1;c.creditWh=5000;strcpy(c.id,"00000000-0000-4000-8000-000000000003");memset(c.digest,'a',64);strcpy(c.canonical,"test-command");auto rec="00000000-0000-4000-8000-000000000004";auto at="2026-11-11T15:00:00Z";
 assert(apply(s,c,rec,at)==Apply::New);State durable=s;
 assert(bootRecover(s));assert(s.ackPending&&s.applicationCounter==1);assert(apply(s,c,rec,at)==Apply::Duplicate);assert(acknowledge(s,c.id,rec));
 assert(observe(s,1230)==Reading::Advanced);assert(s.availableUWh==4970*UWH_PER_WH);
 // Power cuts BEFORE next journal checkpoint. Meter's independent counter survives.
 s=durable;assert(bootRecover(s));assert(observe(s,1230)==Reading::Advanced);assert(s.availableUWh==4970*UWH_PER_WH);
 assert(observe(s,1230)==Reading::Same);assert(s.availableUWh==4970*UWH_PER_WH);
 assert(observe(s,6202)==Reading::Advanced);assert(s.availableUWh==0);seal(s);assert(bootRecover(s));assert(s.availableUWh==0);
 assert(observe(s,6199)==Reading::Fault);assert(s.hold);seal(s);assert(bootRecover(s));assert(observe(s,6203)==Reading::Fault);
 s.crc^=1;assert(!bootRecover(s));
 uint8_t b[25]={0xf8,4,20};auto reg=[&](int i,int v){b[3+2*i]=v>>8;b[4+2*i]=v;};reg(0,2300);reg(1,500);reg(3,1150);reg(5,12);reg(6,1);reg(7,500);reg(8,100);auto crc=pz::crc(b,23);b[23]=crc;b[24]=crc>>8;pz::Reading r{};assert(pz::decode(b,25,0xf8,r)&&r.wh==65548&&r.mv==230000&&r.ma==500&&r.mw==115000);b[11]^=1;assert(!pz::decode(b,25,0xf8,r));assert(!pz::decode(b,24,0xf8,r));
 puts("PASS: persistent credit, duplicate grant, replayed readings, rollback/zero, CRC and PZEM frames");
}
