'use strict';
const budgeting = {
    table: null,
    isGroup: false,
    dragItem: null,
    dragItemHeight: null,
    dragItemParent: null,
    dragItemSibling: null,
    dragItemGroup: null,
    staticItems: [],
    staticItemsY: [],
    initialX: null,
    initialY: null,
    initialMouseX: null,
    initialMouseY: null,
    mouseOffsetX: null,
    mouseOffsetY: null,
    isDragging: false,
    groupOpen: {},
    /**
     * Set up budgeting drag listeners
     */
    setup: function() {
        this.table = document.querySelector('#budget-table');

        // Remove any that exist
        this.table.removeEventListener('mousedown', this.dragStart);
        document.removeEventListener('mouseup', this.dragEnd);

        this.table.addEventListener('mousedown', this.dragStart);
        document.addEventListener('mouseup', this.dragEnd);
    },
    /**
     * On click, record initial positions and such
     *
     * @param {Event} event Triggering event
     */
    dragStart: function(event) {
        const target = event.target;
        if (target.matches('.budget-group-handle, .budget-group-handle *')) {
            budgeting.isGroup = true;
            budgeting.dragItem = target.closest('.budget-group');
            budgeting.staticItems = document.querySelectorAll('.budget-group');
        } else if (target.matches('.budget-row-handle, .budget-row-handle *')) {
            budgeting.isGroup = false;
            budgeting.dragItem = target.closest('.budget-row');
            // Transform both rows and headers
            budgeting.staticItems = document.querySelectorAll(
                '.budget-row, .budget-group-header, .budget-group-toggle-label');
        } else {
            // Not a handle, ignore mouse up
            return;
        }

        let firstGroup = true;
        let firstGroupLabel = true;
        budgeting.staticItems =
            Array.from(budgeting.staticItems).filter((e) => {
                if (e == budgeting.dragItem) {
                    return false;
                }
                if (!budgeting.isGroup) {
                    if (e.matches('.budget-group-header') && firstGroup) {
                        firstGroup = false;
                        return false;
                    }
                    if (e.matches('.budget-group-toggle-label') &&
                        firstGroupLabel) {
                        firstGroupLabel = false;
                        return false;
                    }
                }
                return true;
            });
        budgeting.dragItemParent = budgeting.dragItem.parentNode;
        budgeting.dragItemSibling = budgeting.dragItem.nextSibling;
        budgeting.dragItemGroup = budgeting.dragItem.closest('.budget-group');

        // Set position attribute
        document.querySelectorAll('.budget-row').forEach((e, i) => {
            e.setAttribute('position', i);
        });
        document.querySelectorAll('.budget-group').forEach((e, i) => {
            e.setAttribute('position', i);
        });

        // Record initial position
        const rect = budgeting.dragItem.getBoundingClientRect();
        budgeting.mouseOffsetX = event.clientX - rect.x;
        budgeting.mouseOffsetY = event.clientY - rect.y;
        budgeting.initialMouseX = event.clientX;
        budgeting.initialMouseY = event.clientY;

        // Make nothing selectable
        budgeting.table.classList.add('select-none');

        document.addEventListener('mousemove', budgeting.dragStartTest);
    },
    /**
     * Once mouse moves enough, actually start dragging
     *
     * @param {Event} event Triggering event
     */
    dragStartTest(event) {
        const dx = event.clientX - budgeting.initialMouseX;
        const dy = event.clientY - budgeting.initialMouseY;
        const delta = Math.sqrt(dx * dx + dy * dy);

        if (delta < 10) {
            return;
        }
        document.removeEventListener('mousemove', budgeting.dragStartTest);

        // If dragging a row, move to top so it is visible
        // Also moving group to top makes everything only translate down
        if (budgeting.isGroup) {
            document.querySelector('#budget-temp-group')
                .append(budgeting.dragItem);
        } else {
            document.querySelector('#budget-temp-row')
                .append(budgeting.dragItem);
        }

        // Prepare for dragging
        budgeting.dragItem.classList.add('dragging');

        budgeting.isDragging = true;
        // Add move listener
        document.addEventListener('mousemove', budgeting.drag);

        // Close all groups if dragging a group
        document.querySelectorAll('.budget-group-toggle').forEach((e) => {
            budgeting.groupOpen[e.id] = e.checked;
            e.checked = budgeting.isGroup;
        });

        budgeting.updateInitialOffset(event);
    },
    /**
     * Update the initial locations once opening/closing groups finishes
     *
     * @param {Event} event Triggering event
     */
    updateInitialOffset(event) {
        // After toggling open, compute initial location
        const rect = budgeting.dragItem.getBoundingClientRect();
        budgeting.initialX = rect.x + budgeting.mouseOffsetX;
        budgeting.initialY = rect.y + budgeting.mouseOffsetY;
        budgeting.dragItemHeight = rect.height;

        budgeting.staticItems.forEach((e, i) => {
            const rect = e.getBoundingClientRect();
            budgeting.staticItemsY[i] = rect.y;
        });

        budgeting.drag(event);
    },
    /**
     * On mouse move, translate rows
     *
     * @param {Event} event Triggering event
     */
    drag: function(event) {
        const offsetX = event.clientX - budgeting.initialX;
        const offsetY = event.clientY - budgeting.initialY;
        const dragItemY = event.clientY - budgeting.mouseOffsetY -
            budgeting.dragItemHeight / 2;

        budgeting.dragItem.style.transform =
            `translate(${offsetX}px, ${offsetY}px)`;

        budgeting.staticItems.forEach((e, i) => {
            const initialY = budgeting.staticItemsY[i];
            let offset = 0;
            if (offsetY > 0) {
                if (initialY < dragItemY && initialY > budgeting.initialY) {
                    // dragItem is going down
                    // and e is between initial and new positions
                    // so move e up
                    offset = -budgeting.dragItemHeight;
                    e.setAttribute('reorder', 'up');
                } else {
                    e.setAttribute('reorder', '');
                }
            } else {
                if (initialY > dragItemY && initialY < budgeting.initialY) {
                    // dragItem is going up
                    // and e is between initial and new positions
                    // so move e down
                    offset = budgeting.dragItemHeight;
                    e.setAttribute('reorder', 'down');
                } else {
                    e.setAttribute('reorder', '');
                }
            }
            e.style.transform = `translateY(${offset}px)`;
        });
    },
    /**
     * On mouse release, move rows and submit PUT
     *
     * @param {Event} event Triggering event
     */
    dragEnd: function(event) {
        if (budgeting.isDragging) {
            // Get the final state and submit
            let lastChange = null;
            let invalid = false;
            if (budgeting.isGroup) {
                invalid = true;
                document.querySelectorAll('.budget-group:not(.dragging)')
                    .forEach((e) => {
                        const group = e.closest('.budget-group');
                        const groupChange =
                            group.getAttribute('reorder') || null;

                        if (groupChange != null && groupChange != lastChange) {
                            group.parentNode.insertBefore(
                                budgeting.dragItem, group);
                            invalid = false;
                        }

                        lastChange = groupChange;
                    });
            } else {
                let lastGroup = null;
                let lastGroupName = null;
                let wasMoved = false;
                document.querySelectorAll('.budget-row:not(.dragging)')
                    .forEach((e) => {
                        const group = e.closest('.budget-group');
                        const groupHeader =
                            group.querySelector('.budget-group-header');
                        const rowChange = e.getAttribute('reorder') || null;
                        const groupChange =
                            groupHeader.getAttribute('reorder') || null;
                        const rowURI = e.id.slice(9);
                        const groupURI = group.id.slice(13);

                        if (rowChange != null && rowChange != lastChange) {
                            if (groupChange == null) {
                                group.querySelector('.budget-group-fold')
                                    .insertBefore(budgeting.dragItem, e);
                                wasMoved = true;
                            } else if (lastGroup == null) {
                                // Invalid placed outside a group
                                invalid = true;
                            } else {
                                let nextGroup =
                                    lastGroup.parentNode.querySelector(
                                        `#${lastGroup.id} + .budget-group`);
                                let nextGroupHeader = nextGroup &&
                                    nextGroup.querySelector(
                                        '.budget-group-header');
                                if (nextGroup &&
                                    nextGroupHeader.getAttribute('reorder')) {
                                    // If next group exist and was moved, add to
                                    // lastGroup
                                    lastGroup
                                        .querySelector('.budget-group-fold')
                                        .append(budgeting.dragItem);
                                } else {
                                    nextGroup
                                        .querySelector('.budget-group-fold')
                                        .append(budgeting.dragItem);
                                }
                                wasMoved = true;
                            }
                        }

                        lastChange = rowChange;
                        lastGroup = group;
                    });
                // Move to last group if not moved yet
                if (!invalid && !wasMoved) {
                    const ungroup = document.querySelector('#budget-group-');
                    const ungroupHeader =
                        ungroup.querySelector('.budget-group-header');
                    const ungroupChange =
                        ungroupHeader.getAttribute('reorder') || null;

                    if (ungroupChange) {
                        let nextGroup = lastGroup.parentNode.querySelector(
                            `#${lastGroup.id} + .budget-group`);
                        let nextGroupHeader = nextGroup &&
                            nextGroup.querySelector('.budget-group-header');
                        if (nextGroup &&
                            nextGroupHeader.getAttribute('reorder')) {
                            // If next group exist and was moved, add to
                            // lastGroup
                            lastGroup.querySelector('.budget-group-fold')
                                .append(budgeting.dragItem);
                        } else {
                            nextGroup.querySelector('.budget-group-fold')
                                .append(budgeting.dragItem);
                        }
                    } else {
                        document
                            .querySelector(
                                '#budget-group- > .budget-group-fold')
                            .append(budgeting.dragItem);
                    }
                }
            }

            // Restore open states
            document.querySelectorAll('.budget-group-toggle').forEach((e) => {
                e.checked = budgeting.groupOpen[e.id];
            });
            // Finish dragging
            budgeting.staticItems.forEach((e) => {
                e.style.transform = '';
            })
            budgeting.dragItem.style.transform = '';
            budgeting.table.classList.remove('select-none');
            budgeting.dragItem.classList.remove('dragging');

            if (invalid) {
                // Put dragItem back
                budgeting.dragItemParent.insertBefore(
                    budgeting.dragItem, budgeting.dragItemSibling);
            } else {
                // Add group input on each row
                let anyMoved = budgeting.dragItemGroup !=
                    budgeting.dragItem.closest('.budget-group');
                document.querySelectorAll('.budget-row').forEach((e, i) => {
                    if (i != e.getAttribute('position')) {
                        anyMoved = true;
                    }

                    const group = e.closest('.budget-group');
                    const groupURI = group ? group.id.slice(13) : '';

                    const inputGroup = document.createElement('input');
                    inputGroup.name = 'group';
                    inputGroup.type = 'text';
                    inputGroup.value = groupURI;
                    inputGroup.hidden = true;
                    e.append(inputGroup);
                });
                document.querySelectorAll('.budget-group').forEach((e, i) => {
                    if (i != e.getAttribute('position')) {
                        anyMoved = true;
                    }
                });
                if (anyMoved) {
                    htmx.trigger('#budget-table', 'reorder-rows');
                } else {
                    document.querySelectorAll('.budget-row input[name=group]')
                        .forEach((e) => {
                            e.remove();
                        })
                }
            }
        }

        // Remove styles and listeners
        document.removeEventListener('mousemove', budgeting.drag);
        document.removeEventListener('mousemove', budgeting.dragStartTest);
        budgeting.isDragging = false;
        budgeting.dragItem = null;
    },
};
