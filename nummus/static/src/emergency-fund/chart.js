const emergencyFundChart = {
    chart: null,
    /**
     * Create Emergency Fund Chart
     *
     * @param {Object} raw Raw data from emergency fund controller
     */
    update: function(raw) {
        'use strict';
        const labels = raw.labels;
        const dateMode = raw.date_mode;
        const values = raw.balances.map(v => Number(v));
        const targetLow = Number(raw.target_low);
        const targetHigh = Number(raw.target_high);

        const green = getThemeColor('green');
        const blue = getThemeColor('blue');
        const yellow = getThemeColor('yellow');

        const canvas = document.getElementById('e-fund-chart-canvas');
        const ctx = canvas.getContext('2d');
        const dataset = {
            label: 'Balance',
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
        };
        if (this.chart) this.chart.destroy();
        const plugins = [
            [
                pluginBoxAnnotation, {
                    yMin: targetLow,
                    yMax: targetHigh,
                    borderWidth: 0,
                    backgroundColor: green + '80',
                }
            ],
        ];
        this.ctx = ctx;
        this.chart = nummusChart.create(
            ctx,
            labels,
            dateMode,
            [dataset],
            plugins,
        );
    },
    /**
     * Create Emergency Fund Dashboard Chart
     *
     * @param {Object} raw Raw data from emergency fund controller
     */
    updateDashboard: function(raw) {
        'use strict';
        const labels = raw.labels;
        const dateMode = raw.date_mode;
        const values = raw.balances.map(v => Number(v));
        const targetLow = Number(raw.target_low);
        const targetHigh = Number(raw.target_high);

        const green = getThemeColor('green');
        const blue = getThemeColor('blue');
        const yellow = getThemeColor('yellow');

        const canvas = document.getElementById('e-fund-chart-canvas');
        const ctx = canvas.getContext('2d');
        const dataset = {
            label: 'Balance',
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
        };
        if (this.chart) this.chart.destroy();
        const plugins = [
            [
                pluginBoxAnnotation, {
                    yMin: targetLow,
                    yMax: targetHigh,
                    borderWidth: 0,
                    backgroundColor: green + '80',
                }
            ],
        ];
        this.ctx = ctx;
        this.chart = nummusChart.create(
            ctx,
            labels,
            null,
            [dataset],
            plugins,
            {
                scales: {
                    x: {ticks: {callback: formatDateTicksMonths}},
                    y: {ticks: {display: false}, grid: {drawTicks: false}},
                },
            },
        );
    },
}
