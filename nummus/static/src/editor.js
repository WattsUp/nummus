'use strict';

const editor = {
    /**
     * Add event listeners to form inputs
     *
     * @param {string} form ID of form to watch for changes
     */
    addListeners: function(form) {
        this.removeListeners(form);
        document.querySelectorAll(`#${form} input, #${form} textarea`)
            .forEach((e) => {
                e.addEventListener('keyup', this.onChanges);
            });
        document.querySelectorAll(`#${form} input[type=checkbox]`)
            .forEach((e) => {
                e.addEventListener('change', this.onChanges);
            });
        document.querySelectorAll(`#${form} input[type=date]`).forEach((e) => {
            e.addEventListener('change', this.onChanges);
        });
        document.querySelectorAll(`#${form} select`).forEach((e) => {
            e.addEventListener('change', this.onChanges);
        });
    },
    /**
     * Remove event listeners to form inputs
     *
     * @param {string} form ID of form to watch for changes
     */
    removeListeners: function(form) {
        document.querySelectorAll(`#${form} input, #${form} textarea`)
            .forEach((e) => {
                e.removeEventListener('keyup', this.onChanges);
            });
        document.querySelectorAll(`#${form} input[type=checkbox]`)
            .forEach((e) => {
                e.removeEventListener('change', this.onChanges);
            });
        document.querySelectorAll(`#${form} input[type=date]`).forEach((e) => {
            e.removeEventListener('change', this.onChanges);
        });
        document.querySelectorAll(`#${form} select`).forEach((e) => {
            e.removeEventListener('change', this.onChanges);
        });
    },
    /**
     * Listener on input to clear error boxes
     */
    onChanges: function() {
        let e = document.querySelector('#overlay-error');
        if (e) {
            e.innerHTML = '';
        }
        e = document.querySelector('#sidebar-error');
        if (e) {
            e.innerHTML = '';
        }
    },
};

const overlayEditor = {
    anyPendingChanges: false,
    /**
     * Add event listeners to form inputs
     *
     * @param {string} form ID of form to watch for changes
     */
    addListeners: function(form) {
        this.removeListeners(form);
        document.querySelectorAll(`#${form} input, #${form} textarea`)
            .forEach((e) => {
                e.addEventListener('keyup', this.pendingChanges);
            });
        document.querySelectorAll(`#${form} input[type=checkbox]`)
            .forEach((e) => {
                e.addEventListener('change', this.pendingChanges);
            });
        document.querySelectorAll(`#${form} input[type=date]`).forEach((e) => {
            e.addEventListener('change', this.pendingChanges);
        });
        document.querySelectorAll(`#${form} select`).forEach((e) => {
            e.addEventListener('change', this.pendingChanges);
        });
        // Also add base listeners
        editor.addListeners(form);
    },
    /**
     * Remove event listeners to form inputs
     *
     * @param {string} form ID of form to watch for changes
     */
    removeListeners: function(form) {
        document.querySelectorAll(`#${form} input, #${form} textarea`)
            .forEach((e) => {
                e.removeEventListener('keyup', this.pendingChanges);
            });
        document.querySelectorAll(`#${form} input[type=checkbox]`)
            .forEach((e) => {
                e.removeEventListener('change', this.pendingChanges);
            });
        document.querySelectorAll(`#${form} input[type=date]`).forEach((e) => {
            e.removeEventListener('change', this.pendingChanges);
        });
        document.querySelectorAll(`#${form} select`).forEach((e) => {
            e.removeEventListener('change', this.pendingChanges);
        });
        // Also remove base listeners
        editor.removeListeners(form);
    },
    /**
     * Listener on input to set pending changes
     */
    pendingChanges: function() {
        overlayEditor.anyPendingChanges = true;
    },
    /**
     * Close overlay if no pending changes
     */
    close: function() {
        if (overlayEditor.anyPendingChanges) {
            var result = window.confirm(
                'There are pending changes. Are you sure you want to cancel edits?');
            if (!result) {
                return
            }
        }
        overlayEditor.anyPendingChanges = false;
        document.querySelector('#overlay').innerHTML = '';
    },
};
