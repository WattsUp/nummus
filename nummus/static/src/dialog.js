const dialog = {
    pending: false,
    /**
     * Close dialog if no pending changes
     */
    close: function() {
        if (dialog.pending) {
            var result = window.confirm(
                'There are pending changes. Are you sure you want to cancel edits?');
            if (!result) {
                return
            }
        }
        dialog.pending = false;
        htmx.find('#dialog').innerHTML = '';
    },
    /**
     * On dialog changes, set pending flag
     */
    changes: function() {
        dialog.pending = true;
    },
    /**
     * On dialog reset, reset pending flag
     */
    reset: function() {
        dialog.pending = false;
    },
    /**
     * Check if all required element are populated
     *
     * @return boolean true if all required elements are filled
     */
    checkRequired: function() {
        let allFilled = true
        htmx.findAll('#dialog [required]').forEach((e) => {
            if (!allFilled) return;
            if (!e.value) {
                allFilled = false;
                return;
            }
        });
        return allFilled;
    },
    /**
     * Update dialog save button
     */
    updateSave: function() {
        const allFilled = dialog.checkRequired();
        const anyInvalid = htmx.find('#dialog input~error:not(:empty)') != null;
        htmx.find('#dialog-save').disabled = !allFilled || anyInvalid;
    },
    /**
     * Add event listeners to the dialog
     */
    addListeners: function() {
        htmx.findAll('#dialog [required]').forEach((e) => {
            htmx.on(e, 'input', dialog.updateSave);
        });
        const focusNext = function(start) {
            const results = htmx.findAll(
                '#dialog input:not(:disabled), #dialog select:not(:disabled)');
            for (const next of results) {
                if (next.compareDocumentPosition(start) ===
                    Node.DOCUMENT_POSITION_PRECEDING) {
                    next.focus();
                    return;
                }
            }
        };
        htmx.findAll('#dialog input, #dialog select').forEach((e) => {
            e.addEventListener('keypress', (evt) => {
                if (evt.key == 'Enter') {
                    evt.preventDefault();
                    focusNext(e);
                }
            });
        });
    },
};
