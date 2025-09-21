"use strict";
const txnCat = {
  /**
   * Update is essential spending toggle when group changes
   *
   * INCOME cannot be essential spending
   */
  updateEssential: function () {
    const isIncome = htmx.find("#dialog [name='group']").value == "INCOME";
    const essential = htmx.find("#dialog [name='essential-spending']");
    essential.disabled = isIncome;
    essential.checked = !isIncome && essential.checked;
  },
  /**
   * On click of delete category, confirm action
   *
   * @param {Event} evt Triggering event
   */
  confirmDelete: function (evt) {
    dialog.confirm(
      "Delete category",
      "Delete",
      () => {
        htmx.trigger(evt.target, "delete");
      },
      "Any transactions assigned to this category will revert to uncategorized.",
    );
  },
};
