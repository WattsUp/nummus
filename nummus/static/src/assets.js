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
    const dateMode = raw.mode;
    const avg = raw.avg.map((v) => Number(v));
    const min = raw.min && raw.min.map((v) => Number(v));
    const max = raw.max && raw.max.map((v) => Number(v));

    const canvas = htmx.find("#asset-chart-canvas");
    const ctx = canvas.getContext("2d");
    const datasets = [];
    if (min == null) {
      datasets.push({
        label: "Value",
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
        label: "Min",
        type: "line",
        data: min,
        borderColorRaw: "primary",
        backgroundColorRaw: ["primary-container", "80"],
        borderWidth: 0,
        pointRadius: 0,
        hoverRadius: 0,
      });
    }
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
   * On click of delete asset, confirm action
   *
   * @param {Event} evt Triggering event
   */
  confirmDelete: function (evt) {
    dialog.confirm(
      "Delete asset",
      "Delete",
      () => {
        htmx.trigger(evt.target, "delete");
      },
      "Empty asset will be deleted.",
    );
  },
  /**
   * On click of delete valuation, confirm action
   *
   * @param {Event} evt Triggering event
   */
  confirmDeleteValuation: function (evt) {
    dialog.confirm(
      "Delete valuation",
      "Delete",
      () => {
        htmx.trigger(evt.target, "delete");
      },
      "Valuation will be deleted.",
    );
  },
};
