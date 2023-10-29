const accountChart = {
    chart: null,
    dates: null,
    uri: null,
    create: function(datasets) {
        'use strict';
        const ctx =
            document.querySelector('#account-chart-canvas').getContext('2d');
        this.chart = new Chart(ctx, {
            type: 'line',
            data: {labels: this.dates, datasets: datasets},
            options: {
                // animations: false,
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
    },
    /**
     * Create Account Chart
     *
     * @param raw Raw data from accounts controller
     * @param force True will force recreate the chart
     */
    update: function(raw, uri) {
        'use strict';
        console.log('update');

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

            datasets.push({
                data: valuesAvg,
                borderWidth: 2,
                pointRadius: 0,
                hoverRadius: 0,
                borderColor: getThemeColor('green'),
            });
            datasets.push({
                data: valuesMin,
                borderWidth: 0,
                pointRadius: 0,
                hoverRadius: 0,
                fill: 1,
                backgroundColor: getThemeColor('green') + '40',
            });
            datasets.push({
                data: valuesMax,
                borderWidth: 0,
                pointRadius: 0,
                hoverRadius: 0,
                fill: 1,
                backgroundColor: getThemeColor('green') + '40',
            });
        } else {
            datasets.push({
                data: raw.values,
                borderWidth: 0,
                pointRadius: 0,
                hoverRadius: 0,
                fill: {
                    target: 'origin',
                    above: getThemeColor('green'),
                    below: getThemeColor('blue'),
                },
            })
        }

        if (!this.chart || this.uri != uri) {
            this.uri = uri;
            this.create(datasets);
            this.chart.config.plugins[0].monthly = monthly;
            return;
        }

        this.chart.data.labels = this.dates;
        // if (datasets.length == 1) {
        //     this.chart.data.datasets[0].data = datasets[0].data;
        // } else {
        //     this.chart.data.datasets = datasets;
        // }
        this.chart.data.datasets = datasets;
        this.chart.config.plugins[0].monthly = monthly;
        this.chart.update();
    }
}
