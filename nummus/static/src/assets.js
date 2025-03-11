'use strict';
const assets = {
    chart: null,
    /**
     * Create Asset Chart
     *
     * @param {Object} raw Raw data from assets controller
     */
    update: function(raw) {
        const labels = raw.labels;
        const dateMode = raw.date_mode;
        const values = raw.values;

        const canvas = document.getElementById('asset-chart-canvas');
        const ctx = canvas.getContext('2d');
        const datasets = [
            {
                label: 'Value',
                type: 'line',
                data: values,
                borderColorRaw: 'primary',
                backgroundColorRaw: ['primary-container', '80'],
                borderWidth: 2,
                pointRadius: 0,
                hoverRadius: 0,
                fill: {
                    target: 'origin',
                    aboveRaw: ['primary-container', '80'],
                    belowRaw: ['error-container', '80'],
                },
            },
        ];
        if (this.chart) this.chart.destroy();
        this.ctx = ctx;
        this.chart = nummusChart.create(
            ctx,
            labels,
            dateMode,
            datasets,
        );
    },
}
