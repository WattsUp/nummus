/**
 * Chart.js plugin to draw text at the center of a doughnut chart
 *
 */
const pluginDoughnutText = {
    id: 'doughnutText',
    beforeInit: function(chart) {
        const {config: {options: {plugins: {doughnutText}}}} = chart;
        chart.doughnutText = doughnutText;
    },
    afterDatasetsDraw: function(chart) {
        const {
            ctx,
            chartArea: {top, bottom, left, right, width, height},
            doughnutText: {text, font},
        } = chart;

        const px = Math.floor(height / 10);

        ctx.save();
        ctx.textBaseline = 'middle';
        ctx.textAlign = 'center';
        ctx.font = `${px}px ${font}`;
        ctx.fillText(text, (left + right) / 2, (top + bottom) / 2);

        ctx.restore();
    }
};
