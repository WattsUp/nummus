/**
 * Chart.js plugin to draw a vertical line on hover
 *
 */
const pluginHoverLine = {
    id: 'hoverLine',
    afterInit(chart) {
        const {config: {options: {plugins: {hoverLine}}}} = chart;

        const name = hoverLine.name;

        chart.hoverLine = {
            config: hoverLine,
            eBar: document.getElementById(name + '-chart-bar'),
            eDate: document.getElementById(name + '-chart-date'),
            eValue: document.getElementById(name + '-chart-value'),
            eChange: document.getElementById(name + '-chart-change'),
            eChangeLabel: document.getElementById(name + '-chart-change-label'),
        };
    },
    afterDatasetsDraw(chart) {
        const {
            ctx,
            tooltip,
            chartArea: {top, bottom, left, right, width, height},
            data,
            scales,
            hoverLine,
        } = chart;
        if (tooltip._active.length == 0) {
            hoverLine.eBar.classList.remove('opacity-100');
            hoverLine.eBar.classList.add('opacity-0');
            return;
        }

        const tt = tooltip._active[0];
        const i = tt.index;

        const date = data.labels[i];
        const values = data.datasets[data.datasets.length - 1].data;
        const value = values[i];
        const change = (i == 0) ? 0 : value - values[i - 1];

        const x = Math.min(right - 1, Math.floor(tt.element.x));
        const y = scales.y.getPixelForValue(value);

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

        if (hoverLine.config.monthly) {
            hoverLine.eDate.innerHTML = `${date} AVG`;
            hoverLine.eChangeLabel.innerHTML = '1-Month AVG Change';
        } else {
            hoverLine.eDate.innerHTML = date;
            hoverLine.eChangeLabel.innerHTML = '1-Day Change';
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

        setAndColor(hoverLine.eValue, value);
        setAndColor(hoverLine.eChange, change);

        hoverLine.eBar.classList.remove('opacity-0');
        hoverLine.eBar.classList.add('opacity-100');
    }
};
