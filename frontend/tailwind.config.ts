/**
 * BOS Pipeline v9.0 �� Tailwind CSS Configuration
 *
 * Custom theme tokens, fonts, shadows, and animation.
 */

import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      // ���� Colors ����
      colors: {
        surface: {
          50: "var(--color-surface-50)",
          100: "var(--color-surface-100)",
          200: "var(--color-surface-200)",
          300: "var(--color-surface-300)",
          400: "var(--color-surface-400)",
          500: "var(--color-surface-500)",
          600: "var(--color-surface-600)",
          700: "var(--color-surface-700)",
          800: "var(--color-surface-800)",
          900: "var(--color-surface-900)",
          950: "var(--color-surface-950)",
        },
        brand: {
          50: "var(--color-brand-50)",
          100: "var(--color-brand-100)",
          200: "var(--color-brand-200)",
          300: "var(--color-brand-300)",
          400: "var(--color-brand-400)",
          500: "var(--color-brand-500)",
          600: "var(--color-brand-600)",
          700: "var(--color-brand-700)",
          800: "var(--color-brand-800)",
          900: "var(--color-brand-900)",
        },
      },

      // ���� Font Family ����
      fontFamily: {
        sans: [
          "Aptos",
          "Segoe UI",
          "sans-serif",
        ],
        display: [
          "Bahnschrift",
          "Aptos",
          "Segoe UI",
          "sans-serif",
        ],
        mono: [
          "JetBrains Mono",
          "Fira Code",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "monospace",
        ],
      },

      // ���� Box Shadows ����
      boxShadow: {
        card: "var(--shadow-card)",
        "card-hover": "var(--shadow-card-hover)",
        glow: "var(--shadow-glow)",
      },

      // ���� Animation ����
      animation: {
        "fade-in": "fade-in 0.2s ease-out",
        "spin-slow": "spin-slow 2s linear infinite",
        "pulse-ring": "pulse-ring 2.5s cubic-bezier(0.22, 1, 0.36, 1) infinite",
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "spin-slow": {
          "0%": { transform: "rotate(0deg)" },
          "100%": { transform: "rotate(360deg)" },
        },
        "pulse-ring": {
          "0%": { boxShadow: "0 0 0 0 rgb(17 173 130 / 0.24)" },
          "70%": { boxShadow: "0 0 0 12px rgb(17 173 130 / 0)" },
          "100%": { boxShadow: "0 0 0 0 rgb(17 173 130 / 0)" },
        },
      },

      // ���� Spacing / Sizing ����
      spacing: {
        "18": "4.5rem",
        "88": "22rem",
        "112": "28rem",
        "128": "32rem",
      },

      // ���� Typography ����
      fontSize: {
        "2xs": ["0.625rem", { lineHeight: "0.875rem" }],
      },

      // ���� Border Radius ����
      borderRadius: {
        "4xl": "2rem",
      },

      // ���� Z-Index ����
      zIndex: {
        "60": "60",
        "70": "70",
      },
    },
  },
  plugins: [],
} satisfies Config;

