/**
 * Get theme colors
 *
 * @param {String} name Name of color to get
 * @return {String} Hex string of color
 */
function getThemeColor(name) {
    'use strict';
    const style = getComputedStyle(document.body);
    return style.getPropertyValue(`--color-${name}`);
}

/**
 * Get nth color for chart colors
 *
 * @param {Number} i Index of color to get
 * @return {String} Hex string of color
 */
function getChartColor(i) {
    'use strict';
    const base = getThemeColor('green');
    return tinycolor(base).spin(i * 27).toHexString();
}

/**
 * Downsample data to monthly min/max/avg values
 *
 * @param {Array} dates Array of sample dates
 * @param {Array} values Array of sample values
 * @return {Object} Object with the following keys
 * @return {Array} labels
 * @return {Array} min
 * @return {Array} max
 * @return {Array} avg
 */
function downsampleMonths(dates, values) {
    let labels = [];
    let min = [];
    let max = [];
    let avg = [];

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
            min.push(currentMin);
            max.push(currentMax);
            avg.push(currentSum / currentN);

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
    min.push(currentMin);
    max.push(currentMax);
    avg.push(currentSum / currentN);

    return {
        labels: labels, min: min, max: max, avg: avg,
    }
}

/**
 * USD formatter with zero fractional digits
 */
const formatterF0 = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
});

/**
 * USD formatter with one fractional digit
 */
const formatterF1 = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
});

/**
 * USD formatter with two fractional digits
 */
const formatterF2 = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
});

/**
 * Format ticks as money
 *
 * @param {Number} value Value of current tick
 * @param {Number} index Index of current tick
 * @param {Object} ticks Array of all ticks
 * @return {String} Label for current tick
 */
function formatMoneyTicks(value, index, ticks) {
    'use strict';
    if (index == 0) {
        const step = Math.abs(ticks[0].value - ticks[1].value);
        const smallest = Math.min(...ticks.map((t) => Math.abs(t.value)));
        ticks.forEach((t) => {
            if (step >= 1000) {
                t.label = formatterF0.format(t.value / 1000) + 'k';
            } else if (step >= 100 && smallest >= 1000) {
                t.label = formatterF1.format(t.value / 1000) + 'k';
            } else {
                t.label = formatterF0.format(t.value);
            }
        });
    }
    return ticks[index].label;
}


/**
 * Format ticks as money
 *
 * @param {Number} value Value of current tick
 * @param {Number} index Index of current tick
 * @param {Object} ticks Array of all ticks
 * @return {String} Label for current tick
 */
function formatDateTicks(value, index, ticks) {
    if (index == 0) {
        const chart = this.chart;
        const labels = chart.data.labels;
        const dateMode = chart.config.options.scales.x.ticks.dateMode;
        switch (dateMode) {
            case 'years':
                ticks.forEach((t, i) => {
                    let l = labels[i];
                    if (l.slice(-2) == '01') t.label = l.slice(0, 4);
                });
                break;
            case 'months':
                ticks.forEach((t, i) => {
                    let l = labels[i];
                    if (l.slice(-2) == '01') t.label = l.slice(0, 7);
                });
                break;
            case 'weeks':
                ticks.forEach((t, i) => {
                    let l = labels[i];
                    let date = new Date(l);
                    // Mark each Sunday
                    if (date.getUTCDay() == 0) t.label = l;
                });
                break;
            case 'days':
            default:
                ticks.forEach((t, i) => t.label = labels[i]);
                break
        }
    }
    return ticks[index].label;
}

/**
 * Compute the average of an array
 *
 * @param {Array} array Array to compute over
 * @return {Number} Average value
 */
const average = array => array.reduce((a, b) => a + b) / array.length;
