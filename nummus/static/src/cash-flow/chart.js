const cashFlowChart = {
    chartTotal: null,
    chartIncome: null,
    chartExpenses: null,
    chartPieIncome: null,
    chartPieExpenses: null,
    ctxTotal: null,
    ctxIncome: null,
    ctxExpenses: null,
    ctxPieIncome: null,
    ctxPieExpenses: null,
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
        const incomesCategorized = raw.incomes_categorized.map(a => {
            a.amount = Number(a.amount);
            return a;
        });
        const expensesCategorized = raw.expenses_categorized.map(a => {
            a.amount = -Number(a.amount);
            return a;
        });
        console.log(chartBars);
        console.log(labels);
        console.log(totals);
        console.log(incomes);
        console.log(expenses);
        console.log(incomesCategorized);
        console.log(expensesCategorized);

        const width = 65;

        {
            const canvas = document.getElementById('cash-flow-chart-canvas');
            const ctx = canvas.getContext('2d');
            if (ctx == this.ctxTotal) {
                chartSingle.update(this.chartTotal, dates, values);
            } else {
                const plugins = [
                    [pluginFixedAxisWidth, {width: width}],
                ];
                this.ctxTotal = ctx;
                this.chartTotal = chartSingle.create(
                    ctx,
                    'cash-flow',
                    dates,
                    values,
                    plugins,
                );
            }
        }
    },
}
