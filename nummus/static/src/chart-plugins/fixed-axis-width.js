"use strict";
/**
 * Chart.js plugin to set a fixed axis width
 *
 */
const pluginFixedAxisWidth = {
  id: "fixedAxisWidth",
  beforeInit: function (chart) {
    const {
      config: {
        options: {
          scales: { y },
          plugins: {
            fixedAxisWidth: { width },
          },
        },
      },
    } = chart;
    y.afterFit = function (scale) {
      if (scale.width > width)
        console.error(
          `Scale width ${scale.width} already ` + `over desired ${width}`,
        );
      scale.width = width;
    };
  },
};
