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
          100: "#e6f5ec",
          800: "#006c2d",
        },
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
      boxShadow: {
        'soft': '0 10px 40px -10px rgba(0, 140, 58, 0.15)',
      },
    },
  },
  plugins: [],
};
