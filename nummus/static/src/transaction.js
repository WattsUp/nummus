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
      "Unlinked transaction will be deleted.",
    );
  },
};
