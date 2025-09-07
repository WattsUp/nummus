"use strict";

const chips = {
  /**
   *
   * On input, add a chip
   *
   * @param {Event} evt - Triggering event
   * @param {String} name - Name of chip input
   */
  append(evt, name) {
    if (evt.key != "Enter") return;
    const tgt = evt.target;
    if (!tgt.value) return;

    // Create a chip
    const chip = document.createElement("div");
    chip.innerHTML = `
      <input type="hidden" name="${name}" value="${tgt.value}" />
      ${tgt.value}
      <icon onclick="this.parentNode.remove()">clear</icon>
    `;

    tgt.parentNode.insertBefore(chip, tgt);
    tgt.value = "";
  },
};
