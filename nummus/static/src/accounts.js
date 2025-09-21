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
    const dateMode = raw.mode;
    const avg = raw.avg.map((v) => Number(v));
    const costBasis = raw.cost_basis.map((v) => Number(v));
    const minLine = avg.map((v, i) => Math.min(v, costBasis[i]));

    const canvas = htmx.find("#account-chart-canvas");
    const ctx = canvas.getContext("2d");
    const datasets = [
      {
        label: "Balance",
        type: "line",
        data: avg,
        borderColorRaw: "primary",
        backgroundColorRaw: ["primary-container", "80"],
        borderWidth: 2,
        pointRadius: 0,
        hoverRadius: 0,
        fill: {
          target: 1, // cost basis
          aboveRaw: ["primary-container", "80"],
          belowRaw: ["error-container", "80"],
        },
      },
      {
        label: "Cost Basis",
        type: "line",
        data: costBasis,
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
    if (this.chart && ctx == this.chart.ctx) {
      nummusChart.update(this.chart, labels, dateMode, datasets);
    } else {
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
    }
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
  /**
   * On click of delete account, confirm action
   *
   * @param {Event} evt Triggering event
   */
  confirmDelete: function (evt) {
    dialog.confirm(
      "Delete account",
      "Delete",
      () => {
        htmx.trigger(evt.target, "delete");
      },
      "Empty account will be deleted.",
    );
  },
};
