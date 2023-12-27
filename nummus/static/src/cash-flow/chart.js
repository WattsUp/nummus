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
        const dates = raw.dates;
        const values = raw.total.map(v => Number(v));
        const incomes_categorized = raw.incomes_categorized.map(a => {
            a.amount = Number(a.amount);
            return a;
        });
        const expenses_categorized = raw.expenses_categorized.map(a => {
            a.amount = Number(a.amount);
            return a;
        });
        console.log(incomes_categorized);
        console.log(expenses_categorized);

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
