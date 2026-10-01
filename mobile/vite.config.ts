import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  if (mode === "production" && !/^https:\/\/[^\s/]+(?:\/.*)?$/.test(env.VITE_API_BASE_URL || "")) {
    throw new Error("Release builds require VITE_API_BASE_URL with HTTPS.");
  }
  return {
    base: "./",
    plugins: [react()],
    server: { host: "0.0.0.0" },
    build: { outDir: "dist", emptyOutDir: true },
  };
});
