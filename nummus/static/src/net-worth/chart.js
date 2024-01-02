const netWorthChart = {
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
    update: function(raw) {
        'use strict';
        const labels = raw.labels;
        const dateMode = raw.date_mode;
        const total = raw.total.map(v => Number(v));
        const accounts = raw.accounts.map(a => {
            a.values = a.values.map(v => Number(v));
            return a;
        });

        const blue = getThemeColor('blue');
        const yellow = getThemeColor('yellow');
        const width = 65;

        {
            const canvas = document.getElementById('total-chart-canvas');
            const ctx = canvas.getContext('2d');
            const dataset = {
                label: 'Total',
                type: 'line',
                data: total,
                borderColor: getThemeColor('grey-500'),
                borderWidth: 2,
                pointRadius: 0,
                hoverRadius: 0,
                fill: {
                    target: 'origin',
                    above: blue + '80',
                    below: yellow + '80',
                },
            };
            if (this.chartTotal && ctx == this.chartTotal.ctx) {
                nummusChart.update(
                    this.chartTotal,
                    labels,
                    dateMode,
                    [dataset],
                );
            } else {
                const plugins = [
                    [pluginFixedAxisWidth, {width: width}],
                ];
                this.chartTotal = nummusChart.create(
                    ctx,
                    labels,
                    dateMode,
                    [dataset],
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
            const datasets = nummusChart.datasetsStacked(assets);
            if (this.chartAssets && ctx == this.chartAssets.ctx) {
                nummusChart.update(
                    this.chartAssets,
                    labels,
                    dateMode,
                    datasets,
                );
            } else {
                const plugins = [
                    [pluginFixedAxisWidth, {width: width}],
                ];
                this.chartAssets = nummusChart.create(
                    ctx,
                    labels,
                    dateMode,
                    datasets,
                    plugins,
                    {plugins: {tooltip: {enabled: false}}},
                );
            }
        }

        {
            const canvas = document.getElementById('liabilities-chart-canvas');
            const ctx = canvas.getContext('2d');
            const datasets = nummusChart.datasetsStacked(liabilities);
            if (this.chartLiabilities && ctx == this.chartLiabilities.ctx) {
                nummusChart.update(
                    this.chartLiabilities,
                    labels,
                    dateMode,
                    datasets,
                );
            } else {
                const plugins = [
                    [pluginFixedAxisWidth, {width: width}],
                ];
                this.chartLiabilities = nummusChart.create(
                    ctx,
                    labels,
                    dateMode,
                    datasets,
                    plugins,
                    {plugins: {tooltip: {enabled: false}}},
                );
            }
        }

        {
            const canvas = document.getElementById('assets-pie-chart-canvas');
            const ctx = canvas.getContext('2d');
            if (this.chartPieAssets && ctx == this.chartPieAssets.ctx) {
                nummusChart.updatePie(this.chartPieAssets, assets);
            } else {
                this.chartPieAssets = nummusChart.createPie(ctx, assets);
            }
        }

        {
            const canvas =
                document.getElementById('liabilities-pie-chart-canvas');
            const ctx = canvas.getContext('2d');
            if (this.chartPieLiabilities &&
                ctx == this.chartPieLiabilities.ctx) {
                nummusChart.updatePie(this.chartPieLiabilities, liabilities);
            } else {
                this.chartPieLiabilities =
                    nummusChart.createPie(ctx, liabilities);
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
        const labels = raw.labels;
        const dateMode = raw.date_mode;
        const total = raw.total.map(v => Number(v));

        const blue = getThemeColor('blue');
        const yellow = getThemeColor('yellow');

        const canvas = document.getElementById('net-worth-chart-canvas');
        const ctx = canvas.getContext('2d');
        const dataset = {
            label: 'Total',
            type: 'line',
            data: total,
            borderColor: getThemeColor('grey-500'),
            borderWidth: 2,
            pointRadius: 0,
            hoverRadius: 0,
            fill: {
                target: 'origin',
                above: blue + '80',
                below: yellow + '80',
            },
        };
        if (this.chartTotal && ctx == this.chartTotal.ctx) {
            nummusChart.update(
                this.chartTotal,
                labels,
                dateMode,
                [dataset],
            );
        } else {
            this.chartTotal = nummusChart.create(
                ctx,
                labels,
                dateMode,
                [dataset],
                null,
                {
                    scales: {
                        y: {ticks: {display: false}, grid: {drawTicks: false}},
                    },
                },
            );
        }
    },
}
