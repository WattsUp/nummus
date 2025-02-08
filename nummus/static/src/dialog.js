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
};
