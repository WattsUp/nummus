/**
 * Get theme colors
 *
 * @param name Name of color to get
 * @return Hex string of color
 */
function getThemeColor(name) {
    'use strict';
    let style = getComputedStyle(document.body);
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
        let step = Math.abs(ticks[0].value - ticks[1].value);
        let smallest = Math.min(...ticks.map((t) => Math.abs(t.value)));
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
