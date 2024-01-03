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
        const min = raw.min && raw.min.map(v => Number(v));
        const max = raw.max && raw.max.map(v => Number(v));


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
            this.chart = nummusChart.create(ctx, labels, dateMode, datasets);
        }
    }
}
