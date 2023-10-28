/**
 * Create Account Chart
 *
 * @param raw Raw data from accounts controller
 */
function accountChart(raw) {
    'use strict';
    let dates = raw.dates;
    let values = raw.values;

    // TODO(WattsUp) Add hover logic

    let ctx = document.querySelector('#account-chart-canvas').getContext('2d');
    let chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: dates,
            datasets: [
                {
                    data: values,
                    backgroundColor: getThemeColor('green'),
                    borderWidth: 0,
                    pointRadius: 0,
                    fill: 'origin',
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
                        display: false,
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
            },
        },
    });
}
