/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/js/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        // Palette ERPAC alignée sur erpac-tokens.css
        erpac: {
          primary: "#008C3A",
          dark: "#007330",
          light: "#36B269",
          50: "#EDFCF4",
          100: "#D3F5E1",
          200: "#A5E6C0",
          300: "#73D19A",
          400: "#36B269",
          500: "#008C3A",
          600: "#007330",
          700: "#005925",
          800: "#00451D",
          900: "#002E13",
        },
        // Neutres verdis du design system (remplace slate dans les templates existants)
        slate: {
          50: "#F6FBF9",
          100: "#ECF4F0",
          200: "#DAE6E1",
          300: "#B9C7C1",
          400: "#8B9993",
          500: "#64706B",
          600: "#4B5752",
          700: "#36403C",
          800: "#232B28",
          900: "#131A17",
        },
        success: {
          50: "#E8F6EE",
          500: "#0F7B3D",
        },
        warning: {
          50: "#FCF3E3",
          500: "#8A5A00",
        },
        danger: {
          50: "#FDECEA",
          500: "#B42318",
        },
        info: {
          50: "#E7F2F8",
          500: "#0B5F8A",
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
        display: ['Space Grotesk', 'Inter', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        erp: "18px",
        "erp-sm": "12px",
        "erp-xs": "6px",
      },
      boxShadow: {
        soft: 'var(--erp-shadow-sm)',
        erp: 'var(--erp-shadow-md)',
        "erp-lg": 'var(--erp-shadow-lg)',
        "erp-focus": 'var(--erp-shadow-focus)',
      },
      maxWidth: {
        erp: "1180px",
      },
    },
  },
  plugins: [],
};
