"use strict";
const progress = {
  bar: null,
  /**
   * Update global progress bar
   *
   * @param {Event} evt Triggering event
   * @param {Number} v Progress value
   */
  update: function (evt, v) {
    // Only do progress bar for whole page
    if (evt && evt.target.id != "main") return;
    if (this.bar == null) this.bar = htmx.find("#page-progress");

    if (v == 0) {
      htmx.addClass(this.bar, "open");
      this.bar.innerHTML = "<div style='width:0'></div>";
    } else if (v == 1) {
      htmx.removeClass(this.bar, "open");
      this.bar.firstChild.style.width = "100%";
    } else {
      htmx.addClass(this.bar, "open");
      this.bar.firstChild.style.width = `${v * 100}%`;
    }
  },
};
