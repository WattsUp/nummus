const accountChart = {
    chart: null,
    dates: null,
    observer: null,
    ctx: null,
    /**
     * Create chart if it doesn't already exist
     *
     * @param datasets Datasets to create chart with
     * @return true if chart was created
     * @return false if chart already exists
     */
    create: function(datasets) {
        'use strict';
        const canvas = document.getElementById('account-chart-canvas');
        const ctx = canvas.getContext('2d');
        // Context is the same, chart already exists
        if (ctx == this.ctx) return false;
        this.ctx = ctx;

        this.chart = new Chart(ctx, {
            type: 'line',
            data: {labels: this.dates, datasets: datasets},
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        grid: {
                            display: false,
                        },
                        ticks: {
                            callback: function(value, index, ticks) {
                                if (index == 0 || index == (ticks.length - 1)) {
                                    return this.dates[index];
                                }
                            }.bind(this)
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
            plugins: [hoverLine(
                'account-chart-bar',
                'account-chart-date',
                'account-chart-value',
                'account-chart-change',
                'account-chart-change-label',
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

        this.dates = raw.dates;
        const values = raw.values.map(v => Number(v));
        const datasets = [];
        let monthly = false;
        if (this.dates.length > 400) {
            monthly = true;

            this.dates = [];
            let valuesMin = [];
            let valuesMax = [];
            let valuesAvg = [];

            let currentMonth = raw.dates[0].slice(0, 7);
            let currentMin = values[0];
            let currentMax = values[0];
            let currentSum = 0;
            let currentN = 0
            for (let i = 0; i < raw.dates.length; ++i) {
                let month = raw.dates[i].slice(0, 7);
                let v = values[i];

                if (month != currentMonth) {
                    this.dates.push(currentMonth);
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
            this.dates.push(currentMonth);
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
        if (this.create(datasets)) {
            this.chart.config.plugins[0].monthly = monthly;
            return;
        }

        this.chart.data.labels = this.dates;
        if (this.chart.data.datasets.length == datasets.length) {
            // Swapping same type monthly or not
            for (let i = 0; i < datasets.length; ++i) {
                this.chart.data.datasets[i].data = datasets[i].data;
            }
        } else {
            this.chart.data.datasets = datasets;
        }
        this.chart.config.plugins[0].monthly = monthly;
        this.chart.update();
    }
}
