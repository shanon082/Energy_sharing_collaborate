import type { CapacitorConfig } from "@capacitor/cli";

const debugHttp = process.env.CAPACITOR_DEBUG_HTTP === "1";
const config: CapacitorConfig = {
  appId: "org.gpawa.consumer.prototype",
  appName: "gPawa Consumer Prototype",
  webDir: "dist",
  server: { androidScheme: debugHttp ? "http" : "https" },
};

export default config;
