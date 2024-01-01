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
     * Create Net Worth Chart
     *
     * @param {Object} raw Raw data from net worth controller
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
                rawValues: a.values,
                values: [...a.values].map(v => Math.max(0, v)),
                color: c,
            });
            liabilities.push({
                name: a.name,
                rawValues: a.values,
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

        {
            const breakdown = document.getElementById('assets-breakdown');
            this.createBreakdown(breakdown, assets, false);
        }

        {
            const breakdown = document.getElementById('liabilities-breakdown');
            this.createBreakdown(breakdown, liabilities, true);
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
    createBreakdown: function(parent, accounts, negative) {
        parent.innerHTML = '';
        for (const account of accounts) {
            const v = account.rawValues[account.rawValues.length - 1];
            if (v < 0 ^ negative) continue;

            const row = document.createElement('div');
            row.classList.add('flex');

            const square = document.createElement('div');
            square.style.height = '24px'
            square.style.width = '24px'
            square.style.background = account.color + '80';
            square.style.border = `1px solid ${account.color}`;
            square.style.marginRight = '2px';
            row.appendChild(square);

            const name = document.createElement('div');
            name.innerHTML = account.name;
            name.classList.add('grow');
            row.appendChild(name);

            const value = document.createElement('div');
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
    updateDashboard: function(raw) {
        'use strict';
        const dates = raw.dates;
        const values = raw.total.map(v => Number(v));

        const canvas = document.getElementById('net-worth-chart-canvas');
        const ctx = canvas.getContext('2d');
        if (ctx == this.ctxTotal) {
            chartSingle.update(this.chartTotal, dates, values);
        } else {
            this.ctxTotal = ctx;
            this.chartTotal = chartSingle.create(
                ctx,
                dates,
                values,
                null,
                {
                    scales: {
                        y: {ticks: {display: false}},
                    },
                },
            );
        }
    },
}
