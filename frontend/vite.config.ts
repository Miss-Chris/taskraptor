import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  // In production Django serves static files at /static/. Vite must prefix
  // all asset paths so the built index.html references /static/assets/...
  base: mode === "production" ? "/static/" : "/",
  server: {
    port: 5173,
    proxy: {
      // Forward API calls to Django during development.
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
}));
