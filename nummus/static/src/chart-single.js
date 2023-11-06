/**
 * Type of chart with a single data source dates, values.
 *
 * Creates a area chart with blue above and yellow below
 * If data source is long,
 * Creates a line chart with monthly min, max, & avg
 */
const chartSingle = {
    /**
     * Prepare datasets
     *
     * @param {Array} dates Array of dates
     * @param {Array} values Array of values
     * @return {Object} Object with the following keys
     * @return {Array} labels
     * @return {Array} datasets
     * @return {Array} dateMode Date mode of formatDateTicks
     * @return {Array} monthly True if data is downsampled to months
     */
    datasets: function(dates, values) {
        'use strict';

        // Downsample values to months: min, max, & avg
        if (dates.length > 400) {
            const {
                labels,
                min,
                max,
                avg,
            } = downsampleMonths(dates, values);

            let color = getThemeColor('grey-500');

            const datasets = [];
            datasets.push({
                data: min,
                borderWidth: 0,
                pointRadius: 0,
                hoverRadius: 0,
                fill: 1,
                backgroundColor: color + '40',
            });
            datasets.push({
                data: max,
                borderWidth: 0,
                pointRadius: 0,
                hoverRadius: 0,
                fill: 1,
                backgroundColor: color + '40',
            });
            datasets.push({
                data: avg,
                borderWidth: 2,
                pointRadius: 0,
                hoverRadius: 0,
                borderColor: color,
            });
            return {
                labels: labels,
                datasets: datasets,
                dateMode: 'years',
                monthly: true,
            };
        } else {
            let dateMode = null;

            if (dates.length > 80)
                dateMode = 'months';
            else if (dates.length > 10)
                dateMode = 'weeks';

            const datasets = [];
            datasets.push({
                data: values,
                borderColor: getThemeColor('grey-500'),
                borderWidth: 2,
                pointRadius: 0,
                hoverRadius: 0,
                fill: {
                    target: 'origin',
                    above: getThemeColor('blue') + '80',
                    below: getThemeColor('yellow') + '80',
                },
            })
            return {
                labels: dates,
                datasets: datasets,
                dateMode: dateMode,
                monthly: false,
            };
        }
    },
    /**
     * Create a new chart with a single data source
     *
     * @param {Object} ctx Canvas context to use
     * @param {String} name Name of chart objects for pluginHoverLine
     * @param {Array} dates Array of dates
     * @param {Array} values Array of values
     * @param {Array} plugins Array of plugins
     * @return {Object} Chart object
     */
    create: function(ctx, name, dates, values, plugins) {
        'use strict';
        setChartDefaults();

        const {
            labels,
            datasets,
            dateMode,
            monthly,
        } = this.datasets(dates, values);

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
            hoverLine: {
                name: name,
                monthly: monthly,
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
     * @param {Array} values Array of values
     */
    update: function(chart, dates, values) {
        'use strict';
        const {
            labels,
            datasets,
            dateMode,
            monthly,
        } = this.datasets(dates, values);

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
