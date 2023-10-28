/**
 * Get theme colors
 *
 * @param name Name of color to get
 * @return Hex string of color
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
 * @param value Value of current tick
 * @param index Index of current tick
 * @param ticks Array of all ticks
 * @return Label for current tick
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
 * Chart.js plugin to draw a vertical line on hover
 *
 * @param idBar ID of status bar
 * @param idDate ID of date element
 * @param idValue ID of value element
 * @param idChange ID of value change element
 * @return Chart.js plugin
 */
function hoverLine(idBar, idDate, idValue, idChange) {
    const plugin = {
        id: 'hoverLine',
        eBar: document.getElementById(idBar),
        eDate: document.getElementById(idDate),
        eValue: document.getElementById(idValue),
        eChange: document.getElementById(idChange),
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

            const i = tooltip._active[0].index;
            const x = Math.floor(tooltip._active[0].element.x) + 0.5;
            const y = tooltip._active[0].element.y;
            const color = getThemeColor('grey-500');

            ctx.save();
            ctx.beginPath();
            ctx.lineWidth = 1;
            ctx.strokeStyle = color;
            ctx.moveTo(x, top);
            ctx.lineTo(x, bottom);
            ctx.stroke();

            ctx.beginPath();
            ctx.arc(x, y, 6, 0, 2 * Math.PI);
            ctx.fillStyle = color + '40';
            ctx.fill();
            ctx.stroke();

            ctx.restore();

            const date = data.labels[i];
            const value = data.datasets[0].data[i];
            const change = (i == 0) ? 0 : value - data.datasets[0].data[i - 1];

            this.eDate.innerHTML = date;

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
