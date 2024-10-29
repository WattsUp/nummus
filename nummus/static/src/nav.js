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
    /**
     * After sidebar swap has settled, reopen sidebar
     *
     * @param {Event} event Triggering event
     */
    preserveOpen: function(event) {
        // Call is only on button on open sidebar, so add open back
        document.querySelector('#sidebar').classList.add('open');
    },
};

window.addEventListener('click', navigation.closeDropdown);
window.addEventListener('click', navigation.closeSidebar);
