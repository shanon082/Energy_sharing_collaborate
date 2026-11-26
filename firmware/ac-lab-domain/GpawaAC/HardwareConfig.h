#pragma once
// Keep relay diagnostics separate from authenticated credit and physical output.
#ifndef GPAWA_WIFI_TEST
#define GPAWA_WIFI_TEST 0
#endif
#ifndef GPAWA_RELAY_DIAGNOSTIC
#define GPAWA_RELAY_DIAGNOSTIC 0
#endif
#ifndef GPAWA_PZEM_DIAGNOSTIC
#define GPAWA_PZEM_DIAGNOSTIC 1
#endif
// USB supplies power only. Credit still requires Wi-Fi, TLS and Django auth.
// Separate from synthetic USB exercise and Wi-Fi-only diagnostics.
#ifndef GPAWA_AUTH_CREDIT_ONLY
#define GPAWA_AUTH_CREDIT_ONLY 0
#endif
// 0: authenticated HTTPS operation (or diagnostic-only if unconfigured).
// 1: explicit USB exercise, separate journal; never authenticated credit.
#ifndef GPAWA_USB_EXERCISE
#define GPAWA_USB_EXERCISE 0
#endif
// Physical relay control requires an explicitly measured relay level and
// remains disabled in the default configuration.
#ifndef GPAWA_COMMISSIONED_OUTPUT
#define GPAWA_COMMISSIONED_OUTPUT 0
#endif
#ifndef GPAWA_RELAY_COMMISSIONING_APPROVED
#define GPAWA_RELAY_COMMISSIONING_APPROVED 0
#endif
#if GPAWA_RELAY_DIAGNOSTIC && GPAWA_AUTH_CREDIT_ONLY
#error Relay diagnostics cannot run with authenticated credit enabled
#endif
#if defined(GPAWA_RELAY_ACTIVE_LEVEL) && (GPAWA_RELAY_ACTIVE_LEVEL != 0) && (GPAWA_RELAY_ACTIVE_LEVEL != 1)
#error GPAWA_RELAY_ACTIVE_LEVEL must be 0 (active-LOW) or 1 (active-HIGH)
#endif
#if GPAWA_COMMISSIONED_OUTPUT && !defined(GPAWA_RELAY_ACTIVE_LEVEL)
#error Physical output requires an explicitly measured relay active level
#endif
#if GPAWA_COMMISSIONED_OUTPUT && !GPAWA_RELAY_COMMISSIONING_APPROVED
#error Physical output requires an explicit commissioning approval flag
#endif
#if GPAWA_RELAY_DIAGNOSTIC && (GPAWA_PZEM_DIAGNOSTIC || GPAWA_AUTH_CREDIT_ONLY || GPAWA_WIFI_TEST || GPAWA_USB_EXERCISE || GPAWA_COMMISSIONED_OUTPUT)
#error Relay diagnostics require a separate non-credit, non-exercise, non-output build
#endif
#if GPAWA_PZEM_DIAGNOSTIC && (GPAWA_RELAY_DIAGNOSTIC || GPAWA_AUTH_CREDIT_ONLY || GPAWA_WIFI_TEST || GPAWA_USB_EXERCISE || GPAWA_COMMISSIONED_OUTPUT)
#error PZEM diagnostics require a separate read-only non-credit, non-relay build
#endif
#if GPAWA_AUTH_CREDIT_ONLY && (GPAWA_WIFI_TEST || GPAWA_USB_EXERCISE || GPAWA_COMMISSIONED_OUTPUT)
#error Authenticated credit-only mode cannot enable diagnostics, exercise or output
#endif
#if GPAWA_COMMISSIONED_OUTPUT && (GPAWA_PZEM_DIAGNOSTIC || GPAWA_RELAY_DIAGNOSTIC || GPAWA_WIFI_TEST || GPAWA_USB_EXERCISE)
#error Commissioned output requires the authenticated metered operating mode
#endif
namespace hw{
constexpr int SDA_PIN=8,SCL_PIN=9, RX=16,TX=17,SWITCH_PIN=14,BEEP=18;
constexpr unsigned char LCD_ADDR=0x27, PZEM_ADDR=0x01;
constexpr unsigned SAMPLE_MS=1000,UI_MS=180,TELEMETRY_MS=30000,EMPTY_ALARM_MS=120000;
#if defined(GPAWA_RELAY_ACTIVE_LEVEL)
constexpr int RELAY_ACTIVE_LEVEL=GPAWA_RELAY_ACTIVE_LEVEL;
constexpr int RELAY_INACTIVE_LEVEL=1-GPAWA_RELAY_ACTIVE_LEVEL;
#endif
}

#if GPAWA_WIFI_TEST && (GPAWA_USB_EXERCISE || GPAWA_COMMISSIONED_OUTPUT)
#error Wi-Fi diagnostics cannot enable exercise credit or physical output
#endif
