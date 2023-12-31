/**
 * A pie chart
 *
 */
const chartPie = {
    /**
     * Prepare datasets
     *
     * @param {Array} sources Array of sources [{values:, color:}, ...]
     * @return {Object} Object with the following keys
     * @return {Array} labels
     * @return {Array} datasets
     * @return {Number} total of all sources
     */
    datasets: function(sources) {
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
     * Create a new chart with a multiple data sources
     *
     * @param {Object} ctx Canvas context to use
     * @param {Array} sources Array of sources [values0, values1, ...]
     * @param {Array} plugins Array of plugins
     * @return {Object} Chart object
     */
    create: function(ctx, sources, plugins) {
        'use strict';
        setChartDefaults();

        const {
            labels,
            datasets,
            total,
        } = this.datasets(sources);

        const pluginObjects = [
            pluginDoughnutText,
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

        return new Chart(ctx, {
            type: 'doughnut',
            data: {labels: labels, datasets: datasets},
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: pluginOptions,
            },
            plugins: pluginObjects,
        });
    },
    /**
     * Update existing chart with a single data source
     *
     * @param {Object} chart Chart object
     * @param {Array} sources Array of sources [values0, values1, ...]
     */
    update: function(chart, sources) {
        'use strict';
        const {
            labels,
            datasets,
            total,
        } = this.datasets(sources);

        chart.data.labels = labels;
        if (chart.data.datasets.length == datasets.length) {
            // Swapping same type monthly or not
            for (let i = 0; i < datasets.length; ++i) {
                chart.data.datasets[i].data = datasets[i].data;
            }
        } else {
            chart.data.datasets = datasets;
        }
        chart.config.options.plugins.doughnutText.text =
            formatterF0.format(total);
        chart.update();
    },
};
