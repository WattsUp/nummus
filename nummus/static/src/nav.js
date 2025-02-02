'use strict';
const nav = {
    /**
     * On click, open nav-drawer
     */
    openDrawer: function() {
        htmx.addClass(htmx.find('#nav-drawer'), 'open');
    },
    /**
     * On click of outside of nav-drawer, close nav-drawer
     *
     * @param {Event} event Triggering event
     */
    closeDrawer: function(event) {
        const query = '#nav-drawer, #nav-drawer *, .nav-opener, .nav-opener *';
        if (!event || !event.target.matches(query)) {
            htmx.removeClass(htmx.find('#nav-drawer'), 'open');
        }
    },
};

window.addEventListener('click', nav.closeDrawer);
