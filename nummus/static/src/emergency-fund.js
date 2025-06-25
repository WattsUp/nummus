"use strict";
const emergencyFund = {
  chart: null,
  /**
   * Create Emergency Fund Chart
   *
   * @param {Object} raw Raw data from emergency fund controller
   */
  update: function (raw) {
    const labels = raw.labels;
    const dateMode = raw.date_mode;
    const values = raw.balances;
    const spendingLower = raw.spending_lower;
    const spendingUpper = raw.spending_upper;

    const canvas = htmx.find("#e-fund-chart-canvas");
    const ctx = canvas.getContext("2d");
    const datasets = [
      {
        label: "Balance",
        type: "line",
        data: values,
        borderColorRaw: "outline",
        backgroundColorRaw: ["tertiary-container", "80"],
        borderWidth: 2,
        pointRadius: 0,
        hoverRadius: 0,
        fill: {
          target: "origin",
          aboveRaw: ["tertiary-container", "80"],
          belowRaw: ["error-container", "80"],
        },
      },
      {
        label: "3-Month Spending",
        type: "line",
        data: spendingLower,
        borderColorRaw: "primary",
        backgroundColorRaw: ["primary-container", "80"],
        borderWidth: 2,
        pointRadius: 0,
        hoverRadius: 0,
        fill: {
          target: "+1",
        },
      },
      {
        label: "6-Month Spending",
        type: "line",
        data: spendingUpper,
        borderColorRaw: "primary",
        backgroundColorRaw: ["primary-container", "80"],
        borderWidth: 2,
        pointRadius: 0,
        hoverRadius: 0,
      },
    ];
    if (this.chart) this.chart.destroy();
    this.ctx = ctx;
    this.chart = nummusChart.create(ctx, labels, dateMode, datasets);
  },
  /**
   * Create Emergency Fund Dashboard Chart
   *
   * @param {Object} raw Raw data from emergency fund controller
   */
  updateDashboard: function (raw) {
    const labels = raw.labels;
    const dateMode = raw.date_mode;
    const values = raw.balances;
    const spendingLower = raw.spending_lower;
    const spendingUpper = raw.spending_upper;

    const canvas = htmx.find("#e-fund-chart-canvas-dashboard");
    const ctx = canvas.getContext("2d");
    const datasets = [
      {
        label: "Balance",
        type: "line",
        data: values,
        borderColorRaw: "outline",
        backgroundColorRaw: ["tertiary-container", "80"],
        borderWidth: 2,
        pointRadius: 0,
        hoverRadius: 0,
        fill: {
          target: "origin",
          aboveRaw: ["tertiary-container", "80"],
          belowRaw: ["error-container", "80"],
        },
      },
      {
        label: "3-Month Spending",
        type: "line",
        data: spendingLower,
        borderColorRaw: "primary",
        backgroundColorRaw: ["primary-container", "80"],
        borderWidth: 2,
        pointRadius: 0,
        hoverRadius: 0,
        fill: {
          target: "+1",
        },
      },
      {
        label: "6-Month Spending",
        type: "line",
        data: spendingUpper,
        borderColorRaw: "primary",
        backgroundColorRaw: ["primary-container", "80"],
        borderWidth: 2,
        pointRadius: 0,
        hoverRadius: 0,
      },
    ];
    if (this.chart) this.chart.destroy();
    this.ctx = ctx;
    this.chart = nummusChart.create(ctx, labels, dateMode, datasets, null, {
      scales: {
        y: { ticks: { display: false }, grid: { drawTicks: false } },
      },
    });
  },
};
