import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
    },
  },
  server: {
    port: 5173,
    host: true,
    allowedHosts: true,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        secure: false,
      },
      // Phase A6: forward /agent/* to the BOS Agent service on :8001.
      // Override target via VITE_AGENT_URL at dev time if needed.
      "/agent": {
        target: process.env.VITE_AGENT_URL ?? "http://localhost:8001",
        changeOrigin: true,
        secure: false,
      },
    },
  },
  build: {
    target: "es2020",
    outDir: "dist",
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          "vendor-react": ["react", "react-dom", "react-router-dom"],
          "vendor-query": ["@tanstack/react-query"],
          "vendor-charts": ["recharts"],
          "vendor-forms": ["react-hook-form", "@hookform/resolvers", "zod"],
          "vendor-ui": ["framer-motion", "lucide-react", "clsx", "tailwind-merge"],
        },
      },
    },
    chunkSizeWarningLimit: 600,
  },
  envPrefix: "VITE_",
});
