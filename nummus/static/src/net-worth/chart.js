const netWorthChart = {
    chartTotal: null,
    chartAssets: null,
    chartLiabilities: null,
    chartPieAssets: null,
    chartPieLiabilities: null,
    ctxTotal: null,
    ctxAssets: null,
    ctxLiabilities: null,
    ctxPieAssets: null,
    ctxPieLiabilities: null,
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

        {
            const canvas = document.getElementById('total-chart-canvas');
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
                    'total',
                    dates,
                    values,
                    plugins,
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

        {
            const canvas = document.getElementById('assets-chart-canvas');
            const ctx = canvas.getContext('2d');
            if (ctx == this.ctxAssets) {
                chartStacked.update(
                    this.chartAssets,
                    dates,
                    assets,
                );
            } else {
                const plugins = [
                    [pluginFixedAxisWidth, {width: width}],
                ];
                this.ctxAssets = ctx;
                this.chartAssets = chartStacked.create(
                    ctx,
                    'assets',
                    dates,
                    assets,
                    plugins,
                );
            }
        }

        {
            const canvas = document.getElementById('liabilities-chart-canvas');
            const ctx = canvas.getContext('2d');
            if (ctx == this.ctxLiabilities) {
                chartStacked.update(
                    this.chartLiabilities,
                    dates,
                    liabilities,
                );
            } else {
                const plugins = [
                    [pluginFixedAxisWidth, {width: width}],
                ];
                this.ctxLiabilities = ctx;
                this.chartLiabilities = chartStacked.create(
                    ctx,
                    'liabilities',
                    dates,
                    liabilities,
                    plugins,
                );
            }
        }

        {
            const canvas = document.getElementById('assets-pie-chart-canvas');
            const ctx = canvas.getContext('2d');
            if (ctx == this.ctxPieAssets) {
                chartPie.update(this.chartPieAssets, assets);
            } else {
                this.ctxPieAssets = ctx;
                this.chartPieAssets = chartPie.create(ctx, assets);
            }
        }

        {
            const canvas =
                document.getElementById('liabilities-pie-chart-canvas');
            const ctx = canvas.getContext('2d');
            if (ctx == this.ctxPieLiabilities) {
                chartPie.update(this.chartPieLiabilities, liabilities);
            } else {
                this.ctxPieLiabilities = ctx;
                this.chartPieLiabilities = chartPie.create(ctx, liabilities);
            }
        }
        // TODO(WattsUp): Added data table/legend
    },
}
