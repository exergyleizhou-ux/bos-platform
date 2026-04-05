/**
 * BOS Pipeline v9.0 �� Vite Configuration
 *
 * React + SWC plugin, path aliases, proxy, build optimizations.
 */

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],

  // ���� Path Aliases ����
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
    },
  },

  // ���� Dev Server ����
  server: {
    port: 5173,
    host: true,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        secure: false,
      },
    },
  },

  // ���� Build ����
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

  // ���� Env Prefix ����
  envPrefix: "VITE_",
});
