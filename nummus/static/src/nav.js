const navigation = {
    /**
     * On click of a nav-folder title, toggle open
     *
     * @param {Element} src Triggering element
     */
    openDropdown: function(src) {
        let navFolder = src.parentNode;
        document.querySelectorAll('.nav-folder').forEach((e) => {
            if (e != navFolder) {
                e.classList.remove('open');
            } else {
                e.classList.toggle('open');
            }
        });
    },
    /**
     * On click of a nav-link, close all nav-folders
     *
     * @param {Event} event Triggering event
     */
    closeDropdown: function(event) {
        if (!event || !event.target.matches('.nav-folder, .nav-folder *')) {
            document.querySelectorAll('.nav-folder').forEach((e) => {
                e.classList.remove('open');
            });
        }
    },
    /**
     * On click of a txn-filter icon, toggle open
     *
     * @param {Element} src Triggering element
     */
    openTxnFilter: function(src) {
        let txnFilter = src.parentNode;
        document.querySelectorAll('.txn-filter').forEach((e) => {
            if (e != txnFilter) {
                e.classList.remove('open');
            } else {
                e.classList.toggle('open');
            }
        });
    },
    /**
     * On click outside a txn-filter, close all txn-filters
     *
     * @param {Event} event Triggering event
     */
    closeTxnFilter: function(event) {
        if (!event || !event.target.matches('.txn-filter, .txn-filter *')) {
            document.querySelectorAll('.txn-filter').forEach((e) => {
                e.classList.remove('open');
            });
        }
    },
    /**
     * On click, open accounts sidebar
     */
    openSidebar: function() {
        document.querySelector('#sidebar').classList.toggle('open');
    },
    /**
     * On click of outside of sidebar, close sidebar
     *
     * @param {Event} event Triggering event
     */
    closeSidebar: function(event) {
        if (!event ||
            !event.target.matches(
                '#sidebar, #sidebar *, .sidebar-opener, .sidebar-opener *')) {
            document.querySelector('#sidebar').classList.remove('open');
        }
    },
};

window.addEventListener('click', navigation.closeDropdown);
window.addEventListener('click', navigation.closeSidebar);
window.addEventListener('click', navigation.closeTxnFilter);
