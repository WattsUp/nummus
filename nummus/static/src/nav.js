'use strict';
const nav = {
    lastScroll: null,
    headerHeight: null,
    headerTranslate: 0,
    barRatio: null,
    fabRatio: null,
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
    /**
     * On scroll down, hide nav elements. On up, show
     */
    onScroll: function() {
        // Only do stuff for mobile
        if (window.screen.width >= 768) {
            return;
        }
        const dy = window.scrollY - (nav.lastScroll ?? window.scrollY);
        nav.lastScroll = window.scrollY;

        const header = htmx.find('#nav-header');
        if (nav.headerHeight == null) {
            const rect = header.getBoundingClientRect();
            nav.headerHeight = rect.height;
        }

        const bar = htmx.find('#nav-bar');
        if (nav.barRatio == null) {
            const rect = bar.getBoundingClientRect();
            nav.barRatio = rect.height / nav.headerHeight;
        }

        const fab = htmx.find('#nav-fab');
        if (nav.fabRatio == null) {
            const rect = fab.getBoundingClientRect();
            nav.fabRatio = (rect.width + window.screen.width - rect.right) /
                nav.headerHeight;
        }

        if (dy > 0) {
            nav.headerTranslate = nav.headerHeight * 1.1;
        } else if (window.scrollY == 0 || dy < 0) {
            nav.headerTranslate = 0;
        }

        barTranslate = nav.headerTranslate * nav.barRatio;
        fabTranslate = nav.headerTranslate * nav.fabRatio;

        header.style.translate = `0 ${- nav.headerTranslate}px`;
        bar.style.translate = `0 ${barTranslate}px`;
        fab.style.translate = `${fabTranslate}px ${- barTranslate}px`;
    },
};

htmx.on('click', nav.closeDrawer);
htmx.on(window, 'scroll', nav.onScroll);
