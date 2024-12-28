'use strict';
/**
 * Charts creator and updater for nummus
 *
 */
const nummusChart = {
    /**
     * Create a new chart
     *
     * @param {Object} ctx Canvas context to use
     * @param {Array} labels Array of labels
     * @param {String} dateMode Mode of date tick formatter
     * @param {Array} datasets Array of datasets
     * @param {Array} plugins Array of plugins
     * @param {Object} options override
     * @return {Object} Chart object
     */
    create: function(ctx, labels, dateMode, datasets, plugins, options) {
        'use strict';
        setChartDefaults();

        const pluginObjects = [];
        const pluginOptions = {
            legend: {
                display: false,
            },
            tooltip: {
                intersect: false,
                mode: 'index',
                enabled: window.screen.width >= 768,
                callbacks: {
                    label: function(context) {
                        let label = context.dataset.label || '';
                        if (label) label += ': ';
                        if (context.parsed.y != null)
                            label += formatterF2.format(context.parsed.y);
                        return label;
                    },
                    labelColor: function(context) {
                        const dataset = context.dataset;
                        let color = {
                            borderColor: dataset.borderColor,
                            backgroundColor: dataset.backgroundColor,
                            borderWidth: dataset.borderWidth,
                        };
                        // Only do this if only one dataset, if multiple,
                        // default is fine
                        if (context.chart.data.datasets.length != 1)
                            return color;
                        if (dataset.fill && dataset.fill.above &&
                            dataset.fill.below) {
                            color.backgroundColor = (context.raw >= 0) ?
                                dataset.fill.above :
                                dataset.fill.below;
                        }
                        return color;
                    }
                },
            },
        };
        if (plugins) {
            for (const item of plugins) {
                const plugin = item[0];
                pluginObjects.push(plugin);
                pluginOptions[plugin.id] = item[1];
            }
        }

        options = merge(
            {
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
            options ?? {},
        );

        return new Chart(ctx, {
            data: {labels: labels, datasets: datasets},
            options: options,
            plugins: pluginObjects,
        });
    },
    /**
     * Update existing chart
     *
     * @param {Object} chart Chart object
     * @param {Array} labels Array of labels
     * @param {String} dateMode Mode of date tick formatter
     * @param {Array} values Array of values
     */
    update: function(chart, labels, dateMode, datasets) {
        'use strict';
        chart.data.labels = labels;
        if (chart.data.datasets.length == datasets.length) {
            for (let i = 0; i < datasets.length; ++i) {
                chart.data.datasets[i].data = datasets[i].data;
            }
        } else {
            chart.data.datasets = datasets;
        }
        chart.config.options.scales.x.ticks.dateMode = dateMode;
        chart.update();
    },
    /**
     * Prepare stacked chart datasets
     *
     * @param {Array} sources Array of sources [{values:, color:}, ...]
     * @return {Array} datasets
     */
    datasetsStacked: function(sources) {
        'use strict';
        const datasets = [];
        const n = sources[0].values.length;
        let values = new Array(n).fill(0);
        let first = true;
        for (const source of sources) {
            // Skip if every value is zero
            if (source.values.every((v) => v == 0)) continue;
            for (let i = 0; i < n; ++i) values[i] += source.values[i];
            datasets.push({
                type: 'line',
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
        return datasets;
    },
    /**
     * Prepare pie datasets
     *
     * @param {Array} sources Array of sources [{values:, color:}, ...]
     * @return {Object} Object with the following keys
     * @return {Array} datasets
     * @return {Number} total of all sources
     */
    datasetsPie: function(sources) {
        'use strict';

        const labels = [];
        const datasets = [];

        const data = [];
        const colors = [];
        const backgroundColors = [];

        let total = 0;

        for (const source of sources) {
            const value =
                source.amount ?? source.values[source.values.length - 1];
            total += value;
            data.push(value);
            labels.push(source.name);
            colors.push(source.color);
            backgroundColors.push(source.color + '80');
        }
        datasets.push({
            data: data,
            borderWidth: 1,
            borderColor: colors,
            backgroundColor: backgroundColors,
        });
        return {
            labels: labels,
            datasets: datasets,
            total: total,
        };
    },
    /**
     * Create a new pie chart
     *
     * @param {Object} ctx Canvas context to use
     * @param {Array} sources Array of sources [values0, values1, ...]
     * @param {Array} plugins Array of plugins
     * @param {Object} options override
     * @return {Object} Chart object
     */
    createPie: function(ctx, sources, plugins, options) {
        'use strict';
        setChartDefaults();

        const {labels, datasets, total} = this.datasetsPie(sources);

        const pluginObjects = [
            pluginDoughnutText,
        ];
        const pluginOptions = {
            legend: {
                display: false,
            },
            tooltip: {
                enabled: true,
                callbacks: {
                    label: function(context) {
                        let label = context.dataset.label || '';
                        if (label) label += ': ';
                        if (context.parsed != null) {
                            label += formatterF2.format(context.parsed);
                            const percent = context.parsed / total * 100;
                            label += ` (${percent.toFixed(1)}%)`;
                        }
                        return label;
                    }
                },
            },
            doughnutText: {
                text: formatterF0.format(total),
                font: '\'liberation-sans\', \'sans-serif\'',

            }
        };
        if (plugins) {
            for (const item of plugins) {
                const plugin = item[0];
                pluginObjects.push(plugin);
                pluginOptions[plugin.id] = item[1];
            }
        }

        options = merge(
            {
                responsive: true,
                maintainAspectRatio: true,
                plugins: pluginOptions,
            },
            options ?? {},
        )

        return new Chart(ctx, {
            type: 'doughnut',
            data: {labels: labels, datasets: datasets},
            options: options,
            plugins: pluginObjects,
        });
    },
    /**
     * Update existing pie chart with a single data source
     *
     * @param {Object} chart Chart object
     * @param {Array} sources Array of sources [values0, values1, ...]
     */
    updatePie: function(chart, sources) {
        'use strict';
        const {labels, datasets, total} = this.datasetsPie(sources);

        if (chart.data.datasets.length == datasets.length) {
            // Swapping same type monthly or not
            for (let i = 0; i < datasets.length; ++i) {
                chart.data.datasets[i].data = datasets[i].data;
                chart.data.datasets[i].borderColor = datasets[i].borderColor;
                chart.data.datasets[i].backgroundColor =
                    datasets[i].backgroundColor;
            }
        } else {
            chart.data.datasets = datasets;
        }
        chart.data.labels = labels;
        chart.config.options.plugins.doughnutText.text =
            formatterF0.format(total);
        chart.update();
    },
};
