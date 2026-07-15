import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Absolute base: FastAPI serves the SPA at "/", so asset URLs must be root-absolute
// (otherwise nested client routes like /investigation/ARG-123 request the wrong path).
export default defineConfig({
  base: "/",
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Dev: forward API calls to the FastAPI backend.
      "/api": "http://localhost:8000",
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
