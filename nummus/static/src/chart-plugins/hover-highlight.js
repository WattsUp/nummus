"use strict";
/**
 * Chart.js plugin to highlight another element on hover
 *
 */
const pluginHoverHighlight = {
  id: "hoverHighlight",
  beforeInit: function (chart) {
    const {
      config: {
        options: {
          plugins: { hoverHighlight },
        },
      },
    } = chart;
    hoverHighlight.scroll = hoverHighlight.scroll ?? true;
    hoverHighlight.listenersEnter = [];
    hoverHighlight.listenersExit = [];
    chart.hoverHighlight = hoverHighlight;

    this.addListeners(chart);
  },
  addListeners(chart) {
    const hoverHighlight = chart.hoverHighlight;
    if (!hoverHighlight) return;
    this.removeListeners(chart);
    document
      .querySelectorAll(`#${hoverHighlight.parent}>*`)
      .forEach((child, i) => {
        const enter = function () {
          child.style.fontWeight = "bold";
          this.setHover(chart, i, true);
        }.bind(this);
        const exit = function () {
          child.style.fontWeight = "";
          this.setHover(chart, i, false);
        }.bind(this);
        child.addEventListener("mouseenter", enter);
        child.addEventListener("mouseleave", exit);
        hoverHighlight.listenersEnter[i] = enter;
        hoverHighlight.listenersExit[i] = exit;
      });
  },
  removeListeners(chart) {
    const hoverHighlight = chart.hoverHighlight;
    document
      .querySelectorAll(`#${hoverHighlight.parent}>*`)
      .forEach((child, i) => {
        child.removeEventListener(
          "mouseenter",
          hoverHighlight.listenersEnter[i],
        );
        child.removeEventListener("mouseexit", hoverHighlight.listenersExit[i]);
      });
    hoverHighlight.listenersEnter.length = 0;
    hoverHighlight.listenersExit.length = 0;
  },
  getChild(chart, i) {
    const hoverHighlight = chart.hoverHighlight;
    return document.querySelector(
      `#${hoverHighlight.parent}>:nth-child(${i + 1})`,
    );
  },
  setActive(chart, i, active) {
    const hoverHighlight = chart.hoverHighlight;
    const child = this.getChild(chart, i);
    if (active && (chart.data.labels[i] ?? "Other") != "Other") {
      if (hoverHighlight.scroll)
        child.scrollIntoView({ block: "nearest", inline: "nearest" });
      child.style.fontWeight = "bold";
    } else {
      child.style.fontWeight = "";
    }
  },
  setHover(chart, i, active) {
    const tooltip = chart.tooltip;
    if (active && (chart.data.labels[i] ?? "Other") != "Other") {
      tooltip.setActiveElements([{ datasetIndex: 0, index: i }]);
    } else {
      tooltip.setActiveElements([]);
    }
    chart.update();
  },
  beforeEvent(chart, args, pluginOptions) {
    const hoverHighlight = chart.hoverHighlight;
    const event = args.event;
    if (event.type == "mouseout") {
      if (hoverHighlight.previous != null) {
        this.setActive(chart, hoverHighlight.previous, false);
      }
      hoverHighlight.previous = null;
    } else if (
      event.type == "mousemove" &&
      chart.tooltip.dataPoints != null &&
      chart.tooltip.dataPoints.length > 0
    ) {
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
