"use strict";
const txn = {
  /**
   * On change of period select, hide or show date input
   */
  changePeriod: function () {
    const select = htmx.find("#txn-filters [name='period']");
    const notCustom = select.value != "custom";
    htmx.findAll("#txn-filters [type='date']").forEach((e) => {
      e.disabled = notCustom;
    });
  },
  /**
   * On click of clear transaction, confirm action
   *
   * @param {Event} evt Triggering event
   */
  confirmClear: function (evt) {
    dialog.confirm(
      "Clear transaction",
      "Clear",
      () => {
        htmx.trigger(evt.target, "clear");
      },
      "Transaction will be marked as cleared. Only use on manually updated accounts. Cannot undo.",
    );
  },
  /**
   * On click of delete transaction, confirm action
   *
   * @param {Event} evt Triggering event
   */
  confirmDelete: function (evt) {
    dialog.confirm(
      "Delete transaction",
      "Delete",
      () => {
        htmx.trigger(evt.target, "delete");
      },
      "Uncleared transaction will be deleted.",
    );
  },
};
