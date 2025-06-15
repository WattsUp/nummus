"use strict";
const netWorth = {
  chartTotal: null,
  chartAssets: null,
  chartLiabilities: null,
  chartPieAssets: null,
  chartPieLiabilities: null,
  /**
   * Create Net Worth Chart
   *
   * @param {Object} raw Raw data from net worth controller
   */
  update: function (raw) {
    const labels = raw.labels;
    const dateMode = raw.date_mode;
    const values = raw.values.map((v) => Number(v));
    const min = raw.min && raw.min.map((v) => Number(v));
    const max = raw.max && raw.max.map((v) => Number(v));
    const accounts = raw.accounts.map((a) => {
      a.values = a.values.map((v) => Number(v));
      return a;
    });

    // If only single day data, duplicate for prettier charts
    if (labels.length == 1) {
      labels.push(labels[0]);
      values.push(values[0]);
      if (min) min.push(min[0]);
      if (max) max.push(max[0]);
      for (const account of accounts) {
        account.values.push(account.values[0]);
      }
    }

    const ticksEnabled = window.screen.width >= 768;

    const width = 62;

    {
      const canvas = document.getElementById("total-chart-canvas");
      const ctx = canvas.getContext("2d");
      const datasets = [];
      if (min == null) {
        const blue = getThemeColor("blue");
        const yellow = getThemeColor("yellow");
        datasets.push({
          type: "line",
          data: values,
          borderColor: getThemeColor("grey-500"),
          borderWidth: 2,
          pointRadius: 0,
          hoverRadius: 0,
          fill: {
            target: "origin",
            above: blue + "80",
            below: yellow + "80",
          },
        });
      } else {
        const grey = getThemeColor("grey-500");
        // Plot average as a line and fill between min/max
        datasets.push({
          label: "Max",
          type: "line",
          data: max,
          borderWidth: 0,
          pointRadius: 0,
          hoverRadius: 0,
          fill: 2,
          backgroundColor: grey + "40",
        });
        datasets.push({
          label: "Average",
          type: "line",
          data: values,
          borderWidth: 2,
          pointRadius: 0,
          hoverRadius: 0,
          borderColor: grey,
        });
        datasets.push({
          label: "Min",
          type: "line",
          data: min,
          borderWidth: 0,
          pointRadius: 0,
          hoverRadius: 0,
        });
      }

      if (this.chartTotal && ctx == this.chartTotal.ctx) {
        nummusChart.update(this.chartTotal, labels, dateMode, datasets);
      } else {
        const plugins = [[pluginFixedAxisWidth, { width: width }]];
        this.chartTotal = nummusChart.create(
          ctx,
          labels,
          dateMode,
          datasets,
          plugins,
          {
            scales: {
              x: {
                ticks: { display: ticksEnabled },
                grid: { drawTicks: ticksEnabled },
              },
            },
          },
        );
      }
    }

    const assets = [];
    const liabilities = [];
    for (let i = 0; i < accounts.length; ++i) {
      const a = accounts[i];
      const c = getChartColor(i);

      assets.push({
        name: a.name,
        rawValues: a.values,
        values: [...a.values].map((v) => Math.max(0, v)),
        color: c,
      });
      liabilities.push({
        name: a.name,
        rawValues: a.values,
        values: [...a.values].map((v) => Math.min(0, v)),
        color: c,
      });
    }
    liabilities.reverse();

    {
      const canvas = document.getElementById("assets-chart-canvas");
      const ctx = canvas.getContext("2d");
      const datasets = nummusChart.datasetsStacked(assets);
      if (this.chartAssets && ctx == this.chartAssets.ctx) {
        nummusChart.update(this.chartAssets, labels, dateMode, datasets);
      } else {
        const plugins = [[pluginFixedAxisWidth, { width: width }]];
        this.chartAssets = nummusChart.create(
          ctx,
          labels,
          dateMode,
          datasets,
          plugins,
          {
            plugins: { tooltip: { enabled: false } },
            scales: {
              x: {
                ticks: { display: ticksEnabled },
                grid: { drawTicks: ticksEnabled },
              },
            },
          },
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
        const plugins = [[pluginFixedAxisWidth, { width: width }]];
        this.chartLiabilities = nummusChart.create(
          ctx,
          labels,
          dateMode,
          datasets,
          plugins,
          {
            plugins: { tooltip: { enabled: false } },

            scales: {
              x: {
                ticks: { display: ticksEnabled },
                grid: { drawTicks: ticksEnabled },
              },
            },
          },
        );
      }
    }

    {
      const breakdown = document.getElementById("assets-breakdown");
      if (this.chartPieAssets)
        pluginHoverHighlight.removeListeners(this.chartPieAssets);
      this.createBreakdown(breakdown, assets, false);
    }

    {
      const breakdown = document.getElementById("liabilities-breakdown");
      if (this.chartPieLiabilities)
        pluginHoverHighlight.removeListeners(this.chartPieLiabilities);
      this.createBreakdown(breakdown, liabilities, true);
    }

    {
      const canvas = document.getElementById("assets-pie-chart-canvas");
      const ctx = canvas.getContext("2d");
      if (this.chartPieAssets && ctx == this.chartPieAssets.ctx) {
        nummusChart.updatePie(this.chartPieAssets, assets);
        pluginHoverHighlight.addListeners(this.chartPieAssets);
      } else {
        const plugins = [
          [pluginHoverHighlight, { parent: "assets-breakdown", scroll: false }],
        ];
        this.chartPieAssets = nummusChart.createPie(ctx, assets, plugins);
      }
    }

    {
      const canvas = document.getElementById("liabilities-pie-chart-canvas");
      const ctx = canvas.getContext("2d");
      if (this.chartPieLiabilities && ctx == this.chartPieLiabilities.ctx) {
        nummusChart.updatePie(this.chartPieLiabilities, liabilities);
        pluginHoverHighlight.addListeners(this.chartPieLiabilities);
      } else {
        const plugins = [
          [
            pluginHoverHighlight,
            { parent: "liabilities-breakdown", scroll: false },
          ],
        ];
        this.chartPieLiabilities = nummusChart.createPie(
          ctx,
          liabilities,
          plugins,
        );
      }
    }
  },
  /**
   * Create breakdown table
   *
   * @param {DOMElement} parent Parent table element
   * @param {Array} accounts Array of account objects
   * @param {Boolean} negative True will skip non-negative, False will skip
   *     negative accounts
   */
  createBreakdown: function (parent, accounts, negative) {
    parent.innerHTML = "";
    for (const account of accounts) {
      const v = account.rawValues[account.rawValues.length - 1];
      if ((v < 0) ^ negative) continue;

      const row = document.createElement("div");
      row.classList.add("flex");

      const square = document.createElement("div");
      square.style.height = "24px";
      square.style.width = "24px";
      square.style.background = account.color + "80";
      square.style.border = `1px solid ${account.color}`;
      square.style.marginRight = "2px";
      row.appendChild(square);

      const name = document.createElement("div");
      name.innerHTML = account.name;
      name.classList.add("grow");
      row.appendChild(name);

      const value = document.createElement("div");
      value.innerHTML = formatterF2.format(v);
      row.appendChild(value);

      parent.appendChild(row);
    }
  },
  /**
   * Create Net Worth Dashboard Chart
   *
   * @param {Object} raw Raw data from net worth controller
   */
  updateDashboard: function (raw) {
    const labels = raw.labels;
    const dateMode = raw.date_mode;
    const total = raw.total.map((v) => Number(v));

    const blue = getThemeColor("blue");
    const yellow = getThemeColor("yellow");

    const canvas = document.getElementById("net-worth-chart-canvas-dashboard");
    const ctx = canvas.getContext("2d");
    const dataset = {
      label: "Total",
      type: "line",
      data: total,
      borderColor: getThemeColor("grey-500"),
      borderWidth: 2,
      pointRadius: 0,
      hoverRadius: 0,
      fill: {
        target: "origin",
        above: blue + "80",
        below: yellow + "80",
      },
    };
    if (this.chartTotal && ctx == this.chartTotal.ctx) {
      nummusChart.update(this.chartTotal, labels, dateMode, [dataset]);
    } else {
      this.chartTotal = nummusChart.create(
        ctx,
        labels,
        dateMode,
        [dataset],
        null,
        {
          scales: {
            x: { ticks: { callback: formatDateTicksMonths } },
            y: { ticks: { display: false }, grid: { drawTicks: false } },
          },
        },
      );
    }
  },
};
