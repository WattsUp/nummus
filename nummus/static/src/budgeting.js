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
    mouseOffsetX: null,
    mouseOffsetY: null,
    isDragging: false,
    groupOpen: {},
    setup: function() {
        this.table = document.querySelector('#budget-table');
        this.tableRoot = document.querySelector('#budget-table-root');

        // Remove any that exist
        this.table.removeEventListener('mousedown', this.dragStart);
        document.removeEventListener('mouseup', this.dragEnd);

        this.table.addEventListener('mousedown', this.dragStart);
        document.addEventListener('mouseup', this.dragEnd);
    },
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

        // Record initial position
        const rect = budgeting.dragItem.getBoundingClientRect();
        budgeting.mouseOffsetX = event.clientX - rect.x;
        budgeting.mouseOffsetY = event.clientY - rect.y;

        // If dragging a row, move to top so it is visible
        if (!budgeting.isGroup) {
            budgeting.tableRoot.append(budgeting.dragItem);
        }

        // Prepare for dragging
        // Make nothing selectable
        budgeting.table.classList.add('select-none');
        budgeting.dragItem.classList.add('dragging');

        // Close all groups if dragging a group
        document.querySelectorAll('.budget-group-toggle').forEach((e) => {
            budgeting.groupOpen[e.id] = e.checked;
            e.checked = budgeting.isGroup;
        });

        budgeting.isDragging = true;
        // Add move listener
        document.addEventListener('mousemove', budgeting.drag);

        budgeting.updateInitialOffset(event);
    },
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
                }
            } else {
                if (initialY > dragItemY && initialY < budgeting.initialY) {
                    // dragItem is going up
                    // and e is between initial and new positions
                    // so move e down
                    offset = budgeting.dragItemHeight;
                }
            }
            e.style.transform = `translateY(${offset}px)`;
        });
    },
    dragEnd: function(event) {
        if (budgeting.isDragging) {
            // Get the final state and submit
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

            if (!budgeting.isGroup) {
                // Put dragItem back
                budgeting.dragItemParent.insertBefore(
                    budgeting.dragItem, budgeting.dragItemSibling);
            }
        }

        // Remove styles and listeners
        document.removeEventListener('mousemove', budgeting.drag);
        budgeting.isDragging = false;
        budgeting.dragItem = null;
    },
};
