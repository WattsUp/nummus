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

        let labels = [];
        const datasets = [];

        let dateMode = null;
        let monthly = false;

        // Downsample values to months: min, max, & avg
        if (dates.length > 400) {
            dateMode = 'years';
            monthly = true;

            let valuesMin = [];
            let valuesMax = [];
            let valuesAvg = [];

            let currentMonth = dates[0].slice(0, 7);
            let currentMin = values[0];
            let currentMax = values[0];
            let currentSum = 0;
            let currentN = 0
            for (let i = 0; i < dates.length; ++i) {
                let month = dates[i].slice(0, 7);
                let v = values[i];

                if (month != currentMonth) {
                    labels.push(currentMonth);
                    valuesMin.push(currentMin);
                    valuesMax.push(currentMax);
                    valuesAvg.push(currentSum / currentN);

                    currentMonth = month;
                    currentMin = v;
                    currentMax = v;
                    currentSum = 0;
                    currentN = 0;
                }

                currentMin = Math.min(currentMin, v);
                currentMax = Math.max(currentMax, v);
                currentSum += v;
                ++currentN;
            }
            labels.push(currentMonth);
            valuesMin.push(currentMin);
            valuesMax.push(currentMax);
            valuesAvg.push(currentSum / currentN);

            let color = getThemeColor('grey-500');

            datasets.push({
                data: valuesAvg,
                borderWidth: 2,
                pointRadius: 0,
                hoverRadius: 0,
                borderColor: color,
            });
            datasets.push({
                data: valuesMin,
                borderWidth: 0,
                pointRadius: 0,
                hoverRadius: 0,
                fill: 1,
                backgroundColor: color + '40',
            });
            datasets.push({
                data: valuesMax,
                borderWidth: 0,
                pointRadius: 0,
                hoverRadius: 0,
                fill: 1,
                backgroundColor: color + '40',
            });
        } else {
            labels = dates;
            if (dates.length > 80)
                dateMode = 'months';
            else if (dates.length > 10)
                dateMode = 'weeks';
            datasets.push({
                data: values,
                borderWidth: 0,
                pointRadius: 0,
                hoverRadius: 0,
                fill: {
                    target: 'origin',
                    above: getThemeColor('blue'),
                    below: getThemeColor('yellow'),
                },
            })
        }
        return {
            labels: labels,
            datasets: datasets,
            dateMode: dateMode,
            monthly: monthly,
        };
    },
    /**
     * Create a new chart with a single data source
     *
     * @param {Object} ctx Canvas context to use
     * @param {String} name Name of chart objects for pluginHoverLine
     * @param {Array} dates Array of dates
     * @param {Array} values Array of values
     * @return {Object} Chart object
     */
    create: function(ctx, name, dates, values) {
        'use strict';

        const {
            labels,
            datasets,
            dateMode,
            monthly,
        } = this.datasets(dates, values);

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
        chart.config.plugins[0].monthly = monthly;
        chart.config.options.scales.x.ticks.dateMode = dateMode;
        chart.update();
    },
};
