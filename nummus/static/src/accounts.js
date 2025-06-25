"use strict";
const accounts = {
  chart: null,
  /**
   * Create Account Chart
   *
   * @param {Object} raw Raw data from accounts controller
   */
  update: function (raw) {
    const labels = raw.labels;
    const dateMode = raw.date_mode;
    const values = raw.values;
    const costBases = raw.cost_bases;
    const minLine = values.map((v, i) => Math.min(v, costBases[i]));

    const canvas = htmx.find("#account-chart-canvas");
    const ctx = canvas.getContext("2d");
    const datasets = [
      {
        label: "Balance",
        type: "line",
        data: values,
        borderColorRaw: "primary",
        backgroundColorRaw: ["primary-container", "80"],
        borderWidth: 2,
        pointRadius: 0,
        hoverRadius: 0,
        fill: {
          target: 1,
          aboveRaw: ["primary-container", "80"],
          belowRaw: ["error-container", "80"],
        },
      },
      {
        label: "Cost Basis",
        type: "line",
        data: costBases,
        borderColorRaw: "outline",
        backgroundColorRaw: ["tertiary-container", "80"],
        borderWidth: 2,
        pointRadius: 0,
        hoverRadius: 0,
      },
      {
        type: "line",
        data: minLine,
        borderWidth: 0,
        pointRadius: 0,
        hoverRadius: 0,
        fill: {
          target: "origin",
          aboveRaw: ["tertiary-container", "80"],
          belowRaw: ["error-container", "80"],
        },
      },
    ];
    if (this.chart) this.chart.destroy();
    this.ctx = ctx;
    this.chart = nummusChart.create(ctx, labels, dateMode, datasets, null, {
      plugins: {
        tooltip: {
          callbacks: {
            footer: function (context) {
              let profit = context[0].raw - context[1].raw;
              return "Return: " + formatterF2.format(profit);
            },
          },
        },
      },
    });
  },
  /**
   * Show remaining assets
   *
   * @param {Element} btn Triggering button
   */
  showAllAssets: function (btn) {
    htmx.addClass(btn, "hidden");
    htmx.removeClass(htmx.find("#account-assets-all"), "hidden");
  },
};
