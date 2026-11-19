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
#include "MeterCore.h"
#include "Protocol.h"
#include "PzemFrame.h"
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
char keypadMap[4][4]={{'1','2','3','A'},{'4','5','6','B'},{'7','8','9','C'},{'*','0','#','D'}};
byte rowPins[4]={4,5,6,7}, colPins[4]={10,11,12,13};
Keypad keypad(makeKeymap(keypadMap),rowPins,colPins,4,4);
bool displayOK=false,configured=false,storageOK=false,sensorOK=false,sessionReady=false,loadRequested=false,outputOn=false,busy=false,fatal=false,watchdogReady=false;
char message[48]="Starting",tokenDigits[16]={},bootId[37]={};
uint8_t tokenLength=0, pulses=0, good=0;
uint32_t lastSample=0,lastUi=0,lastTelemetry=0,lastWifiAttempt=0,nextNetwork=0,telemetrySequence=0,retryDelay=2000,showAt=0,soundAt=0,alarmAt=0,savedWh=0;
uint32_t lastSession=0;
bool sounding=false,emptySeen=false,diagnostic=false;
pz::Reading measured{};
enum class JobKind:uint8_t {Session,Redeem,Ack,Telemetry};
struct Request {JobKind kind;char body[2304];};
struct Reply {JobKind kind;int status;char body[4096];};
QueueHandle_t requestQueue=nullptr,replyQueue=nullptr;
void say(const char* msg){snprintf(message,sizeof message,"%s",msg);showAt=millis();}
void eraseToken(){memset(tokenDigits,0,sizeof tokenDigits);tokenLength=0;}
void switchOff(){
#if GPAWA_COMMISSIONED_OUTPUT && !GPAWA_USB_EXERCISE
 digitalWrite(hw::SWITCH_PIN,LOW); // active-HIGH at MCU, including external driver
#endif
 outputOn=false;
}
void beep(uint8_t n){pulses=n;sounding=true;soundAt=millis();digitalWrite(hw::BEEP,HIGH);}
void tickSound(){
 if(pulses && millis()-soundAt>=90){soundAt=millis();if(sounding){digitalWrite(hw::BEEP,LOW);sounding=false;--pulses;}else {digitalWrite(hw::BEEP,HIGH);sounding=true;}}
 bool empty=storageOK&&state.hasMeter&&!fatal&&!state.availableUWh;
 if(empty&&(!emptySeen||millis()-alarmAt>=60000)){if(!pulses){beep(1);alarmAt=millis();emptySeen=true;}}
 if(!empty)emptySeen=false;
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
    latch("Invalid state - service");
    return false;
  }
  if (prefs.putBytes("state", &next, sizeof next) != sizeof next) {
    latch("Storage write failed");
    return false;
  }
  State verify{};
  if (prefs.getBytesLength("state") != sizeof verify || prefs.getBytes("state", &verify, sizeof verify) != sizeof verify || memcmp(&next, &verify, sizeof next) || !valid(verify)) {
    latch("Storage verify failed");
    return false;
  }
  state = next; savedWh=next.meterWh;
  return true;
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
    default: return "/prototype-device/v1/telemetry/";
  }
}
void networkWorker(void*) {
  Request req{};
  for (;;) {
    if (xQueueReceive(requestQueue, &req, portMAX_DELAY) != pdTRUE) continue;
    Reply response{};
    response.kind = req.kind;
    response.status = -1;
    if (WiFi.status() == WL_CONNECTED && clockValid()) {
      WiFiClientSecure tls;
      tls.setCACert(cfg::ROOT_CA);
      tls.setHandshakeTimeout(8);
      HTTPClient http;
      http.setConnectTimeout(5000);
      http.setTimeout(5000);
      http.setFollowRedirects(HTTPC_DISABLE_FOLLOW_REDIRECTS);
      if (http.begin(tls, String(cfg::API_BASE) + route(req.kind))) {
        http.addHeader("Content-Type", "application/json");
        http.addHeader("X-Device-Id", cfg::DEVICE_ID);
        http.addHeader("X-Device-Token", cfg::DEVICE_SECRET);
        response.status = http.POST((uint8_t*)req.body, strlen(req.body));
        if (response.status > 0) {
          BoundedBody body;
          if (http.getSize() > 4095 || http.writeToStream(&body) < 0 || body.overflow) response.status = -2;
          else memcpy(response.body, body.value, body.count + 1);
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
bool enqueue(JobKind kind, JsonDocument& doc) {
  if (busy || !requestQueue || WiFi.status() != WL_CONNECTED || !clockValid()) return false;
  Request r{};
  r.kind = kind;
  if (measureJson(doc) >= sizeof r.body) {
    latch("Request too large");
    return false;
  }
  serializeJson(doc, r.body, sizeof r.body);
  if (xQueueSend(requestQueue, &r, 0) != pdTRUE) return false;
  volatile char* p = r.body;
  for (size_t i = 0; i < sizeof r.body; ++i) p[i] = 0;
  busy = true;
  return true;
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
bool matching(JsonVariantConst j) {
  return matchingIdentity(j, state);
}

void sendSession() {
  JsonDocument j;
  identity(j);
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
    latch("Receipt corrupt - service");
    return;
  }
  j["allocation_id"] = original["allocation_id"];
  j["delivery_id"] = original["delivery_id"];
  enqueue(JobKind::Ack, j);
}
void sendTelemetry() {
  // There is no PZEM evidence in this mode: never send fabricated zero readings.
  if (GPAWA_AUTH_CREDIT_ONLY) return;
  if (telemetrySequence == UINT32_MAX) {
    latch("Sequence exhausted");
    return;
  }
  JsonDocument j;
  identity(j);
  j["boot_id"] = bootId;
  j["boot_counter"] = state.bootCounter;
  j["sequence"] = ++telemetrySequence;
  char at[25];
  timestamp(at, sizeof at);
  j["measured_at"] = at;
  j["clock_status"] = "NETWORK_TIME";
  j["application_counter"] = state.applicationCounter;
  j["credited_uwh"] = state.creditedUWh;
  j["consumed_uwh"] = state.consumedUWh;
  j["uncertain_uwh"] = state.uncertainUWh;
  j["remaining_credit_uwh"] = state.availableUWh;
  j["voltage_mv"] = measured.mv;
  j["current_ma"] = measured.ma;
  j["power_mw"] = measured.mw;
  j["pzem_wh"]=state.meterWh;
  j["output_requested"] = outputOn;
  j["output_feedback"] = "UNKNOWN";
  j["sensor_status"] = sensorOK ? "OK" : "FAULT";
  if (enqueue(JobKind::Telemetry, j)) lastTelemetry = millis();
}
void commandSha(const uint8_t* bytes, size_t n, uint8_t* out) {
  mbedtls_sha256(bytes, n, out, 0);
}
bool parseCommand(JsonVariantConst row, Command& out) {
  return parseCreditCommand(row, state, out, commandSha);
}
void meterTick(bool force = false);
void handleReply() {
  Reply r{};
  if (xQueueReceive(replyQueue, &r, 0) != pdTRUE) return;
  busy = false;
  if (r.status == 401 || r.status == 403) {
    meterTick(true);
    switchOff();
    loadRequested = false;

    sessionReady = false;
    latch("Device access denied");
    return;
  }
  if (r.status < 200 || r.status >= 300) {
    nextNetwork = millis() + retryDelay;
    retryDelay = retryDelay < 30000 ? retryDelay * 2 : 60000;
    if (r.status == 409 && r.kind != JobKind::Redeem) {
      switchOff();
      loadRequested = false;

      sessionReady = false;
      latch("Reconciliation required");
      return;
    }
    if (r.kind == JobKind::Redeem) {
      if (r.status == 409) say("Used token or conflict");
      else if (r.status == 400 || r.status == 404) say("Token not accepted");
      else if (r.status == 503) say("Device API unavailable");
      else say("No result - retry token");
    } else say(r.status == 503 ? "Device API unavailable" : "Offline - retry pending");
    return;
  }
  JsonDocument j;
  if (deserializeJson(j, r.body) || !matching(j.as<JsonVariantConst>())) {
    latch("Invalid server response");
    return;
  }
  retryDelay = 2000;
  nextNetwork = millis() + 1000;
  if (r.kind == JobKind::Session) {
    if (!j["status"].is<const char*>() || strcmp(j["status"], "READY")) {
      latch("Session not authorized");
      return;
    }
    State next = state;
    next.reservedBytes[0] = 1;
    if (!persist(next)) return;
    sessionReady = true;
    say(state.ackPending ? "Recovering receipt" : GPAWA_AUTH_CREDIT_ONLY ? "Credit API ready" : "Ready: D to arm");
  } else if (r.kind == JobKind::Redeem) {
    if (!clockValid()) {
      latch("Clock invalid - service");
      return;
    }
    Command c{};
    if (!parseCommand(j["command"], c)) {
      latch("Invalid credit command");
      return;
    }
    char receipt[37], at[25];
    uuid4(receipt);
    timestamp(at, sizeof at);
    State next = state;
    auto result = apply(next, c, receipt, at);
    if (result == Apply::New) {
      if(persist(next)){beep(2);say("Credit saved");}
    } else if (result == Apply::Duplicate) say("Already stored - recovering");
    else { latch("Credit conflict - service"); }
  } else if (r.kind == JobKind::Ack) {
    if (!j["status"].is<const char*>() || strcmp(j["status"], "APPLIED") || !j["command_id"].is<const char*>() || !j["receipt_id"].is<const char*>() || !j["command_sequence"].is<uint32_t>() || j["command_sequence"].as<uint32_t>() != state.applicationCounter || !j["payload_digest"].is<const char*>() || strcmp(j["payload_digest"], state.lastCommand.digest)) {
      latch("Invalid receipt response");
      return;
    }
    State next = state;
    if (!acknowledge(next, j["command_id"], j["receipt_id"])) {
      latch("Receipt mismatch");
      return;
    }
    if (persist(next)) say("Credit confirmed");
  } else {
    if (!j["status"].is<const char*>() || strcmp(j["status"], "ACCEPTED") || !j["boot_id"].is<const char*>() || strcmp(j["boot_id"], bootId) || !j["sequence"].is<uint32_t>() || j["sequence"].as<uint32_t>() != telemetrySequence) {
      latch("Telemetry response invalid");
      return;
    }
  }
}
bool sample(){
#if GPAWA_USB_EXERCISE
 measured.wh=prefs.getUInt("mockWh",0);return true;
#else
 // PZEM v3 TTL, single instrument, read-only function 04. No counter reset.
 auto &u=Serial1;
 while(u.available())u.read();
 uint8_t req[8]={hw::PZEM_ADDR,4,0,0,0,10,0,0};
 uint16_t c=pz::crc(req,6);req[6]=c;req[7]=c>>8;
 u.write(req,8);u.flush();
 uint8_t b[25];size_t n=0;uint32_t start=millis();
 while(n<25 && millis()-start<180){while(n<25&&u.available())b[n++]=u.read();delay(1);}
 return pz::decode(b,n,hw::PZEM_ADDR,measured);
#endif
}
void meterTick(bool force){
 if(GPAWA_AUTH_CREDIT_ONLY){sensorOK=false;good=0;return;}
 uint32_t now=millis();if(!force&&now-lastSample<hw::SAMPLE_MS)return;
 if(outputOn&&now-lastSample>3000){switchOff();loadRequested=false;say("Sampling gap");}
 lastSample=now;
 if(!sample()){switchOff();loadRequested=false;sensorOK=false;good=0;return;}
 static uint8_t ignoredOff=0;
 if(!GPAWA_USB_EXERCISE && GPAWA_COMMISSIONED_OUTPUT && !outputOn && measured.ma>100){
   if(++ignoredOff>=5){State n=state;n.hold=1;switchOff();persist(n);latch("Load while OFF");return;}
 }else ignoredOff=0;
 if(good<3)++good;
 auto next=state; const auto before=state.availableUWh;
 auto result=observe(next,measured.wh);
 if(result==Reading::BaselineRequired){switchOff();latch("Baseline review");return;}
 if(result==Reading::Fault){switchOff();persist(next);latch("Counter reversed");return;}
 if(!next.availableUWh)switchOff();
 if(result==Reading::First || (before&&!next.availableUWh) || next.meterWh-savedWh>=32){
   if(!persist(next))return;
 }else{seal(next);state=next;}
 sensorOK=good>=3;
}
void outputTick(){
 bool permit=!GPAWA_AUTH_CREDIT_ONLY && storageOK && sensorOK && !fatal && loadRequested && !state.hold &&
             state.hasMeter && state.availableUWh && state.reservedBytes[0];
 if(!permit){switchOff();return;}
#if GPAWA_COMMISSIONED_OUTPUT && !GPAWA_USB_EXERCISE
 digitalWrite(hw::SWITCH_PIN,HIGH); outputOn=true;
#elif GPAWA_USB_EXERCISE
 outputOn=true; // logical indicator; no relay GPIO written
#else
 outputOn=false;
#endif
}
bool viewingMeter=false;
uint32_t meterShownAt=0;
void handleKey(){
 char k=keypad.getKey();if(!k)return;
 if(k=='A'){viewingMeter=!viewingMeter;meterShownAt=millis();return;}
 if(viewingMeter){viewingMeter=false;if(k<'0'||k>'9')return;}
 if(tokenLength && (k=='D'||k=='B'))return;
 if(k>='0'&&k<='9'){if(tokenLength<15){tokenDigits[tokenLength++]=k;tokenDigits[tokenLength]=0;}return;}
 if(k=='*'){if(tokenLength)tokenDigits[--tokenLength]=0;return;}
 if(k=='C'){eraseToken();return;}
 if(k=='D'){
   if(GPAWA_AUTH_CREDIT_ONLY){loadRequested=false;switchOff();say("Output disabled");return;}
   if(loadRequested){loadRequested=false;switchOff();say("Paused");}
   else if(sensorOK && sessionReady && !fatal){loadRequested=true;say("Meter armed");}
   else say("Check meter/API");
   return;
 }
#if GPAWA_USB_EXERCISE
 if(k=='B'){if(outputOn&&state.availableUWh){auto reading=prefs.getUInt("mockWh",0);if(reading==UINT32_MAX||prefs.putUInt("mockWh",reading+1)!=4){latch("Mock meter fault");return;}meterTick(true);outputTick();}return;}
#endif
 if(k!='#')return;
 if(!digits(tokenDigits,15)){say("Need 15 digits");return;}
 if(!creditTransportReady(state,GPAWA_AUTH_CREDIT_ONLY,sensorOK)){say("Check meter");return;}
#if GPAWA_USB_EXERCISE
 const bool second=state.applicationCounter==1 && !strcmp(tokenDigits,"222222222222222");
 if(!second && (state.applicationCounter!=0 || strcmp(tokenDigits,"111111111111111"))){eraseToken();say("Invalid or used");return;}
 Command c{};strcpy(c.id,"00000000-0000-4000-8000-000000000003");memset(c.digest,'a',64);strcpy(c.canonical,"EXERCISE");c.sequence=second?2:1;c.creditWh=10;
 if(second){c.id[35]='5';strcpy(c.canonical,"EXERCISE2");}
 State next=state;
 if(apply(next,c,second?"00000000-0000-4000-8000-000000000006":"00000000-0000-4000-8000-000000000004","2026-01-01T00:00:00Z")!=Apply::New){latch("Exercise fault");return;}
 next.ackPending=0;
 if(persist(next)){beep(2);say("10 test Wh saved");}
 eraseToken();
#else
 if(!sessionReady||WiFi.status()!=WL_CONNECTED||!clockValid()){say("Need device API");return;}
 if(busy||state.ackPending){say("Please retry");return;}
 JsonDocument j;identity(j);j["token"]=tokenDigits;j["application_counter"]=state.applicationCounter;
 if(enqueue(JobKind::Redeem,j)){eraseToken();say("Checking token");}
#endif
}
void row(int n,const char* s){char a[17];snprintf(a,sizeof a,"%-16.16s",s);lcd.setCursor(0,n);lcd.print(a);}
void draw(){
 if(!displayOK||millis()-lastUi<hw::UI_MS)return;lastUi=millis();
 char a[40];if(fatal){row(0,"OFF: needs check");row(1,message);return;}
 if(viewingMeter && millis()-meterShownAt>=5000)viewingMeter=false;
 if(viewingMeter){row(0,"Meter number");row(1,state.meterNumber);return;}
 if(tokenLength){row(0,tokenDigits);row(1,"# Send  * Delete");return;}
 if(GPAWA_AUTH_CREDIT_ONLY){
   if(millis()-showAt>=2000 && (millis()/3500)%2){row(0,"Consumption");row(1,"unavailable");}
   else {snprintf(a,sizeof a,"%llu Wh saved",(unsigned long long)(state.availableUWh/UWH_PER_WH));row(0,a);
     row(1,millis()-showAt<2000 ? message : "Credit-only mode");}
   return;
 }
 if(!state.hasMeter)row(0,"Meter not ready");
 else {snprintf(a,sizeof a,"%llu Wh %s",(unsigned long long)(state.availableUWh/UWH_PER_WH),outputOn?"ON":"OFF");row(0,a);}
 if(millis()-showAt<2000)row(1,message);
 else if(!sensorOK)row(1,"Check PZEM link");
 else if(!state.availableUWh)row(1,"A:Meter or token");
 else if(!loadRequested)row(1,"A:Meter  D:Arm");
 else if(GPAWA_USB_EXERCISE)row(1,"USB B: use 1 Wh");
 else if(!GPAWA_COMMISSIONED_OUTPUT)row(1,"Read-only mode");
 else row(1,WiFi.status()==WL_CONNECTED?"A:Meter  D:Pause":"Offline D:Pause");
}
bool configValid() {
  return (environmentCode(commissioning::ENVIRONMENT) == 1 || environmentCode(commissioning::ENVIRONMENT) == 2) && String(cfg::WIFI_SSID).indexOf("REPLACE") < 0 && strlen(cfg::WIFI_SSID) > 0 && String(cfg::WIFI_PASSWORD).indexOf("REPLACE") < 0 && uuid(cfg::DEVICE_ID) && uuid(cfg::STORAGE_ID) && digits(cfg::METER_NUMBER, 11) && strcmp(cfg::METER_NUMBER, "00000000000") && cfg::BINDING_EPOCH > 0 && strlen(cfg::DEVICE_SECRET) >= 32 && String(cfg::DEVICE_SECRET).indexOf("REPLACE") < 0 && !strncmp(cfg::API_BASE, "https://", 8) && String(cfg::API_BASE).indexOf("REPLACE") < 0 && strlen(cfg::API_BASE) > 15 && String(cfg::API_BASE).endsWith("/api/v1") && !strchr(cfg::API_BASE, '@') && !strchr(cfg::API_BASE, '?') && !strchr(cfg::API_BASE, '#') && String(cfg::ROOT_CA).indexOf("BEGIN CERTIFICATE") >= 0 && String(cfg::ROOT_CA).indexOf("REPLACE") < 0;
}
}
void wifiCheckSetup();
void wifiCheckLoop();
void firmwareSetup(){
#if GPAWA_WIFI_TEST
 wifiCheckSetup(); return;
#endif
#if !GPAWA_USB_EXERCISE && GPAWA_COMMISSIONED_OUTPUT
 digitalWrite(hw::SWITCH_PIN,LOW);pinMode(hw::SWITCH_PIN,OUTPUT);switchOff();
#endif
 Serial.begin(115200);pinMode(hw::BEEP,OUTPUT);digitalWrite(hw::BEEP,HIGH);delay(90);digitalWrite(hw::BEEP,LOW);
 Wire.begin(hw::SDA_PIN,hw::SCL_PIN);Wire.setTimeOut(50);
 displayOK=probe(hw::LCD_ADDR);if(!displayOK){latch("LCD not found");return;}
 lcd.init();lcd.backlight();
 // Some LCD libraries re-initialize Wire. Reapply the chosen S3 pins if changing defaults.
 const bool usb=GPAWA_USB_EXERCISE;
 configured=usb||configValid();if(!configured){
   if(GPAWA_AUTH_CREDIT_ONLY){latch("Check DeviceConfig");return;}
   if(GPAWA_COMMISSIONED_OUTPUT){latch("Set DeviceConfig");return;}
   diagnostic=true;Serial1.begin(9600,SERIAL_8N1,hw::RX,hw::TX);
   row(0,"PZEM read only");row(1,"Waiting for data");return;
 }
 const char* dev=usb?"00000000-0000-4000-8000-000000000001":cfg::DEVICE_ID;
 const char* id=usb?"00000000-0000-4000-8000-000000000002":cfg::STORAGE_ID;
 const char* met=usb?"00000000001":cfg::METER_NUMBER;
 unsigned epoch=usb?1:cfg::BINDING_EPOCH;
 const char* domain=usb?"USB_EXERCISE":commissioning::ENVIRONMENT;
 if(!prefs.begin(usb?"gpawa_ex2":(!strcmp(domain,"SANDBOX")?"gpawa_sbx2":"gpawa_ac1"),false)){latch("NVS unavailable");return;}
 if(prefs.isKey("state")){
   if(prefs.getBytesLength("state")!=sizeof state||prefs.getBytes("state",&state,sizeof state)!=sizeof state||!valid(state)){latch("Invalid journal");return;}
   if(strcmp(dev,state.deviceId)||strcmp(id,state.storageId)||strcmp(met,state.meterNumber)||epoch!=state.bindingEpoch||strcmp(domain,accountingEnvironment(state))){latch("Identity/domain changed");return;}
 }else{
   if(!usb&&!cfg::ALLOW_FIRST_BOOT){latch("Provision first");return;}
   state={};state.magic=MAGIC;state.version=VERSION;state.bindingEpoch=epoch;state.reservedBytes[1]=environmentCode(domain);
   strcpy(state.deviceId,dev);strcpy(state.storageId,id);strcpy(state.meterNumber,met);
   if(usb)state.reservedBytes[0]=1;
   seal(state);
 }
 if(state.hold){latch("Meter needs check");return;}
 if(GPAWA_AUTH_CREDIT_ONLY){
   if(!enterAuthenticatedCreditOnly(state)){latch("Credit mode invalid");return;}
 }else if(measurementPaused(state)){
   // No button or compile flag may turn a suspended lifetime reading into usage.
   latch("Baseline review");return;
 }
 if(!bootRecover(state)){latch("Invalid journal");return;}
 if(!persist(state))return;
 storageOK=true;
#if !GPAWA_USB_EXERCISE
 Serial1.begin(9600,SERIAL_8N1,hw::RX,hw::TX);
 uuid4(bootId);requestQueue=xQueueCreate(1,sizeof(Request));replyQueue=xQueueCreate(1,sizeof(Reply));
 if(!requestQueue||!replyQueue||xTaskCreate(networkWorker,"gpawa_net",32768,nullptr,1,nullptr)!=pdPASS){latch("Net task fault");return;}
 esp_task_wdt_config_t wdt={};wdt.timeout_ms=5000;wdt.trigger_panic=true;
 esp_err_t err=esp_task_wdt_init(&wdt);if(err==ESP_ERR_INVALID_STATE)err=esp_task_wdt_reconfigure(&wdt);
 if(err!=ESP_OK){latch("Watchdog fault");return;}
 err=esp_task_wdt_add(nullptr);watchdogReady=err==ESP_OK||esp_task_wdt_status(nullptr)==ESP_OK;
 if(!watchdogReady){latch("Watchdog fault");return;}
 WiFi.mode(WIFI_STA);WiFi.setAutoReconnect(true);WiFi.begin(cfg::WIFI_SSID,cfg::WIFI_PASSWORD);
 configTime(0,0,"pool.ntp.org","time.cloudflare.com");
#else
 sessionReady=true;
#endif
 if(GPAWA_AUTH_CREDIT_ONLY)Serial.println("Authenticated credit-only: consumption unavailable; physical output disabled.");
 say(usb?"USB exercise":GPAWA_AUTH_CREDIT_ONLY?"Checking credit":"Checking meter");meterTick(true);
}
void firmwareLoop(){
#if GPAWA_WIFI_TEST
 wifiCheckLoop(); return;
#endif
 if(diagnostic){
   if(millis()-lastSample>=1000){
    lastSample=millis();char a[32];
    if(sample()){
      snprintf(a,sizeof a,"%lu V  %lu W",(unsigned long)(measured.mv/1000),(unsigned long)(measured.mw/1000));row(0,a);
      snprintf(a,sizeof a,"%lu Wh total",(unsigned long)measured.wh);row(1,a);
      Serial.printf("PZEM: %lu mV, %lu mA, %lu mW, %lu Wh\n",(unsigned long)measured.mv,(unsigned long)measured.ma,(unsigned long)measured.mw,(unsigned long)measured.wh);
    }else {row(0,"PZEM read only");row(1,"No valid reading");}
   }
   delay(2);return;
 }
 if(watchdogReady)esp_task_wdt_reset();
 tickSound();if(!configured||!storageOK||fatal){draw();delay(3);return;}
 meterTick();if(fatal){draw();return;}
#if !GPAWA_USB_EXERCISE
 handleReply();if(fatal){draw();return;}
 if(WiFi.status()!=WL_CONNECTED){
   sessionReady=false;if(millis()-lastWifiAttempt>=15000){lastWifiAttempt=millis();WiFi.reconnect();}
 }else if(creditTransportReady(state,GPAWA_AUTH_CREDIT_ONLY,sensorOK)&&clockValid()&&!busy&&(int32_t)(millis()-nextNetwork)>=0){
   if(!sessionReady)sendSession();else if(state.ackPending)sendAck();
   else if(GPAWA_AUTH_CREDIT_ONLY){if(millis()-lastSession>=hw::TELEMETRY_MS)sendSession();}
   else if(millis()-lastTelemetry>=hw::TELEMETRY_MS)sendTelemetry();
 }
#endif
 handleKey();outputTick();draw();delay(2);
}
