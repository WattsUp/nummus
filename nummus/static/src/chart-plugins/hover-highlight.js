/**
 * Chart.js plugin to highlight another element on hover
 *
 */
const pluginHoverHighlight = {
    id: 'hoverHighlight',
    afterInit: function(chart) {
        const {config: {options: {plugins: {hoverHighlight}}}} = chart;
        hoverHighlight.scroll = hoverHighlight.scroll ?? true;
        chart.hoverHighlight = hoverHighlight;

        document.querySelectorAll(`#${hoverHighlight.parent}>*`)
            .forEach((child, i) => {
                child.addEventListener('mouseenter', function() {
                    child.style.fontWeight = 'bold';
                    this.setHover(chart, i, true);
                }.bind(this));
                child.addEventListener('mouseleave', function() {
                    child.style.fontWeight = '';
                    this.setHover(chart, i, false);
                }.bind(this));
            });
    },
    getChild(chart, i) {
        const hoverHighlight = chart.hoverHighlight;
        return document.querySelector(
            `#${hoverHighlight.parent}>:nth-child(${i + 1})`);
    },
    setActive(chart, i, active) {
        const hoverHighlight = chart.hoverHighlight;
        const child = this.getChild(chart, i);
        if (active) {
            if (hoverHighlight.scroll) child.scrollIntoView();
            child.style.fontWeight = 'bold';
        } else {
            child.style.fontWeight = '';
        }
    },
    setHover(chart, i, active) {
        const tooltip = chart.tooltip;
        if (active) {
            tooltip.setActiveElements([
                {datasetIndex: 0, index: i},
            ]);
        } else {
            tooltip.setActiveElements([]);
        }
        chart.update();
    },
    beforeEvent(chart, args, pluginOptions) {
        const hoverHighlight = chart.hoverHighlight;
        const event = args.event;
        if (event.type == 'mouseout') {
            if (hoverHighlight.previous != null) {
                this.setActive(chart, hoverHighlight.previous, false);
            }
            hoverHighlight.previous = null;
        } else if (
            event.type == 'mousemove' && chart.tooltip.dataPoints != null &&
            chart.tooltip.dataPoints.length > 0) {
            const dataPoint = chart.tooltip.dataPoints[0];
            if (dataPoint.element.active) {
                const i = dataPoint.dataIndex;
                if (hoverHighlight.previous == i) return;

                this.setActive(chart, i, true);


                if (hoverHighlight.previous != null) {
                    this.setActive(chart, hoverHighlight.previous, false);
                }
                hoverHighlight.previous = i;
            } else if (hoverHighlight.previous != null) {
                this.setActive(chart, hoverHighlight.previous, false);
                hoverHighlight.previous = null;
            }
        }
    },
};
