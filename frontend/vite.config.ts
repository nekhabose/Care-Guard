import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The backend default dev URL. Override at build/dev time with VITE_API_BASE_URL.
// The proxy lets the dev server talk to FastAPI without CORS friction.
const API_TARGET = process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/dashboard": { target: API_TARGET, changeOrigin: true },
      "/health": { target: API_TARGET, changeOrigin: true },
    },
  },
});
