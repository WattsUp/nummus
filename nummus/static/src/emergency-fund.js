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

    const canvas = document.getElementById("e-fund-chart-canvas");
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
        x: { ticks: { callback: formatDateTicksMonths } },
      },
    });
  },
  /**
   * Create Emergency Fund Dashboard Chart
   *
   * @param {Object} raw Raw data from emergency fund controller
   */
  updateDashboard: function (raw) {
    const labels = raw.labels;
    const dateMode = raw.date_mode;
    const values = raw.balances.map((v) => Number(v));
    const spendingLower = raw.spending_lower.map((v) => Number(v));
    const spendingUpper = raw.spending_upper.map((v) => Number(v));

    const green = getThemeColor("green");
    const blue = getThemeColor("blue");
    const yellow = getThemeColor("yellow");

    const canvas = document.getElementById("e-fund-chart-canvas-dashboard");
    const ctx = canvas.getContext("2d");
    const datasets = [
      {
        label: "Balance",
        type: "line",
        data: values,
        borderColor: getThemeColor("grey-500"),
        backgroundColor: blue + "80",
        borderWidth: 2,
        pointRadius: 0,
        hoverRadius: 0,
        fill: {
          target: "origin",
          above: blue + "80",
          below: yellow + "80",
        },
      },
      {
        label: "3-Month Spending",
        type: "line",
        data: spendingLower,
        borderColor: green,
        backgroundColor: green + "80",
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
        borderColor: green,
        backgroundColor: green + "80",
        borderWidth: 2,
        pointRadius: 0,
        hoverRadius: 0,
      },
    ];
    if (this.chart) this.chart.destroy();
    this.ctx = ctx;
    this.chart = nummusChart.create(ctx, labels, null, datasets, null, {
      scales: {
        x: { ticks: { callback: formatDateTicksMonths } },
        y: { ticks: { display: false }, grid: { drawTicks: false } },
      },
    });
  },
};
