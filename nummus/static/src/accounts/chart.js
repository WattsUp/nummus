const accountChart = {
    chart: null,
    /**
     * Create Account Chart
     *
     * @param {Object} raw Raw data from accounts controller
     */
    update: function(raw) {
        'use strict';
        const labels = raw.labels;
        const dateMode = raw.date_mode;
        const values = raw.values.map(v => Number(v));

        const blue = getThemeColor('blue');
        const yellow = getThemeColor('yellow');

        const canvas = document.getElementById('account-chart-canvas');
        const ctx = canvas.getContext('2d');
        const dataset = {
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
        if (this.chart && ctx == this.chart.ctx) {
            nummusChart.update(this.chart, labels, dateMode, [dataset]);
        } else {
            this.chart = nummusChart.create(ctx, labels, dateMode, [dataset]);
        }
    }
}
