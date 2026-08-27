import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#172026",
        panel: "#f7f8fa",
        line: "#d8dde3",
        accent: "#256f7a",
      },
    },
  },
  plugins: [],
};

export default config;
