/**
 * Create Account Chart
 *
 * @param raw Raw data from accounts controller
 */
function accountChart(raw) {
    'use strict';
    const dates = raw.dates;
    const values = raw.values;

    // TODO(WattsUp) Add downsampling
    // TODO(WattsUp) Add data replacement instead of rebuilding

    const ctx =
        document.querySelector('#account-chart-canvas').getContext('2d');
    const chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: dates,
            datasets: [
                {
                    data: values,
                    borderWidth: 0,
                    pointRadius: 0,
                    hoverRadius: 0,
                    fill: {
                        target: 'origin',
                        above: getThemeColor('green'),
                        below: getThemeColor('blue'),
                    },
                },
            ],
        },
        options: {
            animations: false,
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
                                return dates[index];
                            }
                        }
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
            )],
    });
}
