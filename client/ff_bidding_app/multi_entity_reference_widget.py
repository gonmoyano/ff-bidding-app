"""
Multi-Entity Reference Widget for ShotGrid

A custom Qt widget for displaying and managing ShotGrid entity references
in a table cell, with pills/tags showing entity names and removal buttons.

Author: Claude Code
License: MIT
"""

from PySide6 import QtWidgets, QtCore, QtGui


class EntityPillWidget(QtWidgets.QWidget):
    """
    A single entity reference displayed as a pill/tag with name and remove button.

    Features:
    - Rounded rectangle appearance
    - Entity name display
    - X button for removal
    - Hover effects
    - Dark theme styling matching ShotGrid
    - Dynamic height adjustment based on container size

    Signals:
        removeRequested: Emitted when user clicks the X button
    """

    removeRequested = QtCore.Signal(object)  # Emits the entity dict
    clicked = QtCore.Signal(object)  # Emits the entity dict when pill is clicked

    # Default pill height (can be adjusted)
    DEFAULT_HEIGHT = 22
    MIN_HEIGHT = 16  # Minimum height to remain readable
    MAX_HEIGHT = 60  # Maximum height to prevent pills from becoming too tall

    def __init__(self, entity, is_valid=True, max_height=None, parent=None):
        """
        Initialize an entity pill widget.

        Args:
            entity (dict): ShotGrid entity dict with 'type', 'id', 'name' keys
            is_valid (bool): Whether this entity reference is valid (exists in current bid's assets)
            max_height (int): Maximum height for the pill (for clipping to cell size)
            parent (QWidget): Parent widget
        """
        super().__init__(parent)
        self.entity = entity
        self.is_valid = is_valid
        self._max_height = max_height
        # Try 'code' first (used by Asset items), then 'name', finally fallback to ID
        self.entity_name = entity.get("code") or entity.get("name") or f"ID {entity.get('id', 'N/A')}"

        # Colors for custom painting - use same blue as table selection for consistency
        if self.is_valid:
            self.bg_color = QtGui.QColor("#4a9eff")  # Match table selection blue
            self.border_color = QtGui.QColor("#3a8adf")
            self.text_color = "#ffffff"
        else:
            self.bg_color = QtGui.QColor("#e74c3c")  # Red for invalid
            self.border_color = QtGui.QColor("#c0392b")
            self.text_color = "#ffffff"

        self._setup_ui()

    def _setup_ui(self):
        """Build the pill UI with label and close button."""
        # Main layout - horizontal
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 4, 2)
        layout.setSpacing(3)

        # Calculate effective height
        effective_height = self._calculate_effective_height()

        # Entity name label with text elision for long names
        self.name_label = QtWidgets.QLabel(self.entity_name)
        self.name_label.setStyleSheet(f"""
            QLabel {{
                color: {self.text_color};
                font-size: 11px;
                background: transparent;
                border: none;
            }}
        """)
        self.name_label.setCursor(QtCore.Qt.PointingHandCursor)
        self.name_label.mousePressEvent = self._on_label_clicked
        # Limit pill width to prevent extending beyond cell boundaries
        self.name_label.setMaximumWidth(120)
        # Add tooltip with full name in case it's truncated
        self.name_label.setToolTip(self.entity_name)

        # Add tooltip for invalid pills showing the asset name
        if not self.is_valid:
            self.name_label.setToolTip(f"Asset not available: {self.entity_name}\n(Not found in current Bid Assets)")

        layout.addWidget(self.name_label)

        # Close button (X)
        self.close_btn = QtWidgets.QPushButton("×")
        self.close_btn.setFixedSize(16, 16)
        self.close_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #555555;
                font-size: 16px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                color: #ff6b6b;
                background: rgba(255, 107, 107, 0.15);
                border-radius: 8px;
            }
        """)
        self.close_btn.clicked.connect(self._on_remove_clicked)
        layout.addWidget(self.close_btn)

    def paintEvent(self, event):
        """Custom paint event to draw the rounded pill background."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # Get the widget rectangle
        rect = self.rect()

        # Draw rounded rectangle background
        painter.setPen(QtGui.QPen(self.border_color, 1))
        painter.setBrush(QtGui.QBrush(self.bg_color))
        painter.drawRoundedRect(rect, 10, 10)

    def _on_remove_clicked(self):
        """Handle remove button click."""
        self.removeRequested.emit(self.entity)

    def _on_label_clicked(self, event):
        """Handle label click - show asset info for invalid pills."""
        if not self.is_valid:
            # Show a message box with the asset name details
            QtWidgets.QMessageBox.information(
                self,
                "Invalid Asset Reference",
                f"Asset Name: {self.entity_name}\n"
                f"Entity Type: {self.entity.get('type', 'N/A')}\n"
                f"Entity ID: {self.entity.get('id', 'N/A')}\n\n"
                f"This asset is not found in the current bid's Assets tab.\n"
                f"It may have been removed or belongs to a different bid."
            )
        self.clicked.emit(self.entity)

    def get_entity(self):
        """Get the entity dict for this pill.

        Returns:
            dict: Entity dictionary
        """
        return self.entity

    def _calculate_effective_height(self):
        """Calculate the effective height for the pill based on constraints.

        The pill will expand to fill available space (up to MAX_HEIGHT) or
        shrink if space is limited (down to MIN_HEIGHT).

        Returns:
            int: The effective height to use for the pill
        """
        if self._max_height is not None:
            # Clamp height between MIN_HEIGHT and MAX_HEIGHT
            return max(self.MIN_HEIGHT, min(self._max_height, self.MAX_HEIGHT))
        return self.DEFAULT_HEIGHT

    def set_max_height(self, max_height):
        """Set the maximum height for the pill and update the widget.

        Args:
            max_height (int): Maximum height constraint
        """
        self._max_height = max_height
        effective_height = self._calculate_effective_height()
        self.setFixedHeight(effective_height)
        # Update close button size proportionally (scale from 12px at MIN_HEIGHT to 24px at MAX_HEIGHT)
        if hasattr(self, 'close_btn'):
            btn_size = max(12, min(24, int(effective_height * 0.4)))
            self.close_btn.setFixedSize(btn_size, btn_size)
            # Update close button font size
            font_size = max(12, min(20, int(effective_height * 0.35)))
            self.close_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    color: #555555;
                    font-size: {font_size}px;
                    font-weight: bold;
                    padding: 0px;
                }}
                QPushButton:hover {{
                    color: #ff6b6b;
                    background: rgba(255, 107, 107, 0.15);
                    border-radius: {btn_size // 2}px;
                }}
            """)
        # Update label font size proportionally (scale from 11px to 16px)
        if hasattr(self, 'name_label'):
            label_font_size = max(11, min(16, int(effective_height * 0.3)))
            self.name_label.setStyleSheet(f"""
                QLabel {{
                    color: {self.text_color};
                    font-size: {label_font_size}px;
                    background: transparent;
                    border: none;
                }}
            """)
        self.updateGeometry()

    def sizeHint(self):
        """Return the preferred size for this pill widget.

        Returns:
            QSize: Preferred size
        """
        effective_height = self._calculate_effective_height()
        # Width is based on content but capped to prevent overflow
        # Max label width (120) + close button (16) + margins (10) + spacing (3) = 149
        label_width = min(self.name_label.sizeHint().width(), 120)
        width = label_width + 30  # Add space for close button and margins
        return QtCore.QSize(width, effective_height)


class MultiEntityReferenceWidget(QtWidgets.QWidget):
    """
    Container widget for displaying multiple entity references as pills.

    Features:
    - Flow layout for pills with automatic wrapping
    - Add button for new references
    - Remove pills via X button
    - Get/set entity lists
    - Signal emission on changes

    Signals:
        entitiesChanged: Emitted when entities are added or removed (emits list of entity dicts)
    """

    entitiesChanged = QtCore.Signal(list)  # Emits list of entity dicts

    def __init__(self, entities=None, allow_add=True, valid_entity_ids=None, parent=None):
        """
        Initialize the multi-entity reference widget.

        Args:
            entities (list): List of ShotGrid entity dicts
            allow_add (bool): Whether to show the Add button
            valid_entity_ids (set): Set of valid entity names for the current bid (for validation)
                                    Note: Despite the name, this now uses names for matching
            parent (QWidget): Parent widget
        """
        super().__init__(parent)
        self._entities = self._deduplicate_entities(entities or [])
        self._allow_add = allow_add
        self._valid_entity_names = valid_entity_ids  # Set of valid entity names (renamed internally)
        self._is_selected = False  # Track selection state
        self._is_editing = False   # Track edit state
        self._pill_max_height = None  # Max height for pills (calculated from widget height)
        self._skip_resize_pill_updates = False  # Skip pill height updates during manual row resize

        # Colors for custom painting
        self.bg_color = QtGui.QColor("#2b2b2b")      # Normal background
        self.border_color = QtGui.QColor("#0078d4")  # Border color (used when selected/editing)
        self.grid_border_color = QtGui.QColor("#3a3a3a")  # Grid border color (normal state, matches table grid)
        self.border_width = 1                         # Border width in pixels
        self.overflow_dot_color = QtGui.QColor("#888888")  # Color for overflow indicator dots

        self._setup_ui()
        self._populate_entities()

    def _deduplicate_entities(self, entities):
        """Remove duplicate entities from a list, keeping only unique IDs.

        Args:
            entities (list): List of entity dicts

        Returns:
            list: Deduplicated list of entity dicts
        """
        if not entities:
            return []

        seen_ids = set()
        unique_entities = []

        for entity in entities:
            if not isinstance(entity, dict):
                continue

            entity_id = entity.get("id")
            if entity_id and entity_id not in seen_ids:
                seen_ids.add(entity_id)
                unique_entities.append(entity)

        return unique_entities

    def _setup_ui(self):
        """Build the main UI with flow layout."""
        # Set object name for stylesheet targeting
        self.setObjectName("entityReferenceWidget")

        # CRITICAL: Ensure widget clips all children to its bounds
        self.setAttribute(QtCore.Qt.WA_OpaquePaintEvent, False)

        # Set size policy to prevent widget from expanding beyond allocated space
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Ignored,  # Don't grow horizontally
            QtWidgets.QSizePolicy.Fixed      # Fixed height
        )

        # Main layout - no margins to align with table cell boundaries
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Scroll area for pills (in case of many entities)
        # Store as instance variable for later access
        self._scroll_area = QtWidgets.QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        # Hide scroll bars - content will be clipped
        self._scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self._scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        # Container for pills with flow layout
        self.pills_container = QtWidgets.QWidget()
        self.pills_layout = FlowLayout(self.pills_container, margin=4, h_spacing=4, v_spacing=4)

        self._scroll_area.setWidget(self.pills_container)
        main_layout.addWidget(self._scroll_area)

        # Make scroll area and pills container transparent (paintEvent handles main widget)
        self.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QWidget#pillsContainer {
                background-color: transparent;
            }
        """)
        self.pills_container.setObjectName("pillsContainer")

        # Disable auto-fill so paintEvent controls background
        self.setAutoFillBackground(False)
        self._scroll_area.viewport().setAutoFillBackground(False)

    def _populate_entities(self):
        """Create pill widgets for all entities."""
        # Clear existing pills
        self._clear_pills()

        # Add pill for each entity
        for entity in self._entities:
            self._add_pill(entity)

        # Add the "+" button if allowed
        if self._allow_add:
            self._add_add_button()

    def _clear_pills(self):
        """Remove all pill widgets from the layout."""
        while self.pills_layout.count():
            item = self.pills_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add_pill(self, entity):
        """Add a pill widget for an entity.

        Args:
            entity (dict): Entity dictionary
        """
        # Check if this entity is valid (name matches one in the current bid's assets)
        is_valid = True
        if self._valid_entity_names is not None:
            # Use 'code' first (used by Asset items), then 'name' as fallback
            entity_name = entity.get('code') or entity.get('name')
            is_valid = entity_name in self._valid_entity_names if entity_name else False

        pill = EntityPillWidget(entity, is_valid=is_valid, max_height=self._pill_max_height, parent=self)
        pill.removeRequested.connect(self._on_pill_remove)
        self.pills_layout.addWidget(pill)

    def _add_add_button(self):
        """Add the '+' button for adding new entities."""
        add_btn = QtWidgets.QPushButton("+")
        add_btn.setFixedSize(24, 24)
        add_btn.setCursor(QtCore.Qt.PointingHandCursor)
        add_btn.setToolTip("Add entity reference")
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a4a4a;
                border: 1px dashed #777777;
                border-radius: 12px;
                color: #a0a0a0;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
                border-color: #999999;
                color: #e0e0e0;
            }
        """)
        add_btn.clicked.connect(self._on_add_clicked)
        self.pills_layout.addWidget(add_btn)

    def _on_pill_remove(self, entity):
        """Handle pill removal request.

        Args:
            entity (dict): Entity to remove
        """
        # Remove from internal list
        self._entities = [e for e in self._entities if e.get("id") != entity.get("id")]

        # Rebuild pills
        self._populate_entities()

        # Emit change signal
        self.entitiesChanged.emit(self._entities)

    def _on_add_clicked(self):
        """Handle add button click - show entity selection dialog."""
        # This would typically open a ShotGrid entity picker dialog
        # For now, show a simple input dialog as placeholder
        dialog = AddEntityDialog(self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            new_entity = dialog.get_entity()
            if new_entity:
                self.add_entity(new_entity)

    def add_entity(self, entity):
        """Add a new entity reference.

        Args:
            entity (dict): Entity dictionary to add
        """
        # Check if entity already exists (by ID)
        if any(e.get("id") == entity.get("id") for e in self._entities):
            return

        self._entities.append(entity)
        self._populate_entities()
        self.entitiesChanged.emit(self._entities)

    def set_entities(self, entities):
        """Set the list of entity references.

        Args:
            entities (list): List of entity dictionaries
        """
        self._entities = self._deduplicate_entities(entities or [])
        self._populate_entities()

    def set_valid_entity_ids(self, valid_entity_names):
        """Update the set of valid entity names and refresh pills.

        Args:
            valid_entity_names (set): Set of valid entity names for validation
                                      Note: Despite method name, this uses names for matching
        """
        self._valid_entity_names = valid_entity_names
        # Refresh pills to update validation colors
        self._populate_entities()

    def get_entities(self):
        """Get the current list of entity references.

        Returns:
            list: List of entity dictionaries
        """
        return self._entities.copy()

    def sizeHint(self):
        """Provide size hint for layout."""
        return QtCore.QSize(200, 60)

    def resizeEvent(self, event):
        """Handle resize events to update pill sizes based on available height.

        Args:
            event (QResizeEvent): The resize event
        """
        super().resizeEvent(event)

        # Set clip region to ensure content doesn't extend beyond widget bounds
        region = QtGui.QRegion(self.rect())
        self.setMask(region)

        # Skip pill height updates if flag is set (during manual row resize)
        if self._skip_resize_pill_updates:
            return
        # Calculate available height for pills (accounting for margins and border)
        new_height = event.size().height()
        self._update_pill_heights(new_height)

    def _update_pill_heights(self, widget_height):
        """Update the maximum height for all pills based on widget height.

        Args:
            widget_height (int): The current height of the widget
        """
        # Calculate available height for pills
        # Account for: 2px top margin + 2px bottom margin + 2px scroll area margin
        # and leave some vertical padding
        available_height = max(EntityPillWidget.MIN_HEIGHT, widget_height - 8)

        # Store the max height for new pills
        self._pill_max_height = available_height

        # Update existing pills
        for i in range(self.pills_layout.count()):
            item = self.pills_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if isinstance(widget, EntityPillWidget):
                    widget.set_max_height(available_height)

        # Force layout to recalculate by triggering a resize on the container
        # invalidate() only marks layout as dirty but doesn't recalculate
        self.pills_layout.invalidate()
        self.pills_container.updateGeometry()
        # Force the layout to actually apply new geometries
        if self.pills_container.size().isValid():
            self.pills_container.resize(self.pills_container.size())
        self.pills_container.update()

    def update_for_height(self, height):
        """Public method to update pill heights for a given container height.

        Call this method when the widget's height is changed programmatically
        (e.g., via setFixedHeight) to ensure pills are resized accordingly.

        Args:
            height (int): The new height of the widget
        """
        self._update_pill_heights(height)

    def set_skip_resize_pill_updates(self, skip):
        """Set whether to skip pill height updates during resize events.

        Use this when manually resizing the row (e.g., dragging row edge)
        to prevent pills from enlarging to match the row height.

        Args:
            skip (bool): True to skip pill updates during resize, False otherwise
        """
        self._skip_resize_pill_updates = skip

    def _calculate_overflow_info(self):
        """Calculate overflow indicator information.

        Determines if there are hidden pills (on rows below the first row due to
        wrapping) and how many dots to show based on available space between
        the last visible pill on the first row and the widget's right edge.

        Returns:
            tuple: (has_overflow, num_dots, dot_x_start, dot_y) or (False, 0, 0, 0) if no overflow
        """
        if not hasattr(self, 'pills_layout') or not hasattr(self, 'pills_container'):
            return (False, 0, 0, 0)

        # Get widget dimensions
        widget_width = self.width()
        widget_height = self.height()

        # Constants for dots
        dot_diameter = 3
        dot_spacing = 2
        right_margin = 6  # Space from the right edge
        min_space_per_dot = dot_diameter + dot_spacing  # ~5px per dot

        # Find pills on the first row and any pills on subsequent rows
        first_row_pills = []
        overflow_pills = []
        first_row_y = None

        for i in range(self.pills_layout.count()):
            item = self.pills_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if isinstance(widget, EntityPillWidget):
                    # Get pill geometry relative to the pills_container
                    pill_geom = widget.geometry()

                    # Determine which row this pill is on
                    if first_row_y is None:
                        first_row_y = pill_geom.y()

                    # Categorize pills by row
                    if pill_geom.y() == first_row_y:
                        # Pill is on the first row
                        first_row_pills.append((widget, pill_geom))
                    else:
                        # Pill wrapped to a subsequent row (overflow)
                        overflow_pills.append((widget, pill_geom))

        # No overflow if all pills are on the first row
        if not overflow_pills:
            return (False, 0, 0, 0)

        # Find the right edge of the last pill on the first row
        if first_row_pills:
            last_visible = first_row_pills[-1]
            last_pill_right = last_visible[1].x() + last_visible[1].width() + 4  # +4 for container margin
        else:
            # No pills on first row (shouldn't happen, but handle gracefully)
            last_pill_right = 6

        # Calculate available space for dots
        available_space = widget_width - last_pill_right - right_margin

        # Determine number of dots based on available space (max 3)
        num_dots = min(3, max(0, int(available_space / min_space_per_dot)))

        if num_dots == 0:
            return (False, 0, 0, 0)

        # Position dots fixed near the last pill (not centered, so they don't move when resizing)
        dot_x_start = last_pill_right + 4  # Small gap after last pill

        # Y position: 5% from bottom edge of the row
        dot_y = widget_height * 0.95 - dot_diameter / 2

        return (True, num_dots, dot_x_start, dot_y)

    def paintEvent(self, event):
        """Custom paint event to draw the background and border with state colors."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # Get the widget rectangle and clip to it to prevent drawing beyond cell bounds
        rect = self.rect()
        painter.setClipRect(rect)

        # Only draw background when selected or editing, otherwise let table background show through
        if self._is_selected or self._is_editing:
            painter.fillRect(rect, self.bg_color)
            painter.setPen(QtGui.QPen(self.border_color, self.border_width))
            painter.setBrush(QtCore.Qt.NoBrush)
            # Draw border adjusted to fit within widget bounds
            painter.drawRect(rect.adjusted(0, 0, -1, -1))

        # Draw overflow indicator dots if needed
        has_overflow, num_dots, dot_x_start, dot_y = self._calculate_overflow_info()
        if has_overflow and num_dots > 0:
            dot_diameter = 3
            dot_spacing = 2
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QBrush(self.overflow_dot_color))

            for i in range(num_dots):
                dot_x = dot_x_start + i * (dot_diameter + dot_spacing)
                painter.drawEllipse(
                    QtCore.QPointF(dot_x + dot_diameter / 2, dot_y),
                    dot_diameter / 2,
                    dot_diameter / 2
                )

    def set_selected(self, selected):
        """Set the selection state of the widget.

        Args:
            selected (bool): True if cell is selected, False otherwise
        """
        if self._is_selected != selected:
            self._is_selected = selected
            print(f"DEBUG: MultiEntityReferenceWidget.set_selected({selected})")
            self._update_visual_state()

    def set_editing(self, editing):
        """Set the editing state of the widget.

        Args:
            editing (bool): True if cell is being edited (menu open), False otherwise
        """
        if self._is_editing != editing:
            self._is_editing = editing
            print(f"DEBUG: MultiEntityReferenceWidget.set_editing({editing})")
            self._update_visual_state()

    def _update_visual_state(self):
        """Update the widget's visual appearance based on selection and editing states."""
        # Determine background and border colors - use #4a9eff to match table selection
        if self._is_editing:
            # Editing mode: blue border, dark background
            self.bg_color = QtGui.QColor("#2b2b2b")
            self.border_color = QtGui.QColor("#4a9eff")
            self.border_width = 2
            state = "editing"
        elif self._is_selected:
            # Selected mode: blue background matching table selection
            self.bg_color = QtGui.QColor("#4a9eff")
            self.border_color = QtGui.QColor("#4a9eff")
            self.border_width = 1
            state = "selected"
        else:
            # Normal mode: dark background, no border (matching table cells)
            self.bg_color = QtGui.QColor("#2b2b2b")
            # Border not drawn in normal state (table grid lines show through)
            state = "normal"

        # Trigger repaint with new colors
        self.update()


class FlowLayout(QtWidgets.QLayout):
    """
    A layout that arranges widgets in a flow, wrapping to new lines as needed.

    Based on Qt's Flow Layout example, adapted for PySide6.
    """

    def __init__(self, parent=None, margin=0, h_spacing=-1, v_spacing=-1):
        super().__init__(parent)

        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)

        self._h_space = h_spacing
        self._v_space = v_spacing
        self._item_list = []

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self._item_list.append(item)

    def horizontalSpacing(self):
        if self._h_space >= 0:
            return self._h_space
        else:
            return self._smart_spacing(QtWidgets.QStyle.PM_LayoutHorizontalSpacing)

    def verticalSpacing(self):
        if self._v_space >= 0:
            return self._v_space
        else:
            return self._smart_spacing(QtWidgets.QStyle.PM_LayoutVerticalSpacing)

    def count(self):
        return len(self._item_list)

    def itemAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)
        return None

    def expandingDirections(self):
        return QtCore.Qt.Orientations(QtCore.Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self._do_layout(QtCore.QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QtCore.QSize()

        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())

        margin_left, margin_top, margin_right, margin_bottom = self.getContentsMargins()
        size += QtCore.QSize(margin_left + margin_right, margin_top + margin_bottom)
        return size

    def _do_layout(self, rect, test_only):
        left, top, right, bottom = self.getContentsMargins()
        effective_rect = rect.adjusted(left, top, -right, -bottom)
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0

        for item in self._item_list:
            wid = item.widget()
            space_x = self.horizontalSpacing()
            if space_x == -1:
                space_x = wid.style().layoutSpacing(
                    QtWidgets.QSizePolicy.PushButton,
                    QtWidgets.QSizePolicy.PushButton,
                    QtCore.Qt.Horizontal
                )

            space_y = self.verticalSpacing()
            if space_y == -1:
                space_y = wid.style().layoutSpacing(
                    QtWidgets.QSizePolicy.PushButton,
                    QtWidgets.QSizePolicy.PushButton,
                    QtCore.Qt.Vertical
                )

            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > effective_rect.right() and line_height > 0:
                x = effective_rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), item.sizeHint()))

            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y() + bottom

    def _smart_spacing(self, pm):
        parent = self.parent()
        if not parent:
            return -1
        elif parent.isWidgetType():
            return parent.style().pixelMetric(pm, None, parent)
        else:
            return parent.spacing()


class AddEntityDialog(QtWidgets.QDialog):
    """
    Dialog for adding a new entity reference.

    In a real implementation, this would integrate with ShotGrid's entity picker.
    This is a simplified version for demonstration.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Entity Reference")
        self.setModal(True)
        self.setMinimumWidth(400)

        self.entity_data = None
        self._setup_ui()

    def _setup_ui(self):
        """Build dialog UI."""
        layout = QtWidgets.QVBoxLayout(self)

        # Instructions
        info_label = QtWidgets.QLabel(
            "Enter entity details:\n"
            "(In production, this would be a ShotGrid entity picker)"
        )
        info_label.setStyleSheet("color: #a0a0a0; padding: 5px;")
        layout.addWidget(info_label)

        # Form layout
        form_layout = QtWidgets.QFormLayout()

        # Entity type
        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.addItems(["CustomEntity07", "Asset", "Shot", "Sequence"])
        form_layout.addRow("Entity Type:", self.type_combo)

        # Entity ID
        self.id_field = QtWidgets.QSpinBox()
        self.id_field.setRange(1, 999999)
        self.id_field.setValue(1)
        form_layout.addRow("Entity ID:", self.id_field)

        # Entity name
        self.name_field = QtWidgets.QLineEdit()
        self.name_field.setPlaceholderText("e.g., cre_deer")
        form_layout.addRow("Entity Name:", self.name_field)

        layout.addLayout(form_layout)

        # Buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def accept(self):
        """Validate and accept dialog."""
        name = self.name_field.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "Invalid Input", "Please enter an entity name.")
            return

        self.entity_data = {
            "type": self.type_combo.currentText(),
            "id": self.id_field.value(),
            "name": name
        }
        super().accept()

    def get_entity(self):
        """Get the entity data.

        Returns:
            dict: Entity dictionary or None
        """
        return self.entity_data


# Example usage and demo
if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)

    # Sample data matching ShotGrid format
    sample_entities = [
        {"type": "CustomEntity07", "id": 101, "name": "cre_deer"},
        {"type": "CustomEntity07", "id": 102, "name": "cre_fray"},
        {"type": "CustomEntity07", "id": 103, "name": "veh_family_car"},
    ]

    # Create main window for demo
    window = QtWidgets.QMainWindow()
    window.setWindowTitle("Multi-Entity Reference Widget Demo")
    window.setGeometry(100, 100, 800, 600)

    # Central widget
    central_widget = QtWidgets.QWidget()
    window.setCentralWidget(central_widget)

    # Layout
    layout = QtWidgets.QVBoxLayout(central_widget)

    # Title
    title = QtWidgets.QLabel("ShotGrid Multi-Entity Reference Widget")
    title.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
    layout.addWidget(title)

    # Demo widget
    demo_widget = MultiEntityReferenceWidget(sample_entities, allow_add=True)
    demo_widget.setMinimumHeight(100)
    demo_widget.entitiesChanged.connect(
        lambda entities: print(f"Entities changed: {[e['name'] for e in entities]}")
    )
    layout.addWidget(demo_widget)

    # Info label
    info_label = QtWidgets.QLabel(
        "Try:\n"
        "• Click 'X' to remove an entity\n"
        "• Click '+' to add a new entity\n"
        "• Changes are logged to console"
    )
    info_label.setStyleSheet("color: #a0a0a0; padding: 10px;")
    layout.addWidget(info_label)

    layout.addStretch()

    # Apply dark theme to app
    app.setStyle("Fusion")
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.Window, QtGui.QColor(53, 53, 53))
    palette.setColor(QtGui.QPalette.WindowText, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor(25, 25, 25))
    palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(53, 53, 53))
    palette.setColor(QtGui.QPalette.ToolTipBase, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.ToolTipText, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.Text, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.Button, QtGui.QColor(53, 53, 53))
    palette.setColor(QtGui.QPalette.ButtonText, QtCore.Qt.white)
    palette.setColor(QtGui.QPalette.BrightText, QtCore.Qt.red)
    palette.setColor(QtGui.QPalette.Link, QtGui.QColor(42, 130, 218))
    palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(42, 130, 218))
    palette.setColor(QtGui.QPalette.HighlightedText, QtCore.Qt.black)
    app.setPalette(palette)

    window.show()
    sys.exit(app.exec())
