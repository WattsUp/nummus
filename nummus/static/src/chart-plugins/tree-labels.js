"use strict";
/**
 * Chart.js plugin to nicely set labels for tree charts
 *
 */
const pluginTreeLabel = {
  id: "treeLabel",
  defaults: {
    padding: 2,
  },
  beforeInit: function (chart) {
    const {
      config: {
        options,
        data: { datasets },
      },
    } = chart;
    const {
      plugins: { treeLabels: { padding } = this.defaults },
    } = options;

    const elements = merge(
      {
        treemap: {
          captions: {
            align: "center",
            formatter: this.formatGroup,
          },
        },
      },
      options.elements ?? {},
    );
    options.elements = elements;

    datasets.forEach((dataset) => {
      const labels = merge(
        {
          display: true,
          padding: padding,
          formatter: this.formatItem,
        },
        dataset.labels ?? {},
      );
      dataset.labels = labels;
    });
  },
  formatGroup: function (context) {
    const padding =
      context.dataset.labels.padding + context.dataset.borderWidth;
    const rawObj = context.raw._data;
    if (rawObj.name) {
      return null;
    }
    let group = rawObj[0];
    let label = group;
    const ctx = context.chart.ctx;
    const zoom = context.chart.getZoomLevel();

    const maxWidth = context.raw.w * zoom - padding * 2;
    let width = ctx.measureText(label).width;
    while (group && width >= maxWidth) {
      group = group.slice(0, -1);
      label = group + "...";
      width = ctx.measureText(label).width;
    }
    return label;
  },
  formatItem: function (context) {
    const padding =
      context.dataset.labels.padding + context.dataset.borderWidth;
    const treeData = context.dataset.tree;
    const rawObj = context.raw._data;

    let group = rawObj[0];
    const obj = treeData[group][rawObj.name];
    const ctx = context.chart.ctx;
    const zoom = context.chart.getZoomLevel();

    const maxWidth = context.raw.w * zoom - padding * 2;
    const font = Chart.helpers.toFont(ctx.font);
    const maxLines = Math.floor(
      (context.raw.h * zoom - padding * 2) / font.lineHeight,
    );

    let lines = [obj.ticker, obj.name, formatterF2.format(obj.value)];
    return word_wrap(lines, maxWidth, maxLines, ctx);
  },
};
