import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    // El bundle actual ronda los ~533 kB tras minificar; la advertencia de Vite por
    // defecto (500 kB) es ruido. Code-splitting real se abordará si crece mucho más.
    chunkSizeWarningLimit: 600,
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8001",
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: true,
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
