const overlayEditor = {
    anyPendingChanges: false,
    /**
     * Add event listeners to form inputs
     *
     * @param {string} form ID of form to watch for changes
     */
    addListeners: function(form) {
        this.removeListeners(form);
        document
            .querySelectorAll(
                `#${form} input:not([type=checkbox]), #${form} textarea`)
            .forEach((e) => {
                e.addEventListener('keyup', this.pendingChanges);
            });
        document.querySelectorAll(`#${form} input[type=checkbox]`)
            .forEach((e) => {
                e.addEventListener('change', this.pendingChanges);
            });
        document.querySelectorAll(`#${form} select`).forEach((e) => {
            e.addEventListener('change', this.pendingChanges);
        });
    },
    /**
     * Remove event listeners to form inputs
     *
     * @param {string} form ID of form to watch for changes
     */
    removeListeners: function(form) {
        document
            .querySelectorAll(
                `#${form} input:not([type=checkbox]), #${form} textarea`)
            .forEach((e) => {
                e.removeEventListener('keyup', this.pendingChanges);
            });
        document.querySelectorAll(`#${form} input[type=checkbox]`)
            .forEach((e) => {
                e.removeEventListener('change', this.pendingChanges);
            });
        document.querySelectorAll(`#${form} select`).forEach((e) => {
            e.removeEventListener('change', this.pendingChanges);
        });
    },
    /**
     * Listener on input to set pending changes
     */
    pendingChanges: function() {
        overlayEditor.anyPendingChanges = true;
        console.log('changes');
    },
    /**
     * Listener before a request to cancel edits
     *
     * @param {Event} e Before request event
     */
    beforeCancel: function(e) {
        if (overlayEditor.anyPendingChanges) {
            var result = window.confirm(
                'There are pending changes. Are you sure you want to cancel edits?');
            if (result) {
                overlayEditor.anyPendingChanges = false;
            } else {
                e.preventDefault();
            }
        }
    },
};

window.addEventListener('beforeunload', (e) => {
    if (overlayEditor.anyPendingChanges) {
        e.preventDefault();
        e.returnValue = '';
    }
});
