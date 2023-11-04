const netWorthChart = {
    chartTotal: null,
    chartAssets: null,
    chartLiabilities: null,
    ctxTotal: null,
    ctxAssets: null,
    ctxLiabilities: null,
    /**
     * Create Account Chart
     *
     * @param {Object} raw Raw data from accounts controller
     */
    update: function(raw) {
        'use strict';
        const dates = raw.dates;
        const values = raw.total.map(v => Number(v));
        const accounts = raw.accounts.map(a => {
            a.values = a.values.map(v => Number(v));
            return a;
        });
        accounts.sort((a, b) => {
            return b.values[b.values.length - 1] -
                a.values[a.values.length - 1];
        });

        const width = 65;

        const canvasTotal = document.getElementById('total-chart-canvas');
        const ctxTotal = canvasTotal.getContext('2d');
        if (ctxTotal == this.ctxTotal) {
            chartSingle.update(this.chartTotal, dates, values);
        } else {
            const plugins = [
                [pluginFixedAxisWidth, {width: width}],
            ];
            this.ctxTotal = ctxTotal;
            this.chartTotal = chartSingle.create(
                ctxTotal,
                'total',
                dates,
                values,
                plugins,
            );
        }

        const assets = [];
        const liabilities = [];
        for (let i = 0; i < accounts.length; ++i) {
            const a = accounts[i];
            const c = getChartColor(i);

            assets.push({
                name: a.name,
                values: [...a.values].map(v => Math.max(0, v)),
                color: c,
            });
            liabilities.push({
                name: a.name,
                values: [...a.values].map(v => Math.min(0, v)),
                color: c,
            });
        }
        liabilities.reverse();

        const canvasAssets = document.getElementById('assets-chart-canvas');
        const ctxAssets = canvasAssets.getContext('2d');
        if (ctxAssets == this.ctxAssets) {
            chartStacked.update(
                this.chartAssets,
                dates,
                assets,
            );
        } else {
            const plugins = [
                [pluginFixedAxisWidth, {width: width}],
            ];
            this.ctxAssets = ctxAssets;
            this.chartAssets = chartStacked.create(
                ctxAssets,
                'assets',
                dates,
                assets,
                plugins,
            );
        }

        const canvasLiabilities =
            document.getElementById('liabilities-chart-canvas');
        const ctxLiabilities = canvasLiabilities.getContext('2d');
        if (ctxLiabilities == this.ctxLiabilities) {
            chartStacked.update(
                this.chartLiabilities,
                dates,
                liabilities,
            );
        } else {
            const plugins = [
                [pluginFixedAxisWidth, {width: width}],
            ];
            this.ctxLiabilities = ctxLiabilities;
            this.chartLiabilities = chartStacked.create(
                ctxLiabilities,
                'liabilities',
                dates,
                liabilities,
                plugins,
            );
        }
    },
}
