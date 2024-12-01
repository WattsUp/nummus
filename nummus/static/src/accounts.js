'use strict';
const accounts = {
    chart: null,
    chartProfit: null,
    /**
     * Create Account Chart
     *
     * @param {Object} raw Raw data from accounts controller
     */
    update: function(raw) {
        if (nummusChart.pendingSwap) {
            accounts.updateEvent = () => {
                accounts.update(raw);
            };
            document.addEventListener(
                'nummus-chart-after-settle', accounts.updateEvent);
            return;
        }
        if (accounts.updateEvent) {
            document.removeEventListener(
                'nummus-chart-after-settle', accounts.updateEvent);
        }
        const labels = raw.labels;
        const dateMode = raw.date_mode;
        const values = raw.values.map(v => Number(v));
        const min = raw.min && raw.min.map(v => Number(v));
        const max = raw.max && raw.max.map(v => Number(v));
        const profit = raw.profit.map(v => Number(v));
        const profitMin = raw.profit_min && raw.profit_min.map(v => Number(v));
        const profitMax = raw.profit_max && raw.profit_max.map(v => Number(v));

        // If only single day data, duplicate for prettier charts
        if (labels.length == 1) {
            labels.push(labels[0]);
            values.push(values[0]);
            if (min) min.push(min[0]);
            if (max) max.push(max[0]);
            if (profitMin) profitMin.push(profitMin[0]);
            if (profitMax) profitMax.push(profitMax[0]);
        }

        const ticksEnabled = window.screen.width >= 768;

        const width = 65;

        {
            const canvas = document.getElementById('account-chart-canvas');
            const ctx = canvas.getContext('2d');
            const datasets = [];
            if (min == null) {
                const blue = getThemeColor('blue');
                const yellow = getThemeColor('yellow');
                datasets.push({
                    type: 'line',
                    data: values,
                    borderColor: getThemeColor('grey-500'),
                    borderWidth: 2,
                    pointRadius: 0,
                    hoverRadius: 0,
                    fill: {
                        target: 'origin',
                        above: blue + '80',
                        below: yellow + '80',
                    },
                });
            } else {
                const grey = getThemeColor('grey-500');
                // Plot average as a line and fill between min/max
                datasets.push({
                    label: 'Max',
                    type: 'line',
                    data: max,
                    borderWidth: 0,
                    pointRadius: 0,
                    hoverRadius: 0,
                    fill: 2,
                    backgroundColor: grey + '40',
                });
                datasets.push({
                    label: 'Average',
                    type: 'line',
                    data: values,
                    borderWidth: 2,
                    pointRadius: 0,
                    hoverRadius: 0,
                    borderColor: grey,
                });
                datasets.push({
                    label: 'Min',
                    type: 'line',
                    data: min,
                    borderWidth: 0,
                    pointRadius: 0,
                    hoverRadius: 0,
                });
            }
            if (this.chart && ctx == this.chart.ctx) {
                nummusChart.update(this.chart, labels, dateMode, datasets);
            } else {
                const plugins = [
                    [pluginFixedAxisWidth, {width: width}],
                ];
                this.chart = nummusChart.create(
                    ctx,
                    labels,
                    dateMode,
                    datasets,
                    plugins,
                    {
                        scales: {
                            x: {
                                ticks: {display: ticksEnabled},
                                grid: {drawTicks: ticksEnabled}
                            },
                        },
                    },
                );
            }
        }

        {
            const canvas = document.getElementById('profit-chart-canvas');
            const ctx = canvas.getContext('2d');
            const datasets = [];
            if (min == null) {
                const green = getThemeColor('green');
                const red = getThemeColor('red');
                datasets.push({
                    type: 'line',
                    data: profit,
                    borderColor: getThemeColor('grey-500'),
                    borderWidth: 2,
                    pointRadius: 0,
                    hoverRadius: 0,
                    fill: {
                        target: 'origin',
                        above: green + '80',
                        below: red + '80',
                    },
                });
            } else {
                const grey = getThemeColor('grey-500');
                // Plot average as a line and fill between min/max
                datasets.push({
                    label: 'Max',
                    type: 'line',
                    data: profitMax,
                    borderWidth: 0,
                    pointRadius: 0,
                    hoverRadius: 0,
                    fill: 2,
                    backgroundColor: grey + '40',
                });
                datasets.push({
                    label: 'Average',
                    type: 'line',
                    data: profit,
                    borderWidth: 2,
                    pointRadius: 0,
                    hoverRadius: 0,
                    borderColor: grey,
                });
                datasets.push({
                    label: 'Min',
                    type: 'line',
                    data: profitMin,
                    borderWidth: 0,
                    pointRadius: 0,
                    hoverRadius: 0,
                });
            }
            if (this.chartProfit && ctx == this.chartProfit.ctx) {
                nummusChart.update(
                    this.chartProfit, labels, dateMode, datasets);
            } else {
                const plugins = [
                    [pluginFixedAxisWidth, {width: width}],
                ];
                this.chartProfit = nummusChart.create(
                    ctx,
                    labels,
                    dateMode,
                    datasets,
                    plugins,
                    {
                        scales: {
                            x: {
                                ticks: {display: ticksEnabled},
                                grid: {drawTicks: ticksEnabled}
                            },
                        },
                    },
                );
            }
        }
    },
}
