/**
 * Type of chart with a multiple data source dates, values stacked on each
 * other.
 *
 * Creates a stacked area chart
 * If data source is long,
 * Creates a line chart with monthly min, max, & avg TODO
 */
const chartStacked = {
    /**
     * Prepare datasets
     *
     * @param {Array} dates Array of dates
     * @param {Array} sources Array of sources [values0, values1, ...]
     * @param {Boolean} reverse True will plot last source first but keep same
     *     order of colors
     * @return {Object} Object with the following keys
     * @return {Array} labels
     * @return {Array} datasets
     * @return {Array} dateMode Date mode of formatDateTicks
     * @return {Array} monthly True if data is downsampled to months
     */
    datasets: function(dates, sources, reverse) {
        'use strict';

        let labels = [];
        const datasets = [];

        let dateMode = null;
        let monthly = false;

        // Downsample values to months: min, max, & avg
        if (dates.length > 400 && false) {
            // TODO
        } else {
            labels = dates;
            const n = dates.length;
            if (n > 80)
                dateMode = 'months';
            else if (n > 10)
                dateMode = 'weeks';
            let values = new Array(n).fill(0);
            let first = true;
            for (let i = 0; i < sources.length; ++i) {
                const source = sources[reverse ? sources.length - 1 - i : i];
                for (let ii = 0; ii < n; ++ii) values[ii] += source[ii];
                datasets.push({
                    data: [...values],
                    borderWidth: 2,
                    pointRadius: 0,
                    hoverRadius: 0,
                    fill: first ? 'origin' : '-1',
                });
                first = false;
            }
        }
        return {
            labels: labels,
            datasets: datasets,
            dateMode: dateMode,
            monthly: monthly,
        };
    },
    /**
     * Create a new chart with a multiple data sources
     *
     * @param {Object} ctx Canvas context to use
     * @param {String} name Name of chart objects for pluginHoverLine
     * @param {Array} dates Array of dates
     * @param {Array} sources Array of sources [values0, values1, ...]
     * @param {Boolean} reverse True will plot last source first but keep same
     *     order of colors
     * @return {Object} Chart object
     */
    create: function(ctx, name, dates, sources, reverse) {
        'use strict';

        const {
            labels,
            datasets,
            dateMode,
            monthly,
        } = this.datasets(dates, sources, reverse);

        return new Chart(ctx, {
            type: 'line',
            data: {labels: labels, datasets: datasets},
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        grid: {
                            display: true,
                        },
                        ticks: {
                            callback: formatDateTicks,
                            dateMode: dateMode,
                        },
                    },
                    y: {
                        ticks: {
                            callback: formatMoneyTicks,
                            precision: 0,
                        },
                    },
                },
                plugins: {
                    legend: {
                        display: false,
                    },
                    tooltip: {
                        intersect: false,
                        mode: 'index',
                        enabled: false,
                    },
                },
            },
            plugins: [pluginHoverLine(name, monthly)],
        });
    },
    /**
     * Update existing chart with a single data source
     *
     * @param {Object} chart Chart object
     * @param {Array} dates Array of dates
     * @param {Array} sources Array of sources [values0, values1, ...]
     * @param {Boolean} reverse True will plot last source first but keep same
     *     order of colors
     */
    update: function(chart, dates, sources, reverse) {
        'use strict';
        const {
            labels,
            datasets,
            dateMode,
            monthly,
        } = this.datasets(dates, sources, reverse);

        chart.data.labels = labels;
        if (chart.data.datasets.length == datasets.length) {
            // Swapping same type monthly or not
            for (let i = 0; i < datasets.length; ++i) {
                chart.data.datasets[i].data = datasets[i].data;
            }
        } else {
            chart.data.datasets = datasets;
        }
        chart.config.plugins[0].monthly = monthly;
        chart.config.options.scales.x.ticks.dateMode = dateMode;
        chart.update();
    },
};
