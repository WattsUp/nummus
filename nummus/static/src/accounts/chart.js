const accountChart = {
    chart: null,
    observer: null,
    ctx: null,
    /**
     * Create chart if it doesn't already exist
     *
     * @param labels Labels to create chart with
     * @param datasets Datasets to create chart with
     * @param dateMode x ticks date mode
     * @param monthly True if data is monthly data
     * @return true if chart was created
     * @return false if chart already exists
     */
    create: function(labels, datasets, dateMode, monthly) {
        'use strict';
        const canvas = document.getElementById('account-chart-canvas');
        const ctx = canvas.getContext('2d');
        // Context is the same, chart already exists
        if (ctx == this.ctx) return false;
        this.ctx = ctx;

        this.chart = new Chart(ctx, {
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
            plugins: [pluginHoverLine(
                'account-chart-bar',
                'account-chart-date',
                'account-chart-value',
                'account-chart-change',
                'account-chart-change-label',
                monthly,
                )],
        });
        return true;
    },
    /**
     * Create Account Chart
     *
     * @param raw Raw data from accounts controller
     */
    update: function(raw) {
        'use strict';

        let labels = [];
        let dateMode = null;

        const dates = raw.dates;
        const values = raw.values.map(v => Number(v));
        const datasets = [];
        let monthly = false;
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
                data: raw.values,
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

        // If created a new chart, skip update
        if (this.create(labels, datasets, dateMode, monthly)) return;

        this.chart.data.labels = labels;
        if (this.chart.data.datasets.length == datasets.length) {
            // Swapping same type monthly or not
            for (let i = 0; i < datasets.length; ++i) {
                this.chart.data.datasets[i].data = datasets[i].data;
            }
        } else {
            this.chart.data.datasets = datasets;
        }
        this.chart.config.plugins[0].monthly = monthly;
        this.chart.config.options.scales.x.ticks.dateMode = dateMode;
        this.chart.update();
    }
}
