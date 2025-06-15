"use strict";
/**
 * Chart.js plugin to draw a vertical line on hover
 *
 */
const pluginHoverLine = {
  id: "hoverLine",
  afterDatasetsDraw: function (chart) {
    const {
      ctx,
      tooltip,
      chartArea: { top, bottom, left, right },
      data,
      scales,
    } = chart;
    if (tooltip._active.length == 0) {
      return;
    }

    const tt = tooltip._active[0];
    const i = tt.index;

    const date = data.labels[i];
    const values = data.datasets[data.datasets.length - 1].data;
    const value = values[i];
    const change = i == 0 ? 0 : value - values[i - 1];

    const x = Math.min(right - 1, Math.floor(tt.element.x));
    const y = Math.floor(scales.y.getPixelForValue(value));

    const black = getThemeColor("black");
    const white = getThemeColor("white");

    ctx.save();

    // Vertical line
    ctx.beginPath();
    ctx.lineWidth = 1;
    ctx.strokeStyle = black;
    ctx.moveTo(x + 0.5, top);
    ctx.lineTo(x + 0.5, bottom);
    ctx.stroke();

    // Circle at point
    ctx.beginPath();
    ctx.arc(x, y, 6, 0, 2 * Math.PI);
    ctx.fillStyle = white;
    ctx.fill();
    ctx.stroke();

    // Date and value label
    const canvasW = ctx.canvas.clientWidth;
    const canvasH = ctx.canvas.clientHeight;
    const padding = 2;
    ctx.textAlign = "center";
    const valueStr = formatterF2.format(value);
    const metricsDate = ctx.measureText(date);
    const metricsValue = ctx.measureText(valueStr);
    const textW = Math.max(metricsDate.width, metricsValue.width) + padding * 2;
    const fontAscent = metricsDate.fontBoundingBoxAscent;
    const fontDescent = metricsDate.fontBoundingBoxDescent;
    const fontH = fontAscent + fontDescent;
    const textH = fontH * 2 + padding * 2;
    const textX = Math.min(Math.max(x, textW / 2), canvasW - textW / 2);
    const textY = bottom + fontAscent;

    ctx.fillStyle = white;
    ctx.fillRect(textX - textW / 2, bottom + 0.5, textW, canvasH - bottom);

    ctx.fillStyle = black;
    ctx.fillText(date, textX, textY);
    if (value > 0) ctx.fillStyle = getThemeColor("green-600");
    else if (value < 0) ctx.fillStyle = getThemeColor("red-600");
    ctx.fillText(valueStr, textX, textY + fontH);

    ctx.restore();
  },
};
