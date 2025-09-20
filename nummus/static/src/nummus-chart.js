"use strict";
/**
 * Charts creator and updater for nummus
 *
 */
const nummusChart = {
  /**
   * Create a new chart
   *
   * @param {Object} ctx Canvas context to use
   * @param {Array} labels Array of labels
   * @param {String} dateMode Mode of date tick formatter
   * @param {Array} datasets Array of datasets
   * @param {Array} plugins Array of plugins
   * @param {Object} options override
   * @return {Object} Chart object
   */
  create: function (ctx, labels, dateMode, datasets, plugins, options) {
    setChartDefaults();

    // If only single day data, duplicate for prettier charts
    if (labels.length == 1) {
      labels.push(labels[0]);
      datasets.forEach((d) => {
        d.data.push(d.data[0]);
      });
    }

    const pluginObjects = [pluginColor];
    const pluginOptions = {
      legend: {
        display: false,
      },
      tooltip: {
        intersect: false,
        mode: "index",
        enabled: window.screen.width >= 768,
        filter: function (context) {
          return context.dataset.label != null;
        },
        callbacks: {
          label: function (context) {
            let label = context.dataset.label || "";
            if (label) label += ": ";
            if (context.parsed.y != null)
              label += formatterF2.format(context.parsed.y);
            return label;
          },
          labelColor: function (context) {
            const dataset = context.dataset;
            let color = {
              borderColor: dataset.borderColor,
              // Remove opacity
              backgroundColor: dataset.backgroundColor.slice(0, 7),
              borderWidth: 1,
            };
            // Only do this if only one dataset, if multiple,
            // default is fine
            if (context.chart.data.datasets.length != 1) return color;
            if (dataset.fill && dataset.fill.above && dataset.fill.below) {
              color.backgroundColor =
                context.raw >= 0 ? dataset.fill.above : dataset.fill.below;
            }
            return color;
          },
        },
      },
    };
    if (plugins) {
      for (const item of plugins) {
        const plugin = item[0];
        pluginObjects.push(plugin);
        pluginOptions[plugin.id] = item[1];
      }
    }

    options = merge(
      {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            grid: {
              display: true,
            },
            ticks: {
              callback: formatDateTicks,
              dateMode: dateMode,
            },
          },
          y: {
            ticks: {
              callback: formatMoneyTicks,
              precision: 0,
            },
          },
        },
        plugins: pluginOptions,
      },
      options ?? {},
    );

    return new Chart(ctx, {
      data: { labels: labels, datasets: datasets },
      options: options,
      plugins: pluginObjects,
    });
  },
  /**
   * Update existing chart
   *
   * @param {Object} chart Chart object
   * @param {Array} labels Array of labels
   * @param {String} dateMode Mode of date tick formatter
   * @param {Array} values Array of values
   */
  update: function (chart, labels, dateMode, datasets) {
    chart.data.labels = labels;
    if (chart.data.datasets.length == datasets.length) {
      for (let i = 0; i < datasets.length; ++i) {
        chart.data.datasets[i].data = datasets[i].data;
      }
    } else {
      chart.data.datasets = datasets;
    }
    chart.config.options.scales.x.ticks.dateMode = dateMode;
    pluginColor.updateChartColor(chart);
    chart.update();
  },
  /**
   * Prepare stacked chart datasets
   *
   * @param {Array} sources Array of sources [{values:, color:}, ...]
   * @return {Array} datasets
   */
  datasetsStacked: function (sources) {
    const datasets = [];
    const n = sources[0].values.length;
    let values = new Array(n).fill(0);
    let first = true;
    for (const source of sources) {
      // Skip if every value is zero
      if (source.values.every((v) => v == 0)) continue;
      for (let i = 0; i < n; ++i) values[i] += source.values[i];
      datasets.push({
        label: source.name,
        type: "line",
        data: [...values],
        dataRaw: source.values,
        borderColorRaw: "primary",
        backgroundColorRaw: ["primary-container", "80"],
        colorSpin: source.colorSpin,
        borderWidth: 1,
        pointRadius: 0,
        hoverRadius: 0,
        fill: first ? "origin" : "-1",
      });
      first = false;
    }
    return datasets;
  },
  /**
   * Prepare pie datasets
   *
   * @param {Array} sources Array of sources [{values:, color:}, ...]
   * @return {Object} Object with the following keys
   * @return {Array} datasets
   * @return {Number} total of all sources
   */
  datasetsPie: function (sources) {
    const labels = [];
    const datasets = [];

    const data = [];
    const colors = [];
    const backgroundColors = [];
    const spins = [];

    let total = 0;
    let nCollapse = sources.filter((item) => item.collapse).length;

    let totalOther = 0;

    for (const source of sources) {
      const value = source.amount ?? source.values[source.values.length - 1];
      total += value;
      if (nCollapse > 1 && source.collapse) {
        totalOther += value;
      } else {
        data.push(value);
        labels.push(source.name);
        colors.push(source.borderColorRaw);
        backgroundColors.push(source.backgroundColorRaw);
        spins.push(source.colorSpin);
      }
    }
    if (totalOther) {
      data.push(totalOther);
      labels.push("Other");
      colors.push("outline");
      backgroundColors.push("surface-container-high");
      spins.push(null);
    }
    datasets.push({
      data: data,
      borderWidth: 1,
      borderColorRaw: colors,
      backgroundColorRaw: backgroundColors,
      colorSpin: spins,
      total: total,
    });
    return {
      labels: labels,
      datasets: datasets,
      total: total,
    };
  },
  /**
   * Create a new pie chart
   *
   * @param {Object} ctx Canvas context to use
   * @param {Array} sources Array of sources [values0, values1, ...]
   * @param {Array} plugins Array of plugins
   * @param {Object} options override
   * @return {Object} Chart object
   */
  createPie: function (ctx, sources, plugins, options) {
    setChartDefaults();

    const { labels, datasets, total } = this.datasetsPie(sources);

    const pluginObjects = [pluginColor, pluginDoughnutText];
    const pluginOptions = {
      legend: {
        display: false,
      },
      tooltip: {
        enabled: true,
        callbacks: {
          label: function (context) {
            let label = context.dataset.label || "";
            if (label) label += ": ";
            if (context.parsed != null) {
              label += formatterF2.format(context.parsed);
              const percent = (context.parsed / context.dataset.total) * 100;
              label += ` (${percent.toFixed(1)}%)`;
            }
            return label;
          },
        },
      },
      doughnutText: {
        text: formatterF0.format(total),
        font: "'liberation-sans', 'sans-serif'",
      },
    };
    if (plugins) {
      for (const plugin of plugins) {
        pluginObjects.push(plugin);
      }
    }

    options = merge(
      {
        responsive: true,
        maintainAspectRatio: true,
        plugins: pluginOptions,
      },
      options ?? {},
    );

    return new Chart(ctx, {
      type: "doughnut",
      data: { labels: labels, datasets: datasets },
      options: options,
      plugins: pluginObjects,
    });
  },
  /**
   * Update existing pie chart with a single data source
   *
   * @param {Object} chart Chart object
   * @param {Array} sources Array of sources [values0, values1, ...]
   * @param {String} doughnutText Text to update doughnutText
   */
  updatePie: function (chart, sources, doughnutText) {
    const { labels, datasets, total } = this.datasetsPie(sources);

    if (chart.data.datasets.length == datasets.length) {
      for (let i = 0; i < datasets.length; ++i) {
        chart.data.datasets[i].data = datasets[i].data;
        chart.data.datasets[i].borderColorRaw = datasets[i].borderColorRaw;
        chart.data.datasets[i].backgroundColorRaw =
          datasets[i].backgroundColorRaw;
        chart.data.datasets[i].colorSpin = datasets[i].colorSpin;
        chart.data.datasets[i].total = datasets[i].total;
      }
    } else {
      chart.data.datasets = datasets;
    }
    chart.data.labels = labels;
    chart.config.options.plugins.doughnutText.text =
      doughnutText ?? formatterF0.format(total);
    pluginColor.updateChartColor(chart);
    pluginHoverHighlight.addListeners(chart);
    chart.update();
  },
  /**
   * Create a new tree chart
   *
   * @param {Object} ctx Canvas context to use
   * @param {Array} datasets Array of datasets
   * @param {Array} plugins Array of plugins
   * @param {Object} options override
   * @return {Object} Chart object
   */
  createTree: function (ctx, datasets, plugins, options) {
    setChartDefaults();

    const pluginObjects = [pluginColor, pluginTreeColor, pluginTreeLabel];
    const pluginOptions = {
      legend: {
        display: false,
      },
      tooltip: {
        callbacks: {
          title: function () {
            return "Asset Value";
          },
          label: function (context) {
            const obj = context.raw._data;
            let label = obj.name || obj[0];
            return label + ": " + formatterF2.format(obj.value);
          },
        },
      },
      zoom: {
        pan: {
          enabled: true,
          mode: "xy",
        },
        limits: {
          x: { min: "original", max: "original" },
          y: { min: "original", max: "original" },
        },
        zoom: {
          wheel: { enabled: true },
          pinch: { enabled: true },
          mode: "xy",
        },
      },
    };
    if (plugins) {
      for (const item of plugins) {
        const plugin = item[0];
        pluginObjects.push(plugin);
        pluginOptions[plugin.id] = item[1];
      }
    }

    options = merge(
      {
        responsive: true,
        maintainAspectRatio: false,
        animations: false,
        plugins: pluginOptions,
      },
      options ?? {},
    );

    return new Chart(ctx, {
      type: "treemap",
      data: { datasets: datasets },
      options: options,
      plugins: pluginObjects,
    });
  },
};
