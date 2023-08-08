/** @type {import("tailwindcss").Config} */
module.exports = {
  content: ["./nummus/web/templates/**/*.html"],
  theme: {
    colors: {
      green: {
        DEFAULT: "#33ba33",
        50: "#f2fcf1",
        100: "#e0f9df",
        200: "#c2f1c1",
        300: "#90e590",
        400: "#58d058",
        500: "#33ba33",
        600: "#249524",
        700: "#1f7620",
        800: "#1e5d1f",
        900: "#1a4d1b",
        950: "#092a0b",
      },
      blue: {
        DEFAULT: "#4472c4",
        50: "#f2f6fc",
        100: "#e2ecf7",
        200: "#cbdef2",
        300: "#a7c9e9",
        400: "#7dacdd",
        500: "#5e8fd3",
        600: "#4472c4",
        700: "#4064b5",
        800: "#395294",
        900: "#324776",
        950: "#222d49",
      },
      red: {
        DEFAULT: "#ee7674",
        50: "#fdf3f3",
        100: "#fce4e4",
        200: "#facfce",
        300: "#f6acab",
        400: "#ee7674",
        500: "#e35250",
        600: "#d03532",
        700: "#ae2927",
        800: "#902624",
        900: "#782524",
        950: "#410f0e",
      },
      grey: {
        50: "#f6f6f6",
        100: "#e7e7e7",
        200: "#d1d1d1",
        300: "#b0b0b0",
        400: "#888888",
        500: "#6d6d6d",
        600: "#5d5d5d",
        700: "#4f4f4f",
        800: "#454545",
        900: "#3d3d3d",
        950: "#282828",
      },
      white: {
        DEFAULT: "#f6f6f6",
      },
      black: {
        DEFAULT: "#282828",
      },
      c0: {
        DEFAULT: "#4472c4",
      },
      c1: {
        DEFAULT: "#966bc2",
      },
      c2: {
        DEFAULT: "#c16794",
      },
      c3: {
        DEFAULT: "#c4996e",
      },
      c4: {
        DEFAULT: "#6bc296",
      },
    },
    fontFamily: {
      sans: ["linux-libertine", "sans-serif"],
      serif: ["fogtwo-no5", "serif"],
      mono: ["code-new-roman", "monospace"],
    },
    extend: {},
  },
  plugins: [],
};
