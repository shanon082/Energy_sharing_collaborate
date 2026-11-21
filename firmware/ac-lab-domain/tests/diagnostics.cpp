#include "../GpawaAC/SafeDiagnostics.h"
#include <cassert>
#include <cstdio>
int main(){
 using namespace gpawa;
 const char* id="10000000-0000-4000-8000-000000000001";
 assert(diagnosticId(id));assert(!diagnosticId("000123456789012"));assert(!diagnosticId("10000000-0000-1000-8000-000000000001"));
 assert(!strcmp(diagnosticLogId(id,"10000000-0000-4000-8000-000000000002"),"10000000-0000-4000-8000-000000000002"));
 assert(!strcmp(diagnosticLogId(id,"PRIVATE_HEADER_NEVER_LOG"),id));
 assert(!strcmp(diagnosticCorrelation(id,id),"matched"));assert(!strcmp(diagnosticCorrelation(id,""),"missing"));
 assert(!strcmp(diagnosticCorrelation(id,"PRIVATE_HEADER_NEVER_LOG"),"invalid"));
 assert(!strcmp(diagnosticCorrelation(id,"10000000-0000-4000-8000-000000000002"),"mismatch"));
 JsonDocument body;body["code"]="TOKEN_UNAVAILABLE";
 assert(!strcmp(diagnosticCode(body.as<JsonVariantConst>(),404),"TOKEN_UNAVAILABLE"));
 assert(!strcmp(rejectionMessage("TOKEN_UNAVAILABLE"),"Token unavailable"));
 body["code"]="000123456789012";body["message"]="private response, never echoed";
 assert(!strcmp(diagnosticCode(body.as<JsonVariantConst>(),400),"HTTP_BAD_REQUEST"));
 body["code"]="UNTRUSTED_DEVICE_SECRET";
 assert(!strcmp(diagnosticCode(body.as<JsonVariantConst>(),404),"HTTP_NOT_FOUND"));
 body.clear();assert(!strcmp(diagnosticCode(body.as<JsonVariantConst>(),0),"TRANSPORT_ERROR"));
 assert(!strcmp(diagnosticCode(body.as<JsonVariantConst>(),200),"OK"));
 assert(!strcmp(transportCause(DiagnosticTransport::TLS),"TLS_FAILURE"));
 assert(!strcmp(transportCause(DiagnosticTransport::Connection),"CONNECTION_FAILURE"));
 assert(!strcmp(transportCause(DiagnosticTransport::ConnectionTLS),"CONNECTION_OR_TLS_FAILURE"));
 for(auto cause:{"HTTP_REJECTION","INVALID_JSON","COMMAND_VALIDATION_FAILURE","PERSISTENT_STORAGE_FAILURE"}){
   assert(!strcmp(diagnosticCategory(true,cause,true),"ACK_FAILURE"));
   assert(!strcmp(diagnosticCategory(false,cause,true),cause));
 }
 assert(!strcmp(diagnosticCategory(true,"ACK_CONFIRMED",false),"ACK_CONFIRMED"));
 puts("PASS: correlation, transport/HTTP/JSON/command/storage/ACK classification; no arbitrary code/header/body echo");
}
