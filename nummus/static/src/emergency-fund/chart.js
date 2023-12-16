const emergencyFundChart = {
    chart: null,
    ctx: null,
    /**
     * Create Emergency Fund Chart
     *
     * @param {Object} raw Raw data from emergency fund controller
     */
    update: function(raw) {
        'use strict';
        const dates = raw.dates;
        const values = raw.balances.map(v => Number(v));
        const targetLow = Number(raw.target_low);
        const targetHigh = Number(raw.target_high);

        const green = getThemeColor('green');

        const canvas = document.getElementById('e-fund-chart-canvas');
        const ctx = canvas.getContext('2d');
        if (ctx == this.ctx) {
            chartSingle.update(this.chart, dates, values);
        } else {
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
            this.chart = chartSingle.create(
                ctx,
                'e-fund',
                dates,
                values,
                plugins,
            );
        }
    },
}
