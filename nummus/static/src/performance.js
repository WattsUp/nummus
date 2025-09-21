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
    const dateMode = raw.mode;
    const avg = raw.avg.map((v) => Number(v) * 100);
    const min = raw.min && raw.min.map((v) => Number(v) * 100);
    const max = raw.max && raw.max.map((v) => Number(v) * 100);
    const index = raw.index.map((v) => Number(v) * 100);
    const indexName = raw.index_name;
    const indexMin = raw.index_min && raw.index_min.map((v) => Number(v) * 100);
    const indexMax = raw.index_max && raw.index_max.map((v) => Number(v) * 100);
    const mwrr = raw.mwrr && raw.mwrr.map((v) => Number(v) * 100);

    {
      const canvas = document.getElementById("performance-chart-canvas");
      const ctx = canvas.getContext("2d");
      const datasets = [];
      if (min == null) {
        datasets.push({
          label: "Portfolio",
          type: "line",
          data: avg,
          borderColorRaw: "primary",
          backgroundColorRaw: ["primary-container", "80"],
          borderWidth: 2,
          pointRadius: 0,
          hoverRadius: 0,
          fill: true,
        });
        datasets.push({
          label: indexName,
          type: "line",
          data: index,
          borderColorRaw: "tertiary",
          backgroundColorRaw: ["tertiary-container", "80"],
          borderWidth: 2,
          pointRadius: 0,
          hoverRadius: 0,
        });
        datasets.push({
          label: "MWRR Interpolation",
          type: "line",
          data: mwrr,
          borderColorRaw: "secondary",
          backgroundColorRaw: ["secondary-container", "80"],
          borderWidth: 2,
          pointRadius: 0,
          hoverRadius: 0,
        });
      } else {
        // Plot average as a line and fill between min/max
        datasets.push({
          label: "Max",
          type: "line",
          data: max,
          borderColorRaw: "primary",
          backgroundColorRaw: ["primary-container", "80"],
          borderWidth: 0,
          pointRadius: 0,
          hoverRadius: 0,
          fill: 2,
        });
        datasets.push({
          label: "Average",
          type: "line",
          data: avg,
          borderColorRaw: "primary",
          backgroundColorRaw: ["primary-container", "80"],
          borderWidth: 2,
          pointRadius: 0,
          hoverRadius: 0,
        });
        datasets.push({
          label: "Min",
          type: "line",
          data: min,
          borderColorRaw: "primary",
          backgroundColorRaw: ["primary-container", "80"],
          borderWidth: 0,
          pointRadius: 0,
          hoverRadius: 0,
        });
        // Plot average as a line and fill between min/max
        datasets.push({
          label: `${indexName} Max`,
          type: "line",
          data: indexMax,
          borderColorRaw: "tertiary",
          backgroundColorRaw: ["tertiary-container", "80"],
          borderWidth: 0,
          pointRadius: 0,
          hoverRadius: 0,
          fill: 5,
        });
        datasets.push({
          label: `${indexName} Average`,
          type: "line",
          data: index,
          borderColorRaw: "tertiary",
          backgroundColorRaw: ["tertiary-container", "80"],
          borderWidth: 2,
          pointRadius: 0,
          hoverRadius: 0,
        });
        datasets.push({
          label: `${indexName} Min`,
          type: "line",
          data: indexMin,
          borderColorRaw: "tertiary",
          backgroundColorRaw: ["tertiary-container", "80"],
          borderWidth: 0,
          pointRadius: 0,
          hoverRadius: 0,
        });
        datasets.push({
          label: "MWRR Interpolation",
          type: "line",
          data: mwrr,
          borderColorRaw: "secondary",
          backgroundColorRaw: ["secondary-container", "80"],
          borderWidth: 2,
          pointRadius: 0,
          hoverRadius: 0,
        });
      }

      const options = {
        scales: {
          y: { ticks: { callback: formatPercentTicks } },
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
