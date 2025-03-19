'use strict';
/**
 * Chart.js plugin to compute color from semantic name
 *
 */
const pluginColor = {
    id: 'color',
    charts: {},
    afterInit: function(chart) {
        this.charts[chart.id] = chart;
        this.updateChartColor(chart);
    },
    updateChartColor: function(chart) {
        const getColor = function(src) {
            if (Array.isArray(src))
                return getThemeColor(src[0]) + src[1];
            else
                return getThemeColor(src);
        };

        const fields = [
            'borderColor',
            'backgroundColor',
        ];
        const {config: {options, data: {datasets}}} = chart;
        for (const dataset of datasets) {
            const {
                borderColorRaw,
                backgroundColorRaw,
                fill: {aboveRaw, belowRaw} = {}
            } = dataset;
            if (borderColorRaw) dataset.borderColor = getColor(borderColorRaw);
            if (backgroundColorRaw)
                dataset.backgroundColor = getColor(backgroundColorRaw);
            if (aboveRaw) dataset.fill.above = getColor(aboveRaw);
            if (belowRaw) dataset.fill.below = getColor(belowRaw);
        }

        const text = getThemeColor('on-surface');
        const surface = getThemeColor('inverse-surface');
        const textInv = getThemeColor('inverse-on-surface');
        const outline = getThemeColor('outline-variant');

        options.scales.x.ticks.color = text;
        options.scales.x.grid.color = outline;
        options.scales.x.border.color = outline;
        options.scales.y.ticks.color = text;
        options.scales.y.grid.color = outline;
        options.scales.y.border.color = outline;
        options.plugins.tooltip.backgroundColor = surface;
        options.plugins.tooltip.titleColor = textInv;
        options.plugins.tooltip.bodyColor = textInv;
    },
    update: function() {
        for (const chart of Object.values(this.charts)) {
            this.updateChartColor(chart);
            chart.update();
        }
    },
    afterDestroy: function(chart) {
        delete this.charts[chart.id];
    }
};
