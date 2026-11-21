#pragma once
#include <ArduinoJson.h>
#include <cstring>
namespace gpawa {
inline bool diagnosticId(const char* value){
  if(!value||strlen(value)!=36||value[14]!='4'||!strchr("89ab",value[19]))return false;
  for(size_t i=0;i<36;++i){
    if(i==8||i==13||i==18||i==23){if(value[i]!='-')return false;}
    else if(!strchr("0123456789abcdef",value[i]))return false;
  }
  return true;
}
// Fixed literal vocabulary only: never echo arbitrary JSON, headers or TLS text.
inline const char* diagnosticCode(JsonVariantConst body,int status){
  const char* value=body["code"].is<const char*>()?body["code"].as<const char*>():nullptr;
  const char* known[]={"REQUEST_INVALID","REQUEST_TOO_LARGE","TOKEN_LOOKUP_MISS","TOKEN_UNAVAILABLE","TOKEN_AMOUNT_MISMATCH",
    "TOKEN_SOURCE_UNVERIFIED","TOKEN_ALREADY_USED","PENDING_COMMAND","RESERVATION_CONFLICT","DEVICE_UNAUTHORIZED",
    "DEVICE_BINDING_MISMATCH","DEVICE_SESSION_REQUIRED","DEVICE_STORAGE_REQUIRED","DEVICE_STORAGE_RESET","DEVICE_COUNTER_REGRESSION",
    "DEVICE_BOOT_REPLAY","CREDIT_CONSERVATION","COMMAND_UNAVAILABLE","IDENTITY_OUT_OF_RANGE","EVENT_CONFLICT","STALE_TELEMETRY","PZEM_COUNTER_RESET",
    "RECONCILIATION_REQUIRED","TOKEN_SERVICE_UNAVAILABLE","TOKEN_STORAGE_UNAVAILABLE","AC_LAB_DISABLED",
    "DEVICE_RATE_LIMITED","RECEIPT_BINDING_MISMATCH","RECEIPT_CONFLICT","OUTPUT_DISABLED","TESTING_OPERATION_UNAVAILABLE","INTERNAL_ERROR"};
  if(value)for(auto code:known)if(!strcmp(value,code))return code;
  if(status<=0)return "TRANSPORT_ERROR";
  if(status>=200&&status<300)return "OK";
  switch(status){case 400:return "HTTP_BAD_REQUEST";case 401:return "HTTP_UNAUTHORIZED";case 403:return "HTTP_FORBIDDEN";
    case 404:return "HTTP_NOT_FOUND";case 409:return "HTTP_CONFLICT";case 429:return "HTTP_RATE_LIMITED";case 503:return "HTTP_UNAVAILABLE";
    default:return "HTTP_ERROR";}
}
enum class DiagnosticTransport:uint8_t {Ok,Connection,ConnectionTLS,TLS,Clock,HttpBegin,BodyLimit,BodyRead};
inline const char* transportCause(DiagnosticTransport t){
  switch(t){case DiagnosticTransport::Ok:return "HTTP_RESPONSE";case DiagnosticTransport::Connection:return "CONNECTION_FAILURE";
    case DiagnosticTransport::TLS:return "TLS_FAILURE";case DiagnosticTransport::ConnectionTLS:return "CONNECTION_OR_TLS_FAILURE";
    case DiagnosticTransport::Clock:return "CLOCK_UNAVAILABLE";case DiagnosticTransport::HttpBegin:return "HTTP_BEGIN_FAILURE";
    case DiagnosticTransport::BodyLimit:return "RESPONSE_BODY_LIMIT";default:return "RESPONSE_READ_FAILURE";}
}
inline const char* diagnosticCategory(bool ack,const char* cause,bool failed){return ack&&failed?"ACK_FAILURE":cause;}
inline const char* diagnosticLogId(const char* sent,const char* returned){
  return diagnosticId(returned)?returned:diagnosticId(sent)?sent:"unavailable";
}
inline const char* diagnosticCorrelation(const char* sent,const char* returned){
  if(!returned||!returned[0])return "missing";
  if(!diagnosticId(returned))return "invalid";
  return diagnosticId(sent)&&!strcmp(sent,returned)?"matched":"mismatch";
}
inline const char* rejectionMessage(const char* code){
  if(!strcmp(code,"TOKEN_UNAVAILABLE")||!strcmp(code,"TOKEN_LOOKUP_MISS"))return "Token unavailable";
  if(!strcmp(code,"TOKEN_SOURCE_UNVERIFIED"))return "Source review";
  if(!strcmp(code,"TOKEN_AMOUNT_MISMATCH"))return "Amount review";
  if(!strcmp(code,"TOKEN_ALREADY_USED"))return "Token used";
  if(!strcmp(code,"PENDING_COMMAND"))return "Pending delivery";
  if(!strcmp(code,"TOKEN_STORAGE_UNAVAILABLE"))return "Token key review";
  if(!strcmp(code,"TOKEN_SERVICE_UNAVAILABLE"))return "Token service off";
  if(!strcmp(code,"REQUEST_INVALID"))return "Request invalid";
  if(!strcmp(code,"HTTP_NOT_FOUND"))return "Check API route";
  if(!strcmp(code,"RESERVATION_CONFLICT"))return "Credit reserved";
  if(!strcmp(code,"INTERNAL_ERROR"))return "Server error";
  return "Request rejected";
}
}
