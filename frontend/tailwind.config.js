const themes = require("daisyui/src/theming/themes");

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
    "./context/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Poppins", "Arial", "Helvetica", "sans-serif"],
      },
    },
  },
  plugins: [require("daisyui")],
  daisyui: {
    themes: [
      {
        light: {
          ...themes.light,
          primary: "#3A00A3",
          "primary-content": "#FFFFFF",
        },
      },
      {
        dark: {
          ...themes.dark,
          primary: "#7c3aed",
          "primary-content": "#FFFFFF",
          "base-100": "#1a1a2e",
          "base-200": "#16213e",
          "base-300": "#0f3460",
          "base-content": "#e2e8f0",
        },
      },
    ],
    darkTheme: "dark",
  },
};
