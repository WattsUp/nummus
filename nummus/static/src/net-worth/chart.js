const netWorthChart = {
    chart: null,
    ctx: null,
    /**
     * Create Account Chart
     *
     * @param {Object} raw Raw data from accounts controller
     */
    update: function(raw) {
        'use strict';
        const dates = raw.dates;
        const values = raw.total.map(v => Number(v));

        const canvas = document.getElementById('total-chart-canvas');
        const ctx = canvas.getContext('2d');
        if (ctx == this.ctx)
            return chartSingle.update(this.chart, dates, values);
        this.ctx = ctx;

        this.chart = chartSingle.create(ctx, 'total', dates, values);
        return;
    }
}
