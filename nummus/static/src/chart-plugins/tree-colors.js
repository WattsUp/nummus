"use strict";
/**
 * Chart.js plugin to nicely set colors for tree charts
 *
 */
const pluginTreeColor = {
  id: "treeColor",
  charts: {},
  beforeInit: function (chart) {
    const {
      config: {
        data: { datasets },
      },
    } = chart;

    for (const dataset of datasets) {
      let treeValues = Object.values(dataset.tree);
      treeValues.forEach((group) => {
        let sum = 0;
        Object.values(group).forEach((item) => {
          sum += item.value ?? 0;
        });
        group.sum = sum;
      });
      treeValues.sort((a, b) => {
        return b.sum - a.sum;
      });
      treeValues.forEach((group, i) => {
        group.i = i;
      });
    }
  },
  afterInit: function (chart) {
    this.charts[chart.id] = chart;
    this.updateChartColor(chart);
  },
  updateChartColor: function (chart) {
    const base = getThemeColor("primary");
    const baseContainer = getThemeColor("primary-container");
    const onBase = getThemeColor("on-primary");
    const onContainer = getThemeColor("on-surface");

    const {
      config: {
        options,
        data: { datasets },
      },
    } = chart;
    options.elements.treemap.captions.color = onContainer;
    options.elements.treemap.captions.hoverColor = onContainer;

    for (const dataset of datasets) {
      const treeValues = Object.values(dataset.tree);
      treeValues.forEach((group) => {
        const spin = (group.i * 360) / treeValues.length;
        const color = tinycolor(baseContainer).spin(spin).toHexString();
        const hoverColor = tinycolor(base).spin(spin).toHexString();

        group.color = color;
        group.hoverColor = hoverColor;
      });
      dataset.labels.color = onContainer;
      dataset.labels.hoverColor = onBase;
      dataset.backgroundColor = this.backgroundColor;
      dataset.borderColor = this.backgroundColor;
      dataset.hoverBackgroundColor = this.hoverBackgroundColor;
      dataset.hoverBorderColor = this.hoverBorderColor;
    }
  },
  update: function () {
    for (const chart of Object.values(this.charts)) {
      this.updateChartColor(chart);
      chart.update();
    }
  },
  afterDestroy: function (chart) {
    delete this.charts[chart.id];
  },
  backgroundColor: function (context) {
    if (context.type != "data") {
      return "transparent";
    }
    const treeData = context.dataset.tree;
    const obj = context.raw._data;
    const group = obj[0];
    if (obj.name) {
      return treeData[group].color;
    }
    return treeData[group].color + "80";
  },
  hoverBackgroundColor: function (context) {
    if (context.type != "data") {
      return "transparent";
    }
    const treeData = context.dataset.tree;
    const obj = context.raw._data;
    const group = obj[0];
    if (obj.name) {
      return treeData[group].hoverColor;
    }
    return treeData[group].color + "80";
  },
  hoverBorderColor: function (context) {
    if (context.type != "data") {
      return "transparent";
    }
    const treeData = context.dataset.tree;
    const obj = context.raw._data;
    const group = obj[0];
    return treeData[group].hoverColor;
  },
};
