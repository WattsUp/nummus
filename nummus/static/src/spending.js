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
   * Create spending Chart
   *
   * @param {Object} byAccount Spending by account from spending controller
   * @param {Object} byPayee Spending by payee from spending controller
   * @param {Object} byCategory Spending by category from spending controller
   * @param {Object} byLabel Spending by label from spending controller
   * @param {Object} currencyFormat See Python side: Currency
   */
  update(byAccount, byPayee, byCategory, byLabel, currencyFormat) {
    const cf = newCurrencyFormat(currencyFormat);
    this.updateOne("spending-by-account", byAccount, cf);
    this.updateOne("spending-by-payee", byPayee, cf);
    this.updateOne("spending-by-category", byCategory, cf);
    this.updateOne("spending-by-label", byLabel, cf);

    updateColorSwatches();
  },
  /**
   * Update one chart
   *
   * @param {String} id - Top div id
   * @param {Array} raw - Array [[name, value], ...]
   * @param {function} currencyFormat Function to format number, see newCurrencyFormat
   */
  updateOne(id, raw, currencyFormat) {
    const canvas = htmx.find(`#${id} canvas`);
    const breakdown = htmx.find(`#${id}>div:last-of-type`);
    const ctx = canvas.getContext("2d");

    const total = raw.reduce((cum, item) => cum + item[1], 0);
    const collapseThreshold = total * 0.005;

    const spin = Math.max(20, 300 / raw.length);
    const data = raw.map((item, i) => ({
      name: item[0] ?? "[none]",
      amount: item[1],
      colorSpin: item[0] ? i * spin : 0,
      borderColorRaw: item[0] ? "primary" : "outline",
      backgroundColorRaw: [
        item[0] ? "primary-container" : "surface-container-low",
        "80",
      ],
      collapse: item[1] < collapseThreshold,
    }));

    breakdown.innerHTML = "";
    let totalOther = 0;
    data.forEach((category, i) => {
      const v = category.amount;
      if (i >= 200) {
        totalOther += v;
        return;
      }

      const row = document.createElement("div");
      htmx.addClass(row, "flex");
      htmx.addClass(row, "gap-1");
      htmx.addClass(row, "not-last:mb-0.5");

      const square = document.createElement("div");
      square.setAttribute("color-spin", category.colorSpin);
      square.setAttribute("border", category.borderColorRaw);
      square.setAttribute("bg", category.backgroundColorRaw[0]);
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
      value.innerHTML = currencyFormat(v);
      row.appendChild(value);

      breakdown.appendChild(row);
    });

    if (totalOther) {
      const row = document.createElement("div");
      htmx.addClass(row, "flex");
      htmx.addClass(row, "gap-1");
      htmx.addClass(row, "not-last:mb-0.5");

      const square = document.createElement("div");
      htmx.addClass(square, "w-6");
      htmx.addClass(square, "h-6");
      htmx.addClass(square, "shrink-0");
      htmx.addClass(square, "border");
      htmx.addClass(square, "border-outline");
      htmx.addClass(square, "bg-surface-container-high");
      htmx.addClass(square, "rounded");
      row.appendChild(square);

      const name = document.createElement("div");
      name.innerHTML = `Other (${data.length - 200} more)`;
      htmx.addClass(name, "grow");
      htmx.addClass(name, "truncate");
      row.appendChild(name);

      const value = document.createElement("div");
      value.innerHTML = currencyFormat(totalOther);
      row.appendChild(value);

      breakdown.appendChild(row);
    }

    if (this.charts[id] && ctx == this.charts[id].ctx) {
      nummusChart.updatePie(this.charts[id], currencyFormat, data);
    } else {
      this.charts[id] = nummusChart.createPie(
        ctx,
        currencyFormat,
        data,
        [pluginHoverHighlight],
        { plugins: { hoverHighlight: { parent: `${id}>div:last-of-type` } } },
      );
    }
  },
};
