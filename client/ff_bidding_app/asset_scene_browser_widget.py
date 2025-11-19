"""
Asset & Scene Browser Widget
A comprehensive PySide6 widget for browsing and managing assets and scenes with
collapsible categories, grid views, and folder icons.
"""

from PySide6 import QtWidgets, QtCore, QtGui
import logging

try:
    from .logger import logger
except (ImportError, ValueError, SystemError):
    logger = logging.getLogger("FFPackageManager")


class AssetItem(QtWidgets.QWidget):
    """Individual item widget representing a folder/asset with icon and label."""

    clicked = QtCore.Signal(dict)  # Emits item data when clicked
    double_clicked = QtCore.Signal(dict)  # Emits item data when double-clicked
    context_menu_requested = QtCore.Signal(dict, QtCore.QPoint)  # Emits item data and position

    def __init__(self, item_data, parent=None):
        """Initialize the asset item.

        Args:
            item_data: Dictionary with 'name' and 'path' keys
            parent: Parent widget
        """
        super().__init__(parent)
        self.item_data = item_data
        self.selected = False

        self.setFixedSize(120, 100)
        self.setCursor(QtCore.Qt.PointingHandCursor)

        self._setup_ui()

    def _setup_ui(self):
        """Setup the item UI with folder icon and label."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Folder icon
        self.icon_label = QtWidgets.QLabel()
        self.icon_label.setFixedSize(80, 80)
        self.icon_label.setAlignment(QtCore.Qt.AlignCenter)

        # Get system folder icon
        folder_icon = self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DirIcon)
        pixmap = folder_icon.pixmap(64, 64)
        self.icon_label.setPixmap(pixmap)

        # Apply default styling
        self.icon_label.setStyleSheet("""
            QLabel {
                background-color: #2b2b2b;
                border: 2px solid #444;
                border-radius: 4px;
            }
        """)

        layout.addWidget(self.icon_label, alignment=QtCore.Qt.AlignCenter)

        # Item name label
        name_label = QtWidgets.QLabel(self.item_data.get('name', 'Unknown'))
        name_label.setWordWrap(True)
        name_label.setMaximumWidth(110)
        name_label.setAlignment(QtCore.Qt.AlignCenter)
        name_label.setStyleSheet("font-size: 10px; color: #ddd; border: none;")
        layout.addWidget(name_label)

    def mousePressEvent(self, event):
        """Handle mouse press for selection."""
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit(self.item_data)
        elif event.button() == QtCore.Qt.RightButton:
            self.context_menu_requested.emit(self.item_data, event.globalPosition().toPoint())

    def mouseDoubleClickEvent(self, event):
        """Handle double-click to navigate into folder."""
        if event.button() == QtCore.Qt.LeftButton:
            self.double_clicked.emit(self.item_data)

    def set_selected(self, selected):
        """Set the selected state with visual feedback.

        Args:
            selected: Boolean indicating if item is selected
        """
        self.selected = selected
        if selected:
            self.icon_label.setStyleSheet("""
                QLabel {
                    background-color: #2b2b2b;
                    border: 2px solid #4a9eff;
                    border-radius: 4px;
                }
            """)
        else:
            self.icon_label.setStyleSheet("""
                QLabel {
                    background-color: #2b2b2b;
                    border: 2px solid #444;
                    border-radius: 4px;
                }
            """)


class ItemGrid(QtWidgets.QWidget):
    """Grid view widget for displaying folder items with horizontal scrolling."""

    item_clicked = QtCore.Signal(dict)
    item_double_clicked = QtCore.Signal(dict)

    def __init__(self, parent=None):
        """Initialize the item grid."""
        super().__init__(parent)
        self.items = []
        self.item_widgets = []
        self.selected_item = None

        self._setup_ui()

    def _setup_ui(self):
        """Setup the grid UI with horizontal scrolling."""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Scroll area for horizontal scrolling
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll_area.setMaximumHeight(130)

        # Container for items
        self.container = QtWidgets.QWidget()
        self.grid_layout = QtWidgets.QHBoxLayout(self.container)
        self.grid_layout.setSpacing(5)
        self.grid_layout.setContentsMargins(5, 5, 5, 5)
        self.grid_layout.setAlignment(QtCore.Qt.AlignLeft)

        scroll_area.setWidget(self.container)
        main_layout.addWidget(scroll_area)

    def set_items(self, items):
        """Set the items to display in the grid.

        Args:
            items: List of dictionaries with 'name' and 'path' keys
        """
        # Clear existing items
        self.clear()

        self.items = items

        # Add new items
        for item_data in items:
            item_widget = AssetItem(item_data, self)
            item_widget.clicked.connect(self._on_item_clicked)
            item_widget.double_clicked.connect(self._on_item_double_clicked)
            item_widget.context_menu_requested.connect(self._show_context_menu)

            self.grid_layout.addWidget(item_widget)
            self.item_widgets.append(item_widget)

    def _on_item_clicked(self, item_data):
        """Handle item click."""
        # Deselect previous
        if self.selected_item:
            self.selected_item.set_selected(False)

        # Select new
        for widget in self.item_widgets:
            if widget.item_data == item_data:
                widget.set_selected(True)
                self.selected_item = widget
                break

        self.item_clicked.emit(item_data)

    def _on_item_double_clicked(self, item_data):
        """Handle item double-click."""
        self.item_double_clicked.emit(item_data)
        logger.info(f"Item double-clicked: {item_data.get('name')}")

    def _show_context_menu(self, item_data, position):
        """Show context menu for item.

        Args:
            item_data: Dictionary with item information
            position: Global position for menu
        """
        menu = QtWidgets.QMenu(self)

        # Open action
        open_action = menu.addAction("Open")
        open_action.triggered.connect(lambda: self._on_item_double_clicked(item_data))

        # Show in Explorer action
        explorer_action = menu.addAction("Show in Explorer")
        explorer_action.triggered.connect(lambda: self._show_in_explorer(item_data))

        # Properties action
        properties_action = menu.addAction("Properties")
        properties_action.triggered.connect(lambda: self._show_properties(item_data))

        menu.exec(position)

    def _show_in_explorer(self, item_data):
        """Show item in system file explorer."""
        path = item_data.get('path', '')
        logger.info(f"Show in explorer: {path}")
        # TODO: Implement platform-specific file explorer opening
        QtWidgets.QMessageBox.information(
            self,
            "Show in Explorer",
            f"Path: {path}\n\n(Feature not yet implemented)"
        )

    def _show_properties(self, item_data):
        """Show item properties dialog."""
        logger.info(f"Show properties: {item_data.get('name')}")
        QtWidgets.QMessageBox.information(
            self,
            "Properties",
            f"Name: {item_data.get('name')}\nPath: {item_data.get('path')}"
        )

    def clear(self):
        """Clear all items from the grid."""
        for widget in self.item_widgets:
            widget.deleteLater()
        self.item_widgets.clear()
        self.items.clear()
        self.selected_item = None


class CategorySection(QtWidgets.QWidget):
    """Collapsible category section widget with header and grid."""

    def __init__(self, category_name, parent=None):
        """Initialize the category section.

        Args:
            category_name: Name of the category (e.g., "Assets", "Scenes")
            parent: Parent widget
        """
        super().__init__(parent)
        self.category_name = category_name
        self.is_collapsed = False

        self._setup_ui()

    def _setup_ui(self):
        """Setup the category section UI."""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(5)

        # Header with collapse/expand toggle
        self.header_widget = QtWidgets.QWidget()
        self.header_widget.setStyleSheet("""
            QWidget {
                background-color: #353535;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        self.header_widget.setCursor(QtCore.Qt.PointingHandCursor)
        self.header_widget.mousePressEvent = lambda event: self._toggle_collapse()

        header_layout = QtWidgets.QHBoxLayout(self.header_widget)
        header_layout.setContentsMargins(5, 5, 5, 5)

        # Toggle arrow
        self.arrow_label = QtWidgets.QLabel("▼")
        self.arrow_label.setStyleSheet("color: #ddd; font-weight: bold; border: none; background: transparent;")
        header_layout.addWidget(self.arrow_label)

        # Category title
        self.title_label = QtWidgets.QLabel(self.category_name)
        self.title_label.setStyleSheet("color: #ddd; font-weight: bold; font-size: 12px; border: none; background: transparent;")
        header_layout.addWidget(self.title_label)

        header_layout.addStretch()

        # Item count label
        self.count_label = QtWidgets.QLabel("0 items")
        self.count_label.setStyleSheet("color: #888; font-size: 10px; border: none; background: transparent;")
        header_layout.addWidget(self.count_label)

        main_layout.addWidget(self.header_widget)

        # Item grid
        self.item_grid = ItemGrid(self)
        main_layout.addWidget(self.item_grid)

    def _toggle_collapse(self):
        """Toggle the collapsed state of the category."""
        self.is_collapsed = not self.is_collapsed
        self.item_grid.setVisible(not self.is_collapsed)
        self.arrow_label.setText("▶" if self.is_collapsed else "▼")

    def set_items(self, items):
        """Set the items for this category.

        Args:
            items: List of dictionaries with 'name' and 'path' keys
        """
        self.item_grid.set_items(items)
        self.count_label.setText(f"{len(items)} items")

    def get_item_grid(self):
        """Get the item grid widget.

        Returns:
            ItemGrid widget
        """
        return self.item_grid


class AssetBrowserWidget(QtWidgets.QWidget):
    """Main asset and scene browser widget with categorized browsing."""

    item_selected = QtCore.Signal(str, dict)  # Emits category and item data
    item_opened = QtCore.Signal(str, dict)  # Emits category and item data

    def __init__(self, parent=None):
        """Initialize the asset browser widget."""
        super().__init__(parent)
        self.categories = {}
        self.category_sections = {}

        self._setup_ui()
        self._load_sample_data()

    def _setup_ui(self):
        """Setup the main browser UI."""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)

        # Header with title
        header_layout = QtWidgets.QHBoxLayout()

        title_label = QtWidgets.QLabel("Assets & Scenes")
        title_font = title_label.font()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # Search/filter (placeholder for future implementation)
        search_box = QtWidgets.QLineEdit()
        search_box.setPlaceholderText("Search...")
        search_box.setMaximumWidth(200)
        search_box.textChanged.connect(self._on_search_changed)
        header_layout.addWidget(search_box)

        main_layout.addLayout(header_layout)

        # Scroll area for categories
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        # Container for category sections
        self.container = QtWidgets.QWidget()
        self.container_layout = QtWidgets.QVBoxLayout(self.container)
        self.container_layout.setSpacing(10)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setAlignment(QtCore.Qt.AlignTop)

        scroll_area.setWidget(self.container)
        main_layout.addWidget(scroll_area)

        # Initialize default categories
        self._create_category("Assets")
        self._create_category("Scenes")

    def _create_category(self, category_name):
        """Create a new category section.

        Args:
            category_name: Name of the category
        """
        section = CategorySection(category_name, self)

        # Connect signals
        section.get_item_grid().item_clicked.connect(
            lambda item_data: self._on_item_selected(category_name, item_data)
        )
        section.get_item_grid().item_double_clicked.connect(
            lambda item_data: self._on_item_opened(category_name, item_data)
        )

        self.container_layout.addWidget(section)
        self.category_sections[category_name] = section
        self.categories[category_name] = []

    def _on_item_selected(self, category, item_data):
        """Handle item selection.

        Args:
            category: Category name
            item_data: Item data dictionary
        """
        logger.info(f"Item selected: {category} - {item_data.get('name')}")
        self.item_selected.emit(category, item_data)

    def _on_item_opened(self, category, item_data):
        """Handle item double-click/open.

        Args:
            category: Category name
            item_data: Item data dictionary
        """
        logger.info(f"Item opened: {category} - {item_data.get('name')}")
        self.item_opened.emit(category, item_data)

    def _on_search_changed(self, text):
        """Handle search text changes.

        Args:
            text: Search text
        """
        if not text:
            # Show all items
            for category_name, items in self.categories.items():
                if category_name in self.category_sections:
                    self.category_sections[category_name].set_items(items)
        else:
            # Filter items
            text_lower = text.lower()
            for category_name, items in self.categories.items():
                filtered = [
                    item for item in items
                    if text_lower in item.get('name', '').lower()
                ]
                if category_name in self.category_sections:
                    self.category_sections[category_name].set_items(filtered)

    def set_category_data(self, category_name, items):
        """Set the data for a specific category.

        Args:
            category_name: Name of the category (e.g., "Assets", "Scenes")
            items: List of dictionaries with 'name' and 'path' keys
        """
        if category_name not in self.category_sections:
            self._create_category(category_name)

        self.categories[category_name] = items
        self.category_sections[category_name].set_items(items)

        logger.info(f"Set {len(items)} items for category '{category_name}'")

    def populate_from_data(self, data):
        """Populate all categories from a data dictionary.

        Args:
            data: Dictionary mapping category names to lists of items
                  Example: {'Assets': [...], 'Scenes': [...]}
        """
        for category_name, items in data.items():
            self.set_category_data(category_name, items)

    def _load_sample_data(self):
        """Load sample data for demonstration (can be removed in production)."""
        sample_data = {
            'Assets': [
                {'name': 'Characters', 'path': '/path/to/characters'},
                {'name': 'Props', 'path': '/path/to/props'},
                {'name': 'Environments', 'path': '/path/to/environments'},
                {'name': 'Vehicles', 'path': '/path/to/vehicles'},
                {'name': 'Weapons', 'path': '/path/to/weapons'},
            ],
            'Scenes': [
                {'name': 'scene_001', 'path': '/path/to/scene_001'},
                {'name': 'scene_002', 'path': '/path/to/scene_002'},
                {'name': 'scene_003', 'path': '/path/to/scene_003'},
                {'name': 'scene_004', 'path': '/path/to/scene_004'},
            ]
        }

        self.populate_from_data(sample_data)

    def clear_category(self, category_name):
        """Clear all items from a category.

        Args:
            category_name: Name of the category to clear
        """
        if category_name in self.category_sections:
            self.category_sections[category_name].set_items([])
            self.categories[category_name] = []

    def clear_all(self):
        """Clear all items from all categories."""
        for category_name in self.category_sections.keys():
            self.clear_category(category_name)


# Example usage and testing
if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)

    # Apply dark theme
    app.setStyle("Fusion")
    dark_palette = QtGui.QPalette()
    dark_palette.setColor(QtGui.QPalette.Window, QtGui.QColor(43, 43, 43))
    dark_palette.setColor(QtGui.QPalette.WindowText, QtCore.Qt.white)
    dark_palette.setColor(QtGui.QPalette.Base, QtGui.QColor(25, 25, 25))
    dark_palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(53, 53, 53))
    dark_palette.setColor(QtGui.QPalette.ToolTipBase, QtCore.Qt.white)
    dark_palette.setColor(QtGui.QPalette.ToolTipText, QtCore.Qt.white)
    dark_palette.setColor(QtGui.QPalette.Text, QtCore.Qt.white)
    dark_palette.setColor(QtGui.QPalette.Button, QtGui.QColor(53, 53, 53))
    dark_palette.setColor(QtGui.QPalette.ButtonText, QtCore.Qt.white)
    dark_palette.setColor(QtGui.QPalette.BrightText, QtCore.Qt.red)
    dark_palette.setColor(QtGui.QPalette.Link, QtGui.QColor(42, 130, 218))
    dark_palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(42, 130, 218))
    dark_palette.setColor(QtGui.QPalette.HighlightedText, QtCore.Qt.black)
    app.setPalette(dark_palette)

    # Create and show the widget
    widget = AssetBrowserWidget()
    widget.setWindowTitle("Asset & Scene Browser")
    widget.resize(800, 600)
    widget.show()

    sys.exit(app.exec())
