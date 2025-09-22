"use strict";
const nummusLabels = {
  /**
   * On click of delete label, confirm action
   *
   * @param {Event} evt Triggering event
   */
  confirmDelete: function (evt) {
    dialog.confirm(
      "Delete label",
      "Delete",
      () => {
        htmx.trigger(evt.target, "delete");
      },
      "This label will be removed from all transactions.",
    );
  },
};
