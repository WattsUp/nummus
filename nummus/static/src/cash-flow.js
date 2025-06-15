"use strict";
const cashFlow = {
  chartTotal: null,
  chartIncome: null,
  chartExpense: null,
  chartPieIncome: null,
  chartPieExpense: null,
  chartPieIncomeTag: null,
  chartPieExpenseTag: null,
  /**
   * Create Cash Flow Chart
   *
   * @param {Object} raw Raw data from cash flow controller
   */
  update: function (raw) {
    // Import data, Strings to Numbers
    const chartBars = raw.chart_bars;
    const labels = raw.labels;
    const dateMode = raw.date_mode;
    const totals = raw.totals.map((v) => Number(v));
    const incomes = raw.incomes.map((v) => Number(v));
    const expenses = raw.expenses.map((v) => Number(v));
    const incomeCategorized = raw.income_categorized.map((a) => {
      a.amount = Number(a.amount);
      return a;
    });
    const expenseCategorized = raw.expense_categorized.map((a) => {
      a.amount = -Number(a.amount);
      return a;
    });
    const incomeTagged = raw.income_tagged.map((a) => {
      a.amount = Number(a.amount);
      return a;
    });
    const expenseTagged = raw.expense_tagged.map((a) => {
      a.amount = -Number(a.amount);
      return a;
    });

    // Set a color for each category
    incomeCategorized.forEach((a, i) => {
      const c = getChartColor(i);
      a.color = c;
    });
    expenseCategorized.forEach((a, i) => {
      const c = getChartColor(i);
      a.color = c;
    });

    // Set a color for each tag
    incomeTagged.forEach((a, i) => {
      const c = getChartColor(i);
      a.color = c;
    });
    expenseTagged.forEach((a, i) => {
      const c = getChartColor(i);
      a.color = c;
    });

    if (this.chartBars != chartBars) {
      // Destroy all existing charts
      if (this.chartTotal) this.chartTotal.destroy();
      if (this.chartIncome) this.chartIncome.destroy();
      if (this.chartExpense) this.chartExpense.destroy();

      this.ctxTotal = null;
      this.ctxIncome = null;
      this.ctxExpense = null;
      this.chartTotal = null;
      this.chartIncome = null;
      this.chartExpense = null;
    }
    const green = getThemeColor("green");
    const red = getThemeColor("red");
    const datasetIncome = {
      label: "Income",
      type: chartBars ? "bar" : "line",
      data: incomes,
      backgroundColor: green,
      borderColor: green,
      borderWidth: chartBars ? 0 : 2,
      pointRadius: 0,
      hoverRadius: 0,
    };
    const datasetExpense = {
      label: "Expense",
      type: chartBars ? "bar" : "line",
      data: expenses,
      backgroundColor: red,
      borderColor: red,
      borderWidth: chartBars ? 0 : 2,
      pointRadius: 0,
      hoverRadius: 0,
    };

    const ticksEnabled = window.screen.width >= 768;

    {
      const canvas = document.getElementById("cash-flow-chart-canvas");
      const ctx = canvas.getContext("2d");
      const datasets = chartBars ? [datasetIncome, datasetExpense] : [];
      datasets.push({
        label: "Total",
        type: "line",
        data: totals,
        borderColor: getThemeColor("grey-500"),
        borderWidth: 2,
        borderDash: chartBars ? [5] : [10, 0],
        pointRadius: 0,
        hoverRadius: 0,
        order: -1,
        fill: chartBars
          ? null
          : {
              target: "origin",
              above: green + "80",
              below: red + "80",
            },
      });
      if (this.chartTotal && ctx == this.chartTotal.ctx) {
        nummusChart.update(this.chartTotal, labels, dateMode, datasets);
      } else {
        this.chartTotal = nummusChart.create(
          ctx,
          labels,
          dateMode,
          datasets,
          null,
          {
            scales: {
              x: {
                stacked: true,
                ticks: { display: ticksEnabled },
                grid: { drawTicks: ticksEnabled },
              },
            },
          },
        );
      }
    }

    {
      const breakdown = document.getElementById("income-breakdown");
      if (this.chartPieIncome)
        pluginHoverHighlight.removeListeners(this.chartPieIncome);
      this.createBreakdown(breakdown, incomeCategorized);
    }

    {
      const breakdown = document.getElementById("expense-breakdown");
      if (this.chartPieExpense)
        pluginHoverHighlight.removeListeners(this.chartPieExpense);
      this.createBreakdown(breakdown, expenseCategorized);
    }

    {
      const breakdown = document.getElementById("income-tag-breakdown");
      if (this.chartPieIncomeTag)
        pluginHoverHighlight.removeListeners(this.chartPieIncomeTag);
      this.createBreakdown(breakdown, incomeTagged);
    }

    {
      const breakdown = document.getElementById("expense-tag-breakdown");
      if (this.chartPieExpenseTag)
        pluginHoverHighlight.removeListeners(this.chartPieExpenseTag);
      this.createBreakdown(breakdown, expenseTagged);
    }

    {
      const canvas = document.getElementById("income-pie-chart-canvas");
      const ctx = canvas.getContext("2d");
      if (this.chartPieIncome && ctx == this.chartPieIncome.ctx) {
        nummusChart.updatePie(this.chartPieIncome, incomeCategorized);
        pluginHoverHighlight.addListeners(this.chartPieIncome);
      } else {
        const plugins = [
          [pluginHoverHighlight, { parent: "income-breakdown" }],
        ];
        this.chartPieIncome = nummusChart.createPie(
          ctx,
          incomeCategorized,
          plugins,
        );
      }
    }

    {
      const canvas = document.getElementById("expense-pie-chart-canvas");
      const ctx = canvas.getContext("2d");
      if (this.chartPieExpense && ctx == this.chartPieExpense.ctx) {
        nummusChart.updatePie(this.chartPieExpense, expenseCategorized);
        pluginHoverHighlight.addListeners(this.chartPieExpense);
      } else {
        const plugins = [
          [pluginHoverHighlight, { parent: "expense-breakdown" }],
        ];
        this.chartPieExpense = nummusChart.createPie(
          ctx,
          expenseCategorized,
          plugins,
        );
      }
    }

    {
      const canvas = document.getElementById("income-tag-pie-chart-canvas");
      const ctx = canvas.getContext("2d");
      if (this.chartPieIncomeTag && ctx == this.chartPieIncomeTag.ctx) {
        nummusChart.updatePie(this.chartPieIncomeTag, incomeTagged);
        pluginHoverHighlight.addListeners(this.chartPieIncomeTag);
      } else {
        const plugins = [
          [pluginHoverHighlight, { parent: "income-tag-breakdown" }],
        ];
        this.chartPieIncomeTag = nummusChart.createPie(
          ctx,
          incomeTagged,
          plugins,
        );
      }
    }

    {
      const canvas = document.getElementById("expense-tag-pie-chart-canvas");
      const ctx = canvas.getContext("2d");
      if (this.chartPieExpenseTag && ctx == this.chartPieExpenseTag.ctx) {
        nummusChart.updatePie(this.chartPieExpenseTag, expenseTagged);
        pluginHoverHighlight.addListeners(this.chartPieExpenseTag);
      } else {
        const plugins = [
          [pluginHoverHighlight, { parent: "expense-tag-breakdown" }],
        ];
        this.chartPieExpenseTag = nummusChart.createPie(
          ctx,
          expenseTagged,
          plugins,
        );
      }
    }

    this.chartBars = chartBars;
  },
  /**
   * Create breakdown table
   *
   * @param {DOMElement} parent Parent table element
   * @param {Array} categories Array of category objects
   */
  createBreakdown: function (parent, categories) {
    parent.innerHTML = "";
    for (const category of categories) {
      const v = category.amount;

      const row = document.createElement("div");
      row.classList.add("flex");

      const square = document.createElement("div");
      square.style.height = "24px";
      square.style.width = "24px";
      square.style.background = category.color + "80";
      square.style.border = `1px solid ${category.color}`;
      square.style.marginRight = "2px";
      square.style.flexShrink = "0";
      row.appendChild(square);

      const name = document.createElement("div");
      if (category.emoji) name.innerHTML = `${category.emoji} ${category.name}`;
      else name.innerHTML = category.name;
      name.classList.add("grow");
      name.classList.add("truncate");
      row.appendChild(name);

      const value = document.createElement("div");
      value.innerHTML = formatterF2.format(v);
      value.style.paddingLeft = "4px";
      row.appendChild(value);

      parent.appendChild(row);
    }
  },
  /**
   * Create Emergency Fund Dashboard Chart
   *
   * @param {Object} raw Raw data from emergency fund controller
   */
  updateDashboard: function (raw) {
    // Always chartBars
    const labels = raw.labels;
    const dateMode = raw.date_mode;
    const totals = raw.totals.map((v) => Number(v));
    const incomes = raw.incomes.map((v) => Number(v));
    const expenses = raw.expenses.map((v) => Number(v));

    const green = getThemeColor("green");
    const red = getThemeColor("red");

    const canvas = document.getElementById("cash-flow-chart-canvas-dashboard");
    const ctx = canvas.getContext("2d");
    const datasets = [
      {
        label: "Income",
        type: "bar",
        data: incomes,
        backgroundColor: green,
        borderWidth: 0,
        pointRadius: 0,
        hoverRadius: 0,
      },
      {
        label: "Expense",
        type: "bar",
        data: expenses,
        backgroundColor: red,
        borderWidth: 0,
        pointRadius: 0,
        hoverRadius: 0,
      },
      {
        label: "Total",
        type: "line",
        data: totals,
        borderColor: getThemeColor("grey-500"),
        borderWidth: 2,
        borderDash: [5],
        pointRadius: 0,
        hoverRadius: 0,
        order: -1,
      },
    ];
    if (this.chartTotal) this.chartTotal.destroy();
    this.chartTotal = nummusChart.create(
      ctx,
      labels,
      dateMode,
      datasets,
      null,
      {
        scales: {
          x: {
            ticks: { callback: formatDateTicksMonths },
            stacked: true,
          },
          y: { ticks: { display: false }, grid: { drawTicks: false } },
        },
      },
    );
  },
};
