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
    ],
    darkTheme: false,
  },
};
