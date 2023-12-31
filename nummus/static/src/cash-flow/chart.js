const cashFlowChart = {
    chartTotal: null,
    chartIncome: null,
    chartExpense: null,
    chartPieIncome: null,
    chartPieExpense: null,
    ctxTotal: null,
    ctxIncome: null,
    ctxExpense: null,
    ctxPieIncome: null,
    ctxPieExpense: null,
    /**
     * Create Cash Flow Chart
     *
     * @param {Object} raw Raw data from cash flow controller
     */
    update: function(raw) {
        'use strict';
        const chartBars = raw.chart_bars;
        const labels = raw.labels;
        const totals = raw.totals.map(v => Number(v));
        const incomes = raw.incomes.map(v => Number(v));
        const expenses = raw.expenses.map(v => Number(v));
        const incomeCategorized = raw.income_categorized.map(a => {
            a.amount = Number(a.amount);
            return a;
        });
        const expenseCategorized = raw.expense_categorized.map(a => {
            a.amount = -Number(a.amount);
            return a;
        });
        console.log(chartBars);
        console.log(labels);
        console.log(totals);
        console.log(incomes);
        console.log(expenses);

        incomeCategorized.sort((a, b) => {
            return b.amount - a.amount;
        });
        expenseCategorized.sort((a, b) => {
            return b.amount - a.amount;
        });

        incomeCategorized.forEach((a, i) => {
            const c = getChartColor(i);
            a.color = c;
        });
        expenseCategorized.forEach((a, i) => {
            const c = getChartColor(i);
            a.color = c;
        });

        const width = 65;

        {
            const canvas = document.getElementById('cash-flow-chart-canvas');
            const ctx = canvas.getContext('2d');
            if (ctx == this.ctxTotal) {
                chartSingle.update(this.chartTotal, labels, totals);
            } else {
                const plugins = [
                    [pluginFixedAxisWidth, {width: width}],
                ];
                this.ctxTotal = ctx;
                this.chartTotal = chartSingle.create(
                    ctx,
                    'cash-flow',
                    labels,
                    totals,
                    plugins,
                );
            }
        }

        {
            const canvas = document.getElementById('income-pie-chart-canvas');
            const ctx = canvas.getContext('2d');
            if (ctx == this.ctxPieIncome) {
                chartPie.update(this.chartPieIncome, incomeCategorized);
            } else {
                this.ctxPieIncome = ctx;
                this.chartPieIncome = chartPie.create(ctx, incomeCategorized);
            }
        }

        {
            const canvas = document.getElementById('expense-pie-chart-canvas');
            const ctx = canvas.getContext('2d');
            if (ctx == this.ctxPieExpense) {
                chartPie.update(this.chartPieExpense, expenseCategorized);
            } else {
                this.ctxPieExpense = ctx;
                this.chartPieExpense = chartPie.create(ctx, expenseCategorized);
            }
        }

        {
            const breakdown = document.getElementById('income-breakdown');
            this.createBreakdown(breakdown, incomeCategorized);
        }

        {
            const breakdown = document.getElementById('expense-breakdown');
            this.createBreakdown(breakdown, expenseCategorized);
        }
    },
    /**
     * Create breakdown table
     *
     * @param {DOMElement} parent Parent table element
     * @param {Array} categories Array of category objects
     */
    createBreakdown: function(parent, categories) {
        parent.innerHTML = '';
        for (const category of categories) {
            const v = category.amount;
            // TODO (WattsUp): Make these links to filtered matching
            // transactions

            // TODO (WattsUp): Synchronize hovering pie chart and breakdown
            // on other pages too

            const row = document.createElement('div');
            row.classList.add('flex');

            const square = document.createElement('div');
            square.style.height = '24px'
            square.style.width = '24px'
            square.style.background = category.color + '80';
            square.style.border = `1px solid ${category.color}`;
            square.style.marginRight = '2px';
            square.style.flexShrink = '0';
            row.appendChild(square);

            const name = document.createElement('div');
            name.innerHTML = category.name;
            name.classList.add('grow');
            name.classList.add('truncate');
            row.appendChild(name);

            const value = document.createElement('div');
            value.innerHTML = formatterF2.format(v);
            value.style.paddingLeft = '4px';
            row.appendChild(value);

            parent.appendChild(row);
        }
    },
}
