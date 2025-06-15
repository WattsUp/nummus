"use strict";
const performance = {
  chart: null,
  /**
   * Create Performance Chart
   *
   * @param {Object} raw Raw data from performance controller
   */
  update: function (raw) {
    const labels = raw.labels;
    const dateMode = raw.date_mode;
    const values = raw.values.map((v) => Number(v) * 100);
    const min = raw.min && raw.min.map((v) => Number(v) * 100);
    const max = raw.max && raw.max.map((v) => Number(v) * 100);
    const index = raw.index.map((v) => Number(v) * 100);
    const indexMin = raw.index_min && raw.index_min.map((v) => Number(v) * 100);
    const indexMax = raw.index_max && raw.index_max.map((v) => Number(v) * 100);

    // If only single day data, duplicate for prettier charts
    if (labels.length == 1) {
      labels.push(labels[0]);
      values.push(values[0]);
      if (min) min.push(min[0]);
      if (max) max.push(max[0]);
      index.push(index[0]);
      if (indexMin) min.push(indexMin[0]);
      if (indexMax) max.push(indexMax[0]);
    }

    const blue = getThemeColor("blue");
    const yellow = getThemeColor("yellow");
    const ticksEnabled = window.screen.width >= 768;

    {
      const canvas = document.getElementById("performance-chart-canvas");
      const ctx = canvas.getContext("2d");
      const datasets = [];
      if (min == null) {
        datasets.push({
          label: "Portfolio",
          type: "line",
          data: values,
          borderColor: blue,
          borderWidth: 2,
          backgroundColor: blue + "80",
          pointRadius: 0,
          hoverRadius: 0,
        });
        datasets.push({
          label: "S&P 500",
          type: "line",
          data: index,
          borderColor: yellow,
          borderWidth: 2,
          backgroundColor: yellow + "80",
          pointRadius: 0,
          hoverRadius: 0,
        });
      } else {
        // Plot average as a line and fill between min/max
        datasets.push({
          label: "Max",
          type: "line",
          data: max,
          borderWidth: 0,
          pointRadius: 0,
          hoverRadius: 0,
          fill: 2,
          borderColor: blue,
          backgroundColor: blue + "40",
        });
        datasets.push({
          label: "Average",
          type: "line",
          data: values,
          borderWidth: 2,
          pointRadius: 0,
          hoverRadius: 0,
          borderColor: blue,
          backgroundColor: blue + "40",
        });
        datasets.push({
          label: "Min",
          type: "line",
          data: min,
          borderWidth: 0,
          pointRadius: 0,
          hoverRadius: 0,
          borderColor: blue,
          backgroundColor: blue + "40",
        });
        // Plot average as a line and fill between min/max
        datasets.push({
          label: "S&P 500 Max",
          type: "line",
          data: indexMax,
          borderWidth: 0,
          pointRadius: 0,
          hoverRadius: 0,
          fill: 5,
          borderColor: yellow,
          backgroundColor: yellow + "40",
        });
        datasets.push({
          label: "S&P 500 Average",
          type: "line",
          data: index,
          borderWidth: 2,
          pointRadius: 0,
          hoverRadius: 0,
          borderColor: yellow,
          backgroundColor: yellow + "40",
        });
        datasets.push({
          label: "S&P 500 Min",
          type: "line",
          data: indexMin,
          borderWidth: 0,
          pointRadius: 0,
          hoverRadius: 0,
          borderColor: yellow,
          backgroundColor: yellow + "40",
        });
      }

      const options = {
        scales: {
          x: {
            ticks: { display: ticksEnabled },
            grid: { drawTicks: ticksEnabled },
          },
          y: {
            ticks: {
              callback: formatPercentTicks,
              precision: 0,
            },
            grid: {
              color: (ctx) =>
                ctx.tick.value == 0 ? "black" : "rgba(0,0,0,0.1)",
            },
          },
        },
        plugins: {
          tooltip: {
            callbacks: {
              label: function (context) {
                let label = context.dataset.label || "";
                if (label) label += ": ";
                if (context.parsed.y != null)
                  label += `${context.parsed.y.toFixed(1)}%`;
                return label;
              },
            },
          },
        },
      };

      if (this.chart && ctx == this.chart.ctx) {
        nummusChart.update(this.chart, labels, dateMode, datasets);
      } else {
        this.chart = nummusChart.create(
          ctx,
          labels,
          dateMode,
          datasets,
          null,
          options,
        );
      }
    }
  },
};
