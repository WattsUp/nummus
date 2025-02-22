'use strict';
const txn = {
    /**
     * On change of period select, hide or show date input
     */
    changePeriod: function() {
        const select = htmx.find('#txn-filters [name=\'period\']');
        const notCustom = select.value != 'custom';
        htmx.findAll('#txn-filters [type=\'date\']').forEach((e) => {
            e.disabled = notCustom;
        });
    },
};
