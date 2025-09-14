"use strict";
const spending = {
  charts: {},
  /**
   * On change of period select, hide or show date input
   */
  changePeriod() {
    const select = htmx.find("#spending-filters [name='period']");
    const notCustom = select.value != "custom";
    htmx.findAll("#spending-filters [type='date']").forEach((e) => {
      e.disabled = notCustom;
    });
  },
  /**
   * Create Performance Chart
   *
   * @param {Object} byAccount Spending by account from spending controller
   * @param {Object} byPayee Spending by payee from spending controller
   * @param {Object} byCategory Spending by category from spending controller
   * @param {Object} byTag Spending by tag from spending controller
   */
  update(byAccount, byPayee, byCategory, byTag) {
    this.updateOne("spending-by-account", byAccount);
    this.updateOne("spending-by-payee", byPayee);
    this.updateOne("spending-by-category", byCategory);
    this.updateOne("spending-by-tag", byTag);

    updateColorSwatches();
  },
  /**
   * @param {String} id - Top div id
   * @param {Array} raw - Array [[name, value], ...]
   */
  updateOne(id, raw) {
    const canvas = htmx.find(`#${id} canvas`);
    const breakdown = htmx.find(`#${id}>div:last-of-type`);
    const ctx = canvas.getContext("2d");

    const spin = Math.max(20, 300 / raw.length);
    const data = raw.map((item, i) => ({
      name: item[0] ?? "[none]",
      amount: -item[1],
      colorSpin: i * spin,
      borderColorRaw: "primary",
      backgroundColorRaw: ["primary-container", "80"],
    }));

    if (this.charts[id] && ctx == this.charts[id].ctx) {
      nummusChart.updatePie(this.charts[id], data);
    } else {
      this.charts[id] = nummusChart.createPie(ctx, data);
    }

    breakdown.innerHTML = "";
    for (const category of data) {
      const v = category.amount;

      const row = document.createElement("div");
      htmx.addClass(row, "flex");
      htmx.addClass(row, "gap-1");
      htmx.addClass(row, "not-last:mb-0.5");

      const square = document.createElement("div");
      square.setAttribute("color-spin", category.colorSpin);
      htmx.addClass(square, "w-6");
      htmx.addClass(square, "h-6");
      htmx.addClass(square, "shrink-0");
      htmx.addClass(square, "border");
      htmx.addClass(square, "rounded");
      row.appendChild(square);

      const name = document.createElement("div");
      name.innerHTML = category.name;
      htmx.addClass(name, "grow");
      htmx.addClass(name, "truncate");
      row.appendChild(name);

      const value = document.createElement("div");
      value.innerHTML = formatterF2.format(v);
      row.appendChild(value);

      breakdown.appendChild(row);
    }
  },
};
