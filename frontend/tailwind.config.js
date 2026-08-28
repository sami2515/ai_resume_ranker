/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Enterprise Slate & Royal Sapphire Design System
        base: "#090D16", // Deep Obsidian Canvas
        surface: {
          1: "#0F172A", // Slate Dark Surface
          2: "#161F33", // Elevated Container Surface
          3: "#1E293B", // Highlight & Hover Surface
        },
        line: {
          DEFAULT: "#26354D", // Subtle Slate Border
          soft: "#1A2536",
        },
        ink: {
          DEFAULT: "#F8FAFC", // Pure Crisp White
          muted: "#94A3B8", // Slate Muted
          faint: "#64748B", // Slate Faint
        },
        accent: {
          DEFAULT: "#2563EB", // Royal Sapphire Blue
          hover: "#1D4ED8",
          soft: "rgba(37, 99, 235, 0.12)",
          ring: "rgba(37, 99, 235, 0.35)",
        },
        gold: {
          DEFAULT: "#F59E0B", // Warm Amber
          soft: "rgba(245, 158, 11, 0.12)",
        },
        good: {
          DEFAULT: "#10B981", // Crisp Emerald Green
          soft: "rgba(16, 185, 129, 0.12)",
        },
        warn: {
          DEFAULT: "#F59E0B",
          soft: "rgba(245, 158, 11, 0.12)",
        },
        bad: {
          DEFAULT: "#F43F5E", // Refined Rose/Crimson
          soft: "rgba(244, 63, 94, 0.12)",
        },
      },
      fontFamily: {
        display: ["'Plus Jakarta Sans'", "system-ui", "sans-serif"],
        sans: ["'Inter'", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
      },
      boxShadow: {
        panel: "0 1px 0 0 rgba(255,255,255,0.05) inset, 0 20px 40px -15px rgba(0,0,0,0.7)",
        glow: "0 0 0 1px rgba(37,99,235,0.35), 0 8px 24px -6px rgba(37,99,235,0.35)",
        "glow-gold": "0 0 0 1px rgba(245,158,11,0.4), 0 8px 24px -6px rgba(245,158,11,0.3)",
      },
      borderRadius: {
        xl: "0.875rem",
        "2xl": "1.25rem",
      },
      keyframes: {
        "fade-up": { from: { opacity: 0, transform: "translateY(6px)" }, to: { opacity: 1, transform: "translateY(0)" } },
        shimmer: { from: { backgroundPosition: "-400px 0" }, to: { backgroundPosition: "400px 0" } },
      },
      animation: {
        "fade-up": "fade-up 0.28s cubic-bezier(0.16,1,0.3,1) both",
        shimmer: "shimmer 1.6s linear infinite",
      },
    },
  },
  plugins: [],
};
