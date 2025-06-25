"use strict";
const assets = {
  chart: null,
  /**
   * Create Asset Chart
   *
   * @param {Object} raw Raw data from assets controller
   */
  update: function (raw) {
    const labels = raw.labels;
    const dateMode = raw.date_mode;
    const values = raw.values;

    const canvas = htmx.find("#asset-chart-canvas");
    const ctx = canvas.getContext("2d");
    const datasets = [
      {
        label: "Value",
        type: "line",
        data: values,
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
      },
    ];
    if (this.chart) this.chart.destroy();
    this.ctx = ctx;
    this.chart = nummusChart.create(ctx, labels, dateMode, datasets);
  },
  /**
   * On change of period select, hide or show date input
   */
  changeTablePeriod: function () {
    const select = htmx.find("#valuation-filters [name='period']");
    const notCustom = select.value != "custom";
    htmx.findAll("#valuation-filters [type='date']").forEach((e) => {
      e.disabled = notCustom;
    });
  },
  /**
   * On click of delete valuation, confirm action
   *
   * @param {Event} evt Triggering event
   */
  confirmDelete: function (evt) {
    dialog.confirm(
      "Delete Valuation",
      "Delete",
      () => {
        htmx.trigger(evt.target, "delete");
      },
      "Valuation will be deleted.",
    );
  },
};
