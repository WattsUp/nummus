const transactionEditor = {
    anyPendingChanges: false,
    /**
     * Add event listeners to form inputs
     */
    addListeners: function(){
        this.removeListeners();
        document.querySelectorAll("#form-txn input").forEach((e)=>{
            e.addEventListener("keyup", this.pendingChanges);
        });
        document.querySelectorAll("#form-txn select").forEach((e)=>{
            e.addEventListener("change", this.pendingChanges);
        });
    },
    /**
     * Remove event listeners to form inputs
     */
    removeListeners: function(){
        document.querySelectorAll("#form-txn input").forEach((e)=>{
            e.removeEventListener("keyup", this.pendingChanges);
        });
        document.querySelectorAll("#form-txn select").forEach((e)=>{
            e.removeEventListener("change", this.pendingChanges);
        });
    },
    /**
     * Listener on input to set pending changes
    */
    pendingChanges: function() {
        transactionEditor.anyPendingChanges = true;
    },
    /**
     * Listener before a request to cancel edits
     *
     * @param {Event} e Before request event
    */
    beforeCancel: function(e) {
        if (transactionEditor.anyPendingChanges) {
            var result = window.confirm("There are pending changes. Are you sure you want to cancel edits?");
           if (result) {
                transactionEditor.anyPendingChanges = false;
            } else {
                e.preventDefault();
            }
        }
    },
};

window.addEventListener("beforeunload", (e)=>{
    if (transactionEditor.anyPendingChanges){

    e.preventDefault();
    e.returnValue = "";
    }
});
