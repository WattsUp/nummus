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
 * Chart.js plugin to draw a vertical line on hover
 *
 * @param {String} name Base name of chart elements
 * @param {Boolean} monthly True if data is monthly data
 * @return {Object} Chart.js plugin
 */
function pluginHoverLine(name, monthly) {
    const plugin = {
        id: 'hoverLine',
        eBar: document.getElementById(name + '-chart-bar'),
        eDate: document.getElementById(name + '-chart-date'),
        eValue: document.getElementById(name + '-chart-value'),
        eChange: document.getElementById(name + '-chart-change'),
        eChangeLabel: document.getElementById(name + '-chart-change-label'),
        monthly: monthly,
        afterDatasetsDraw(chart, args, plugins) {
            const {
                ctx,
                tooltip,
                chartArea: {top, bottom, left, right, width, height},
                data,
            } = chart;
            if (tooltip._active.length == 0) {
                this.eBar.classList.remove('opacity-100');
                this.eBar.classList.add('opacity-0');
                return;
            }

            const tt = tooltip._active[0];
            const i = tt.index;
            const x = Math.min(right - 1, Math.floor(tt.element.x));
            const y = tt.element.y;

            ctx.save();
            ctx.beginPath();
            ctx.lineWidth = 1;
            ctx.strokeStyle = getThemeColor('black');
            ctx.moveTo(x + 0.5, top);
            ctx.lineTo(x + 0.5, bottom);
            ctx.stroke();

            ctx.beginPath();
            ctx.arc(x, y, 6, 0, 2 * Math.PI);
            ctx.fillStyle = getThemeColor('white');
            ctx.fill();
            ctx.stroke();

            ctx.restore();

            const date = data.labels[i];
            const value = data.datasets[0].data[i];
            const change = (i == 0) ? 0 : value - data.datasets[0].data[i - 1];

            if (this.monthly) {
                this.eDate.innerHTML = `${date} AVG`;
                this.eChangeLabel.innerHTML = '1-Month AVG Change';
            } else {
                this.eDate.innerHTML = date;
                this.eChangeLabel.innerHTML = '1-Day Change';
            }

            function setAndColor(e, v) {
                e.innerHTML = formatterF2.format(v);
                if (v > 0) {
                    e.classList.remove('text-red-600');
                    e.classList.add('text-green-600');
                } else if (v < 0) {
                    e.classList.add('text-red-600');
                    e.classList.remove('text-green-600');
                } else {
                    e.classList.remove('text-red-600');
                    e.classList.remove('text-green-600');
                }
            }

            setAndColor(this.eValue, value);
            setAndColor(this.eChange, change);

            this.eBar.classList.remove('opacity-0');
            this.eBar.classList.add('opacity-100');
        }
    };
    return plugin;
}

/**
 * Compute the average of an array
 *
 * @param {Array} array Array to compute over
 * @return {Number} Average value
 */
const average = array => array.reduce((a, b) => a + b) / array.length;
