import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#111827",
        panel: "#f8fafc",
        line: "#cbd5e1",
        accent: "#0f766e",
        "deep-teal": "#115e59",
        amber: "#d97706",
      },
    },
  },
  plugins: [],
};

export default config;
