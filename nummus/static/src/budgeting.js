'use strict';
const budgeting = {
    table: null,
    tableRoot: null,
    isGroup: false,
    dragItem: null,
    dragItemHeight: null,
    dragItemParent: null,
    dragItemSibling: null,
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
        this.tableRoot = document.querySelector('#budget-table-root');

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
        budgeting.staticItems = Array.from(budgeting.staticItems)
                                    .filter((e) => e != budgeting.dragItem);
        budgeting.dragItemParent = budgeting.dragItem.parentNode;
        budgeting.dragItemSibling = budgeting.dragItem.nextSibling;

        // Set position attribute
        document.querySelectorAll('.budget-row').forEach((e, i) => {
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
        const delta = Math.sqrt(dx * dx + dy + dy);

        if (delta < 10) {
            return;
        }
        document.removeEventListener('mousemove', budgeting.dragStartTest);

        // If dragging a row, move to top so it is visible
        // Also moving group to top makes everything only translate down
        budgeting.tableRoot.append(budgeting.dragItem);

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
                document.querySelectorAll('.budget-group:not(.dragging)')
                    .forEach((e) => {
                        const group = e.closest('.budget-group');
                        const groupChange =
                            group.getAttribute('reorder') || null;
                        const groupName = group.id.slice(13);

                        if (groupChange != null && groupChange != lastChange) {
                            group.parentNode.insertBefore(
                                budgeting.dragItem, group);
                        }

                        lastChange = groupChange;
                    });
            } else {
                let lastGroup = null;
                let lastGroupName = null;
                document.querySelectorAll('.budget-row:not(.dragging)')
                    .forEach((e) => {
                        const group = e.closest('.budget-group');
                        const groupHeader =
                            group.querySelector('.budget-group-header');
                        const rowChange = e.getAttribute('reorder') || null;
                        const groupChange =
                            groupHeader.getAttribute('reorder') || null;
                        const rowURI = e.id.slice(9);
                        const groupName = group.id.slice(13);

                        if (rowChange != null && rowChange != lastChange) {
                            if (groupChange == null) {
                                group.querySelector('.budget-group-fold')
                                    .insertBefore(budgeting.dragItem, e);
                            } else if (lastGroup == null) {
                                // Invalid placed outside a group
                                invalid = true;
                            } else {
                                lastGroup.querySelector('.budget-group-fold')
                                    .append(budgeting.dragItem);
                            }
                        }

                        lastChange = rowChange;
                        lastGroup = group;
                        lastGroupName = groupName;
                    });
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
                let anyMoved = false;
                document.querySelectorAll('.budget-row').forEach((e, i) => {
                    if (i != e.getAttribute('position')) {
                        anyMoved = true;
                    }

                    const group = e.closest('.budget-group');
                    const groupName = group.id.slice(13);

                    const inputGroup = document.createElement('input');
                    inputGroup.name = 'group';
                    inputGroup.type = 'text';
                    inputGroup.value = groupName;
                    inputGroup.hidden = true;
                    e.append(inputGroup);
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
