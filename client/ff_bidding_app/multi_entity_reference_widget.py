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

    Signals:
        removeRequested: Emitted when user clicks the X button
    """

    removeRequested = QtCore.Signal(object)  # Emits the entity dict

    def __init__(self, entity, parent=None):
        """
        Initialize an entity pill widget.

        Args:
            entity (dict): ShotGrid entity dict with 'type', 'id', 'name' keys
            parent (QWidget): Parent widget
        """
        super().__init__(parent)
        self.entity = entity
        self.entity_name = entity.get("name", f"ID {entity.get('id', 'N/A')}")

        # Colors for custom painting
        self.bg_color = QtGui.QColor("#b0b0b0")
        self.border_color = QtGui.QColor("#888888")

        self._setup_ui()

    def _setup_ui(self):
        """Build the pill UI with label and close button."""
        # Main layout - horizontal
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 4, 3)
        layout.setSpacing(4)

        # Entity name label
        self.name_label = QtWidgets.QLabel(self.entity_name)
        self.name_label.setStyleSheet("""
            QLabel {
                color: #2b2b2b;
                font-size: 11px;
                background: transparent;
                border: none;
            }
        """)
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

    def get_entity(self):
        """Get the entity dict for this pill.

        Returns:
            dict: Entity dictionary
        """
        return self.entity


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

    def __init__(self, entities=None, allow_add=True, parent=None):
        """
        Initialize the multi-entity reference widget.

        Args:
            entities (list): List of ShotGrid entity dicts
            allow_add (bool): Whether to show the Add button
            parent (QWidget): Parent widget
        """
        super().__init__(parent)
        self._entities = entities or []
        self._allow_add = allow_add

        self._setup_ui()
        self._populate_entities()

    def _setup_ui(self):
        """Build the main UI with flow layout."""
        # Main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(0)

        # Scroll area for pills (in case of many entities)
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
        """)

        # Container for pills with flow layout
        self.pills_container = QtWidgets.QWidget()
        self.pills_layout = FlowLayout(self.pills_container, margin=2, h_spacing=4, v_spacing=4)

        scroll_area.setWidget(self.pills_container)
        main_layout.addWidget(scroll_area)

        # Apply dark theme styling
        self.setStyleSheet("""
            MultiEntityReferenceWidget {
                background-color: #2b2b2b;
                border: 1px solid #555555;
                border-radius: 4px;
            }
            QWidget#pillsContainer {
                background-color: transparent;
            }
        """)
        self.pills_container.setObjectName("pillsContainer")

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
        pill = EntityPillWidget(entity, self)
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
        self._entities = entities or []
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
