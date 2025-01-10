'use strict';
const numpad = {
    currentFocus: null,
    debounceTimer: null,
    /**
     * Add event listeners to form inputs
     *
     * @param {string} form ID of form to watch for changes
     */
    addListeners: function(form) {
        this.removeListeners(form);
        document.querySelectorAll(`#${form} input[inputmode=none]`)
            .forEach((e) => {
                e.addEventListener('focus', this.onFocus);
            });
    },
    /**
     * Remove event listeners to form inputs
     *
     * @param {string} form ID of form to watch for changes
     */
    removeListeners: function(form) {
        document.querySelectorAll(`#${form} input[inputmode=none]`)
            .forEach((e) => {
                e.removeEventListener('focus', this.onFocus);
            });
    },
    /**
     * On focus of input, show virtual numpad
     *
     * @param {Event} event Triggering event
     */
    onFocus: function(event) {
        numpad.currentFocus = event.target;
        document.querySelector('#overlay').style.paddingBottom = '18rem';
        document.body.style.paddingBottom = '18rem';
        document.querySelector('#virtual-numpad')
            .classList.remove('translate-y-72');
    },
    /**
     * Close virtual numpad
     *
     * @param {Event} event Triggering event
     */
    close: function(event) {
        if (!event ||
            !event.target.matches(
                '#virtual-numpad, #virtual-numpad *, input[inputmode=none]')) {
            numpad.currentFocus = null;
            document.querySelector('#virtual-numpad')
                .classList.add('translate-y-72');
            document.querySelector('#overlay').style.paddingBottom = '0';
            document.body.style.paddingBottom = '0';
        }
    },
    /**
     * On numpad button, add character to input
     *
     * @param {string} c Character to add to input
     */
    input: function(c) {
        clearTimeout(numpad.debounceTimer);
        if (numpad.currentFocus) {
            numpad.debounceTimer = setTimeout(() => {
                const i = numpad.currentFocus.selectionStart;
                const v = numpad.currentFocus.value
                // Simulate keyboard
                const event = new KeyboardEvent('keyup');
                numpad.currentFocus.dispatchEvent(event);

                numpad.currentFocus.value = v.slice(0, i) + c + v.slice(i);

                // Reset focus
                numpad.currentFocus.focus();
                numpad.currentFocus.setSelectionRange(i + 1, i + 1);
            }, 100);
        }
    },
    /**
     * On numpad backspace, remove last character
     */
    backspace: function() {
        clearTimeout(numpad.debounceTimer);
        if (numpad.currentFocus) {
            numpad.debounceTimer = setTimeout(() => {
                const i = numpad.currentFocus.selectionStart;
                const v = numpad.currentFocus.value
                // Simulate keyboard
                const event = new KeyboardEvent('keyup');
                numpad.currentFocus.dispatchEvent(event);

                if (i > 0) {
                    numpad.currentFocus.value = v.slice(0, i - 1) + v.slice(i);
                }

                // Reset focus
                numpad.currentFocus.focus();
                numpad.currentFocus.setSelectionRange(i - 1, i - 1);
            }, 100);
        }
    },
};

window.addEventListener('click', numpad.close);
