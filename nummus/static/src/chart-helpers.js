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
 * Format ticks as money
 *
 * @param value Value of current tick
 * @param index Index of current tick
 * @param ticks Array of all ticks
 * @return Label for current tick
 */
function formatMoneyTicks(value, index, ticks) {
    'use strict';
    const formatterF0 = new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
    });
    const formatterF1 = new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
    });
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
 */
const hoverLine = {
    id: 'hoverLine',
    afterDatasetsDraw(chart, args, plugins) {
        const {
            ctx,
            tooltip,
            chartArea: {top, bottom, left, right, width, height},
        } = chart;
        if (tooltip._active.length == 0) return;

        const e = tooltip._active[0].element;
        const x = Math.floor(e.x) + 0.5;
        const y = e.y;
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
    }
}
