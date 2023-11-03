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

        const canvasTotal = document.getElementById('total-chart-canvas');
        const ctxTotal = canvasTotal.getContext('2d');
        if (ctxTotal == this.ctxTotal) {
            chartSingle.update(this.chartTotal, dates, values);
        } else {
            this.ctxTotal = ctxTotal;
            this.chartTotal =
                chartSingle.create(ctxTotal, 'total', dates, values);
        }

        const assets = [];
        const liabilities = [];
        const valuesAssets = [];
        const valuesLiabilities = [];
        for (const a of accounts) {
            const valuesPos = [...a.values].map(v => Math.max(0, v));
            const valuesNeg = [...a.values].map(v => Math.min(0, v));

            assets.push({
                name: a.name,
                values: valuesPos,
            });
            valuesAssets.push(valuesPos);

            liabilities.push({
                name: a.name,
                values: valuesNeg,
            });
            valuesLiabilities.push(valuesNeg);
        }



        const canvasAssets = document.getElementById('assets-chart-canvas');
        const ctxAssets = canvasAssets.getContext('2d');
        if (ctxAssets == this.ctxAssets) {
            chartSingle.update(
                this.chartAssets,
                dates,
                valuesAssets,
                true,
            );
        } else {
            this.ctxAssets = ctxAssets;
            this.chartAssets = chartStacked.create(
                ctxAssets,
                'assets',
                dates,
                valuesAssets,
                false,
            );
        }

        const canvasLiabilities =
            document.getElementById('liabilities-chart-canvas');
        const ctxLiabilities = canvasLiabilities.getContext('2d');
        if (ctxLiabilities == this.ctxLiabilities) {
            chartSingle.update(
                this.chartLiabilities,
                dates,
                valuesLiabilities,
                true,
            );
        } else {
            this.ctxLiabilities = ctxLiabilities;
            this.chartLiabilities = chartStacked.create(
                ctxLiabilities,
                'liabilities',
                dates,
                valuesLiabilities,
                true,
            );
        }
    },
}
