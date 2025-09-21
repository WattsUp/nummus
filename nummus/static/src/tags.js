"use strict";
const tags = {
  /**
   * On click of delete tag, confirm action
   *
   * @param {Event} evt Triggering event
   */
  confirmDelete: function (evt) {
    dialog.confirm(
      "Delete tag",
      "Delete",
      () => {
        htmx.trigger(evt.target, "delete");
      },
      "This tag will be removed from all transactions.",
    );
  },
};
