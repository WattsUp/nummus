'use strict';
const dialog = {
    pending: false,
    /**
     * Close dialog if no pending changes
     *
     * @param {boolean} force true will ignore pending changes
     */
    close: function(force) {
        if (!force && dialog.pending) {
            dialog.confirm('Discard draft?', 'Discard', () => {
                dialog.pending = false;
                htmx.find('#dialog').innerHTML = '';
            });
            return;
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
        const saveBtn = htmx.find('#dialog-save');
        if (!saveBtn) return;
        const allFilled = dialog.checkRequired();
        const anyInvalid = htmx.find('#dialog error:not(:empty)') != null;
        saveBtn.disabled = !allFilled || anyInvalid;
    },
    /**
     * Add event listeners to the dialog
     */
    addListeners: function() {
        const d = htmx.find('#dialog');
        htmx.findAll(d, '[required]').forEach((e) => {
            htmx.on(e, 'input', dialog.updateSave);
        });
        const focusNext = function(start) {
            const results = htmx.findAll(
                d,
                'input:not(:disabled), textarea:not(:disabled), select:not(:disabled)');
            for (const next of results) {
                if (next.compareDocumentPosition(start) ===
                    Node.DOCUMENT_POSITION_PRECEDING) {
                    next.focus({preventScroll: true});
                    next.selectionStart = 0;
                    next.selectionEnd = next.value.length;
                    return;
                }
            }
        };
        htmx.findAll(d, 'input, textarea, select').forEach((e) => {
            htmx.on(e, 'input', dialog.changes);
            htmx.on(e, 'keypress', (evt) => {
                if (evt.key == 'Enter') {
                    evt.preventDefault();
                    focusNext(e);
                }
            });
            htmx.on(e, 'focus', (evt) => {
                // Smooth scroll nearest
                evt.preventDefault();
                e.scrollIntoView({block: 'nearest'});
            })
        });
    },
    /**
     * On load of a dialog, addListeners and autofocus
     */
    onLoad: function() {
        dialog.addListeners();
        // Only autofocus for not mobile
        if (window.screen.width >= 768) {
            const d = htmx.find('#dialog');
            const firstInput = htmx.find(d, 'input, textarea, select');
            firstInput.focus();
            if (firstInput.type == 'text') {
                const n = firstInput.value.length;
                firstInput.setSelectionRange(n, n);
            }
        }
    },
    /**
     * Create confirm dialog
     *
     * @param {String} headline Headline text
     * @param {String} actionLabel Label for the action button
     * @param {Function} action Event handler for the action button
     * @param {String} details Explanation text
     */
    confirm: function(headline, actionLabel, action, details) {
        const e = htmx.find('#confirm-dialog');
        e.innerHTML = `
            <div><h1>${headline}</h1></div>
            <p>${details ?? ''}</p>
            <div class="flex justify-end">
                <button class="btn-text" onclick="dialog.closeConfirm()">Cancel</button>
                <button class="btn-text" onclick="dialog.closeConfirm()">
                    ${actionLabel}
                </button>
            </div>
            `;
        htmx.on(htmx.find(e, 'button:last-child'), 'click', action);
    },
    /**
     * Close confirm dialog
     */
    closeConfirm: function() {
        htmx.find('#confirm-dialog').innerHTML = '';
    },
};
