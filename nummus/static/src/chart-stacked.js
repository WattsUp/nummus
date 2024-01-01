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
     * @param {Array} sources Array of sources [{values:, color:}, ...]
     * @return {Object} Object with the following keys
     * @return {Array} labels
     * @return {Array} datasets
     * @return {Array} dateMode Date mode of formatDateTicks
     * @return {Array} monthly True if data is downsampled to months
     */
    datasets: function(dates, sources) {
        'use strict';

        let labels = null;
        const datasets = [];

        let dateMode = null;
        let monthly = false;

        // Downsample values to months: min, max, & avg
        if (dates.length > 400) {
            let sourcesDownsampled = [];
            for (const source of sources) {
                const result = downsampleMonths(dates, source.values);
                if (!labels) labels = result.labels;
                sourcesDownsampled.push({
                    color: source.color,
                    values: result.avg,
                });
            }
            sources = sourcesDownsampled
            dateMode = 'years';
            monthly = true;
        } else {
            labels = dates;
            if (dates.length > 80)
                dateMode = 'months';
            else if (dates.length > 10)
                dateMode = 'weeks';
        }
        const n = labels.length;
        let values = new Array(n).fill(0);
        let first = true;
        for (const source of sources) {
            // Skip if every value is zero
            if (source.values.every((v) => v == 0)) continue;
            for (let i = 0; i < n; ++i) values[i] += source.values[i];
            datasets.push({
                data: [...values],
                borderColor: source.color,
                backgroundColor: source.color + '80',
                borderWidth: 1,
                pointRadius: 0,
                hoverRadius: 0,
                fill: first ? 'origin' : '-1',
            });
            first = false;
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
     * @param {Array} dates Array of dates
     * @param {Array} sources Array of sources [values0, values1, ...]
     * @param {Array} plugins Array of plugins
     * @return {Object} Chart object
     */
    create: function(ctx, dates, sources, plugins) {
        'use strict';
        setChartDefaults();

        const {
            labels,
            datasets,
            dateMode,
            monthly,
        } = this.datasets(dates, sources);

        const pluginObjects = [
            pluginHoverLine,
        ];
        const pluginOptions = {
            legend: {
                display: false,
            },
            tooltip: {
                intersect: false,
                mode: 'index',
                enabled: false,
            },
        };
        if (plugins) {
            for (const item of plugins) {
                const plugin = item[0];
                pluginObjects.push(plugin);
                pluginOptions[plugin.id] = item[1];
            }
        }

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
                plugins: pluginOptions,
            },
            plugins: pluginObjects,
        });
    },
    /**
     * Update existing chart with a single data source
     *
     * @param {Object} chart Chart object
     * @param {Array} dates Array of dates
     * @param {Array} sources Array of sources [values0, values1, ...]
     */
    update: function(chart, dates, sources) {
        'use strict';
        const {
            labels,
            datasets,
            dateMode,
            monthly,
        } = this.datasets(dates, sources);

        chart.data.labels = labels;
        if (chart.data.datasets.length == datasets.length) {
            // Swapping same type monthly or not
            for (let i = 0; i < datasets.length; ++i) {
                chart.data.datasets[i].data = datasets[i].data;
            }
        } else {
            chart.data.datasets = datasets;
        }
        chart.config.options.plugins.hoverLine.monthly = monthly;
        chart.config.options.scales.x.ticks.dateMode = dateMode;
        chart.update();
    },
};
