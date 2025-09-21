"use strict";
const netWorth = {
  chart: null,
  chartAssets: null,
  chartLiabilities: null,
  chartPieAssets: null,
  chartPieLiabilities: null,
  /**
   * Create Net Worth Chart
   *
   * @param {Object} raw Raw data from net worth controller
   * @param {Object} rawAccounts Raw account data from net worth controller
   */
  update: function (raw, rawAccounts) {
    const labels = raw.labels;
    const dateMode = raw.mode;
    const avg = raw.avg.map((v) => Number(v));
    const min = raw.min && raw.min.map((v) => Number(v));
    const max = raw.max && raw.max.map((v) => Number(v));
    const accounts = rawAccounts.map((a) => {
      a.avg = a.avg.map((v) => Number(v));
      return a;
    });

    {
      const canvas = document.getElementById("net-worth-chart-canvas");
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
          fill: {
            target: "origin",
            aboveRaw: ["primary-container", "80"],
            belowRaw: ["error-container", "80"],
          },
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
          order: 1,
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
          order: 0,
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
          order: 2,
        });
      }

      if (this.chart && ctx == this.chart.ctx) {
        nummusChart.update(this.chart, labels, dateMode, datasets);
      } else {
        this.chart = nummusChart.create(ctx, labels, dateMode, datasets);
      }
    }

    const assets = [];
    const liabilities = [];
    for (let i = 0; i < accounts.length; ++i) {
      const a = accounts[i];
      const spin = (i * 300) / accounts.length;

      assets.push({
        name: a.name,
        values: [...a.avg].map((v) => Math.max(0, v)),
        colorSpin: spin,
      });
      liabilities.push({
        name: a.name,
        values: [...a.avg].map((v) => Math.min(0, v)),
        colorSpin: spin,
      });
    }
    liabilities.reverse();

    const options = {
      plugins: {
        tooltip: {
          filter: function (context) {
            return (
              context.dataset.label != null &&
              context.dataset.dataRaw[context.dataIndex]
            );
          },
          callbacks: {
            label: function (context) {
              let label = context.dataset.label || "";
              if (label) label += ": ";
              const y = context.dataset.dataRaw[context.dataIndex];
              if (y != null) label += formatterF2.format(y);
              return label;
            },
          },
        },
      },
    };

    {
      const canvas = document.getElementById("assets-chart-canvas");
      const ctx = canvas.getContext("2d");
      const datasets = nummusChart.datasetsStacked(assets);
      if (this.chartAssets && ctx == this.chartAssets.ctx) {
        nummusChart.update(this.chartAssets, labels, dateMode, datasets);
      } else {
        this.chartAssets = nummusChart.create(
          ctx,
          labels,
          dateMode,
          datasets,
          null,
          options,
        );
      }
    }

    {
      const canvas = document.getElementById("liabilities-chart-canvas");
      const ctx = canvas.getContext("2d");
      const datasets = nummusChart.datasetsStacked(liabilities);
      if (this.chartLiabilities && ctx == this.chartLiabilities.ctx) {
        nummusChart.update(this.chartLiabilities, labels, dateMode, datasets);
      } else {
        this.chartLiabilities = nummusChart.create(
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
  /**
   * Create Net Worth Dashboard Chart
   *
   * @param {Object} raw Raw data from net worth controller
   */
  updateDashboard: function (raw) {
    const labels = raw.labels;
    const dateMode = raw.mode;
    const total = raw.avg.map((v) => Number(v));

    const canvas = document.getElementById("net-worth-chart-canvas-dashboard");
    const ctx = canvas.getContext("2d");
    const dataset = {
      label: "Total",
      type: "line",
      data: total,
      borderColorRaw: "primary",
      backgroundColorRaw: ["primary-container", "80"],
      borderWidth: 2,
      pointRadius: 0,
      hoverRadius: 0,
      fill: true,
    };
    if (this.chart && ctx == this.chart.ctx) {
      nummusChart.update(this.chart, labels, dateMode, [dataset]);
    } else {
      this.chart = nummusChart.create(ctx, labels, dateMode, [dataset], null, {
        scales: {
          y: { ticks: { display: false }, grid: { drawTicks: false } },
        },
      });
    }
  },
};
