#include "../GpawaAC/MeterCore.h"
#include "../GpawaAC/PzemFrame.h"
#include "../GpawaAC/RecoveryCore.h"
#include <cassert>
#include <cstdio>
using namespace gpawa;
static void setReg(uint8_t* bytes, int index, uint32_t value) {
 bytes[3+2*index]=uint8_t(value>>8);bytes[4+2*index]=uint8_t(value);
}
static void setWide(uint8_t* bytes, int lowIndex, uint32_t value) {
 setReg(bytes,lowIndex,value);setReg(bytes,lowIndex+1,value>>16);
}
static void finishFrame(uint8_t* bytes) {
 const uint16_t value=pz::crc(bytes,23);bytes[23]=uint8_t(value);bytes[24]=uint8_t(value>>8);
}
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
 uint8_t b[25]={0x01,4,20};
 setReg(b,0,2300);setReg(b,1,500);setReg(b,3,1150);setReg(b,5,12);setReg(b,6,1);setReg(b,7,500);setReg(b,8,100);finishFrame(b);
 pz::Reading r{};assert(pz::decode(b,25,0x01,r)&&r.wh==65548&&r.mv==230000&&r.ma==500&&r.mw==115000&&r.frequency_cHz==5000&&r.powerFactorPct==100);
 assert(pz::decodeChecked(b,24,0x01,r)==pz::DecodeError::IncompleteFrame);
 assert(pz::responseLengthError(0)==pz::DecodeError::NoResponse);
 assert(pz::responseLengthError(1)==pz::DecodeError::IncompleteFrame);
 assert(pz::responseLengthError(24)==pz::DecodeError::IncompleteFrame);
 assert(pz::responseLengthError(25)==pz::DecodeError::None);
 assert(pz::responseLengthError(26)==pz::DecodeError::ExtraBytes);
 const uint8_t requestPrefix[]={0x01,4,0,0,0,10};
 assert(pz::crc(requestPrefix,sizeof requestPrefix)==0x0d70);
 const uint8_t requestFrame[]={0x01,4,0,0,0,10,0x70,0x0d};
 assert(pz::hasRequestEcho(requestFrame,sizeof requestFrame,requestFrame));
 assert(!pz::hasRequestEcho(requestFrame,sizeof requestFrame-1,requestFrame));
 const uint8_t observedNoise[]={0xfe,0xc7,0xc0,0xc0,0xc0,0xee,0xff};
 assert(!pz::hasRequestEcho(observedNoise,sizeof observedNoise,requestFrame));
 assert(pz::decodeChecked(observedNoise,sizeof observedNoise,0x01,r)==pz::DecodeError::IncompleteFrame);
 uint8_t echoedResponse[8+25];
 memcpy(echoedResponse,requestFrame,sizeof requestFrame);
 memcpy(echoedResponse+sizeof requestFrame,b,sizeof b);
 assert(pz::hasRequestEcho(echoedResponse,sizeof echoedResponse,requestFrame));
 assert(pz::responseLengthError(sizeof echoedResponse-sizeof requestFrame)==pz::DecodeError::None);
 b[0]=0xf9;assert(pz::decodeChecked(b,25,0x01,r)==pz::DecodeError::Address);b[0]=0x01;
 b[1]=3;assert(pz::decodeChecked(b,25,0x01,r)==pz::DecodeError::Function);b[1]=4;
 b[2]=18;assert(pz::decodeChecked(b,25,0x01,r)==pz::DecodeError::ByteCount);b[2]=20;
 b[11]^=1;assert(pz::decodeChecked(b,25,0x01,r)==pz::DecodeError::Crc);b[11]^=1;
 pz::Reading unchanged{11,22,33,44,55,66};
 setReg(b,0,799);finishFrame(b);assert(pz::decodeChecked(b,25,0x01,unchanged)==pz::DecodeError::Voltage);assert(unchanged.mv==11);
 setReg(b,0,2300);setWide(b,1,100001);finishFrame(b);assert(pz::decodeChecked(b,25,0x01,r)==pz::DecodeError::Current);
 setWide(b,1,500);setWide(b,3,260001);finishFrame(b);assert(pz::decodeChecked(b,25,0x01,r)==pz::DecodeError::Power);
 setWide(b,3,42950000);finishFrame(b);assert(pz::decodeChecked(b,25,0x01,r)==pz::DecodeError::Power);
 setWide(b,3,1000);setWide(b,1,1);finishFrame(b);assert(pz::decodeChecked(b,25,0x01,r)==pz::DecodeError::ApparentPower);
 setWide(b,1,500);setWide(b,3,1150);setReg(b,7,449);finishFrame(b);assert(pz::decodeChecked(b,25,0x01,r)==pz::DecodeError::Frequency);
 setReg(b,7,500);setReg(b,8,101);finishFrame(b);assert(pz::decodeChecked(b,25,0x01,r)==pz::DecodeError::PowerFactor);
 setReg(b,8,100);setReg(b,9,1);finishFrame(b);assert(pz::decodeChecked(b,25,0x01,r)==pz::DecodeError::Alarm);

 pz::MeterMonitor monitor;
 assert(monitor.accept(1000,1000,false,0)==pz::CounterStatus::First);
 assert(monitor.accept(1005,2000,false,0)==pz::CounterStatus::Valid);
 assert(monitor.accept(1015,3000,false,0)==pz::CounterStatus::ImplausibleJump);
 assert(monitor.accept(999,3000,false,0)==pz::CounterStatus::Regression);
 assert(monitor.stale(5001,monitor.previousAt,3000));
 pz::MeterMonitor baseline;
 assert(baseline.accept(999,1000,true,1000)==pz::CounterStatus::Regression);
 assert(baseline.accept(1000,1000,true,1000)==pz::CounterStatus::First);
 assert(leaseLiveAt(4999,0,5));
 assert(!leaseLiveAt(5000,0,5));
 assert(leaseLiveAt(0,UINT32_MAX-499,1));
 assert(!leaseLiveAt(500,UINT32_MAX-499,1));
 assert(!leaseLiveAt(0,0,0)&&!leaseLiveAt(0,0,91));
 OutputConditions output{false, true, true, false, false, false, true,
                         true, true, false, true, true, true, true, false};
 assert(!strcmp(outputInhibit(output), "METER_RECOVERY_PENDING"));
 output.recoveryPending=false;
 assert(!strcmp(outputInhibit(output), "OUTPUT_NOT_AUTHORIZED"));
 output.leaseLive=leaseLiveAt(100,0,5);
 assert(!outputInhibit(output));
 output.hasCredit=false;
 assert(!strcmp(outputInhibit(output), "CREDIT_EMPTY"));
 output.ackPending=true; output.hasCredit=true;
 assert(!strcmp(outputInhibit(output), "ACK_PENDING"));
 output.ackPending=false; output.recoveryPending=true;
 assert(!strcmp(outputInhibit(output), "METER_RECOVERY_PENDING"));
 output.recoveryPending=false;
 assert(!outputInhibit(output));
 output.sensorReady=false;
 assert(!strcmp(outputInhibit(output), "SENSOR_NOT_READY"));
 output.sensorReady=true; output.leaseLive=leaseLiveAt(5000,0,5);
 assert(!strcmp(outputInhibit(output), "OUTPUT_NOT_AUTHORIZED"));
 output.leaseLive=true; output.storageReady=false;
 assert(!strcmp(outputInhibit(output), "STORAGE_UNAVAILABLE"));
 output.storageReady=true; output.profileEnabled=false;
 assert(!strcmp(outputInhibit(output), "OUTPUT_NOT_COMMISSIONED"));
 output.profileEnabled=true; output.offlineApproved=true;
 output.sessionReady=false; output.networkReady=false; output.clockReady=false;
 output.recoveryPending=true; output.leaseLive=false;
 assert(!outputInhibit(output)); // A network outage or offline reboot alone leaves the load on.
 output.ackPending=true;
 assert(!strcmp(outputInhibit(output), "ACK_PENDING"));
 output.ackPending=false; output.sensorReady=false;
 assert(!strcmp(outputInhibit(output), "SENSOR_NOT_READY"));
 output.sensorReady=true; output.offlineApproved=false;
 assert(outputInhibit(output)); // A received revocation removes the local permission.
 State saved=durable;
 assert(acknowledge(saved,c.id,rec));
 saved.reservedBytes[0]=1;
 assert(observe(saved,3180)==Reading::Advanced && saved.availableUWh==3020*UWH_PER_WH);
 seal(saved);
 const auto approval=offlineApprovalFor(saved,0);
 assert(bootRecover(saved) && matchesOfflineApproval(approval,saved,0));
 assert(offlineCounterRestorable(saved.meterWh,3200));
 assert(!offlineCounterRestorable(saved.meterWh,3179));
 assert(!offlineCounterRestorable(saved.meterWh,3300));
 assert(observe(saved,3200)==Reading::Advanced && saved.availableUWh==3000*UWH_PER_WH);
 assert(observe(saved,3200)==Reading::Same && saved.availableUWh==3000*UWH_PER_WH);
 assert(!matchesOfflineApproval(approval,saved,1));
 ++saved.bindingEpoch;
 assert(!matchesOfflineApproval(approval,saved,0));
 // Close the old epoch before applying credit. Excess measured Wh during
 // depletion may not be retroactively billed to the next command.
 State epoch=durable;
 assert(acknowledge(epoch,c.id,rec));
 assert(observe(epoch,6202)==Reading::Advanced&&epoch.availableUWh==0);
 Command topup=c; topup.id[35]='4';topup.sequence=2;topup.creditWh=10;
 assert(apply(epoch,topup,"00000000-0000-4000-8000-000000000005",at)==Apply::New);
 assert(bootRecover(epoch)&&epoch.ackPending);
 assert(observe(epoch,6203)==Reading::Advanced);
 assert(epoch.consumedUWh==5001*UWH_PER_WH&&epoch.availableUWh==9*UWH_PER_WH);
 puts("PASS: persistent credit, top-up boundary, delayed lease, strict PZEM frame/range validation, regression, jump and stale checks");
}
