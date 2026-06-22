/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/js/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        erpac: {
          primary: "#008C3A",
          dark: "#006c2d",
          light: "#00a945",
          50: "#e9f7ef",
          100: "#e6f5ec",
          200: "#a7e0bd",
          700: "#0a7a37",
          800: "#006c2d",
        },
      },
      fontFamily: {
        // Inter en priorité ; repli sur des polices système natives pour rester
        // lisible si l'intranet n'a pas accès à Google Fonts (hors-ligne).
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
      },
      boxShadow: {
        // Ombre douce et neutre (design épuré : carte = bordure fine + légère ombre).
        'soft': '0 1px 2px rgba(15, 23, 42, 0.04), 0 1px 3px rgba(15, 23, 42, 0.06)',
      },
    },
  },
  plugins: [],
};
