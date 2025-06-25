"use strict";
const importFile = {
  /** Before sending file, hide the previous success */
  beforeSend() {
    const success = htmx.find("#import-success");
    if (success) {
      success.remove();
    }
  },
  /**
   * When file upload starts, display progress bar
   *
   * @param {Event} evt - Triggering event
   */
  xhrLoadStart(evt) {
    const file = htmx.find("#dialog>form input[type=file]").value;
    if (file) {
      htmx.removeClass(htmx.find("#import-upload-progress"), "hidden");
    }
  },
  /**
   * On file upload progress, update progress bar
   *
   * @param {Event} evt - Triggering event
   */
  xhrProgress(evt) {
    htmx
      .find("#import-upload-progress>progress")
      .setAttribute("value", (evt.detail.loaded / evt.detail.total) * 100);
  },
  /** After sending file, hide progress bar */
  xhrLoadEnd() {
    htmx.addClass(htmx.find("#import-upload-progress"), "hidden");
  },
};
