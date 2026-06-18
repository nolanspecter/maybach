import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      colors: {
        surface: {
          DEFAULT: "#0a0a0b",
          1: "#111113",
          2: "#18181b",
          3: "#232329",
          4: "#2e2e36",
        },
        border: "#2e2e36",
        accent: "#7c6af7",
      },
    },
  },
  plugins: [],
};

export default config;
