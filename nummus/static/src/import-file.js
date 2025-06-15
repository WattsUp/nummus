"use strict";
const importFile = {
  beforeSend: function () {
    document.querySelector("#import-button>button").disabled = true;
    const success = document.querySelector("#import-success");
    if (success) {
      success.remove();
    }
  },
  xhrLoadStart: function (evt) {
    const file = document.querySelector("#import-form>input[type=file]").value;
    if (file) {
      document
        .querySelector("#import-upload-progress")
        .classList.remove("hidden");
    }
  },
  xhrProgress: function (evt) {
    document
      .querySelector("#import-upload-progress>progress")
      .setAttribute("value", (evt.detail.loaded / evt.detail.total) * 100);
  },
  xhrLoadEnd: function () {
    document.querySelector("#import-upload-progress").classList.add("hidden");
  },
};
