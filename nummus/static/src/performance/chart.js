const performanceChart = {
    chart: null,
    /**
     * Create Performance Chart
     *
     * @param {Object} raw Raw data from performance controller
     */
    update: function(raw) {
        'use strict';
        const labels = raw.labels;
        const dateMode = raw.date_mode;
        const values = raw.values.map(v => Number(v) * 100);
        const min = raw.min && raw.min.map(v => Number(v) * 100);
        const max = raw.max && raw.max.map(v => Number(v) * 100);

        // If only single day data, duplicate for prettier charts
        if (labels.length == 1) {
            labels.push(labels[0]);
            values.push(values[0]);
            if (min) min.push(min[0]);
            if (max) max.push(max[0]);
        }


        const width = 65;

        {
            const canvas = document.getElementById('performance-chart-canvas');
            const ctx = canvas.getContext('2d');
            const datasets = [];
            if (min == null) {
                const green = getThemeColor('green');
                const red = getThemeColor('red');
                datasets.push({
                    type: 'line',
                    data: values,
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

            const options = {
                scales: {
                    y: {
                        ticks: {
                            callback: formatPercentTicks,
                            precision: 0,
                        },
                    },
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) label += ': ';
                                if (context.parsed.y != null)
                                    label += `${context.parsed.y.toFixed(1)}%`;
                                return label;
                            }
                        },
                    },
                },
            };

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
                    options,
                );
            }
        }


        const charts = [
            'performance-chart-canvas',
        ];
        for (const chart of charts) {
            nummusChart.removeDeferredChart(chart);
        }
    },
    /**
     * Defer loading of charts by drawing a spinner on all charts
     */
    defer: function() {
        const charts = [
            'performance-chart-canvas',
        ];
        for (const chart of charts) {
            nummusChart.addDeferredChart(chart);
        }
    },
}
