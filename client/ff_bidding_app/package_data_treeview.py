from PySide6 import QtWidgets, QtCore, QtGui
import logging

# Try relative import first, fall back to creating a logger
try:
    from .logger import logger
except (ImportError, ValueError, SystemError):
    logger = logging.getLogger("FireframeProdigy")


class SGWorker(QtCore.QObject):
    """Worker for running ShotGrid operations in a background thread."""

    finished = QtCore.Signal(bool, str)  # (success, error_message)

    def __init__(self, sg_session, operation, *args, **kwargs):
        super().__init__()
        self.sg_session = sg_session
        self.operation = operation
        self.args = args
        self.kwargs = kwargs

    def run(self):
        """Execute the ShotGrid operation."""
        try:
            method = getattr(self.sg_session, self.operation)
            method(*self.args, **self.kwargs)
            self.finished.emit(True, "")
        except Exception as e:
            logger.error(f"SG operation failed: {e}", exc_info=True)
            self.finished.emit(False, str(e))


class TreeCheckBoxDelegate(QtWidgets.QStyledItemDelegate):
    """Custom delegate for rendering checkboxes in tree widget with DPI scaling."""

    def __init__(self, parent=None):
        """Initialize the delegate."""
        super().__init__(parent)

    def paint(self, painter, option, index):
        """Paint the checkbox with custom styling and DPI scaling."""
        # Only handle checkbox column (column 0) with checkable items
        if index.column() == 0:
            flags = index.flags()
            if flags & QtCore.Qt.ItemIsUserCheckable:
                painter.save()

                # Get DPI scale fresh on each paint to reflect real-time changes
                # Try to get from active app (for live preview), fall back to settings
                try:
                    from .app import PackageManagerApp
                    dpi_scale = getattr(PackageManagerApp, '_active_dpi_scale', None)
                except ImportError:
                    dpi_scale = None

                if dpi_scale is None:
                    try:
                        from .settings import AppSettings
                    except ImportError:
                        from settings import AppSettings
                    app_settings = AppSettings()
                    dpi_scale = app_settings.get_dpi_scale()

                checkbox_size = int(18 * dpi_scale)

                # Calculate checkbox rect (centered in the cell)
                checkbox_rect = QtCore.QRect(
                    option.rect.center().x() - checkbox_size // 2,
                    option.rect.center().y() - checkbox_size // 2,
                    checkbox_size,
                    checkbox_size
                )

                # Get check state
                check_state = index.data(QtCore.Qt.CheckStateRole)
                is_checked = (check_state == QtCore.Qt.Checked)

                # Scale pen width and corner radius with DPI
                pen_width = max(1, int(1 * dpi_scale))
                corner_radius = max(2, int(3 * dpi_scale))

                # Set up pen and brush for border
                if is_checked:
                    # Checked: blue border and background
                    pen = QtGui.QPen(QtGui.QColor("#4a9eff"), pen_width)
                    painter.setPen(pen)
                    painter.setBrush(QtGui.QColor("#4a9eff"))
                else:
                    # Unchecked: gray border
                    pen = QtGui.QPen(QtGui.QColor("#555555"), pen_width)
                    painter.setPen(pen)
                    painter.setBrush(QtGui.QColor("#404040"))

                # Draw rounded rectangle
                painter.setRenderHint(QtGui.QPainter.Antialiasing)
                painter.drawRoundedRect(checkbox_rect, corner_radius, corner_radius)

                # Draw tick if checked
                if is_checked:
                    painter.setPen(QtGui.QPen(QtGui.QColor("#ffffff"), max(2, int(2 * dpi_scale))))
                    # Draw checkmark path
                    check_path = QtGui.QPainterPath()
                    # Scale the checkmark coordinates
                    offset = checkbox_size * 0.2
                    mid_x = checkbox_rect.left() + checkbox_size * 0.4
                    mid_y = checkbox_rect.center().y() + checkbox_size * 0.1
                    check_path.moveTo(checkbox_rect.left() + offset, checkbox_rect.center().y())
                    check_path.lineTo(mid_x, checkbox_rect.bottom() - offset)
                    check_path.lineTo(checkbox_rect.right() - offset, checkbox_rect.top() + offset)
                    painter.drawPath(check_path)

                painter.restore()
                return

        # Default painting for other columns
        super().paint(painter, option, index)

    def editorEvent(self, event, model, option, index):
        """Handle mouse events for toggling checkboxes."""
        if index.column() == 0:
            flags = index.flags()
            if flags & QtCore.Qt.ItemIsUserCheckable:
                if event.type() == QtCore.QEvent.MouseButtonRelease:
                    if event.button() == QtCore.Qt.LeftButton:
                        # Toggle the check state
                        check_state = index.data(QtCore.Qt.CheckStateRole)
                        new_state = QtCore.Qt.Unchecked if check_state == QtCore.Qt.Checked else QtCore.Qt.Checked
                        model.setData(index, new_state, QtCore.Qt.CheckStateRole)
                        return True
                return True

        # Default behavior for other columns
        return super().editorEvent(event, model, option, index)


class CustomCheckBox(QtWidgets.QCheckBox):
    """Custom checkbox with visible checkmark for dark theme."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)

    def paintEvent(self, event):
        super().paintEvent(event)

        if self.isChecked():
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)

            # Get the indicator rectangle
            opt = QtWidgets.QStyleOptionButton()
            self.initStyleOption(opt)
            style = self.style()
            rect = style.subElementRect(QtWidgets.QStyle.SE_CheckBoxIndicator, opt, self)

            # Draw checkmark
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 2))
            # Draw a check symbol
            check_path = QtGui.QPainterPath()
            check_path.moveTo(rect.left() + 4, rect.center().y())
            check_path.lineTo(rect.center().x() - 1, rect.bottom() - 5)
            check_path.lineTo(rect.right() - 3, rect.top() + 4)
            painter.drawPath(check_path)


class SGTreeItem(QtWidgets.QTreeWidgetItem):
    """Custom tree item that stores Shotgrid entity data."""

    def __init__(self, parent, columns, sg_data=None, item_type=None):
        """
        Initialize tree item with Shotgrid data.

        Args:
            parent: Parent widget or tree item
            columns: List of column values
            sg_data: Dictionary containing Shotgrid entity data
            item_type: Type of item (e.g., "version", "asset", "shot", "folder")
        """
        super().__init__(parent, columns)

        self._sg_data = sg_data or {}
        self._item_type = item_type or "unknown"

    def get_sg_data(self, key=None):
        """
        Get Shotgrid data.

        Args:
            key: Optional key to get specific field. If None, returns all data.

        Returns:
            Shotgrid data dictionary or specific field value
        """
        if key is None:
            return self._sg_data
        return self._sg_data.get(key)

    def set_sg_data(self, data):
        """
        Set or update Shotgrid data.

        Args:
            data: Dictionary with Shotgrid data to store
        """
        self._sg_data.update(data)

    def get_item_type(self):
        """Get the item type."""
        return self._item_type

    def get_sg_id(self):
        """Get the Shotgrid entity ID."""
        return self._sg_data.get('id')

    def get_sg_type(self):
        """Get the Shotgrid entity type."""
        return self._sg_data.get('type')

    def get_entity_name(self):
        """Get the entity name (code or name field)."""
        return self._sg_data.get('code') or self._sg_data.get('name')

    def has_sg_data(self):
        """Check if item has Shotgrid data."""
        return bool(self._sg_data)

    def get_version_info(self):
        """
        Get version-specific information if this is a version item.

        Returns:
            Dictionary with version info or None
        """
        if self._item_type != "version":
            return None

        return {
            'id': self._sg_data.get('id'),
            'code': self._sg_data.get('code'),
            'status': self._sg_data.get('sg_status_list'),
            'entity': self._sg_data.get('entity'),
            'task': self._sg_data.get('sg_task'),
            'user': self._sg_data.get('user'),
            'created_at': self._sg_data.get('created_at'),
            'description': self._sg_data.get('description'),
            'uploaded_movie': self._sg_data.get('sg_uploaded_movie'),
            'path_to_movie': self._sg_data.get('sg_path_to_movie'),
            'path_to_frames': self._sg_data.get('sg_path_to_frames'),
        }

    def get_uploaded_movie_url(self):
        """Get the URL of the uploaded movie if available."""
        uploaded_movie = self._sg_data.get('sg_uploaded_movie')
        if uploaded_movie and isinstance(uploaded_movie, dict):
            return uploaded_movie.get('url')
        return None

    def __repr__(self):
        """String representation for debugging."""
        return f"SGTreeItem(type={self._item_type}, id={self.get_sg_id()}, name={self.get_entity_name()})"


class BidTrackerVersionDialog(QtWidgets.QDialog):
    """Dialog for selecting a Bid Tracker version to link to a package."""

    def __init__(self, versions, current_version_id, parent=None):
        """
        Initialize the dialog.

        Args:
            versions: List of Bid Tracker version entities
            current_version_id: ID of the currently linked version (or None)
            parent: Parent widget
        """
        super().__init__(parent)
        self.versions = versions
        self.current_version_id = current_version_id
        self.selected_version_id = None

        self.setWindowTitle("Select Bid Tracker Version")
        self.resize(500, 150)

        self._setup_ui()

    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QtWidgets.QVBoxLayout(self)

        # Description label
        desc_label = QtWidgets.QLabel(
            "Select a Bid Tracker version to link to this package:"
        )
        layout.addWidget(desc_label)

        # Version dropdown
        version_layout = QtWidgets.QHBoxLayout()
        version_label = QtWidgets.QLabel("Version:")
        version_layout.addWidget(version_label)

        self.version_combo = QtWidgets.QComboBox()
        self.version_combo.setMinimumWidth(300)

        # Populate combo box with versions
        current_index = -1
        for i, version in enumerate(self.versions):
            version_code = version.get('code', 'Unknown')
            version_id = version.get('id')

            # Add extra info if this is the current version
            if version_id == self.current_version_id:
                display_text = f"{version_code} (Current)"
                current_index = i
            else:
                display_text = version_code

            self.version_combo.addItem(display_text, version_id)

        # Select current version by default
        if current_index >= 0:
            self.version_combo.setCurrentIndex(current_index)

        version_layout.addWidget(self.version_combo)
        version_layout.addStretch()
        layout.addLayout(version_layout)

        layout.addSpacing(20)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()

        ok_btn = QtWidgets.QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)

        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def get_selected_version_id(self):
        """Get the selected version ID."""
        return self.version_combo.currentData()


# Status colors (adjusted for dark theme)
status_colors = {
    "ip": QtGui.QColor(255, 180, 60),  # In Progress - Orange
    "wtg": QtGui.QColor(120, 120, 120),  # Waiting - Gray
    "rev": QtGui.QColor(255, 120, 120),  # Review - Red
    "apr": QtGui.QColor(100, 200, 100),  # Approved - Green
}


class PackageTreeView(QtWidgets.QWidget):
    """Widget for displaying package data in a tree view."""

    # Signal emitted when a document/script is removed from a package
    documentRemovedFromPackage = QtCore.Signal(int, str)  # (version_id, folder_path)
    # Signal emitted when a remove operation fails and document is restored
    documentRestoredToPackage = QtCore.Signal(int, str)  # (version_id, folder_path)

    def __init__(self, parent=None):
        """Initialize the PackageTreeView widget."""
        super().__init__(parent)

        # Initialize selected RFQ storage
        self.selected_rfq = None
        self.sg_session = None
        self.current_package_id = None  # Store current package ID for version selection

        # Store root category items for show/hide functionality
        self.category_items = {}

        # Store visibility preferences (persists across tree reloads)
        self.category_visibility_prefs = {}

        # Define canonical order of categories
        self.category_order = ["Bid Tracker", "Documents", "Images"]

        # Build the UI
        self._setup_ui()

    def set_sg_session(self, sg_session):
        self.sg_session = sg_session

    def get_tree_widget(self):
        return self.tree_widget

    def _setup_ui(self):
        """Setup the widget UI."""
        # Create main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Add the panel to the layout
        panel = self.create_panel()
        main_layout.addWidget(panel)

    def create_panel(self):
        """Create the version tree panel."""
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)

        # Header
        header_layout = QtWidgets.QHBoxLayout()

        tree_label = QtWidgets.QLabel("Package Data")
        tree_font = tree_label.font()
        tree_font.setPointSize(12)
        tree_font.setBold(True)
        tree_label.setFont(tree_font)
        header_layout.addWidget(tree_label)

        header_layout.addStretch()

        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(refresh_btn)

        layout.addLayout(header_layout)

        # Tree widget
        self.tree_widget = QtWidgets.QTreeWidget()
        self.tree_widget.setHeaderLabels(["Name", "Type", "Status", "Version"])

        # Get DPI scale for column widths
        try:
            from .settings import AppSettings
        except ImportError:
            from settings import AppSettings
        app_settings = AppSettings()
        dpi_scale = app_settings.get_dpi_scale()

        # Scale column widths with DPI
        self.tree_widget.setColumnWidth(0, int(250 * dpi_scale))  # Name
        self.tree_widget.setColumnWidth(1, int(80 * dpi_scale))  # Type
        self.tree_widget.setColumnWidth(2, int(80 * dpi_scale))  # Status
        self.tree_widget.setAlternatingRowColors(True)
        self.tree_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

        # Enable tree item animations and proper branch indicators
        self.tree_widget.setAnimated(True)
        self.tree_widget.setIndentation(20)
        self.tree_widget.setRootIsDecorated(True)  # Show expand/collapse indicators

        # Enable context menu
        self.tree_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self.show_tree_context_menu)

        # Connect to handle expand/collapse for arrow updates
        self.tree_widget.itemExpanded.connect(self._on_item_expanded)
        self.tree_widget.itemCollapsed.connect(self._on_item_collapsed)

        layout.addWidget(self.tree_widget)

        return panel

    def _on_item_expanded(self, item):
        """Update arrow when item is expanded."""
        if isinstance(item, SGTreeItem) and item.get_item_type() == "folder":
            text = item.text(0)
            if text.startswith("►"):
                item.setText(0, text.replace("►", "▼", 1))

    def _on_item_collapsed(self, item):
        """Update arrow when item is collapsed."""
        if isinstance(item, SGTreeItem) and item.get_item_type() == "folder":
            text = item.text(0)
            if text.startswith("▼"):
                item.setText(0, text.replace("▼", "►", 1))

    def _create_version_item(self, parent, version, column_data):
        """Helper to create a version item."""
        version_item = SGTreeItem(
            parent,
            column_data,
            sg_data=version,
            item_type="version"
        )
        return version_item

    def set_rfq(self, rfq_data):
        """Set the RFQ data and reload the tree.

        Args:
            rfq_data (dict): The RFQ entity data from Shotgrid
        """
        self.selected_rfq = rfq_data

        # Just load the tree - visibility will be applied from the app
        self.load_tree_data()

    def load_package_versions(self, package_id):
        """Load versions from a Package instead of from RFQ.

        Args:
            package_id: ID of the Package entity
        """
        # Store package ID for use in context menu
        self.current_package_id = package_id

        self.tree_widget.clear()
        self.category_items.clear()

        if not package_id or not self.sg_session:
            return

        # Get versions with folder info from Package's PackageItems
        package_versions_with_folders = self.sg_session.get_package_versions_with_folders(
            package_id,
            fields=[
                "id", "code", "entity", "sg_status_list", "created_at", "updated_at",
                "user", "description", "sg_task", "sg_path_to_movie", "sg_path_to_frames",
                "sg_uploaded_movie", "sg_path_to_geometry", "sg_version_type"
            ]
        )

        # Get other versions (Script, Concept Art, Storyboard) from sg_parent_packages
        other_versions = self.sg_session.get_versions_by_parent_package(
            package_id,
            fields=[
                "id", "code", "entity", "sg_status_list", "created_at", "updated_at",
                "user", "description", "sg_task", "sg_path_to_movie", "sg_path_to_frames",
                "sg_uploaded_movie", "sg_path_to_geometry", "sg_version_type"
            ]
        )

        # Separate bid tracker versions from image versions, script versions, and document versions
        bid_tracker_versions = [v for v in package_versions_with_folders if self._is_bid_tracker_version(v)]
        image_versions_with_folders = [v for v in package_versions_with_folders if self._is_image_version(v)]
        script_versions_with_folders = [v for v in package_versions_with_folders if self._is_script_version(v)]
        document_versions_with_folders = [v for v in package_versions_with_folders if self._is_document_version(v)]

        # Also get versions from other_versions (without folder info)
        image_versions_without_folders = [v for v in other_versions if self._is_image_version(v)]
        script_versions_from_other = [v for v in other_versions if self._is_script_version(v)]
        document_versions_from_other = [v for v in other_versions if self._is_document_version(v)]

        # Combine versions from both sources (PackageItems and parent package linked)
        all_script_versions = script_versions_with_folders + script_versions_from_other
        all_document_versions = document_versions_with_folders + document_versions_from_other

        # Build the tree with actual version data
        self.set_bid_tracker_item(bid_tracker_versions)
        self.set_scripts_item(all_script_versions)
        self.set_documents_item(all_document_versions)
        # Show images organized by folder under Images section
        self.set_images_item(image_versions_with_folders, image_versions_without_folders)

        # Apply stored visibility preferences
        for category_name, visible in self.category_visibility_prefs.items():
            if category_name in self.category_items:
                self.category_items[category_name].setHidden(not visible)

    def clear(self):
        """Clear the tree view."""
        self.tree_widget.clear()
        self.selected_rfq = None

    def refresh(self):
        """Refresh the tree with current package or RFQ data from ShotGrid."""
        # Check if we're viewing a package
        if self.current_package_id:
            self.load_package_versions(self.current_package_id)
        # Otherwise check if we're viewing an RFQ
        elif self.selected_rfq:
            self.load_tree_data()
        else:
            self.tree_widget.clear()
            self.category_items.clear()

    def update_column_widths_for_dpi(self):
        """Update column widths based on current DPI scale."""
        try:
            from .settings import AppSettings
        except ImportError:
            from settings import AppSettings
        app_settings = AppSettings()
        dpi_scale = app_settings.get_dpi_scale()

        # Scale column widths with DPI
        self.tree_widget.setColumnWidth(0, int(250 * dpi_scale))  # Name
        self.tree_widget.setColumnWidth(1, int(80 * dpi_scale))  # Type
        self.tree_widget.setColumnWidth(2, int(80 * dpi_scale))  # Status

    def load_tree_data(self):
        """Load version tree with data from selected RFQ."""
        self.tree_widget.clear()
        self.category_items.clear()

        # Check if we have a selected RFQ
        if not self.selected_rfq:
            return

        rfq_id = self.selected_rfq.get('id')

        # Get versions with sg_version_type field
        versions = self.sg_session.get_rfq_versions(
            rfq_id,
            fields=[
                "id", "code", "entity", "sg_status_list", "created_at", "updated_at",
                "user", "description", "sg_task", "sg_path_to_movie", "sg_path_to_frames",
                "sg_uploaded_movie", "sg_path_to_geometry", "sg_version_type"
            ]
        )

        # Build the tree with actual version data
        self.set_bid_tracker_item(versions)
        self.set_scripts_item(versions)
        self.set_documents_item(versions)
        # For RFQ-based view, no folder info, so all images are without folders
        self.set_images_item([], versions)

        # Apply stored visibility preferences
        for category_name, visible in self.category_visibility_prefs.items():
            if category_name in self.category_items:
                self.category_items[category_name].setHidden(not visible)

    def set_category_visibility(self, category_name, visible):
        """
        Show or hide a category in the tree.

        Args:
            category_name: Name of the category (e.g., "Bid Tracker", "Script")
            visible: True to show, False to hide
        """
        # Store the preference
        self.category_visibility_prefs[category_name] = visible

        if category_name not in self.category_items:
            return

        item = self.category_items[category_name]

        # Remove the item from the tree if it's currently there
        index = self.tree_widget.indexOfTopLevelItem(item)

        if index >= 0:
            self.tree_widget.takeTopLevelItem(index)

        # If we want it visible, add it back in the correct position
        if visible:
            # Find the correct index by checking which categories should come before this one
            insert_index = 0
            for cat in self.category_order:
                if cat == category_name:
                    break
                # If this category exists and is visible, increment insert position
                if cat in self.category_items:
                    cat_item = self.category_items[cat]
                    cat_index = self.tree_widget.indexOfTopLevelItem(cat_item)
                    if cat_index >= 0:
                        insert_index += 1

            self.tree_widget.insertTopLevelItem(insert_index, item)
            item.setHidden(False)

    def apply_visibility_states(self, visibility_states):
        """
        Apply visibility states to categories after tree is loaded.

        Args:
            visibility_states: Dictionary mapping category names to visibility (bool)
        """
        for category_name, visible in visibility_states.items():
            self.set_category_visibility(category_name, visible)

    def set_bid_tracker_item(self, versions):
        """Build Bid Tracker section with real version data."""
        # Create root folder with arrow
        bid_tracker_root = SGTreeItem(
            self.tree_widget,
            ["Bid Tracker", "Folder", "", ""],
            sg_data={'type': 'folder'},
            item_type="folder"
        )

        self.category_items["Bid Tracker"] = bid_tracker_root
        bid_tracker_root.setExpanded(True)
        font = bid_tracker_root.font(0)
        font.setBold(True)
        bid_tracker_root.setFont(0, font)

        # Filter bid tracker versions
        bid_tracker_versions = [v for v in versions if self._is_bid_tracker_version(v)]

        if bid_tracker_versions:
            for version in bid_tracker_versions:
                version_code = version.get('code', 'Unknown')
                status = version.get('sg_status_list', '')
                status_display = status if status else 'N/A'
                version_number = version_code.split('_')[-1] if '_' in version_code else ""

                # Use helper to create version item
                version_item = self._create_version_item(
                    bid_tracker_root,
                    version,
                    [version_code, "Version", status_display, version_number]
                )
        else:
            # No bid tracker versions found
            no_data_item = SGTreeItem(
                bid_tracker_root,
                ["No Bid Tracker attached", "Info", "", ""],
                item_type="info"
            )
            no_data_item.setForeground(0, QtGui.QColor(120, 120, 120))

    def set_documents_item(self, versions):
        """Build Documents section with hierarchical folders and versions.

        Supports folder paths like /Documents (root level) or /scenes/ARR/Document (nested).
        """
        documents_root = SGTreeItem(
            self.tree_widget,
            ["Documents", "Folder", "", ""],
            sg_data={'type': 'folder'},
            item_type="folder"
        )

        self.category_items["Documents"] = documents_root
        documents_root.setExpanded(True)
        font = documents_root.font(0)
        font.setBold(True)
        documents_root.setFont(0, font)

        # Filter document versions
        document_versions = [v for v in versions if self._is_document_version(v)]

        # Process each version's folder paths individually
        # A version can appear both at root level AND in nested folders
        versions_for_root = []
        versions_for_nested = []

        for version in document_versions:
            folders_str = version.get('_package_folders', '')
            if folders_str:
                folder_paths = [f.strip() for f in folders_str.split(';') if f.strip()]
                has_root_path = False
                has_nested_path = False
                for fp in folder_paths:
                    if '/scenes/' in fp or '/assets/' in fp:
                        has_nested_path = True
                    else:
                        # Root-level path (e.g., /Document or /Documents)
                        has_root_path = True

                if has_root_path:
                    versions_for_root.append(version)
                if has_nested_path:
                    versions_for_nested.append(version)
            else:
                # No folder assignment - add to root
                versions_for_root.append(version)

        # Build hierarchical tree for versions in scene/asset folders
        if versions_for_nested or versions_for_root:
            if versions_for_nested:
                path_tree = {}
                for version in versions_for_nested:
                    folders_str = version.get('_package_folders', '')
                    folder_paths = [f.strip() for f in folders_str.split(';') if f.strip()]
                    for folder_path in folder_paths:
                        # Only process paths with scenes or assets
                        if '/scenes/' in folder_path or '/assets/' in folder_path:
                            # Parse the path, skip the Script/Document part at the end
                            parts = [p for p in folder_path.split('/') if p]
                            # Remove the last part if it's Script/Document (category)
                            if parts and parts[-1].lower() in ['script', 'document', 'scripts', 'documents']:
                                parts = parts[:-1]

                            if parts:
                                # Navigate/create the tree structure
                                current_level = path_tree
                                for part in parts:
                                    if part not in current_level:
                                        current_level[part] = {'_versions': [], '_children': {}}
                                    current_level = current_level[part]['_children']

                                # Add version to the deepest level
                                current_level = path_tree
                                for part in parts[:-1]:
                                    current_level = current_level[part]['_children']
                                if parts:
                                    current_level[parts[-1]]['_versions'].append(version)

                self._build_folder_tree(documents_root, path_tree, "")

            # Add versions with root-level paths directly under Documents
            for version in versions_for_root:
                version_code = version.get('code', 'Unknown')
                status = version.get('sg_status_list', '')
                status_display = status if status else 'N/A'
                version_number = version_code.split('_')[-1] if '_' in version_code else ""

                version_item = self._create_version_item(
                    documents_root,
                    version,
                    [version_code, "Version", status_display, version_number]
                )

                status_lower = status.lower() if status else ''
                if status_lower in status_colors:
                    version_item.setBackground(2, status_colors[status_lower])
        else:
            # Add info message if no versions found
            no_data_item = SGTreeItem(
                documents_root,
                ["No versions found", "Info", "", ""],
                item_type="info"
            )
            no_data_item.setForeground(0, QtGui.QColor(120, 120, 120))

    def set_scripts_item(self, versions):
        """Build Scripts section with hierarchical folders and versions.

        Supports folder paths like /Script (root level) or /scenes/ARR/Script (nested).
        """
        scripts_root = SGTreeItem(
            self.tree_widget,
            ["Scripts", "Folder", "", ""],
            sg_data={'type': 'folder'},
            item_type="folder"
        )

        self.category_items["Scripts"] = scripts_root
        scripts_root.setExpanded(True)
        font = scripts_root.font(0)
        font.setBold(True)
        scripts_root.setFont(0, font)

        # Filter script versions
        script_versions = [v for v in versions if self._is_script_version(v)]

        # Process each version's folder paths individually
        # A version can appear both at root level AND in nested folders
        versions_for_root = []
        versions_for_nested = []

        for version in script_versions:
            folders_str = version.get('_package_folders', '')
            if folders_str:
                folder_paths = [f.strip() for f in folders_str.split(';') if f.strip()]
                has_root_path = False
                has_nested_path = False
                for fp in folder_paths:
                    if '/scenes/' in fp or '/assets/' in fp:
                        has_nested_path = True
                    else:
                        # Root-level path (e.g., /Script or /Scripts)
                        has_root_path = True

                if has_root_path:
                    versions_for_root.append(version)
                if has_nested_path:
                    versions_for_nested.append(version)
            else:
                # No folder assignment - add to root
                versions_for_root.append(version)

        # Build hierarchical tree for versions in scene/asset folders
        if versions_for_nested or versions_for_root:
            if versions_for_nested:
                path_tree = {}
                for version in versions_for_nested:
                    folders_str = version.get('_package_folders', '')
                    folder_paths = [f.strip() for f in folders_str.split(';') if f.strip()]
                    for folder_path in folder_paths:
                        # Only process paths with scenes or assets
                        if '/scenes/' in folder_path or '/assets/' in folder_path:
                            # Parse the path, skip the Script/Document part at the end
                            parts = [p for p in folder_path.split('/') if p]
                            # Remove the last part if it's Script/Document (category)
                            if parts and parts[-1].lower() in ['script', 'document', 'scripts', 'documents']:
                                parts = parts[:-1]

                            if parts:
                                # Navigate/create the tree structure
                                current_level = path_tree
                                for part in parts:
                                    if part not in current_level:
                                        current_level[part] = {'_versions': [], '_children': {}}
                                    current_level = current_level[part]['_children']

                                # Add version to the deepest level
                                current_level = path_tree
                                for part in parts[:-1]:
                                    current_level = current_level[part]['_children']
                                if parts:
                                    current_level[parts[-1]]['_versions'].append(version)

                self._build_folder_tree(scripts_root, path_tree, "")

            # Add versions with root-level paths directly under Scripts
            for version in versions_for_root:
                version_code = version.get('code', 'Unknown')
                status = version.get('sg_status_list', '')
                status_display = status if status else 'N/A'
                version_number = version_code.split('_')[-1] if '_' in version_code else ""

                version_item = self._create_version_item(
                    scripts_root,
                    version,
                    [version_code, "Version", status_display, version_number]
                )

                status_lower = status.lower() if status else ''
                if status_lower in status_colors:
                    version_item.setBackground(2, status_colors[status_lower])
        else:
            # Add info message if no versions found
            no_data_item = SGTreeItem(
                scripts_root,
                ["No versions found", "Info", "", ""],
                item_type="info"
            )
            no_data_item.setForeground(0, QtGui.QColor(120, 120, 120))

    def set_images_item(self, versions_with_folders, versions_without_folders):
        """Build Images section with hierarchical folders and versions.

        Args:
            versions_with_folders: List of version dicts with '_package_folders' key
            versions_without_folders: List of version dicts without folder assignments
        """
        images_root = SGTreeItem(
            self.tree_widget,
            ["Images", "Folder", "", ""],
            sg_data={'type': 'folder'},
            item_type="folder"
        )
        self.category_items["Images"] = images_root
        images_root.setExpanded(True)
        font = images_root.font(0)
        font.setBold(True)
        images_root.setFont(0, font)

        # Build a tree structure from all paths
        path_tree = {}

        for version in versions_with_folders:
            folders_str = version.get('_package_folders', '')
            if folders_str:
                # Split by ";" for multiple folder paths
                folder_paths = [f.strip() for f in folders_str.split(';') if f.strip()]
                for folder_path in folder_paths:
                    # Parse the path (e.g., '/assets/CRE/Concept Art')
                    parts = [p for p in folder_path.split('/') if p]

                    # Navigate/create the tree structure
                    current_level = path_tree
                    for part in parts:
                        if part not in current_level:
                            current_level[part] = {'_versions': [], '_children': {}}
                        current_level = current_level[part]['_children']

                    # Add version to the deepest level
                    current_level = path_tree
                    for part in parts[:-1]:
                        current_level = current_level[part]['_children']
                    current_level[parts[-1]]['_versions'].append(version)

        # Recursively build the tree items with folder icons
        if path_tree or versions_without_folders:
            if path_tree:
                self._build_folder_tree(images_root, path_tree, "")

            # Add versions with no folder assignment directly under Images
            if versions_without_folders:
                for version in versions_without_folders:
                    version_code = version.get('code', 'Unknown')
                    status = version.get('sg_status_list', '')
                    status_display = status if status else 'N/A'
                    version_number = version_code.split('_')[-1] if '_' in version_code else ""

                    version_item = self._create_version_item(
                        images_root,
                        version,
                        [version_code, "Version", status_display, version_number]
                    )

                    status_lower = status.lower() if status else ''
                    if status_lower in status_colors:
                        version_item.setBackground(2, status_colors[status_lower])
        else:
            no_data_item = SGTreeItem(
                images_root,
                ["No versions found", "Info", "", ""],
                item_type="info"
            )
            no_data_item.setForeground(0, QtGui.QColor(120, 120, 120))

    def set_folders_item(self, versions_with_folders):
        """Build Folders section with versions grouped by hierarchical folder paths.

        Args:
            versions_with_folders: List of version dicts with '_package_folders' key
                                   containing paths like '/assets/CRE/Concept Art'
        """
        folders_root = SGTreeItem(
            self.tree_widget,
            ["Folders", "Folder", "", ""],
            sg_data={'type': 'folder'},
            item_type="folder"
        )
        self.category_items["Folders"] = folders_root
        folders_root.setExpanded(True)
        font = folders_root.font(0)
        font.setBold(True)
        folders_root.setFont(0, font)

        # Build a tree structure from all paths
        # path_tree[path_component] = {'_versions': [], '_children': {}}
        path_tree = {}
        no_folder_versions = []

        for version in versions_with_folders:
            folders_str = version.get('_package_folders', '')
            if folders_str:
                # Split by ";" for multiple folder paths
                folder_paths = [f.strip() for f in folders_str.split(';') if f.strip()]
                for folder_path in folder_paths:
                    # Parse the path (e.g., '/assets/CRE/Concept Art')
                    parts = [p for p in folder_path.split('/') if p]

                    # Navigate/create the tree structure
                    current_level = path_tree
                    for part in parts:
                        if part not in current_level:
                            current_level[part] = {'_versions': [], '_children': {}}
                        current_level = current_level[part]['_children']

                    # Add version to the deepest level
                    # Go back up to add to the last part's versions list
                    current_level = path_tree
                    for part in parts[:-1]:
                        current_level = current_level[part]['_children']
                    current_level[parts[-1]]['_versions'].append(version)
            else:
                no_folder_versions.append(version)

        # Recursively build the tree items with folder icons
        if path_tree:
            self._build_folder_tree(folders_root, path_tree, "")

            # Add versions with no folder assignment
            if no_folder_versions:
                unassigned_item = SGTreeItem(
                    folders_root,
                    ["📁 (Unassigned)", "Folder", "", f"{len(no_folder_versions)}"],
                    sg_data={'type': 'folder', 'folder_path': ''},
                    item_type="folder"
                )
                unassigned_item.setExpanded(False)
                unassigned_item.setForeground(0, QtGui.QColor(120, 120, 120))

                for version in no_folder_versions:
                    version_code = version.get('code', 'Unknown')
                    status = version.get('sg_status_list', '')
                    status_display = status if status else 'N/A'
                    version_number = version_code.split('_')[-1] if '_' in version_code else ""

                    version_item = self._create_version_item(
                        unassigned_item,
                        version,
                        [version_code, "Version", status_display, version_number]
                    )

                    status_lower = status.lower() if status else ''
                    if status_lower in status_colors:
                        version_item.setBackground(2, status_colors[status_lower])
        else:
            # No versions with folders
            no_data_item = SGTreeItem(
                folders_root,
                ["No folder assignments", "Info", "", ""],
                item_type="info"
            )
            no_data_item.setForeground(0, QtGui.QColor(120, 120, 120))

    def _build_folder_tree(self, parent_item, tree_dict, current_path):
        """Recursively build folder tree items from the tree dictionary.

        Args:
            parent_item: Parent SGTreeItem to add children to
            tree_dict: Dictionary with folder structure
            current_path: Current path string for tracking full path
        """
        # Sort folders alphabetically
        for folder_name in sorted(tree_dict.keys()):
            folder_data = tree_dict[folder_name]
            versions = folder_data['_versions']
            children = folder_data['_children']

            # Build full path
            full_path = f"{current_path}/{folder_name}" if current_path else f"/{folder_name}"

            # Count total versions including descendants
            total_versions = len(versions) + self._count_versions_recursive(children)

            # Create folder item with icon
            folder_item = SGTreeItem(
                parent_item,
                [f"📁 {folder_name}", "Folder", "", f"{total_versions}"],
                sg_data={'type': 'folder', 'folder_path': full_path},
                item_type="folder"
            )
            folder_item.setExpanded(False)

            # Add versions at this level
            for version in versions:
                version_code = version.get('code', 'Unknown')
                status = version.get('sg_status_list', '')
                status_display = status if status else 'N/A'
                version_number = version_code.split('_')[-1] if '_' in version_code else ""

                version_item = self._create_version_item(
                    folder_item,
                    version,
                    [version_code, "Version", status_display, version_number]
                )

                status_lower = status.lower() if status else ''
                if status_lower in status_colors:
                    version_item.setBackground(2, status_colors[status_lower])

            # Recursively add child folders
            if children:
                self._build_folder_tree(folder_item, children, full_path)

    def _count_versions_recursive(self, tree_dict):
        """Count all versions in a tree dictionary recursively.

        Args:
            tree_dict: Dictionary with folder structure

        Returns:
            Total count of versions in this tree and all descendants
        """
        total = 0
        for folder_data in tree_dict.values():
            total += len(folder_data['_versions'])
            total += self._count_versions_recursive(folder_data['_children'])
        return total

    def _is_bid_tracker_version(self, version):
        """Determine if a version belongs to Bid Tracker category."""
        sg_version_type = version.get('sg_version_type')

        # If sg_version_type is set, use it
        if sg_version_type:
            # Handle both string and dict formats
            if isinstance(sg_version_type, dict):
                version_type = sg_version_type.get('name', '').lower()
            else:
                version_type = str(sg_version_type).lower()

            return 'bid' in version_type or 'tracker' in version_type

        # Fallback to task/code checking if sg_version_type is not set
        task = version.get('sg_task', {})
        if task:
            task_name = task.get('name', '').lower()
            if 'bid' in task_name or 'tracker' in task_name:
                return True

        code = version.get('code', '').lower()
        if 'bid' in code or 'tracker' in code:
            return True

        return False

    def _is_document_version(self, version):
        """Determine if a version belongs to Documents category (was Script)."""
        sg_version_type = version.get('sg_version_type')

        # If sg_version_type is set, use it
        if sg_version_type:
            if isinstance(sg_version_type, dict):
                version_type = sg_version_type.get('name', '').lower()
            else:
                version_type = str(sg_version_type).lower()

            return 'script' in version_type or 'document' in version_type

        # Fallback to task/code checking
        code = version.get('code', '').lower()
        task = version.get('sg_task', {})
        task_name = task.get('name', '').lower() if task else ''

        return 'script' in code or 'script' in task_name or 'document' in code or 'document' in task_name

    def _is_image_version(self, version):
        """Determine if a version belongs to Images category (combines Concept Art, Storyboard, Reference)."""
        sg_version_type = version.get('sg_version_type')

        # If sg_version_type is set, use it
        if sg_version_type:
            if isinstance(sg_version_type, dict):
                version_type = sg_version_type.get('name', '').lower()
            else:
                version_type = str(sg_version_type).lower()

            # Check for concept, storyboard, reference, art, image, etc.
            return any(keyword in version_type for keyword in [
                'concept', 'art', 'storyboard', 'reference', 'image', 'ref'
            ])

        # Fallback to task/code checking
        code = version.get('code', '').lower()
        task = version.get('sg_task', {})
        task_name = task.get('name', '').lower() if task else ''

        # Check for various image-related keywords
        image_keywords = ['concept', 'art', 'storyboard', 'reference', 'image', 'ref']
        return any(keyword in code or keyword in task_name for keyword in image_keywords)

    def _is_script_version(self, version):
        """Determine if a version belongs to Scripts category."""
        sg_version_type = version.get('sg_version_type')

        if sg_version_type:
            if isinstance(sg_version_type, dict):
                version_type = sg_version_type.get('name', '').lower()
            else:
                version_type = str(sg_version_type).lower()

            # Check for script type only
            return 'script' in version_type

        return False

    def _is_document_version(self, version):
        """Determine if a version belongs to Documents category (Document types, not Scripts)."""
        sg_version_type = version.get('sg_version_type')

        if sg_version_type:
            if isinstance(sg_version_type, dict):
                version_type = sg_version_type.get('name', '').lower()
            else:
                version_type = str(sg_version_type).lower()

            # Check for document types, but NOT script
            if 'script' in version_type:
                return False
            return any(keyword in version_type for keyword in [
                'document', 'doc', 'pdf'
            ])

        return False

    def get_active_versions(self):
        """
        Get list of all version items.

        Returns:
            List of SGTreeItem objects that are versions
        """
        versions = []

        # Iterate through all top-level items (categories)
        for i in range(self.tree_widget.topLevelItemCount()):
            category_item = self.tree_widget.topLevelItem(i)

            # Iterate through children (versions)
            for j in range(category_item.childCount()):
                child = category_item.child(j)

                if isinstance(child, SGTreeItem) and child.get_item_type() == "version":
                    versions.append(child)

        return versions

    def get_active_version_ids(self):
        """
        Get list of Shotgrid IDs for all versions.

        Returns:
            List of version IDs (integers)
        """
        versions = self.get_active_versions()
        return [v.get_sg_id() for v in versions if v.get_sg_id()]

    def get_active_version_data(self):
        """
        Get full Shotgrid data for all versions.

        Returns:
            List of dictionaries containing version data
        """
        versions = self.get_active_versions()
        return [v.get_sg_data() for v in versions]

    def get_package_manifest(self):
        """
        Get a manifest of the package structure with folders and their files.

        Returns:
            Dictionary with the complete package structure:
            {
                "folders": {
                    "/folder/path": {
                        "files": [
                            {
                                "id": 123,
                                "code": "version_code",
                                "name": "file_name",
                                "status": "approved",
                                "type": "Version",
                                "sg_uploaded_movie": {...},
                                "sg_path_to_movie": "...",
                                "sg_path_to_frames": "..."
                            },
                            ...
                        ]
                    },
                    ...
                },
                "root_files": [...],  # Files not in any folder
                "summary": {
                    "total_folders": N,
                    "total_files": N
                }
            }
        """
        manifest = {
            "folders": {},
            "root_files": [],
            "summary": {
                "total_folders": 0,
                "total_files": 0
            }
        }

        def extract_file_info(version_data):
            """Extract relevant file information from version data."""
            return {
                "id": version_data.get("id"),
                "code": version_data.get("code"),
                "name": version_data.get("code", "Unknown"),
                "status": version_data.get("sg_status_list", ""),
                "type": version_data.get("type", "Version"),
                "description": version_data.get("description", ""),
                "sg_uploaded_movie": version_data.get("sg_uploaded_movie"),
                "sg_path_to_movie": version_data.get("sg_path_to_movie"),
                "sg_path_to_frames": version_data.get("sg_path_to_frames"),
                "created_at": version_data.get("created_at"),
                "user": version_data.get("user"),
            }

        def traverse_item(item, current_path=""):
            """Recursively traverse tree items to build manifest."""
            if not isinstance(item, SGTreeItem):
                return

            item_type = item.get_item_type()

            if item_type == "folder":
                # Get folder path from sg_data
                sg_data = item.get_sg_data()
                folder_path = sg_data.get("folder_path", "") if sg_data else ""

                if folder_path:
                    if folder_path not in manifest["folders"]:
                        manifest["folders"][folder_path] = {"files": []}
                    current_path = folder_path

            elif item_type == "version":
                # Add version to the appropriate folder or root
                version_data = item.get_sg_data()
                if version_data:
                    file_info = extract_file_info(version_data)

                    # Check if version has folder assignment
                    folders_str = version_data.get("_package_folders", "")
                    if folders_str:
                        folder_paths = [f.strip() for f in folders_str.split(";") if f.strip()]
                        for folder_path in folder_paths:
                            if folder_path not in manifest["folders"]:
                                manifest["folders"][folder_path] = {"files": []}
                            # Avoid duplicate entries
                            existing_ids = [f["id"] for f in manifest["folders"][folder_path]["files"]]
                            if file_info["id"] not in existing_ids:
                                manifest["folders"][folder_path]["files"].append(file_info)
                    elif current_path and current_path in manifest["folders"]:
                        # Add to current folder path
                        existing_ids = [f["id"] for f in manifest["folders"][current_path]["files"]]
                        if file_info["id"] not in existing_ids:
                            manifest["folders"][current_path]["files"].append(file_info)
                    else:
                        # Root-level version
                        existing_ids = [f["id"] for f in manifest["root_files"]]
                        if file_info["id"] not in existing_ids:
                            manifest["root_files"].append(file_info)

            # Traverse children
            for i in range(item.childCount()):
                child = item.child(i)
                traverse_item(child, current_path)

        # Traverse all top-level items
        for i in range(self.tree_widget.topLevelItemCount()):
            top_item = self.tree_widget.topLevelItem(i)
            traverse_item(top_item)

        # Calculate summary
        manifest["summary"]["total_folders"] = len(manifest["folders"])
        manifest["summary"]["total_files"] = (
            sum(len(folder["files"]) for folder in manifest["folders"].values())
            + len(manifest["root_files"])
        )

        return manifest

    def get_selected_version_data(self):
        """
        Get Shotgrid data from currently selected item.

        Returns:
            Shotgrid data dictionary or None
        """
        selected_items = self.tree_widget.selectedItems()
        if not selected_items:
            return None

        item = selected_items[0]
        if isinstance(item, SGTreeItem):
            return item.get_sg_data()

        return None

    def show_tree_context_menu(self, position):
        """Show context menu for tree items."""
        item = self.tree_widget.itemAt(position)
        if not item:
            return

        menu = QtWidgets.QMenu()

        # Check if it's an SGTreeItem
        if isinstance(item, SGTreeItem):
            item_type = item.get_item_type()

            if item_type == "version":
                # Check if this is a Bid Tracker version
                if self._is_bid_tracker_version(item.get_sg_data()) and self.current_package_id:
                    select_version_action = menu.addAction("Select Version")
                    select_version_action.triggered.connect(lambda: self._select_bid_tracker_version())

                    remove_action = menu.addAction("Remove from Package")
                    remove_action.triggered.connect(lambda: self._remove_bid_tracker_from_package(item))

                    menu.addSeparator()
                # Check if this is an image version with folder assignment
                elif self._is_image_version(item.get_sg_data()) and self.current_package_id:
                    delete_action = menu.addAction("Delete from Package")
                    delete_action.triggered.connect(lambda: self._delete_version_from_package(item))

                    menu.addSeparator()
                # Check if this is a script or document version
                elif (self._is_script_version(item.get_sg_data()) or self._is_document_version(item.get_sg_data())) and self.current_package_id:
                    delete_action = menu.addAction("Remove from Package")
                    delete_action.triggered.connect(lambda: self._delete_document_from_package(item))

                    menu.addSeparator()

                view_action = menu.addAction("View Details")
                view_action.triggered.connect(lambda: self._show_version_details(item))

                download_action = menu.addAction("Download Version")
                download_action.triggered.connect(lambda: self._download_version(item))

                menu.addSeparator()

                info_action = menu.addAction("Show SG Data")
                info_action.triggered.connect(lambda: self._show_sg_data(item))

            elif item_type == "entity":
                expand_action = menu.addAction("Expand All")
                expand_action.triggered.connect(lambda: item.setExpanded(True))

            elif item_type == "info":
                # Check if this is the "No Bid Tracker attached" item
                item_text = item.text(0)
                if item_text == "No Bid Tracker attached" and self.current_package_id:
                    select_version_action = menu.addAction("Select Version")
                    select_version_action.triggered.connect(lambda: self._select_bid_tracker_version())

            else:  # folder
                expand_action = menu.addAction("Expand All")
                expand_action.triggered.connect(lambda: self._expand_all(item))

                collapse_action = menu.addAction("Collapse All")
                collapse_action.triggered.connect(lambda: self._collapse_all(item))

        menu.exec_(self.tree_widget.mapToGlobal(position))

    def _show_version_details(self, item):
        """Show detailed version information."""
        if not isinstance(item, SGTreeItem):
            return

        version_info = item.get_version_info()
        if version_info:
            details = f"Version: {version_info['code']}\n"
            details += f"ID: {version_info['id']}\n"
            details += f"Status: {version_info['status']}\n"

            entity = version_info.get('entity', {})
            if entity:
                details += f"Entity: {entity.get('name', 'N/A')}\n"

            task = version_info.get('task', {})
            if task:
                details += f"Task: {task.get('name', 'N/A')}\n"

            user = version_info.get('user', {})
            if user:
                details += f"User: {user.get('name', 'N/A')}\n"

            if version_info.get('description'):
                details += f"\nDescription:\n{version_info['description']}\n"

            QtWidgets.QMessageBox.information(self, "Version Details", details)

    def _download_version(self, item):
        """Download version movie."""
        if not isinstance(item, SGTreeItem):
            return

        version_id = item.get_sg_id()
        if not version_id:
            return

        from PySide6.QtWidgets import QFileDialog

        download_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Download Directory",
            ""
        )

        if download_dir:
            try:
                path = self.sg_session.download_version_movie(version_id, download_dir)
                if path:
                    QtWidgets.QMessageBox.information(
                        self,
                        "Download Complete",
                        f"Downloaded to:\n{path}"
                    )
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Download Failed",
                    f"Failed to download: {str(e)}"
                )

    def _show_sg_data(self, item):
        """Show raw Shotgrid data."""
        if not isinstance(item, SGTreeItem):
            return

        sg_data = item.get_sg_data()

        from pprint import pformat
        data_str = pformat(sg_data, indent=2, width=80)

        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Shotgrid Data")
        dialog.resize(600, 400)

        layout = QtWidgets.QVBoxLayout(dialog)

        text_edit = QtWidgets.QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(data_str)
        text_edit.setFont(QtGui.QFont("Courier", 9))
        layout.addWidget(text_edit)

        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)

        dialog.exec_()

    def _select_bid_tracker_version(self):
        """Show dialog to select a Bid Tracker version for the current package."""
        if not self.current_package_id or not self.sg_session:
            QtWidgets.QMessageBox.warning(
                self,
                "No Package Selected",
                "No package is currently selected."
            )
            return

        try:
            # Get project and RFQ info for querying available versions
            # Walk up the widget hierarchy to find the parent app
            parent_app = None
            parent_widget = self.parent()

            # First check if the immediate parent has a parent_app attribute (e.g., PackagesTab)
            if parent_widget and hasattr(parent_widget, 'parent_app') and parent_widget.parent_app is not None:
                parent_app = parent_widget.parent_app
            else:
                # Otherwise walk up the hierarchy looking for the combo boxes
                temp_parent = parent_widget
                depth = 0
                while temp_parent and depth < 10:  # Limit depth to avoid infinite loop
                    # Check if this widget has the required attributes (sg_project_combo and rfq_combo)
                    if hasattr(temp_parent, 'sg_project_combo') and hasattr(temp_parent, 'rfq_combo'):
                        parent_app = temp_parent
                        break
                    temp_parent = temp_parent.parent()
                    depth += 1

            if not parent_app:
                logger.error("Could not find parent app with sg_project_combo and rfq_combo")
                QtWidgets.QMessageBox.warning(
                    self,
                    "Error",
                    "Could not find parent application. Please try again."
                )
                return

            # Get project ID
            current_project_index = parent_app.sg_project_combo.currentIndex()
            sg_project = parent_app.sg_project_combo.itemData(current_project_index)
            project_id = sg_project.get("id") if sg_project else None

            if not project_id:
                QtWidgets.QMessageBox.warning(
                    self,
                    "No Project Selected",
                    "No project is currently selected."
                )
                return

            # Get all available Bid Tracker versions for this project (not filtered by RFQ)
            all_versions = self.sg_session.get_all_bid_tracker_versions_for_project(
                project_id=project_id,
                rfq_code=None  # Don't filter by RFQ - show all versions for the project
            )

            if not all_versions:
                QtWidgets.QMessageBox.information(
                    self,
                    "No Versions Available",
                    "No Bid Tracker versions found for this project."
                )
                return

            # Get currently linked versions for this package
            package_versions = self.sg_session.get_package_versions(
                self.current_package_id,
                fields=["id", "code", "sg_version_type"]
            )

            # Find the current Bid Tracker version (if any)
            current_version_id = None
            for version in package_versions:
                if self._is_bid_tracker_version(version):
                    current_version_id = version.get('id')
                    break

            # Show dialog
            dialog = BidTrackerVersionDialog(
                versions=all_versions,
                current_version_id=current_version_id,
                parent=self
            )

            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                selected_version_id = dialog.get_selected_version_id()

                if selected_version_id and selected_version_id != current_version_id:
                    # Unlink the old version if there is one
                    if current_version_id:
                        self.sg_session.unlink_version_from_package(
                            current_version_id,
                            self.current_package_id
                        )

                    # Link the new version
                    self.sg_session.link_version_to_package(
                        selected_version_id,
                        self.current_package_id
                    )

                    # Reload the tree to show the new version
                    self.load_package_versions(self.current_package_id)

                    QtWidgets.QMessageBox.information(
                        self,
                        "Version Updated",
                        "Bid Tracker version has been updated successfully."
                    )

        except Exception as e:
            logger.error(f"Error selecting Bid Tracker version: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to select version: {str(e)}"
            )

    def _remove_bid_tracker_from_package(self, item):
        """Remove the Bid Tracker version from the package (but don't delete from ShotGrid)."""
        if not isinstance(item, SGTreeItem) or not self.current_package_id:
            return

        version_id = item.get_sg_id()
        version_code = item.get_entity_name()

        if not version_id:
            return

        # Confirm the removal
        reply = QtWidgets.QMessageBox.question(
            self,
            "Remove Bid Tracker",
            f"Remove '{version_code}' from this package?\n\n"
            f"The version will not be deleted from ShotGrid,\n"
            f"only unlinked from this package.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            try:
                # Unlink the version from the package
                self.sg_session.unlink_version_from_package(
                    version_id,
                    self.current_package_id
                )

                # Reload the tree to show "No Bid Tracker attached"
                self.load_package_versions(self.current_package_id)

                QtWidgets.QMessageBox.information(
                    self,
                    "Bid Tracker Removed",
                    f"'{version_code}' has been removed from the package."
                )

            except Exception as e:
                logger.error(f"Error removing Bid Tracker: {e}", exc_info=True)
                QtWidgets.QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to remove Bid Tracker: {str(e)}"
                )

    def _delete_version_from_package(self, item):
        """Delete a version from the package by removing its folder reference.

        If the PackageItem's sg_package_folders becomes empty, delete the PackageItem.
        """
        if not isinstance(item, SGTreeItem) or not self.current_package_id:
            return

        version_id = item.get_sg_id()
        version_code = item.get_entity_name()

        if not version_id:
            return

        # Build the folder path by walking up the tree
        folder_path = self._get_folder_path_from_item(item)

        if not folder_path:
            logger.warning(f"Could not determine folder path for version {version_id}")
            return

        # Confirm the deletion
        reply = QtWidgets.QMessageBox.question(
            self,
            "Delete from Package",
            f"Delete '{version_code}' from folder '{folder_path}'?\n\n"
            f"This will remove the folder assignment from ShotGrid.\n"
            f"If this is the last folder for this version, the PackageItem will be deleted.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            try:
                # Remove the folder reference from the PackageItem
                self.sg_session.remove_folder_reference_from_package(
                    version_id,
                    self.current_package_id,
                    folder_path
                )

                # Reload the tree
                self.load_package_versions(self.current_package_id)

                QtWidgets.QMessageBox.information(
                    self,
                    "Version Deleted",
                    f"'{version_code}' has been removed from '{folder_path}'."
                )

            except Exception as e:
                logger.error(f"Error deleting version from package: {e}", exc_info=True)
                QtWidgets.QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to delete version: {str(e)}"
                )

    def _get_folder_path_from_item(self, item):
        """Build the folder path by walking up the tree from a version item.

        Args:
            item: SGTreeItem representing a version

        Returns:
            Full folder path (e.g., '/assets/CRE/Concept Art') or None
        """
        path_parts = []
        current = item.parent()

        # Walk up the tree until we reach the root Images folder
        while current:
            sg_data = current.get_sg_data() if isinstance(current, SGTreeItem) else None
            if sg_data and sg_data.get('type') == 'folder':
                folder_path = sg_data.get('folder_path')
                if folder_path:
                    # We found a folder with a path, use it directly
                    return folder_path

                # Otherwise, collect the folder name
                folder_name = current.text(0).replace('📁 ', '').strip()
                # Stop if we've reached the Images root
                if folder_name == "Images":
                    break
                path_parts.insert(0, folder_name)

            current = current.parent() if hasattr(current, 'parent') else None

        # Build the path
        if path_parts:
            return '/' + '/'.join(path_parts)

        return None

    def _get_document_folder_path_from_item(self, item):
        """Build the folder path by walking up the tree from a document/script version item.

        Args:
            item: SGTreeItem representing a version

        Returns:
            Full folder path (e.g., '/Script', '/Document', '/scenes/ARR/Script') or None
        """
        # Determine if this is a script or document to know the suffix
        sg_data = item.get_sg_data() if isinstance(item, SGTreeItem) else None
        is_script = self._is_script_version(sg_data) if sg_data else False
        category_suffix = "Script" if is_script else "Document"

        path_parts = []
        current = item.parent()
        found_root = False

        # Walk up the tree until we reach the root Scripts or Documents folder
        while current:
            item_sg_data = current.get_sg_data() if isinstance(current, SGTreeItem) else None
            if item_sg_data and item_sg_data.get('type') == 'folder':
                folder_path = item_sg_data.get('folder_path')

                # Check folder name to see if we reached the root
                folder_name = current.text(0).replace('📁 ', '').strip()

                if folder_name in ["Scripts", "Documents"]:
                    # Reached the root folder
                    found_root = True
                    if path_parts:
                        # We have nested folders (e.g., scenes/ARR), append category suffix
                        return '/' + '/'.join(path_parts) + '/' + category_suffix
                    else:
                        # Direct child of root, return just /Script or /Document
                        return '/' + category_suffix

                if folder_path:
                    # We found a folder with a stored path (like /scenes/ARR)
                    # Append the category suffix to get the full path
                    return folder_path + '/' + category_suffix

                # Collect folder name for path building
                path_parts.insert(0, folder_name)

            current = current.parent() if hasattr(current, 'parent') else None

        # If we collected path parts but didn't find root, build the path anyway
        if path_parts:
            return '/' + '/'.join(path_parts) + '/' + category_suffix

        # Fallback to just the category
        return '/' + category_suffix

    def _delete_document_from_package(self, item):
        """Delete a document/script from the package by removing its folder reference.

        Updates UI immediately for fluid interaction, then performs SG operation
        in background. Reverts UI on failure.
        """
        if not isinstance(item, SGTreeItem) or not self.current_package_id:
            return

        version_id = item.get_sg_id()
        version_code = item.get_entity_name()

        if not version_id:
            return

        # Determine if this is a script or document
        sg_data = item.get_sg_data()
        is_script = self._is_script_version(sg_data)
        item_type = "script" if is_script else "document"

        # Build the folder path by walking up the tree
        folder_path = self._get_document_folder_path_from_item(item)

        if not folder_path:
            # Default to root folder based on type
            folder_path = "/Script" if is_script else "/Document"

        # Confirm the deletion
        reply = QtWidgets.QMessageBox.question(
            self,
            "Remove from Package",
            f"Remove '{version_code}' from '{folder_path}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            # Store item data for potential restoration
            parent_item = item.parent()
            item_index = parent_item.indexOfChild(item) if parent_item else -1
            item_columns = [item.text(i) for i in range(item.columnCount())]
            item_sg_data = item.get_sg_data()
            item_type_stored = item.get_item_type()

            # Update UI immediately - remove item from tree
            if parent_item:
                parent_item.removeChild(item)

            # Update folder counts and remove empty folders
            self._update_folder_counts_and_cleanup(parent_item)

            # Emit signal to update document folder pane immediately
            self.documentRemovedFromPackage.emit(version_id, folder_path)

            # Run SG operation in background thread
            self._run_sg_remove_operation(
                version_id, folder_path, version_code, item_type,
                parent_item, item_index, item_columns, item_sg_data, item_type_stored
            )

    def _update_folder_counts_and_cleanup(self, folder_item):
        """Update folder counts after removing an item and remove empty folders.

        Args:
            folder_item: The folder item to update
        """
        if not folder_item or not isinstance(folder_item, SGTreeItem):
            return

        # Walk up the tree and update counts
        current = folder_item
        folders_to_remove = []

        while current and isinstance(current, SGTreeItem):
            sg_data = current.get_sg_data() if isinstance(current, SGTreeItem) else None

            if sg_data and sg_data.get('type') == 'folder':
                folder_name = current.text(0).replace('📁 ', '').strip()

                # Skip root folders (Scripts, Documents, Images, Bid Tracker)
                if folder_name in ["Scripts", "Documents", "Images", "Bid Tracker"]:
                    break

                # Count remaining children (versions and non-empty folders)
                child_count = self._count_folder_children(current)

                # Update the count column
                current.setText(3, str(child_count))

                # Mark for removal if empty
                if child_count == 0:
                    folders_to_remove.append(current)

            current = current.parent() if hasattr(current, 'parent') else None

        # Remove empty folders (from deepest to shallowest)
        for folder in folders_to_remove:
            parent = folder.parent()
            if parent:
                parent.removeChild(folder)
                # Update parent's count after removal
                if isinstance(parent, SGTreeItem):
                    new_count = self._count_folder_children(parent)
                    parent.setText(3, str(new_count))

    def _count_folder_children(self, folder_item):
        """Count the total number of version items in a folder and its subfolders.

        Args:
            folder_item: The folder item to count children for

        Returns:
            Total count of version items
        """
        count = 0
        for i in range(folder_item.childCount()):
            child = folder_item.child(i)
            if isinstance(child, SGTreeItem):
                if child.get_item_type() == "version":
                    count += 1
                elif child.get_item_type() == "folder":
                    count += self._count_folder_children(child)
        return count

    def _run_sg_remove_operation(self, version_id, folder_path, version_code, item_type,
                                  parent_item, item_index, item_columns, item_sg_data, item_type_stored):
        """Run the ShotGrid remove operation in a background thread.

        Args:
            version_id: ID of the version to remove
            folder_path: Folder path to remove from
            version_code: Display name of the version
            item_type: Type string for display ("script" or "document")
            parent_item: Parent tree item for restoration on failure
            item_index: Original index of the item in parent
            item_columns: Column values for restoration
            item_sg_data: SG data for restoration
            item_type_stored: Item type for restoration
        """
        # Create thread and worker
        self._sg_thread = QtCore.QThread()
        self._sg_worker = SGWorker(
            self.sg_session,
            "remove_folder_reference_from_package",
            version_id,
            self.current_package_id,
            folder_path
        )
        self._sg_worker.moveToThread(self._sg_thread)

        # Store data for the callback
        self._pending_remove_data = {
            'version_id': version_id,
            'folder_path': folder_path,
            'version_code': version_code,
            'item_type': item_type,
            'parent_item': parent_item,
            'item_index': item_index,
            'item_columns': item_columns,
            'item_sg_data': item_sg_data,
            'item_type_stored': item_type_stored
        }

        # Connect signals
        self._sg_thread.started.connect(self._sg_worker.run)
        self._sg_worker.finished.connect(self._on_sg_remove_finished)
        self._sg_worker.finished.connect(self._sg_thread.quit)
        self._sg_worker.finished.connect(self._sg_worker.deleteLater)
        self._sg_thread.finished.connect(self._sg_thread.deleteLater)

        # Start the thread
        self._sg_thread.start()

    def _on_sg_remove_finished(self, success, error_message):
        """Handle completion of the background SG remove operation.

        Args:
            success: Whether the operation succeeded
            error_message: Error message if failed
        """
        data = self._pending_remove_data
        if not data:
            return

        if success:
            logger.info(f"Successfully removed {data['item_type']} '{data['version_code']}' from '{data['folder_path']}'")
        else:
            # Revert UI - restore the item
            logger.warning(f"Failed to remove {data['item_type']}, reverting UI: {error_message}")

            parent_item = data['parent_item']
            if parent_item and isinstance(parent_item, SGTreeItem):
                # Re-create the item
                restored_item = SGTreeItem(
                    parent_item,
                    data['item_columns'],
                    sg_data=data['item_sg_data'],
                    item_type=data['item_type_stored']
                )

                # Try to restore at original position
                if data['item_index'] >= 0 and data['item_index'] < parent_item.childCount():
                    # Move to original position by removing and re-inserting
                    parent_item.removeChild(restored_item)
                    parent_item.insertChild(data['item_index'], restored_item)

                # Update folder counts
                self._update_folder_counts_after_restore(parent_item)

            # Emit signal to restore document folder pane
            self.documentRestoredToPackage.emit(data['version_id'], data['folder_path'])

            # Show error message
            QtWidgets.QMessageBox.warning(
                self,
                "Operation Failed",
                f"Failed to remove '{data['version_code']}' from ShotGrid.\n"
                f"The item has been restored in the tree.\n\n"
                f"Error: {error_message}"
            )

        # Clear pending data
        self._pending_remove_data = None

    def _update_folder_counts_after_restore(self, folder_item):
        """Update folder counts after restoring an item.

        Args:
            folder_item: The folder item to update
        """
        if not folder_item or not isinstance(folder_item, SGTreeItem):
            return

        # Walk up the tree and update counts
        current = folder_item
        while current and isinstance(current, SGTreeItem):
            sg_data = current.get_sg_data() if isinstance(current, SGTreeItem) else None

            if sg_data and sg_data.get('type') == 'folder':
                folder_name = current.text(0).replace('📁 ', '').strip()

                # Skip root folders
                if folder_name in ["Scripts", "Documents", "Images", "Bid Tracker"]:
                    break

                # Update the count
                child_count = self._count_folder_children(current)
                current.setText(3, str(child_count))

            current = current.parent() if hasattr(current, 'parent') else None

    def _expand_all(self, item):
        """Recursively expand all children."""
        item.setExpanded(True)
        for i in range(item.childCount()):
            self._expand_all(item.child(i))

    def _collapse_all(self, item):
        """Recursively collapse all children."""
        item.setExpanded(False)
        for i in range(item.childCount()):
            self._collapse_all(item.child(i))