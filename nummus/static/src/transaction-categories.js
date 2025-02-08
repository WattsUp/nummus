const txnCat = {
    /**
     * Update is essential toggle when group changes
     *
     * INCOME cannot be essential spending
     */
    updateEssential: function() {
        const isIncome =
            htmx.find('#dialog [name=\'group\']').value == 'INCOME';
        const essential = htmx.find('#dialog [name=\'essential\']');
        essential.disabled = isIncome;
        essential.checked = !isIncome && essential.checked;
    },
}
