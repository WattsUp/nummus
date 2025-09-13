"use strict";
const spending = {
  chart: null,
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
  update(byAccount, byPayee, byCategory, byTag) {},
};
