from PySide6 import QtWidgets, QtCore, QtGui
import logging

# Try relative import first, fall back to creating a logger
try:
    from .logger import logger
except (ImportError, ValueError, SystemError):
    logger = logging.getLogger("FFPackageManager")


class TreeCheckBoxDelegate(QtWidgets.QStyledItemDelegate):
    """Custom delegate for rendering checkboxes in tree widget with DPI scaling."""

    def __init__(self, parent=None):
        """Initialize the delegate."""
        super().__init__(parent)
        try:
            from .settings import AppSettings
        except ImportError:
            from settings import AppSettings
        self.app_settings = AppSettings()

    def paint(self, painter, option, index):
        """Paint the checkbox with custom styling and DPI scaling."""
        # Only handle checkbox column (column 0) with checkable items
        if index.column() == 0:
            flags = index.flags()
            if flags & QtCore.Qt.ItemIsUserCheckable:
                painter.save()

                # Get DPI scale
                dpi_scale = self.app_settings.get_dpi_scale()
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


# Status colors (adjusted for dark theme)
status_colors = {
    "ip": QtGui.QColor(255, 180, 60),  # In Progress - Orange
    "wtg": QtGui.QColor(120, 120, 120),  # Waiting - Gray
    "rev": QtGui.QColor(255, 120, 120),  # Review - Red
    "apr": QtGui.QColor(100, 200, 100),  # Approved - Green
}


class PackageTreeView(QtWidgets.QWidget):
    """Widget for displaying package data in a tree view."""

    def __init__(self, parent=None):
        """Initialize the PackageTreeView widget."""
        super().__init__(parent)

        # Initialize selected RFQ storage
        self.selected_rfq = None
        self.sg_session = None

        # Store root category items for show/hide functionality
        self.category_items = {}

        # Store visibility preferences (persists across tree reloads)
        self.category_visibility_prefs = {}

        # Define canonical order of categories
        self.category_order = ["VFX Breakdown", "Script", "Concept Art", "Storyboard"]

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
        logger.info("create_panel() started")

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
        refresh_btn.clicked.connect(self.load_tree_data)
        header_layout.addWidget(refresh_btn)

        layout.addLayout(header_layout)

        # Tree widget - Added "Active" column at the beginning
        self.tree_widget = QtWidgets.QTreeWidget()
        self.tree_widget.setHeaderLabels(["Active", "Name", "Type", "Status", "Version"])
        self.tree_widget.setColumnWidth(0, 60)  # Active checkbox column
        self.tree_widget.setColumnWidth(1, 250)  # Name
        self.tree_widget.setColumnWidth(2, 80)  # Type
        self.tree_widget.setColumnWidth(3, 80)  # Status
        self.tree_widget.setAlternatingRowColors(True)
        self.tree_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

        # Set custom delegate for checkbox column to support DPI scaling
        checkbox_delegate = TreeCheckBoxDelegate(self.tree_widget)
        self.tree_widget.setItemDelegateForColumn(0, checkbox_delegate)

        # Enable tree item animations and proper branch indicators
        self.tree_widget.setAnimated(True)
        self.tree_widget.setIndentation(20)
        self.tree_widget.setRootIsDecorated(True)  # Show expand/collapse indicators

        # Enable context menu
        self.tree_widget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self.show_tree_context_menu)

        # Connect to handle checkbox changes
        self.tree_widget.itemChanged.connect(self._on_item_changed)

        # Connect to handle expand/collapse for arrow updates
        self.tree_widget.itemExpanded.connect(self._on_item_expanded)
        self.tree_widget.itemCollapsed.connect(self._on_item_collapsed)

        layout.addWidget(self.tree_widget)

        logger.info("create_panel() completed")
        return panel

    def _on_item_changed(self, item, column):
        """Handle item changes (checkbox toggles)."""
        # Only handle column 0 (checkbox column) and only for version items
        if column == 0 and isinstance(item, SGTreeItem) and item.get_item_type() == "version":
            is_checked = item.checkState(0) == QtCore.Qt.Checked
            self._set_version_active_state(item, is_checked)
            logger.info(f"Version '{item.get_entity_name()}' active state changed to: {is_checked}")

    def _on_item_expanded(self, item):
        """Update arrow when item is expanded."""
        if isinstance(item, SGTreeItem) and item.get_item_type() == "folder":
            text = item.text(1)
            if text.startswith("►"):
                item.setText(1, text.replace("►", "▼", 1))

    def _on_item_collapsed(self, item):
        """Update arrow when item is collapsed."""
        if isinstance(item, SGTreeItem) and item.get_item_type() == "folder":
            text = item.text(1)
            if text.startswith("▼"):
                item.setText(1, text.replace("▼", "►", 1))

    def _set_version_active_state(self, item, is_active):
        """Set the visual state of a version item based on its active status."""
        if is_active:
            # Active state - normal colors (light text for dark theme)
            for col in range(self.tree_widget.columnCount()):
                item.setForeground(col, QtGui.QColor(224, 224, 224))  # Light gray text
                # Restore original font
                font = item.font(col)
                font.setStrikeOut(False)
                item.setFont(col, font)
        else:
            # Inactive state - grayed out (darker gray for dark theme)
            gray_color = QtGui.QColor(100, 100, 100)
            for col in range(self.tree_widget.columnCount()):
                item.setForeground(col, gray_color)
                # Add strikethrough to make it more obvious
                font = item.font(col)
                font.setStrikeOut(True)
                item.setFont(col, font)

    def _create_version_item(self, parent, version, column_data):
        """Helper to create a version item with checkbox."""
        version_item = SGTreeItem(
            parent,
            [""] + column_data,  # Add empty string for checkbox column
            sg_data=version,
            item_type="version"
        )

        # Make the item checkable in the first column
        version_item.setFlags(version_item.flags() | QtCore.Qt.ItemIsUserCheckable)
        version_item.setCheckState(0, QtCore.Qt.Checked)  # Default to checked/active

        return version_item

    def set_rfq(self, rfq_data):
        """Set the RFQ data and reload the tree.

        Args:
            rfq_data (dict): The RFQ entity data from Shotgrid
        """
        logger.info(f"set_rfq() called with RFQ: {rfq_data.get('code', 'N/A') if rfq_data else None}")
        self.selected_rfq = rfq_data

        # Just load the tree - visibility will be applied from the app
        self.load_tree_data()

    def clear(self):
        """Clear the tree view."""
        logger.info("clear() called")
        self.tree_widget.clear()
        self.selected_rfq = None

    def refresh(self):
        """Refresh the tree with current RFQ data."""
        logger.info("refresh() called")
        self.load_tree_data()

    def load_tree_data(self):
        """Load version tree with data from selected RFQ."""
        logger.info("load_tree_data() started")

        self.tree_widget.clear()
        self.category_items.clear()

        # Check if we have a selected RFQ
        if not self.selected_rfq:
            logger.info("No RFQ selected - showing empty tree")
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

        logger.info(f"Found {len(versions)} versions linked to RFQ ID {rfq_id}")

        # Build the tree with actual version data
        self.set_vfx_breakdown_item(versions)
        self.set_script_item(versions)
        self.set_concept_art_item(versions)
        self.set_storyboard_item(versions)

        # Apply stored visibility preferences
        logger.info(f"Applying visibility preferences: {self.category_visibility_prefs}")
        for category_name, visible in self.category_visibility_prefs.items():
            if category_name in self.category_items:
                self.category_items[category_name].setHidden(not visible)
                logger.info(f"Applied pref: '{category_name}' = {visible}")

        logger.info("load_tree_data() completed with RFQ data")

    def set_category_visibility(self, category_name, visible):
        """
        Show or hide a category in the tree.

        Args:
            category_name: Name of the category (e.g., "VFX Breakdown", "Script")
            visible: True to show, False to hide
        """
        # Store the preference
        self.category_visibility_prefs[category_name] = visible

        logger.info(f"set_category_visibility: '{category_name}' = {visible} (type: {type(visible)})")

        if category_name not in self.category_items:
            logger.info(f"Category '{category_name}' not in tree yet, saved preference")
            return

        item = self.category_items[category_name]

        # Remove the item from the tree if it's currently there
        index = self.tree_widget.indexOfTopLevelItem(item)
        logger.info(f"Current index of '{category_name}': {index}")

        if index >= 0:
            self.tree_widget.takeTopLevelItem(index)
            logger.info(f"Removed '{category_name}' from tree at index {index}")
        else:
            logger.info(f"'{category_name}' was not in tree (index={index})")

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
                        logger.info(
                            f"  Category '{cat}' is visible at index {cat_index}, incrementing insert_index to {insert_index}")

            logger.info(f"Inserting '{category_name}' at calculated index {insert_index}")
            self.tree_widget.insertTopLevelItem(insert_index, item)
            item.setHidden(False)

            # Verify insertion
            new_index = self.tree_widget.indexOfTopLevelItem(item)
            logger.info(
                f"Successfully inserted '{category_name}' - new index: {new_index}, isHidden: {item.isHidden()}")
        else:
            logger.info(f"'{category_name}' removed and will stay hidden")

    def apply_visibility_states(self, visibility_states):
        """
        Apply visibility states to categories after tree is loaded.

        Args:
            visibility_states: Dictionary mapping category names to visibility (bool)
        """
        for category_name, visible in visibility_states.items():
            self.set_category_visibility(category_name, visible)

    def set_vfx_breakdown_item(self, versions):
        """Build VFX Breakdown section with VFX Breakdown entity (no versions underneath)."""
        # Get VFX Breakdown from the RFQ
        vfx_breakdown = self.selected_rfq.get('sg_vfx_breakdown')

        # Create root folder with arrow
        vfx_breakdown_root = SGTreeItem(
            self.tree_widget,
            ["", "VFX Breakdown", "Folder", "", ""],
            sg_data={'type': 'folder'},
            item_type="folder"
        )

        self.category_items["VFX Breakdown"] = vfx_breakdown_root
        vfx_breakdown_root.setExpanded(True)
        font = vfx_breakdown_root.font(1)
        font.setBold(True)
        vfx_breakdown_root.setFont(1, font)

        # Add VFX Breakdown entity if it exists (no versions underneath)
        if vfx_breakdown:
            logger.info(f"VFX Breakdown field: {vfx_breakdown}")

            # Handle if it's a list or a single entity
            breakdown_entities = vfx_breakdown if isinstance(vfx_breakdown, list) else [vfx_breakdown]

            for breakdown in breakdown_entities:
                if isinstance(breakdown, dict):
                    breakdown_name = breakdown.get('name', 'Unknown VFX Breakdown')
                    breakdown_id = breakdown.get('id', 'N/A')

                    # Create VFX Breakdown entity item (no children)
                    breakdown_item = SGTreeItem(
                        vfx_breakdown_root,
                        ["", breakdown_name, "VFX Breakdown", "", f"ID: {breakdown_id}"],
                        sg_data=breakdown,
                        item_type="entity"
                    )
        else:
            # No VFX Breakdown entity in RFQ
            no_data_item = SGTreeItem(
                vfx_breakdown_root,
                ["", "No VFX Breakdown linked", "Info", "", ""],
                item_type="info"
            )
            no_data_item.setForeground(1, QtGui.QColor(120, 120, 120))

    def set_script_item(self, versions):
        """Build Script section with real version data."""
        script_root = SGTreeItem(
            self.tree_widget,
            ["", "Script", "Folder", "", ""],
            sg_data={'type': 'folder'},
            item_type="folder"
        )

        self.category_items["Script"] = script_root
        script_root.setExpanded(True)
        font = script_root.font(1)
        font.setBold(True)
        script_root.setFont(1, font)

        # Filter script versions
        script_versions = [v for v in versions if self._is_script_version(v)]

        if script_versions:
            for version in script_versions:
                version_code = version.get('code', 'Unknown')
                status = version.get('sg_status_list', '')
                status_display = status if status else 'N/A'
                version_number = version_code.split('_')[-1] if '_' in version_code else ""

                # Use helper to create version item with checkbox
                version_item = self._create_version_item(
                    script_root,
                    version,
                    [version_code, "Version", status_display, version_number]
                )

                # Set status color if it matches our color scheme (check lowercase)
                status_lower = status.lower() if status else ''
                if status_lower in status_colors:
                    version_item.setBackground(3, status_colors[status_lower])
        else:
            # Add info message if no versions found
            no_data_item = SGTreeItem(
                script_root,
                ["", "No versions found", "Info", "", ""],
                item_type="info"
            )
            no_data_item.setForeground(1, QtGui.QColor(120, 120, 120))

    def set_concept_art_item(self, versions):
        """Build Concept Art section with real version data."""
        concept_root = SGTreeItem(
            self.tree_widget,
            ["", "Concept Art", "Folder", "", ""],
            sg_data={'type': 'folder'},
            item_type="folder"
        )
        self.category_items["Concept Art"] = concept_root
        concept_root.setExpanded(True)
        font = concept_root.font(1)
        font.setBold(True)
        concept_root.setFont(1, font)

        # Filter concept art versions
        concept_versions = [v for v in versions if self._is_concept_art_version(v)]

        if concept_versions:
            for version in concept_versions:
                version_code = version.get('code', 'Unknown')
                status = version.get('sg_status_list', '')
                status_display = status if status else 'N/A'
                version_number = version_code.split('_')[-1] if '_' in version_code else ""

                version_item = self._create_version_item(
                    concept_root,
                    version,
                    [version_code, "Version", status_display, version_number]
                )

                status_lower = status.lower() if status else ''
                if status_lower in status_colors:
                    version_item.setBackground(3, status_colors[status_lower])
        else:
            no_data_item = SGTreeItem(
                concept_root,
                ["", "No versions found", "Info", "", ""],
                item_type="info"
            )
            no_data_item.setForeground(1, QtGui.QColor(120, 120, 120))

    def set_storyboard_item(self, versions):
        """Build Storyboard section with real version data."""
        storyboard_root = SGTreeItem(
            self.tree_widget,
            ["", "Storyboard", "Folder", "", ""],
            sg_data={'type': 'folder'},
            item_type="folder"
        )
        self.category_items["Storyboard"] = storyboard_root
        storyboard_root.setExpanded(True)
        font = storyboard_root.font(1)
        font.setBold(True)
        storyboard_root.setFont(1, font)

        # Filter storyboard versions
        storyboard_versions = [v for v in versions if self._is_storyboard_version(v)]

        if storyboard_versions:
            for version in storyboard_versions:
                version_code = version.get('code', 'Unknown')
                status = version.get('sg_status_list', '')
                status_display = status if status else 'N/A'
                version_number = version_code.split('_')[-1] if '_' in version_code else ""

                version_item = self._create_version_item(
                    storyboard_root,
                    version,
                    [version_code, "Version", status_display, version_number]
                )

                status_lower = status.lower() if status else ''
                if status_lower in status_colors:
                    version_item.setBackground(3, status_colors[status_lower])
        else:
            no_data_item = SGTreeItem(
                storyboard_root,
                ["", "No versions found", "Info", "", ""],
                item_type="info"
            )
            no_data_item.setForeground(1, QtGui.QColor(120, 120, 120))

    def _is_vfx_breakdown_version(self, version):
        """Determine if a version belongs to VFX Breakdown category."""
        sg_version_type = version.get('sg_version_type')

        # If sg_version_type is set, use it
        if sg_version_type:
            # Handle both string and dict formats
            if isinstance(sg_version_type, dict):
                version_type = sg_version_type.get('name', '').lower()
            else:
                version_type = str(sg_version_type).lower()

            logger.debug(f"Version {version.get('code')} has type: {version_type}")
            return 'vfx' in version_type or 'breakdown' in version_type

        # Fallback to task/code checking if sg_version_type is not set
        task = version.get('sg_task', {})
        if task:
            task_name = task.get('name', '').lower()
            if 'vfx' in task_name or 'breakdown' in task_name:
                return True

        code = version.get('code', '').lower()
        if 'vfx' in code or 'breakdown' in code:
            return True

        return False

    def _is_script_version(self, version):
        """Determine if a version belongs to Script category."""
        sg_version_type = version.get('sg_version_type')

        # If sg_version_type is set, use it
        if sg_version_type:
            if isinstance(sg_version_type, dict):
                version_type = sg_version_type.get('name', '').lower()
            else:
                version_type = str(sg_version_type).lower()

            logger.debug(f"Version {version.get('code')} has type: {version_type}")
            return 'script' in version_type

        # Fallback to task/code checking
        code = version.get('code', '').lower()
        task = version.get('sg_task', {})
        task_name = task.get('name', '').lower() if task else ''

        return 'script' in code or 'script' in task_name

    def _is_concept_art_version(self, version):
        """Determine if a version belongs to Concept Art category."""
        sg_version_type = version.get('sg_version_type')

        # If sg_version_type is set, use it
        if sg_version_type:
            if isinstance(sg_version_type, dict):
                version_type = sg_version_type.get('name', '').lower()
            else:
                version_type = str(sg_version_type).lower()

            logger.debug(f"Version {version.get('code')} has type: {version_type}")
            return 'concept' in version_type or 'art' in version_type

        # Fallback to task/code checking
        code = version.get('code', '').lower()
        task = version.get('sg_task', {})
        task_name = task.get('name', '').lower() if task else ''

        return 'concept' in code or 'concept' in task_name or 'art' in task_name

    def _is_storyboard_version(self, version):
        """Determine if a version belongs to Storyboard category."""
        sg_version_type = version.get('sg_version_type')

        # If sg_version_type is set, use it
        if sg_version_type:
            if isinstance(sg_version_type, dict):
                version_type = sg_version_type.get('name', '').lower()
            else:
                version_type = str(sg_version_type).lower()

            logger.debug(f"Version {version.get('code')} has type: {version_type}")
            return 'storyboard' in version_type

        # Fallback to task/code checking
        code = version.get('code', '').lower()
        task = version.get('sg_task', {})
        task_name = task.get('name', '').lower() if task else ''

        return 'storyboard' in code or 'storyboard' in task_name

    def get_active_versions(self):
        """
        Get list of all active (checked) version items.

        Returns:
            List of SGTreeItem objects that are versions and are checked
        """
        active_versions = []

        # Iterate through all top-level items (categories)
        for i in range(self.tree_widget.topLevelItemCount()):
            category_item = self.tree_widget.topLevelItem(i)

            # Iterate through children (versions)
            for j in range(category_item.childCount()):
                child = category_item.child(j)

                if isinstance(child, SGTreeItem) and child.get_item_type() == "version":
                    if child.checkState(0) == QtCore.Qt.Checked:
                        active_versions.append(child)

        return active_versions

    def get_active_version_ids(self):
        """
        Get list of Shotgrid IDs for all active versions.

        Returns:
            List of version IDs (integers)
        """
        active_versions = self.get_active_versions()
        return [v.get_sg_id() for v in active_versions if v.get_sg_id()]

    def get_active_version_data(self):
        """
        Get full Shotgrid data for all active versions.

        Returns:
            List of dictionaries containing version data
        """
        active_versions = self.get_active_versions()
        return [v.get_sg_data() for v in active_versions]

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