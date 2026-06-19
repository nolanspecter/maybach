import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans:    ["DM Sans", "system-ui", "sans-serif"],
        serif:   ["Cormorant Garamond", "Georgia", "serif"],
        mono:    ["JetBrains Mono", "monospace"],
      },
      colors: {
        surface: {
          DEFAULT: "#0D0D0B",
          1: "#141412",
          2: "#1C1C19",
          3: "#252522",
          4: "#2E2E2A",
        },
        border:      "#2A2A26",
        gold:        "#C9A96E",
        "gold-dim":  "#7A6240",
      },
      letterSpacing: {
        widest2: "0.25em",
      },
    },
  },
  plugins: [],
};

export default config;
