"use strict";
/**
 * Chart.js plugin to draw a box annotation
 *
 */
const pluginBoxAnnotation = {
  id: "boxAnnotation",
  beforeInit: function (chart) {
    const {
      config: {
        options: {
          plugins: { boxAnnotation },
          scales: { y },
        },
      },
    } = chart;

    // Add suggested min/max so box is visible
    let { yMin, yMax } = boxAnnotation;
    let { min, max } = widenRange(yMin, yMax, 0.05);
    min = Math.min(min, y.suggestedMin ?? min);
    max = Math.max(max, y.suggestedMax ?? max);
    y.suggestedMin = min;
    y.suggestedMax = max;

    chart.boxAnnotation = boxAnnotation;
  },
  beforeDatasetsDraw: function (chart) {
    let {
      ctx,
      chartArea: { top, bottom, left, right, width, height },
      scales,
      boxAnnotation: { yMin, yMax, borderColor, borderWidth, backgroundColor },
    } = chart;

    borderWidth = borderWidth ?? 1;
    borderColor = borderColor ?? "#000";

    const yMinPx = scales.y.getPixelForValue(yMin);
    const yMaxPx = scales.y.getPixelForValue(yMax);

    const x = left;
    const y = yMinPx;
    const w = right - left;
    const h = yMaxPx - yMinPx;

    ctx.save();

    if (backgroundColor != null) {
      ctx.fillStyle = backgroundColor;
      ctx.fillRect(x, y, w, h);
    }
    if (borderWidth > 0) {
      // Only stroke top and bottom lines
      ctx.beginPath();
      ctx.moveTo(left, yMinPx);
      ctx.lineTo(right, yMinPx);
      ctx.moveTo(left, yMaxPx);
      ctx.lineTo(right, yMaxPx);

      ctx.lineWidth = borderWidth;
      ctx.strokeStyle = borderColor;
      ctx.stroke();
    }

    ctx.restore();
  },
};
