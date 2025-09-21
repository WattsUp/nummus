"use strict";
const budgeting = {
  editing: false,
  sidebarChart: null,
  table: null,
  isGroup: false,
  dragItem: null,
  dragItemHeight: null,
  staticItems: [],
  staticItemsY: [],
  initialScroll: null,
  doScroll: 0,
  initialMouseX: null,
  initialMouseY: null,
  mouseOffsetX: null,
  mouseOffsetY: null,
  isDragging: false,
  currentURI: null,
  barOn: true,
  barHeight: null,
  barTranslate: 0,
  bar: null,
  isTouch: false,
  /**
   * Set up budgeting drag listeners
   */
  setupDrag() {
    this.table = htmx.find("#budget-table");

    this.dragStartBound = this.dragStart.bind(this);
    this.dragEndBound = this.dragEnd.bind(this);
    htmx.on(this.table, "mousedown", this.dragStartBound);
    htmx.on(this.table, "touchstart", this.dragStartBound);
    htmx.on("mouseup", this.dragEndBound);
    htmx.on("touchend", this.dragEndBound);
  },
  /**
   * On click, record initial positions and such
   *
   * @param {Event} evt Triggering event
   */
  dragStart(evt) {
    const target = evt.target;
    if (!target.matches(".budget-drag")) {
      // Not a handle, ignore mouse up
      return;
    }
    // Don't scroll on mobile
    if (evt.type == "touchstart") {
      this.isTouch = true;
      evt.preventDefault();
    }
    if (target.matches(".budget-category, .budget-category *")) {
      this.isGroup = false;
      this.dragItem = target.closest(".budget-category");
      this.staticItems = Array.from(
        htmx.findAll(".budget-group>label, .budget-category"),
      );
    } else {
      this.isGroup = true;
      this.dragItem = target.closest(".budget-group");
      this.staticItems = Array.from(
        htmx.findAll(".budget-group:not(#group-ungrouped)"),
      );
    }

    let firstGroup = true;
    this.staticItems = this.staticItems.filter((e) => {
      if (e == this.dragItem) return false;
      if (this.isGroup || !firstGroup) return true;
      if (e.matches("label")) {
        firstGroup = false;
        return false;
      }
      return true;
    });

    // Set position attribute
    htmx.findAll(".budget-category").forEach((e, i) => {
      e.setAttribute("position", i);
    });
    htmx.findAll(".budget-group").forEach((e, i) => {
      e.setAttribute("position", i);
    });

    // Record initial position
    const evtX = evt.clientX ?? evt.targetTouches[0].clientX;
    const evtY = evt.clientY ?? evt.targetTouches[0].clientY;
    const rect = this.dragItem.getBoundingClientRect();
    this.mouseOffsetX = evtX - rect.x;
    this.mouseOffsetY = evtY - rect.y;
    this.initialMouseX = evtX;
    this.initialMouseY = evtY;
    this.initialScroll = window.scrollY;
    this.dragItemHeight = rect.height;

    // Make nothing selectable
    htmx.addClass(this.table, "select-none");

    this.dragStartTestBound = this.dragStartTest.bind(this);
    htmx.on(this.isTouch ? "touchmove" : "mousemove", this.dragStartTestBound, {
      passive: false,
    });
  },
  /**
   * Once mouse moves enough, actually start dragging
   *
   * @param {Event} evt Triggering event
   */
  dragStartTest(evt) {
    const evtX = evt.clientX ?? evt.targetTouches[0].clientX;
    const evtY = evt.clientY ?? evt.targetTouches[0].clientY;
    const dx = evtX - this.initialMouseX;
    const dy =
      evtY - this.initialMouseY + (window.scrollY - this.initialScroll);
    const delta = Math.sqrt(dx * dx + dy * dy);

    if (delta < 10) {
      return;
    }
    htmx.off("mousemove", this.dragStartTestBound);
    htmx.off("touchmove", this.dragStartTestBound);
    this.dragStartTestBound = null;

    htmx.addClass(this.dragItem, "budget-dragging");

    this.isDragging = true;

    const scrollY = window.scrollY;
    if (this.isGroup) {
      htmx.findAll(".budget-group-items").forEach((e) => {
        htmx.addClass(e, "hidden");
      });
    }
    const dyScroll = window.scrollY - scrollY;
    this.initialScroll += dyScroll;

    // After toggling open, compute initial location
    const rect = this.dragItem.getBoundingClientRect();
    this.initialMouseX = rect.x + this.mouseOffsetX;
    this.initialMouseY = rect.y + this.mouseOffsetY;
    this.dragItemHeight = rect.height;

    this.staticItems.forEach((e, i) => {
      const rect = e.getBoundingClientRect();
      // Center of dragItem
      this.staticItemsY[i] = rect.y + rect.height / 2;
    });

    this.drag(evt);

    // Add move listener
    this.dragBound = this.drag.bind(this);
    htmx.on(this.isTouch ? "touchmove" : "mousemove", this.dragBound, {
      passive: false,
    });
  },
  doScrollFrame() {
    if (!this.doScroll) return;
    window.scrollBy(0, this.doScroll);
    requestAnimationFrame(this.doScrollFrame.bind(this));
  },
  /**
   * On mouse move, translate rows
   *
   * @param {Event} evt Triggering event
   */
  drag(evt) {
    const evtX = evt.clientX ?? evt.targetTouches[0].clientX;
    const evtY = evt.clientY ?? evt.targetTouches[0].clientY;
    if (evt.type == "touchmove") {
      evt.preventDefault();
      const prevDoScroll = this.doScroll;
      const th = 150;
      if (evtY < th) this.doScroll = (evtY - th) * 2;
      else if (evtY > window.innerHeight - th)
        this.doScroll = evtY - window.innerHeight + th;
      else this.doScroll = 0;

      if (this.doScroll && !prevDoScroll)
        requestAnimationFrame(this.doScrollFrame.bind(this));
    }
    const offsetX = evtX - this.initialMouseX;
    const scrollY = window.scrollY - this.initialScroll;
    const offsetY = evtY - this.initialMouseY + scrollY;
    this.dragItem.style.transform = `translate(${offsetX}px, ${offsetY}px)`;

    const dragItemYTop = evtY - this.mouseOffsetY + scrollY;
    const dragItemYBot = dragItemYTop + this.dragItemHeight;

    this.staticItems.forEach((e, i) => {
      const initialY = this.staticItemsY[i];
      let offset = 0;
      if (offsetY > 0) {
        if (initialY < dragItemYBot && initialY > this.initialMouseY) {
          // dragItem is going down
          // and e is between initial and new positions
          // so move e up
          offset = -this.dragItemHeight;
          e.setAttribute("reorder", "up");
        } else {
          e.setAttribute("reorder", "");
        }
      } else {
        if (initialY > dragItemYTop && initialY < this.initialMouseY) {
          // dragItem is going up
          // and e is between initial and new positions
          // so move e down
          offset = this.dragItemHeight;
          e.setAttribute("reorder", "down");
        } else {
          e.setAttribute("reorder", "");
        }
      }
      e.style.transform = `translateY(${offset}px)`;
    });
  },
  /**
   * On mouse release, move rows and submit PUT
   *
   * @param {Event} evt Triggering event
   */
  dragEnd(evt) {
    if (!this.isDragging) {
      this.cleanUpDrag();
      return;
    }
    let anyMoved = false;
    // Get the final state and submit
    let lastChange = null;
    let invalid = false;
    const movedUp = Array.from(
      htmx.findAll(
        `.budget-${this.isGroup ? "group" : "category"}:not(.budget-dragging)[reorder="up"]`,
      ),
    );
    const movedDown = Array.from(
      htmx.findAll(
        `.budget-${this.isGroup ? "group" : "category"}:not(.budget-dragging)[reorder="down"]`,
      ),
    );
    const groupLabelsMovedUp = Array.from(
      htmx.findAll('.budget-group>label:not(.budget-dragging)[reorder="up"]'),
    );
    const groupLabelsMovedDown = Array.from(
      htmx.findAll('.budget-group>label:not(.budget-dragging)[reorder="down"]'),
    );

    let items = null;
    let before = null;
    if (movedUp.length) {
      // Insert dragItem after last one
      let last = movedUp[movedUp.length - 1];
      items = last.parentNode;
      before = last.nextElementSibling;
      if (groupLabelsMovedUp.length) {
        // Groups also moved see if the last one to move is different from last's group
        const group =
          groupLabelsMovedUp[groupLabelsMovedUp.length - 1].parentNode;
        if (group != last.closest(".budget-group")) {
          items = htmx.find(group, ".budget-group-items");
          before = items.firstChild;
        }
      }
    } else if (movedDown.length) {
      // Insert dragItem before first one
      const first = movedDown[0];
      items = first.parentNode;
      before = first;
      if (groupLabelsMovedDown.length) {
        const group = groupLabelsMovedDown[0].parentNode;
        const prevGroup = group.previousElementSibling;
        if (
          prevGroup &&
          !htmx.find(prevGroup, '.budget-category:not([reorder=""])')
        ) {
          // previous to first moved group had no changes
          // move dragItem to end of prevGroup
          items = htmx.find(prevGroup, ".budget-group-items");
          before = null;
        }
      }
    } else if (groupLabelsMovedUp.length) {
      // Insert dragItem at top of last one's items
      items =
        groupLabelsMovedUp[groupLabelsMovedUp.length - 1].nextElementSibling;
      before = items.firstChild;
    } else if (groupLabelsMovedDown.length) {
      // Insert dragItem at bottom of previous one's items
      const prevGroup =
        groupLabelsMovedDown[0].parentNode.previousElementSibling;
      if (prevGroup) {
        items = htmx.find(prevGroup, ".budget-group-items");
        before = null;
      }
    }

    if (!items) {
      // Nothing moved
      this.cleanUpDrag();
      return;
    }
    try {
      items.insertBefore(this.dragItem, before);
    } catch (error) {
      // There's a bug with self-ancestor
      // Hard to catch so add context to error next time it shows up
      console.error(this.dragItem, items, before);
      console.error(error);
    }

    // Add group input on each row
    htmx.findAll(".budget-category").forEach((e, i) => {
      const group = e.closest(".budget-group");
      const groupURI = group.id.slice(6);

      const inputGroup = document.createElement("input");
      inputGroup.name = "group";
      inputGroup.type = "text";
      inputGroup.value = groupURI;
      inputGroup.hidden = true;
      e.append(inputGroup);
    });
    htmx.trigger("#budget-table", "reorder");
    this.cleanUpDrag();
  },
  /**
   * Clean up dragging listeners
   */
  cleanUpDrag() {
    // Remove styles and listeners
    this.staticItems.forEach((e) => {
      e.style.transform = "";
    });
    this.staticItems.length = 0;
    this.isTouch = false;
    this.doScroll = 0;

    if (this.dragBound) {
      htmx.off("mousemove", this.dragBound);
      htmx.off("touchmove", this.dragBound);
      this.dragBound = null;
    }
    if (this.dragStartTestBound) {
      htmx.off("mousemove", this.dragStartTestBound);
      htmx.off("touchmove", this.dragStartTestBound);
      this.dragStartTestBound = null;
    }

    htmx.findAll(".budget-group-items").forEach((e) => {
      htmx.removeClass(e, "hidden");
    });

    if (this.dragItem) {
      this.dragItem.style.transform = "";
      htmx.removeClass(this.dragItem, "budget-dragging");
      // Scroll drag item back into view if uncollapsing groups
      if (this.isGroup) this.dragItem.scrollIntoView({ block: "center" });
      this.dragItem = null;
    }

    htmx.removeClass(this.table, "select-none");

    htmx.findAll('.budget-category>input[name="group"]').forEach((e) => {
      htmx.remove(e);
    });

    this.isDragging = false;
  },
  /**
   * Create budgeting sidebar Chart
   *
   * @param {Number} assigned Amount of money assigned to target
   * @param {Number} targetAmount Full target amount
   * @param {Boolean} onTrack True if target is on track
   */
  update(assigned, targetAmount, onTrack) {
    const remaining = targetAmount - assigned;
    const percent = Math.min(100, (assigned / targetAmount) * 100);

    const canvas = htmx.find("#budget-sidebar-canvas");
    const ctx = canvas.getContext("2d");
    const datasets = [
      {
        name: "Assigned",
        amount: assigned,
        borderColorRaw: "primary",
        backgroundColorRaw: "primary-container",
      },
    ];
    if (remaining > 0) {
      datasets.push({
        name: "Remaining",
        amount: remaining,
        borderColorRaw: "tertiary",
        backgroundColorRaw: "tertiary-container",
      });
    }
    if (this.sidebarChart && ctx == this.sidebarChart.ctx) {
      nummusChart.updatePie(
        this.sidebarChart,
        datasets,
        `${percent.toFixed(0)}%`,
      );
    } else {
      this.sidebarChart = nummusChart.createPie(ctx, datasets, null, {
        plugins: { doughnutText: { text: `${percent.toFixed(0)}%` } },
        animations: false,
      });
    }
  },
  /**
   * Update group open state from checkbox
   *
   * @param {Element} e Checkbox input element
   * @param {String} uri URI of group to update
   */
  openGroup(e, uri) {
    // do nothing during edit
    if (this.editing) return;

    htmx.trigger(e, "send-state");
    const isOpen = e.checked;
    if (isOpen) {
      htmx.addClass(htmx.find(`#group-${uri}`), "open");
    } else {
      htmx.removeClass(htmx.find(`#group-${uri}`), "open");
    }
  },
  /**
   * On click of category, activate assigned input
   *
   * @param {Element} e Category element
   * @param {Event} evt Triggering event
   */
  onClickCategory(e, evt) {
    // do nothing during edit
    if (this.editing) return;

    if (!e) {
      if (
        this.currentURI &&
        (!evt || !evt.target.matches(".budget-category, .budget-category * "))
      ) {
        // Click was not on a category, deactivate
        htmx.removeClass(
          htmx.find(`#category-${this.currentURI}`),
          "budget-category-active",
        );
        this.currentURI = null;
        this.updateBar(false);
        nav.setOverrideBarOff(true);
      }

      return;
    }

    if (window.screen.width < 768) {
      // for small, activate budget-bar
      const uri = e.id.slice(9);
      if (this.currentURI == uri) {
        this.currentURI = null;
        this.updateBar(false);
        nav.setOverrideBarOff(true);
        htmx.removeClass(e, "budget-category-active");
      } else {
        if (this.currentURI) {
          htmx.removeClass(
            htmx.find(`#category-${this.currentURI}`),
            "budget-category-active",
          );
        }
        htmx.find("#budget-button-bar input").value = uri;
        this.currentURI = uri;
        this.updateBar(true);
        nav.setOverrideBarOff();
        htmx.addClass(e, "budget-category-active");
      }

      return;
    }
    // for larger, activate sidebar
    htmx.trigger(e, "sidebar");
  },
  /**
   * Update bar translate
   *
   * @param {Boolean} on true show the bar
   */
  updateBar(on) {
    this.barOn = on;

    if (this.bar == null) this.bar = htmx.find("#budget-button-bar");
    if (this.barHeight == null) {
      const rect = this.bar.getBoundingClientRect();
      this.barHeight = rect.height;
    }

    this.barTranslate = on ? 0 : this.barHeight * 1.1;
    this.bar.style.translate = `0 ${this.barTranslate}px`;
  },
  /**
   * On click of delete target, confirm action
   *
   * @param {Event} evt Triggering event
   */
  confirmDelete(evt) {
    dialog.confirm(
      "Delete target",
      "Delete",
      () => {
        htmx.trigger(evt.target, "delete");
      },
      "Target will be deleted.",
    );
  },
  /**
   * On click of move bar button, trigger the category
   */
  onBarMove() {
    const e = htmx.find(`#category-${this.currentURI} .hx-assign`);
    htmx.trigger(e, "button");
  },
  /**
   * On click of target bar button, trigger the category
   */
  onBarTarget() {
    const e = htmx.find(`#category-${this.currentURI} .hx-target`);
    htmx.trigger(e, "button");
  },
  /**
   * Reset budgeting JS states
   */
  reset() {
    this.bar = null;
    if (this.currentURI) {
      this.currentURI = null;
      this.updateBar(false);
      nav.setOverrideBarOff(true);
    }
  },
  /**
   * On click of edit switch, change edit mode
   *
   * @param {Element} e Toggle element
   */
  toggleEdit(e) {
    this.editing = e.checked;
    htmx
      .findAll(
        ".budget-category button, .budget-sidebar-target select, .budget-sidebar-target button",
      )
      .forEach((button) => {
        button.setAttribute("disabled", "");
      });
    if (this.editing) {
      htmx.addClass(htmx.find("#budget-table"), "edit");
      this.setupDrag();
    } else {
      this.cleanUpDrag();
      // On exit of editing, refresh budget page
      // This sets new group names and resets buttons
      htmx.trigger(document.body, "budget");
    }
  },
  /**
   * Delete group, move items to neighbor
   *
   * @param {Element} btn - Triggering button
   */
  deleteGroup(btn) {
    const group = btn.closest(".budget-group");
    const items = htmx.find(group, ".budget-group-items");
    const prevGroup = group.previousElementSibling;
    if (prevGroup && prevGroup.matches(".budget-group")) {
      const newItems = htmx.find(prevGroup, ".budget-group-items");
      htmx.findAll(items, ".budget-category").forEach((e) => {
        newItems.insertBefore(e, null);
      });
      htmx.remove(group);
    } else {
      const nextGroup = group.nextElementSibling;
      const newItems = htmx.find(nextGroup, ".budget-group-items");
      const first = newItems.firstChild;
      htmx.findAll(items, ".budget-category").forEach((e) => {
        newItems.insertBefore(e, first);
      });
      htmx.remove(group);
    }

    htmx.findAll(".budget-category").forEach((e, i) => {
      const group = e.closest(".budget-group");
      const groupURI = group.id.slice(6);

      const inputGroup = document.createElement("input");
      inputGroup.name = "group";
      inputGroup.type = "text";
      inputGroup.value = groupURI;
      inputGroup.hidden = true;
      e.append(inputGroup);
    });
    htmx.trigger("#budget-table", "reorder");
    this.cleanUpDrag();
  },
};

htmx.on("click", (evt) => {
  budgeting.onClickCategory(null, evt);
});
