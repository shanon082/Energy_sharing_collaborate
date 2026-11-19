#pragma once
// Copy to DeviceConfig.h. Never commit the filled file or share its contents.
// This firmware requires the NEW backend contract in docs/API_CONTRACT.md.
namespace cfg {
constexpr char WIFI_SSID[] = "REPLACE_WIFI_SSID";
constexpr char WIFI_PASSWORD[] = "REPLACE_WIFI_PASSWORD";
// Leave this placeholder until the separately implemented device API is deployed.
// Example value AFTER deployment: https://shanonsimon.alwaysdata.net/api/v1
constexpr char API_BASE[] = "https://shanonsimon.alwaysdata.net/api/v1";
constexpr char DEVICE_ID[] = "REPLACE_PROVISIONED_DEVICE_UUID";
constexpr char DEVICE_SECRET[] = "REPLACE_UNIQUE_DEVICE_SECRET_AT_LEAST_32_CHARS";
constexpr char METER_NUMBER[] = "00000000000"; // replace; exactly 11 ASCII digits
constexpr unsigned BINDING_EPOCH = 1;
// Provision the SAME random UUID on the server. It is public identity, not a password.
constexpr char STORAGE_ID[] = "REPLACE_PROVISIONED_STORAGE_UUID";
// True only for an explicitly provisioned unused device. After first upload set false.
// Server MUST refuse reinitialization of a previously used binding.
constexpr bool ALLOW_FIRST_BOOT = false;
// Paste the trusted CA root for the API hostname, NOT a device token or private key.
// Do not use setInsecure(). CA rotation requires controlled firmware maintenance.
constexpr char ROOT_CA[] = R"CERT(
-----BEGIN CERTIFICATE-----
REPLACE_WITH_VERIFIED_ROOT_CA_CERTIFICATE
-----END CERTIFICATE-----
)CERT";
}
