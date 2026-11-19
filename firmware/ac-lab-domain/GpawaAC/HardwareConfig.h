#pragma once
// Active sketch is already provisioned; preserve authenticated operation.
#ifndef GPAWA_WIFI_TEST
#define GPAWA_WIFI_TEST 0
#endif
// USB supplies power only. Credit still requires Wi-Fi, TLS and Django auth.
// Separate from synthetic USB exercise and Wi-Fi-only diagnostics.
#ifndef GPAWA_AUTH_CREDIT_ONLY
#define GPAWA_AUTH_CREDIT_ONLY 1
#endif
// 0: authenticated HTTPS operation (or diagnostic-only if unconfigured).
// 1: explicit USB exercise, separate journal; never authenticated credit.
#ifndef GPAWA_USB_EXERCISE
#define GPAWA_USB_EXERCISE 0
#endif
// This credit-only branch requires 0 and rejects every output-enable build.
#ifndef GPAWA_COMMISSIONED_OUTPUT
#define GPAWA_COMMISSIONED_OUTPUT 0
#endif
#if GPAWA_COMMISSIONED_OUTPUT
#error Physical relay output is forbidden in this credit-only integration
#endif
#if GPAWA_AUTH_CREDIT_ONLY && (GPAWA_WIFI_TEST || GPAWA_USB_EXERCISE || GPAWA_COMMISSIONED_OUTPUT)
#error Authenticated credit-only mode cannot enable diagnostics, exercise or output
#endif
namespace hw{
constexpr int SDA_PIN=8,SCL_PIN=9, RX=16,TX=17,SWITCH_PIN=14,BEEP=18;
constexpr unsigned char LCD_ADDR=0x27, PZEM_ADDR=0xf8;
constexpr unsigned SAMPLE_MS=1000,UI_MS=180,TELEMETRY_MS=30000;
}

#if GPAWA_WIFI_TEST && (GPAWA_USB_EXERCISE || GPAWA_COMMISSIONED_OUTPUT)
#error Wi-Fi diagnostics cannot enable exercise credit or physical output
#endif
