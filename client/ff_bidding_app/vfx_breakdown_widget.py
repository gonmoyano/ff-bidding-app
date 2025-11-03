"""
VFX Breakdown Widget
Reusable widget component for displaying and editing VFX bidding scenes data using Qt Model/View pattern.
"""

from PySide6 import QtWidgets, QtCore, QtGui
import logging
import json

try:
    from .logger import logger
    from .vfx_breakdown_model import VFXBreakdownModel, PasteCommand, CheckBoxDelegate
    from .settings import AppSettings
    from .multi_entity_reference_widget import MultiEntityReferenceWidget
except ImportError:
    logger = logging.getLogger("FFPackageManager")
    from vfx_breakdown_model import VFXBreakdownModel, PasteCommand, CheckBoxDelegate
    from settings import AppSettings
    from multi_entity_reference_widget import MultiEntityReferenceWidget


class NoElideDelegate(QtWidgets.QStyledItemDelegate):
    """Base delegate that prevents text elision (truncation with '...')."""

    def paint(self, painter, option, index):
        # Ensure text is not elided (truncated with "...")
        option.textElideMode = QtCore.Qt.ElideNone
        super().paint(painter, option, index)


class DropdownMenuDelegate(NoElideDelegate):
    """Delegate that paints the blue editing border when a dropdown menu is active."""

    def __init__(self, parent_widget, parent=None):
        super().__init__(parent)
        self.parent_widget = parent_widget

    def createEditor(self, parent, option, index):
        """Disable the default editor - dropdown menus are shown separately."""
        return None

    def paint(self, painter, option, index):
        # Ensure text is not elided (truncated with "...")
        option.textElideMode = QtCore.Qt.ElideNone
        super().paint(painter, option, index)

        if not self.parent_widget:
            return

        if self.parent_widget.is_dropdown_menu_active(index):
            painter.save()
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            pen = QtGui.QPen(QtGui.QColor("#0078d4"), 2)
            painter.setPen(pen)
            painter.setBrush(QtCore.Qt.NoBrush)
            border_rect = option.rect.adjusted(1, 1, -1, -1)
            painter.drawRoundedRect(border_rect, 4, 4)
            painter.restore()


class ConfigColumnsDialog(QtWidgets.QDialog):
    """Dialog for configuring column visibility and dropdown lists in VFX Breakdown table."""

    def __init__(self, column_fields, column_headers, current_visibility, current_dropdowns, parent=None):
        """Initialize the dialog.

        Args:
            column_fields: List of field names
            column_headers: List of display names for the fields
            current_visibility: Dictionary mapping field names to visibility (bool)
            current_dropdowns: Dictionary mapping field names to dropdown enabled (bool)
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Configure Columns")
        self.setModal(True)

        self.column_fields = column_fields
        self.column_headers = column_headers
        self.visibility_checkboxes = {}
        self.dropdown_checkboxes = {}

        self._build_ui(current_visibility, current_dropdowns)

        # Adjust size to content
        self.adjustSize()
        # Set a reasonable minimum but allow it to grow
        self.setMinimumWidth(500)

    def _build_ui(self, current_visibility, current_dropdowns):
        """Build the dialog UI."""
        layout = QtWidgets.QVBoxLayout(self)

        # Instructions
        instructions = QtWidgets.QLabel(
            "Configure column visibility and dropdown filters for the VFX Breakdown table:"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("padding: 10px; background-color: #2b2b2b; border-radius: 4px;")
        layout.addWidget(instructions)

        # Scroll area for the table
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_widget)

        # Header row
        header_widget = QtWidgets.QWidget()
        header_layout = QtWidgets.QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 5, 0, 5)
        header_layout.setSpacing(10)

        # Field name header
        field_header = QtWidgets.QLabel("Field Name")
        field_header.setStyleSheet("font-weight: bold; padding: 5px;")
        field_header.setMinimumWidth(200)
        header_layout.addWidget(field_header)

        # Visible header
        visible_header = QtWidgets.QLabel("Visible")
        visible_header.setStyleSheet("font-weight: bold; padding: 5px;")
        visible_header.setAlignment(QtCore.Qt.AlignCenter)
        visible_header.setMinimumWidth(80)
        header_layout.addWidget(visible_header)

        # Dropdown list header
        dropdown_header = QtWidgets.QLabel("Dropdown List")
        dropdown_header.setStyleSheet("font-weight: bold; padding: 5px;")
        dropdown_header.setAlignment(QtCore.Qt.AlignCenter)
        dropdown_header.setMinimumWidth(120)
        dropdown_header.setToolTip("Enable dropdown selection with unique values from this column")
        header_layout.addWidget(dropdown_header)

        header_layout.addStretch()
        scroll_layout.addWidget(header_widget)

        # Separator line
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        scroll_layout.addWidget(line)

        # Create row for each column
        for field, header in zip(self.column_fields, self.column_headers):
            row_widget = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 2, 0, 2)
            row_layout.setSpacing(10)

            # Field name label
            field_label = QtWidgets.QLabel(header)
            field_label.setMinimumWidth(200)
            field_label.setStyleSheet("padding: 5px;")
            row_layout.addWidget(field_label)

            # Visible checkbox with custom indicator
            visible_indicator, visible_checkbox = self._create_custom_checkbox(
                current_visibility.get(field, True)
            )
            visible_container = QtWidgets.QWidget()
            visible_container_layout = QtWidgets.QHBoxLayout(visible_container)
            visible_container_layout.setContentsMargins(30, 0, 0, 0)
            visible_container_layout.addWidget(visible_indicator)
            visible_container_layout.addWidget(visible_checkbox)
            visible_container_layout.addStretch()
            visible_container.setMinimumWidth(80)
            row_layout.addWidget(visible_container)

            # Dropdown checkbox with custom indicator
            dropdown_indicator, dropdown_checkbox = self._create_custom_checkbox(
                current_dropdowns.get(field, False)
            )
            dropdown_container = QtWidgets.QWidget()
            dropdown_container_layout = QtWidgets.QHBoxLayout(dropdown_container)
            dropdown_container_layout.setContentsMargins(50, 0, 0, 0)
            dropdown_container_layout.addWidget(dropdown_indicator)
            dropdown_container_layout.addWidget(dropdown_checkbox)
            dropdown_container_layout.addStretch()
            dropdown_container.setMinimumWidth(120)
            row_layout.addWidget(dropdown_container)

            row_layout.addStretch()

            self.visibility_checkboxes[field] = visible_checkbox
            self.dropdown_checkboxes[field] = dropdown_checkbox
            scroll_layout.addWidget(row_widget)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll, stretch=1)

        # Select/Deselect All buttons
        button_row = QtWidgets.QHBoxLayout()

        visible_group = QtWidgets.QLabel("Visibility:")
        visible_group.setStyleSheet("font-weight: bold;")
        button_row.addWidget(visible_group)

        select_all_btn = QtWidgets.QPushButton("Select All")
        select_all_btn.clicked.connect(self._select_all_visible)
        button_row.addWidget(select_all_btn)

        deselect_all_btn = QtWidgets.QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(self._deselect_all_visible)
        button_row.addWidget(deselect_all_btn)

        button_row.addStretch()
        layout.addLayout(button_row)

        # OK/Cancel buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()

        self.ok_button = QtWidgets.QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setDefault(True)
        button_layout.addWidget(self.ok_button)

        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def _create_custom_checkbox(self, checked=False):
        """Create a checkbox with custom tick icon indicator.

        Args:
            checked: Initial checked state

        Returns:
            tuple: (indicator_label, checkbox)
        """
        # Custom checkbox indicator
        indicator_label = QtWidgets.QLabel()
        indicator_label.setFixedSize(20, 20)
        indicator_label.setAlignment(QtCore.Qt.AlignCenter)

        # Checkbox (hidden default indicator)
        checkbox = QtWidgets.QCheckBox()
        checkbox.setChecked(checked)

        # Remove default indicator and add custom styling
        checkbox.setStyleSheet("""
            QCheckBox {
                spacing: 0px;
            }
            QCheckBox::indicator {
                width: 0px;
                height: 0px;
            }
        """)

        # Function to update indicator appearance
        def update_indicator(is_checked):
            if is_checked:
                # Checked state: show tick icon
                indicator_label.setStyleSheet("""
                    QLabel {
                        border: 2px solid #0078d4;
                        border-radius: 3px;
                        background-color: #2b2b2b;
                        color: #0078d4;
                        font-size: 16px;
                        font-weight: bold;
                    }
                """)
                indicator_label.setText("✓")
            else:
                # Unchecked state: empty box
                indicator_label.setStyleSheet("""
                    QLabel {
                        border: 2px solid #555;
                        border-radius: 3px;
                        background-color: #2b2b2b;
                    }
                """)
                indicator_label.setText("")

        # Connect checkbox to update indicator
        checkbox.toggled.connect(update_indicator)
        update_indicator(checkbox.isChecked())  # Set initial state

        # Make indicator clickable
        indicator_label.mousePressEvent = lambda event: checkbox.setChecked(not checkbox.isChecked())
        indicator_label.setCursor(QtCore.Qt.PointingHandCursor)

        return indicator_label, checkbox

    def _select_all_visible(self):
        """Select all visibility checkboxes."""
        for checkbox in self.visibility_checkboxes.values():
            checkbox.setChecked(True)

    def _deselect_all_visible(self):
        """Deselect all visibility checkboxes."""
        for checkbox in self.visibility_checkboxes.values():
            checkbox.setChecked(False)

    def get_column_visibility(self):
        """Get the column visibility settings.

        Returns:
            dict: Mapping of field names to visibility (bool)
        """
        visibility = {}
        for field, checkbox in self.visibility_checkboxes.items():
            visibility[field] = checkbox.isChecked()
        return visibility

    def get_column_dropdowns(self):
        """Get the column dropdown settings.

        Returns:
            dict: Mapping of field names to dropdown enabled (bool)
        """
        dropdowns = {}
        for field, checkbox in self.dropdown_checkboxes.items():
            dropdowns[field] = checkbox.isChecked()
        return dropdowns


class VFXBreakdownWidget(QtWidgets.QWidget):
    """
    Reusable widget for displaying and editing VFX Breakdown bidding scenes.
    Uses Qt Model/View pattern with VFXBreakdownModel.
    """

    # Signals
    statusMessageChanged = QtCore.Signal(str, bool)  # message, is_error

    def __init__(self, sg_session, show_toolbar=True, parent=None):
        """Initialize the widget.

        Args:
            sg_session: ShotGrid session for API access
            show_toolbar: Whether to show the search/filter toolbar
            parent: Parent widget
        """
        super().__init__(parent)
        self.sg_session = sg_session
        self.show_toolbar = show_toolbar
        self.current_bid = None  # Store reference to current Bid
        self._asset_menu_open = False  # Guard to prevent re-entry

        # Create the model
        self.model = VFXBreakdownModel(sg_session, parent=self)

        # Connect model signals
        self.model.statusMessageChanged.connect(self._on_model_status_changed)
        self.model.rowCountChanged.connect(self._on_model_row_count_changed)
        self.model.dataChanged.connect(self._on_model_data_changed)

        # UI widgets
        self.table_view = None
        self.global_search_box = None
        self.clear_filters_btn = None
        self.compound_sort_btn = None
        self.config_columns_btn = None
        self.row_height_slider = None
        self.row_height_label = None
        self.template_dropdown = None
        self.row_count_label = None

        # Settings for column visibility and dropdowns
        self.app_settings = AppSettings()
        self.column_visibility = {}  # field_name -> bool
        self.column_dropdowns = {}  # field_name -> bool
        self.dropdown_values = {}  # field_name -> list of unique values (shared reference)
        self._dropdown_delegates = {}  # field_name -> DropdownMenuDelegate
        self._active_dropdown_index = None  # Track which cell should show the editing border

        # Build UI
        self._build_ui()
        self._setup_shortcuts()

        # Load and apply column settings
        self._load_column_order()  # Load column order first
        self._load_column_visibility()  # Then apply visibility
        self._load_column_dropdowns()  # Load dropdown settings
        self._load_row_height()  # Load row height

    def _build_ui(self):
        """Build the widget UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar (search and filter controls)
        if self.show_toolbar:
            toolbar_layout = QtWidgets.QHBoxLayout()

            # Global search box
            search_label = QtWidgets.QLabel("Search:")
            toolbar_layout.addWidget(search_label)

            self.global_search_box = QtWidgets.QLineEdit()
            self.global_search_box.setPlaceholderText("Search across all columns...")
            self.global_search_box.textChanged.connect(self._on_search_changed)
            toolbar_layout.addWidget(self.global_search_box, stretch=2)

            # Clear filters button
            self.clear_filters_btn = QtWidgets.QPushButton("Clear")
            self.clear_filters_btn.clicked.connect(self._clear_filters)
            toolbar_layout.addWidget(self.clear_filters_btn)

            # Compound Sorting button
            self.compound_sort_btn = QtWidgets.QPushButton("Compound Sorting")
            self.compound_sort_btn.clicked.connect(self._open_compound_sort_dialog)
            toolbar_layout.addWidget(self.compound_sort_btn)

            # Config Columns button
            self.config_columns_btn = QtWidgets.QPushButton("Config Columns")
            self.config_columns_btn.clicked.connect(self._open_config_columns_dialog)
            toolbar_layout.addWidget(self.config_columns_btn)

            # Row height slider
            toolbar_layout.addWidget(QtWidgets.QLabel("Row Height:"))
            self.row_height_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            self.row_height_slider.setMinimum(30)
            self.row_height_slider.setMaximum(200)
            self.row_height_slider.setValue(80)  # Default height
            self.row_height_slider.setFixedWidth(120)
            self.row_height_slider.setToolTip("Adjust table row height")
            self.row_height_slider.valueChanged.connect(self._on_row_height_changed)
            toolbar_layout.addWidget(self.row_height_slider)

            # Row height value label
            self.row_height_label = QtWidgets.QLabel("80")
            self.row_height_label.setMinimumWidth(30)
            self.row_height_label.setStyleSheet("color: #606060; padding: 2px 4px;")
            toolbar_layout.addWidget(self.row_height_label)

            # Template dropdown
            toolbar_layout.addWidget(QtWidgets.QLabel("Template:"))
            self.template_dropdown = QtWidgets.QComboBox()
            self.template_dropdown.addItem("(No Template)")
            self.template_dropdown.setMinimumWidth(150)
            self.template_dropdown.currentTextChanged.connect(self._apply_sort_template)
            toolbar_layout.addWidget(self.template_dropdown)

            # Row count label
            self.row_count_label = QtWidgets.QLabel("Showing 0 of 0 rows")
            self.row_count_label.setStyleSheet("color: #606060; padding: 2px 4px;")
            toolbar_layout.addWidget(self.row_count_label)

            layout.addLayout(toolbar_layout)

        # Table view
        self.table_view = QtWidgets.QTableView()
        self.table_view.setModel(self.model)

        # Set default delegate to prevent text elision on all columns
        self.table_view.setItemDelegate(NoElideDelegate(self.table_view))

        # Configure table view
        self.table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectItems)
        self.table_view.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.table_view.setAlternatingRowColors(False)
        self.table_view.setWordWrap(True)
        self.table_view.setTextElideMode(QtCore.Qt.ElideNone)  # Don't truncate text with "..."

        # Configure headers
        h_header = self.table_view.horizontalHeader()
        h_header.setStretchLastSection(False)
        h_header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        h_header.setSectionsClickable(True)
        h_header.setSectionsMovable(True)  # Enable draggable columns
        h_header.sectionClicked.connect(self._on_header_clicked)
        h_header.sectionMoved.connect(self._on_column_moved)  # Save order when moved
        h_header.sectionResized.connect(self._on_column_resized)  # Save width when resized

        v_header = self.table_view.verticalHeader()
        v_header.sectionClicked.connect(self._on_row_header_clicked)

        # Context menu
        self.table_view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._on_context_menu)

        # Double-click handler for adding bid assets
        self.table_view.doubleClicked.connect(self._on_cell_double_clicked)

        # Selection change handler for visual feedback on bid assets widgets
        selection_model = self.table_view.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(self._on_selection_changed)

        # Install event filter
        self.table_view.installEventFilter(self)

        layout.addWidget(self.table_view)

        # Update template dropdown
        self._update_template_dropdown()

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts for undo/redo and copy/paste."""
        # Undo shortcut (Ctrl+Z)
        undo_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Z"), self)
        undo_shortcut.activated.connect(self._undo)

        # Redo shortcut (Ctrl+Y)
        redo_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Y"), self)
        redo_shortcut.activated.connect(self._redo)

        # Copy shortcut (Ctrl+C)
        copy_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+C"), self)
        copy_shortcut.activated.connect(self._copy_selection)

        # Paste shortcut (Ctrl+V)
        paste_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+V"), self)
        paste_shortcut.activated.connect(self._paste_selection)

        logger.info("Keyboard shortcuts set up: Ctrl+Z (undo), Ctrl+Y (redo), Ctrl+C (copy), Ctrl+V (paste)")

    def eventFilter(self, obj, event):
        """Event filter to handle Enter/Delete keys and double-clicks on index widgets."""
        # Handle double-click on MultiEntityReferenceWidget (sg_bid_assets cells)
        if isinstance(obj, MultiEntityReferenceWidget) and event.type() == QtCore.QEvent.MouseButtonDblClick:
            # Get the stored model index
            index = obj.property("modelIndex")
            if index and index.isValid():
                logger.info(f"Double-click detected on Assets widget at row {index.row()}")
                self._on_cell_double_clicked(index)
                return True

        if obj == self.table_view and event.type() == QtCore.QEvent.KeyPress:
            if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                # Enter pressed - move to next row
                current_index = self.table_view.currentIndex()
                if current_index.isValid():
                    next_row = current_index.row() + 1
                    if next_row < self.model.rowCount():
                        next_index = self.model.index(next_row, current_index.column())
                        self.table_view.setCurrentIndex(next_index)
                return True
            elif event.key() == QtCore.Qt.Key_Delete:
                # Delete key pressed - delete selected rows
                selected_rows = set()
                for index in self.table_view.selectedIndexes():
                    selected_rows.add(index.row())
                if selected_rows:
                    self._delete_bidding_scene(min(selected_rows))
                return True

        return super().eventFilter(obj, event)

    def load_bidding_scenes(self, bidding_scenes, field_schema=None):
        """Load bidding scenes data into the widget.

        Args:
            bidding_scenes: List of bidding scene dictionaries from ShotGrid
            field_schema: Optional field schema for type conversions
        """
        if field_schema:
            self.model.set_field_schema(field_schema)

            # Debug: Log list fields and their values
            logger.info("=== Field Schema Debug ===")
            for col_idx, field_name in enumerate(self.model.column_fields):
                if field_name in field_schema:
                    field_info = field_schema[field_name]
                    data_type = field_info.get("data_type")
                    if data_type == "list":
                        list_values = field_info.get("list_values", [])
                        logger.info(f"List field: {field_name}, values count: {len(list_values)}, values: {list_values[:5] if list_values else 'NONE'}")

            # Set up delegates for checkbox fields (list fields now use QMenu on double-click)
            for col_idx, field_name in enumerate(self.model.column_fields):
                if field_name in field_schema:
                    field_info = field_schema[field_name]
                    # List fields now handled by _show_list_selection_menu on double-click
                    # if field_info.get("data_type") == "list":
                    #     list_values = field_info.get("list_values", [])
                    #     if list_values:
                    #         delegate = ComboBoxDelegate(field_name, list_values, self.table_view)
                    #         self.table_view.setItemDelegateForColumn(col_idx, delegate)
                    if field_info.get("data_type") == "checkbox":
                        # Use custom checkbox delegate for checkbox fields
                        delegate = CheckBoxDelegate(self.table_view)
                        self.table_view.setItemDelegateForColumn(col_idx, delegate)

        self.model.load_bidding_scenes(bidding_scenes)

        # Ensure table is updated before sizing
        QtWidgets.QApplication.processEvents()

        # Check if we have saved column widths
        saved_widths = self.app_settings.get_column_widths("vfx_breakdown")

        if saved_widths:
            # If we have saved widths, use them (skip auto-sizing)
            self._load_column_widths()
        else:
            # First time: auto-size columns to content
            self._autosize_columns()
            # Save the auto-sized widths so they persist
            widths = self._get_current_column_widths()
            self.app_settings.set_column_widths("vfx_breakdown", widths)

        # Apply dropdown delegates to columns marked for dropdowns
        self._apply_column_dropdowns()

        # Set up MultiEntityReferenceWidget for sg_bid_assets column
        self._setup_bid_assets_widgets()

    def _setup_bid_assets_widgets(self):
        """Set up MultiEntityReferenceWidget for each row in the sg_bid_assets column."""
        # Find the column index for sg_bid_assets
        try:
            assets_col_idx = self.model.column_fields.index("sg_bid_assets")
        except ValueError:
            # Column not present in this table
            return

        # Get valid asset IDs from the current bid for validation
        valid_entity_ids = self._get_valid_asset_ids()
        logger.info(f"Setting up bid assets widgets with validation: {valid_entity_ids}")

        # Create widget for each row
        for row in range(self.model.rowCount()):
            # Get the model index for this cell
            index = self.model.index(row, assets_col_idx)

            # Get the actual data row index
            data_row = self.model.filtered_row_indices[row]
            bidding_scene_data = self.model.all_bidding_scenes_data[data_row]

            # Get current entities for this row
            entities = bidding_scene_data.get("sg_bid_assets", [])
            if not isinstance(entities, list):
                entities = [entities] if entities else []

            # Create the widget with validation
            widget = MultiEntityReferenceWidget(
                entities=entities,
                allow_add=False,
                valid_entity_ids=valid_entity_ids
            )
            # Set height to match current row height setting
            current_row_height = self.app_settings.get("vfx_breakdown_row_height", 80)
            widget.setFixedHeight(current_row_height)

            # Connect signal to update model when entities change
            widget.entitiesChanged.connect(
                lambda ents, r=row, col=assets_col_idx: self._on_bid_assets_changed(r, col, ents)
            )

            # Install event filter to catch double-clicks (index widgets consume events)
            widget.installEventFilter(self)
            # Store the model index on the widget for later retrieval
            widget.setProperty("modelIndex", index)

            # Set the widget in the table
            self.table_view.setIndexWidget(index, widget)

            # Check if this cell is currently selected and update widget state
            if self.table_view.selectionModel():
                is_selected = self.table_view.selectionModel().isSelected(index)
                widget.set_selected(is_selected)

        # Row height is controlled by the slider - don't override it here

    def _on_bid_assets_changed(self, row, col, entities):
        """Handle when bid assets are changed in a cell widget.

        Args:
            row: Table row index
            col: Column index
            entities: Updated list of entity dicts
        """
        # Get the model index
        index = self.model.index(row, col)

        # Update the model data
        # The model expects the list of entity dicts
        self.model.setData(index, entities, QtCore.Qt.EditRole)

        logger.info(f"Updated sg_bid_assets for row {row}: {[e.get('name') for e in entities]}")

    def set_current_bid(self, bid):
        """Set the current Bid for this widget.

        Args:
            bid: Bid dictionary from ShotGrid
        """
        self.current_bid = bid
        logger.info(f"VFXBreakdownWidget: Current bid set to {bid.get('code') if bid else None}")

        # Refresh asset widgets with new validation when bid changes
        self._refresh_asset_widgets_validation()

    def _refresh_asset_widgets_validation(self):
        """Refresh validation for all asset widgets based on current bid."""
        # Find the column index for sg_bid_assets
        try:
            assets_col_idx = self.model.column_fields.index("sg_bid_assets")
        except ValueError:
            # Column not present in this table
            return

        # Get the new valid asset IDs
        valid_entity_ids = self._get_valid_asset_ids()
        logger.info(f"Refreshing asset widgets validation with IDs: {valid_entity_ids}")

        # Update all existing asset widgets
        for row in range(self.model.rowCount()):
            index = self.model.index(row, assets_col_idx)
            widget = self.table_view.indexWidget(index)

            if isinstance(widget, MultiEntityReferenceWidget):
                # Update the validation IDs for this widget
                widget.set_valid_entity_ids(valid_entity_ids)
                logger.debug(f"Updated validation for row {row}")

    def _on_selection_changed(self, selected, deselected):
        """Handle table selection changes to update bid assets widget visual state.

        Args:
            selected: QItemSelection of newly selected items
            deselected: QItemSelection of newly deselected items
        """
        # Update deselected widgets
        for index in deselected.indexes():
            if index.column() < len(self.model.column_fields):
                field_name = self.model.column_fields[index.column()]
                if field_name == "sg_bid_assets":
                    widget = self.table_view.indexWidget(index)
                    if isinstance(widget, MultiEntityReferenceWidget):
                        logger.debug(f"Setting deselected state for row {index.row()}")
                        widget.set_selected(False)

        # Update selected widgets
        for index in selected.indexes():
            if index.column() < len(self.model.column_fields):
                field_name = self.model.column_fields[index.column()]
                if field_name == "sg_bid_assets":
                    widget = self.table_view.indexWidget(index)
                    if isinstance(widget, MultiEntityReferenceWidget):
                        logger.debug(f"Setting selected state for row {index.row()}")
                        widget.set_selected(True)

    def _on_cell_double_clicked(self, index):
        """Handle double-click on a cell.

        Shows a dropdown menu for:
        - sg_bid_assets column: asset selection menu
        - List type fields: value selection menu

        Args:
            index: QModelIndex of the clicked cell
        """
        field_name = self.model.column_fields[index.column()]

        # Handle sg_bid_assets column
        if field_name == "sg_bid_assets":
            # Check if we have a current bid
            if not self.current_bid:
                QtWidgets.QMessageBox.warning(
                    self,
                    "No Bid Selected",
                    "Please select a Bid from the Bids tab first."
                )
                return
            self._show_add_asset_dialog(index)
            return

        # Handle list type fields
        if hasattr(self.model, 'field_schema') and self.model.field_schema:
            field_info = self.model.field_schema.get(field_name, {})
            logger.info(f"Double-click on {field_name}: field_info={field_info}")

            # Text fields that are configured for dropdowns should use the menu styling
            if (
                self.column_dropdowns.get(field_name, False)
                and field_info.get("data_type") == "text"
            ):
                shared_list = self.dropdown_values.get(field_name)
                if shared_list is None:
                    shared_list = self._get_unique_column_values(field_name)
                    self.dropdown_values[field_name] = shared_list

                self._show_text_dropdown_menu(index, field_name, shared_list)
                return

            if field_info.get("data_type") == "list":
                list_values = field_info.get("list_values", [])
                logger.info(f"List field {field_name} has {len(list_values)} values")
                if list_values:
                    self._show_list_selection_menu(index, field_name, list_values)
                    return
                else:
                    logger.warning(f"List field {field_name} has no list_values")
            else:
                logger.info(f"Field {field_name} is not a list type (type={field_info.get('data_type')})")
        else:
            logger.warning(f"No field_schema available for {field_name}")

    def _show_add_asset_dialog(self, index):
        """Show dialog to select and add a bid asset to the cell.

        Args:
            index: QModelIndex of the cell to add asset to
        """
        # Prevent re-entry while menu is open
        if self._asset_menu_open:
            return

        self._asset_menu_open = True

        row = index.row()
        col = index.column()

        # Get currently selected assets in this cell
        data_row = self.model.filtered_row_indices[row]
        bidding_scene_data = self.model.all_bidding_scenes_data[data_row]
        current_entities = bidding_scene_data.get("sg_bid_assets", [])
        if not isinstance(current_entities, list):
            current_entities = [current_entities] if current_entities else []

        # Get IDs of already-added assets
        current_asset_ids = {e.get("id") for e in current_entities if isinstance(e, dict)}

        # Query available assets from current Bid
        available_assets = self._get_available_bid_assets()

        if not available_assets:
            self._asset_menu_open = False
            QtWidgets.QMessageBox.information(
                self,
                "No Assets Available",
                "No Bid Assets found for the current Bid.\n\n"
                "Please ensure the Bid has Bid Assets with Asset items."
            )
            return

        # Filter out already-added assets
        available_assets = [a for a in available_assets if a.get("id") not in current_asset_ids]

        if not available_assets:
            self._asset_menu_open = False
            QtWidgets.QMessageBox.information(
                self,
                "All Assets Added",
                "All available Bid Assets have already been added to this cell."
            )
            return

        # Set editing state on the widget to show blue border
        widget = self.table_view.indexWidget(index)
        if isinstance(widget, MultiEntityReferenceWidget):
            widget.set_editing(True)

        # Create a QMenu for asset selection (simpler and more reliable than QComboBox popup)
        menu = QtWidgets.QMenu(self.table_view)

        # Add available assets as menu actions
        for asset in available_assets:
            asset_code = asset.get("code", f"ID {asset.get('id', 'N/A')}")
            action = menu.addAction(asset_code)
            # Store the full asset dict as action data
            action.setData(asset)

        # Define handler for selection
        def on_action_triggered(action):
            selected_asset = action.data()
            if selected_asset:
                # Add to current entities
                current_entities.append(selected_asset)

                # Update the model
                self.model.setData(index, current_entities, QtCore.Qt.EditRole)

                # Refresh the widget
                widget = self.table_view.indexWidget(index)
                if isinstance(widget, MultiEntityReferenceWidget):
                    widget.set_entities(current_entities)

                logger.info(f"Added asset {selected_asset.get('code')} to row {row}")

        # Connect signal
        menu.triggered.connect(on_action_triggered)

        # Get cell rectangle and calculate position
        cell_rect = self.table_view.visualRect(index)
        viewport = self.table_view.viewport()

        # Convert to global coordinates
        bottom_left = viewport.mapToGlobal(cell_rect.bottomLeft())
        top_left = viewport.mapToGlobal(cell_rect.topLeft())

        # Get menu size hint
        menu.adjustSize()
        menu_height = menu.sizeHint().height()

        # Get screen geometry
        screen_geometry = QtWidgets.QApplication.primaryScreen().availableGeometry()

        # Calculate position: below cell if room, otherwise above
        if bottom_left.y() + menu_height <= screen_geometry.bottom():
            # Position below cell (align top of menu with bottom of cell)
            menu.exec(bottom_left)
        else:
            # Position above cell (align bottom of menu with top of cell)
            menu.exec(QtCore.QPoint(top_left.x(), top_left.y() - menu_height))

        # Reset editing state on widget after menu closes
        if isinstance(widget, MultiEntityReferenceWidget):
            widget.set_editing(False)

        # Reset flag after menu closes
        self._asset_menu_open = False

    def _show_text_dropdown_menu(self, index, field_name, shared_list):
        """Show the dropdown menu for text fields configured as dropdowns."""

        # Ensure the menu operates on the shared list reference
        if shared_list is None:
            shared_list = []
            self.dropdown_values[field_name] = shared_list

        menu = QtWidgets.QMenu(self.table_view)

        # Empty option allows clearing the value
        empty_action = menu.addAction("")
        empty_action.setData(None)

        # Sort values for consistent ordering in the menu
        if shared_list:
            sorted_values = sorted(shared_list, key=lambda v: v.lower() if isinstance(v, str) else str(v).lower())
            for value in sorted_values:
                action = menu.addAction(value)
                action.setData(value)
        else:
            placeholder = menu.addAction("(No saved values)")
            placeholder.setEnabled(False)

        menu.addSeparator()
        add_new_action = menu.addAction("Add New Value…")
        add_new_action.setData("__add_new__")

        def on_action_triggered(action):
            selected_value = action.data()

            if selected_value == "__add_new__":
                text, ok = QtWidgets.QInputDialog.getText(
                    self,
                    "Add New Dropdown Value",
                    f"Enter a new value for {field_name}:"
                )
                if ok:
                    new_value = text.strip()
                    if new_value:
                        if new_value not in shared_list:
                            shared_list.append(new_value)
                            shared_list.sort(key=lambda v: v.lower() if isinstance(v, str) else str(v).lower())
                            self._on_dropdown_value_added(field_name, new_value)
                        self.model.setData(index, new_value, QtCore.Qt.EditRole)
                        logger.info(f"Added new dropdown value '{new_value}' to '{field_name}'")
                return

            # Persist selected value (may be None for cleared option)
            if selected_value is None:
                self.model.setData(index, None, QtCore.Qt.EditRole)
                logger.info(f"Cleared value for '{field_name}' at row {index.row()}")
            else:
                self.model.setData(index, selected_value, QtCore.Qt.EditRole)
                logger.info(f"Set '{field_name}' to '{selected_value}' for row {index.row()}")

        menu.triggered.connect(on_action_triggered)

        # Record the active index to paint the blue editing border
        self._set_active_dropdown_index(index)

        cell_rect = self.table_view.visualRect(index)
        viewport = self.table_view.viewport()
        bottom_left = viewport.mapToGlobal(cell_rect.bottomLeft())
        top_left = viewport.mapToGlobal(cell_rect.topLeft())

        menu.adjustSize()
        menu_height = menu.sizeHint().height()
        screen_geometry = QtWidgets.QApplication.primaryScreen().availableGeometry()

        try:
            if bottom_left.y() + menu_height <= screen_geometry.bottom():
                menu.exec(bottom_left)
            else:
                menu.exec(QtCore.QPoint(top_left.x(), top_left.y() - menu_height))
        finally:
            self._clear_active_dropdown_index(index)

    def _show_list_selection_menu(self, index, field_name, list_values):
        """Show menu to select a value from a list field.

        Args:
            index: QModelIndex of the cell
            field_name: Name of the field
            list_values: List of possible values
        """
        # Create a QMenu for value selection
        menu = QtWidgets.QMenu(self.table_view)

        # Add empty option first
        empty_action = menu.addAction("")
        empty_action.setData(None)

        # Add all list values as menu actions
        for value in list_values:
            action = menu.addAction(value)
            action.setData(value)

        # Define handler for selection
        def on_action_triggered(action):
            selected_value = action.data()
            # Update the model (even if None/empty)
            self.model.setData(index, selected_value, QtCore.Qt.EditRole)
            logger.info(f"Set {field_name} to '{selected_value}' for row {index.row()}")

        # Connect signal
        menu.triggered.connect(on_action_triggered)

        # Get cell rectangle and calculate position
        cell_rect = self.table_view.visualRect(index)
        viewport = self.table_view.viewport()

        # Convert to global coordinates
        bottom_left = viewport.mapToGlobal(cell_rect.bottomLeft())
        top_left = viewport.mapToGlobal(cell_rect.topLeft())

        # Get menu size hint
        menu.adjustSize()
        menu_height = menu.sizeHint().height()

        # Get screen geometry
        screen_geometry = QtWidgets.QApplication.primaryScreen().availableGeometry()

        # Calculate position: below cell if room, otherwise above
        if bottom_left.y() + menu_height <= screen_geometry.bottom():
            # Position below cell (align top of menu with bottom of cell)
            menu.exec(bottom_left)
        else:
            # Position above cell (align bottom of menu with top of cell)
            menu.exec(QtCore.QPoint(top_left.x(), top_left.y() - menu_height))

    def _get_available_bid_assets(self):
        """Query and return all Asset items from the current Bid's Bid Assets.

        Returns:
            list: List of Asset item dicts (CustomEntity07) with id, code, name, type
        """
        if not self.current_bid:
            return []

        # Get the Bid Assets entity from the current Bid
        bid_assets_entity = self.current_bid.get("sg_bid_assets")

        if not bid_assets_entity:
            logger.warning(f"Current Bid {self.current_bid.get('code')} has no sg_bid_assets")
            return []

        # Extract Bid Assets ID
        if isinstance(bid_assets_entity, dict):
            bid_assets_id = bid_assets_entity.get("id")
        elif isinstance(bid_assets_entity, list) and bid_assets_entity:
            bid_assets_id = bid_assets_entity[0].get("id")
        else:
            logger.warning(f"Invalid sg_bid_assets format: {bid_assets_entity}")
            return []

        if not bid_assets_id:
            return []

        try:
            # Query all Asset items (CustomEntity07) that belong to this Bid Assets
            filters = [
                ["sg_bid_assets", "is", {"type": "CustomEntity08", "id": bid_assets_id}]
            ]

            assets = self.sg_session.sg.find(
                "CustomEntity07",
                filters,
                ["id", "code", "name", "type"]
            )

            logger.info(f"Found {len(assets)} Asset items in Bid Assets {bid_assets_id}")
            return assets

        except Exception as e:
            logger.error(f"Failed to query Asset items: {e}", exc_info=True)
            return []

    def _get_valid_asset_ids(self):
        """Get the set of valid asset IDs from the current bid's Assets tab.

        Returns:
            set: Set of asset IDs (integers) that are valid for the current bid.
                 Returns None if no bid is selected (meaning all assets are valid/no validation).
        """
        if not self.current_bid:
            # No bid selected - no validation
            return None

        # Get all assets from the current bid
        assets = self._get_available_bid_assets()

        # Extract IDs into a set
        valid_ids = {asset['id'] for asset in assets if 'id' in asset}

        logger.info(f"Valid asset IDs for current bid: {valid_ids}")
        return valid_ids

    def clear_data(self):
        """Clear all data from the widget."""
        self.model.clear_data()
        if self.row_count_label:
            self.row_count_label.setText("Showing 0 of 0 rows")

    def _on_search_changed(self, text):
        """Handle search text change."""
        self.model.set_global_search(text)

    def _on_header_clicked(self, column_index):
        """Handle header click for sorting."""
        # Block single-column sorting if compound sorting is active
        if self.model.compound_sort_columns:
            logger.info("Single-column sorting disabled while compound sorting template is active")
            return

        # Toggle sort direction
        if self.model.sort_column == column_index:
            direction = "desc" if self.model.sort_direction == "asc" else "asc"
        else:
            direction = "asc"

        self.model.set_sort(column_index, direction)
        self._update_header_sort_indicators()

        logger.info(f"Sorting by column {column_index}: {direction}")

    def _update_header_sort_indicators(self):
        """Update table headers to show sort indicators."""
        import re

        for col_idx in range(self.model.columnCount()):
            header_text = self.model.headerData(col_idx, QtCore.Qt.Horizontal, QtCore.Qt.DisplayRole)

            # Remove existing indicators
            original_text = re.sub(r'\s*\d*[↑↓]', '', header_text)

            # Add indicators for compound sorting
            if self.model.compound_sort_columns:
                for priority, (sort_col, sort_dir) in enumerate(self.model.compound_sort_columns, 1):
                    if col_idx == sort_col:
                        arrow = "↑" if sort_dir == "asc" else "↓"
                        header_text = f"{original_text} {priority}{arrow}"
                        break
                else:
                    header_text = original_text
            # Add indicator for single-column sorting
            elif col_idx == self.model.sort_column and self.model.sort_direction:
                arrow = " ↑" if self.model.sort_direction == "asc" else " ↓"
                header_text = f"{original_text}{arrow}"
            else:
                header_text = original_text

            self.model.setHeaderData(col_idx, QtCore.Qt.Horizontal, header_text, QtCore.Qt.DisplayRole)

    def _clear_filters(self):
        """Clear search and sorting."""
        if self.global_search_box:
            self.global_search_box.clear()

        self.model.clear_sorting()

        if self.template_dropdown:
            self.template_dropdown.setCurrentIndex(0)

        self._update_header_sort_indicators()
        logger.info("Search and sorting cleared")

    def _open_compound_sort_dialog(self):
        """Open the compound sorting dialog."""
        # Import here to avoid circular dependency
        from vfx_breakdown_tab import CompoundSortDialog

        # Open dialog
        dialog = CompoundSortDialog(
            column_names=self.model.column_headers,
            current_sort=self.model.compound_sort_columns.copy(),
            templates=self.model.get_sort_templates(),
            parent=self
        )

        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            # Get the sort configuration
            sort_config = dialog.get_sort_configuration()

            # Update model
            if sort_config:
                self.model.set_compound_sort(sort_config)
            else:
                self.model.clear_sorting()

            # Update templates
            self.model.set_sort_templates(dialog.templates)
            self._update_template_dropdown()

            # Check if a template was applied
            applied_template = dialog.get_applied_template_name()
            if applied_template and self.template_dropdown:
                index = self.template_dropdown.findText(applied_template)
                if index >= 0:
                    self.template_dropdown.blockSignals(True)
                    self.template_dropdown.setCurrentIndex(index)
                    self.template_dropdown.blockSignals(False)

            # Update header indicators
            self._update_header_sort_indicators()

            logger.info(f"Compound sort applied: {len(sort_config)} levels")

    def _open_config_columns_dialog(self):
        """Open the column configuration dialog."""
        # Get current visibility state
        current_visibility = self.column_visibility.copy()
        current_dropdowns = self.column_dropdowns.copy()

        # Ensure all fields have settings
        for field in self.model.column_fields:
            if field not in current_visibility:
                current_visibility[field] = True
            if field not in current_dropdowns:
                current_dropdowns[field] = False

        # Get columns in their current visual order
        ordered_fields = self._get_current_column_order()
        ordered_headers = []

        # Build headers list in the same order
        field_to_header = {field: header for field, header in zip(self.model.column_fields, self.model.column_headers)}
        for field in ordered_fields:
            ordered_headers.append(field_to_header.get(field, field))

        # Open dialog with columns in visual order
        dialog = ConfigColumnsDialog(
            column_fields=ordered_fields,
            column_headers=ordered_headers,
            current_visibility=current_visibility,
            current_dropdowns=current_dropdowns,
            parent=self
        )

        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            # Get the new settings
            new_visibility = dialog.get_column_visibility()
            new_dropdowns = dialog.get_column_dropdowns()

            # Save to settings
            self.app_settings.set_column_visibility("vfx_breakdown", new_visibility)
            self.app_settings.set_column_dropdowns("vfx_breakdown", new_dropdowns)

            # Update local state
            self.column_visibility = new_visibility
            self.column_dropdowns = new_dropdowns

            # Apply visibility to table
            self._apply_column_visibility()

            # Apply dropdown delegates
            self._apply_column_dropdowns()

            logger.info(f"Column visibility updated: {sum(new_visibility.values())} of {len(new_visibility)} visible")
            logger.info(f"Column dropdowns updated: {sum(new_dropdowns.values())} of {len(new_dropdowns)} with dropdowns")

    def _load_column_visibility(self):
        """Load column visibility settings from AppSettings."""
        saved_visibility = self.app_settings.get_column_visibility("vfx_breakdown")

        if saved_visibility:
            self.column_visibility = saved_visibility
        else:
            # Default: all columns visible
            self.column_visibility = {field: True for field in self.model.column_fields}

        # Apply visibility
        self._apply_column_visibility()

    def _apply_column_visibility(self):
        """Apply column visibility settings to the table view."""
        if not self.table_view:
            return

        for col_index, field in enumerate(self.model.column_fields):
            is_visible = self.column_visibility.get(field, True)
            self.table_view.setColumnHidden(col_index, not is_visible)

    def _load_column_dropdowns(self):
        """Load column dropdown settings from AppSettings."""
        saved_dropdowns = self.app_settings.get_column_dropdowns("vfx_breakdown")

        if saved_dropdowns:
            self.column_dropdowns = saved_dropdowns
        else:
            # Default: no dropdowns enabled
            self.column_dropdowns = {field: False for field in self.model.column_fields}

        # Apply dropdowns
        self._apply_column_dropdowns()

    def _load_row_height(self):
        """Load row height setting from AppSettings."""
        saved_height = self.app_settings.get("vfx_breakdown_row_height", 80)

        if self.row_height_slider:
            self.row_height_slider.blockSignals(True)
            self.row_height_slider.setValue(saved_height)
            self.row_height_slider.blockSignals(False)

        if self.row_height_label:
            self.row_height_label.setText(str(saved_height))

        # Apply the height to the table
        if self.table_view:
            v_header = self.table_view.verticalHeader()
            v_header.setDefaultSectionSize(saved_height)

            # Update any existing asset widgets
            try:
                assets_col_idx = self.model.column_fields.index("sg_bid_assets")
                for row in range(self.model.rowCount()):
                    index = self.model.index(row, assets_col_idx)
                    widget = self.table_view.indexWidget(index)
                    if widget:
                        widget.setFixedHeight(saved_height)
                        widget.updateGeometry()

                    # Force the row to resize
                    v_header.resizeSection(row, saved_height)
            except (ValueError, AttributeError):
                # Column not present or other issue - skip widget updates
                pass

    def _on_row_height_changed(self, value):
        """Handle row height slider change."""
        # Update the label
        if self.row_height_label:
            self.row_height_label.setText(str(value))

        # Apply to the table in real-time
        if self.table_view:
            v_header = self.table_view.verticalHeader()
            v_header.setDefaultSectionSize(value)

            # Update all MultiEntityReferenceWidget heights in the sg_bid_assets column
            try:
                assets_col_idx = self.model.column_fields.index("sg_bid_assets")
                for row in range(self.model.rowCount()):
                    index = self.model.index(row, assets_col_idx)
                    widget = self.table_view.indexWidget(index)
                    if widget:
                        # Update both minimum and maximum height to match row height
                        widget.setMinimumHeight(value)
                        widget.setMaximumHeight(value)
                        widget.setFixedHeight(value)
                        widget.updateGeometry()

                    # Force the row to resize
                    v_header.resizeSection(row, value)
            except (ValueError, AttributeError):
                # Column not present or other issue - skip widget updates
                pass

        # Save to settings
        self.app_settings.set("vfx_breakdown_row_height", value)
        logger.info(f"Row height changed to {value}px")

    def _apply_column_dropdowns(self):
        """Apply dropdown delegates to columns marked for dropdowns."""
        if not self.table_view or not self.model.field_schema:
            return

        # Get field schema from the model
        field_schema = self.model.field_schema

        active_delegate_fields = set()

        for col_idx, field_name in enumerate(self.model.column_fields):
            # Check if dropdown is enabled for this field
            dropdown_enabled = self.column_dropdowns.get(field_name, False)

            if dropdown_enabled and field_name in field_schema:
                field_info = field_schema[field_name]
                data_type = field_info.get("data_type")

                # Only apply dropdown to text fields (list fields use QMenu on double-click)
                if data_type == "text":
                    # Get or create the shared list for this field
                    if field_name not in self.dropdown_values:
                        # Extract unique values from this column
                        self.dropdown_values[field_name] = self._get_unique_column_values(field_name)

                    # Get the shared list reference
                    shared_list = self.dropdown_values[field_name]

                    if shared_list is not None:
                        # Create (or reuse) a delegate that paints the menu editing border
                        delegate = self._dropdown_delegates.get(field_name)
                        if delegate is None:
                            delegate = DropdownMenuDelegate(self, parent=self.table_view)
                            self._dropdown_delegates[field_name] = delegate

                        self.table_view.setItemDelegateForColumn(col_idx, delegate)
                        active_delegate_fields.add(field_name)
                        logger.info(
                            f"Applied dropdown menu styling to '{field_name}' with {len(shared_list)} unique values"
                        )

        # Remove delegates from fields that are no longer marked as dropdowns
        for field_name in list(self._dropdown_delegates.keys()):
            if field_name not in active_delegate_fields:
                delegate = self._dropdown_delegates.pop(field_name)
                # Reset the column delegate to default if the field is still present
                if field_name in self.model.column_fields:
                    col_idx = self.model.column_fields.index(field_name)
                    self.table_view.setItemDelegateForColumn(col_idx, None)
                del delegate

    def _set_active_dropdown_index(self, index):
        """Record the index whose dropdown menu is currently shown."""
        if index and index.isValid():
            self._active_dropdown_index = (index.row(), index.column())
            self._update_dropdown_highlight_region(index)

    def _clear_active_dropdown_index(self, index=None):
        """Clear the active dropdown index and refresh the cell painting."""
        if self._active_dropdown_index is None:
            return

        # Store the previous index so we can trigger an update after clearing
        previous_row, previous_col = self._active_dropdown_index
        self._active_dropdown_index = None

        if index and index.isValid():
            self._update_dropdown_highlight_region(index)
        else:
            model = self.table_view.model()
            if model and 0 <= previous_row < model.rowCount() and 0 <= previous_col < model.columnCount():
                prev_index = model.index(previous_row, previous_col)
                self._update_dropdown_highlight_region(prev_index)

    def _update_dropdown_highlight_region(self, index):
        """Repaint the viewport region associated with an index."""
        if not index or not index.isValid():
            return

        rect = self.table_view.visualRect(index)
        if rect.isValid():
            self.table_view.viewport().update(rect)

    def is_dropdown_menu_active(self, index):
        """Return True if the dropdown menu highlight should be shown for index."""
        if not index or not index.isValid() or self._active_dropdown_index is None:
            return False

        return (index.row(), index.column()) == self._active_dropdown_index

    def _on_dropdown_value_added(self, field_name, new_value):
        """Callback when a new value is added to a dropdown list.

        Args:
            field_name: The field that had a new value added
            new_value: The new value that was added
        """
        # The value is already in the shared list, but we can log it or save to settings
        logger.info(f"New dropdown value added to '{field_name}': '{new_value}'")

    def _get_unique_column_values(self, field_name):
        """Extract unique non-empty values from a column.

        Args:
            field_name: Name of the field to extract values from

        Returns:
            list: Sorted list of unique non-empty values
        """
        if field_name not in self.model.column_fields:
            return []

        col_idx = self.model.column_fields.index(field_name)
        unique_values = set()

        # Iterate through all rows in the model
        for row_idx in range(self.model.rowCount()):
            index = self.model.index(row_idx, col_idx)
            value = self.model.data(index, QtCore.Qt.DisplayRole)

            # Add non-empty, non-None values (filter out empty strings, "-", None, etc.)
            if value is not None:
                value_str = str(value).strip()
                if value_str and value_str != "-" and value_str.lower() != "none":
                    unique_values.add(value_str)

        # Return sorted list
        return sorted(list(unique_values))

    def _on_column_moved(self, logical_index, old_visual_index, new_visual_index):
        """Handle column reorder event and save the new order."""
        # Get the current visual order of columns
        column_order = self._get_current_column_order()

        # Save to settings
        self.app_settings.set_column_order("vfx_breakdown", column_order)

        logger.info(f"Column moved: {self.model.column_fields[logical_index]} from position {old_visual_index} to {new_visual_index}")

    def _get_current_column_order(self):
        """Get the current visual order of columns.

        Returns:
            list: Field names in their current visual order
        """
        if not self.table_view:
            return self.model.column_fields

        header = self.table_view.horizontalHeader()
        order = []

        # Get fields in visual order
        for visual_index in range(len(self.model.column_fields)):
            logical_index = header.logicalIndex(visual_index)
            if 0 <= logical_index < len(self.model.column_fields):
                order.append(self.model.column_fields[logical_index])

        return order

    def _load_column_order(self):
        """Load and apply saved column order."""
        saved_order = self.app_settings.get_column_order("vfx_breakdown")

        if not saved_order or not self.table_view:
            return

        header = self.table_view.horizontalHeader()

        # Block signals to avoid triggering sectionMoved
        header.blockSignals(True)

        try:
            # Build a map of field names to logical indices
            field_to_logical = {field: i for i, field in enumerate(self.model.column_fields)}

            # Move columns to match saved order
            for visual_index, field in enumerate(saved_order):
                if field in field_to_logical:
                    logical_index = field_to_logical[field]
                    current_visual_index = header.visualIndex(logical_index)

                    if current_visual_index != visual_index:
                        header.moveSection(current_visual_index, visual_index)

            logger.info(f"Loaded column order with {len(saved_order)} columns")

        finally:
            header.blockSignals(False)

    def _on_column_resized(self, logical_index, old_size, new_size):
        """Handle column resize event and save the new width."""
        if logical_index < 0 or logical_index >= len(self.model.column_fields):
            return

        field_name = self.model.column_fields[logical_index]

        # Get current widths
        widths = self._get_current_column_widths()

        # Save to settings
        self.app_settings.set_column_widths("vfx_breakdown", widths)

        logger.info(f"Column '{field_name}' resized from {old_size}px to {new_size}px")

    def _get_current_column_widths(self):
        """Get the current widths of all columns.

        Returns:
            dict: Mapping of field names to column widths in pixels
        """
        if not self.table_view:
            return {}

        widths = {}
        for logical_index, field_name in enumerate(self.model.column_fields):
            width = self.table_view.columnWidth(logical_index)
            widths[field_name] = width

        return widths

    def _load_column_widths(self):
        """Load and apply saved column widths."""
        saved_widths = self.app_settings.get_column_widths("vfx_breakdown")

        if not saved_widths or not self.table_view:
            return

        header = self.table_view.horizontalHeader()

        # Block signals to avoid triggering sectionResized
        header.blockSignals(True)

        try:
            # Apply saved widths to columns
            for logical_index, field_name in enumerate(self.model.column_fields):
                if field_name in saved_widths:
                    width = saved_widths[field_name]
                    self.table_view.setColumnWidth(logical_index, width)

            logger.info(f"Loaded column widths for {len(saved_widths)} columns")

        finally:
            header.blockSignals(False)

    def _apply_sort_template(self, template_name):
        """Apply a saved sort template."""
        if template_name == "(No Template)" or not template_name:
            if self.model.compound_sort_columns:
                self.model.clear_sorting()
                self._update_header_sort_indicators()
                logger.info("Compound sorting cleared")
            return

        templates = self.model.get_sort_templates()
        if template_name in templates:
            self.model.set_compound_sort(templates[template_name])
            self._update_header_sort_indicators()
            logger.info(f"Sort template applied: {template_name}")

    def _update_template_dropdown(self):
        """Update the template dropdown with current templates."""
        if not self.template_dropdown:
            return

        current_text = self.template_dropdown.currentText()
        self.template_dropdown.blockSignals(True)
        self.template_dropdown.clear()
        self.template_dropdown.addItem("(No Template)")

        templates = self.model.get_sort_templates()
        for template_name in sorted(templates.keys()):
            self.template_dropdown.addItem(template_name)

        # Try to restore previous selection
        index = self.template_dropdown.findText(current_text)
        if index >= 0:
            self.template_dropdown.setCurrentIndex(index)

        self.template_dropdown.blockSignals(False)

    def _on_row_header_clicked(self, row):
        """Handle row header click to select entire row."""
        self.table_view.selectRow(row)

    def _undo(self):
        """Undo the last change."""
        self.model.undo()

    def _redo(self):
        """Redo the last undone change."""
        self.model.redo()

    def _copy_selection(self):
        """Copy selected cells to clipboard."""
        selection = self.table_view.selectedIndexes()
        if not selection:
            return

        # Get bounding rectangle
        rows = set(idx.row() for idx in selection)
        cols = set(idx.column() for idx in selection)

        if not rows or not cols:
            return

        min_row = min(rows)
        max_row = max(rows)
        min_col = min(cols)
        max_col = max(cols)

        # Build clipboard text
        clipboard_text = []
        for row in range(min_row, max_row + 1):
            row_data = []
            for col in range(min_col, max_col + 1):
                index = self.model.index(row, col)
                field_name = self.model.column_fields[col]

                # For multi-entity fields like sg_bid_assets, use EditRole and serialize as JSON
                if field_name == "sg_bid_assets":
                    value = self.model.data(index, QtCore.Qt.EditRole)
                    if isinstance(value, list):
                        # Serialize entity list as JSON
                        text = json.dumps(value)
                    else:
                        text = ""
                else:
                    # For other fields, use DisplayRole
                    text = self.model.data(index, QtCore.Qt.DisplayRole) or ""

                row_data.append(text)
            clipboard_text.append("\t".join(row_data))

        final_text = "\n".join(clipboard_text)

        # Copy to clipboard
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(final_text)

        num_cells = len(rows) * len(cols)
        self.statusMessageChanged.emit(f"Copied {num_cells} cell(s) to clipboard", False)
        logger.info(f"Copied {len(rows)} row(s) × {len(cols)} col(s) to clipboard")

    def _paste_selection(self):
        """Paste from clipboard to selected cells."""
        clipboard = QtWidgets.QApplication.clipboard()
        text = clipboard.text()

        if not text:
            return

        # Parse clipboard
        rows_data = text.split("\n")
        if rows_data and rows_data[-1] == "":
            rows_data = rows_data[:-1]

        is_single_value = len(rows_data) == 1 and "\t" not in rows_data[0]

        # Collect changes
        changes = []
        selected_indexes = self.table_view.selectedIndexes()

        # Single value to multiple cells
        if is_single_value and len(selected_indexes) > 1:
            paste_value = rows_data[0]
            for index in selected_indexes:
                if not (self.model.flags(index) & QtCore.Qt.ItemIsEditable):
                    continue

                field_name = self.model.column_fields[index.column()]

                # For multi-entity fields, try to parse JSON
                if field_name == "sg_bid_assets":
                    try:
                        parsed_value = json.loads(paste_value) if paste_value else []
                    except (json.JSONDecodeError, ValueError):
                        logger.warning(f"Failed to parse JSON for sg_bid_assets: {paste_value}")
                        continue
                    new_value = parsed_value
                    old_value = self.model.data(index, QtCore.Qt.EditRole) or []
                else:
                    new_value = paste_value
                    old_value = self.model.data(index, QtCore.Qt.EditRole) or ""

                if new_value == old_value:
                    continue

                bidding_scene_data = self.model.get_bidding_scene_data_for_row(index.row())
                if not bidding_scene_data:
                    continue

                changes.append({
                    'row': index.row(),
                    'col': index.column(),
                    'old_value': old_value,
                    'new_value': new_value,
                    'bidding_scene_data': bidding_scene_data,
                    'field_name': field_name
                })

        else:
            # Standard paste
            current_index = self.table_view.currentIndex()
            if not current_index.isValid():
                return

            start_row = current_index.row()
            start_col = current_index.column()

            for row_offset, row_text in enumerate(rows_data):
                cells = row_text.split("\t")
                for col_offset, cell_value in enumerate(cells):
                    target_row = start_row + row_offset
                    target_col = start_col + col_offset

                    if target_row >= self.model.rowCount():
                        break
                    if target_col >= self.model.columnCount():
                        continue

                    index = self.model.index(target_row, target_col)
                    if not (self.model.flags(index) & QtCore.Qt.ItemIsEditable):
                        continue

                    field_name = self.model.column_fields[target_col]

                    # For multi-entity fields, try to parse JSON
                    if field_name == "sg_bid_assets":
                        try:
                            parsed_value = json.loads(cell_value) if cell_value else []
                        except (json.JSONDecodeError, ValueError):
                            logger.warning(f"Failed to parse JSON for sg_bid_assets: {cell_value}")
                            continue
                        new_value = parsed_value
                        old_value = self.model.data(index, QtCore.Qt.EditRole) or []
                    else:
                        new_value = cell_value
                        old_value = self.model.data(index, QtCore.Qt.EditRole) or ""

                    if new_value == old_value:
                        continue

                    bidding_scene_data = self.model.get_bidding_scene_data_for_row(target_row)
                    if not bidding_scene_data:
                        continue

                    changes.append({
                        'row': target_row,
                        'col': target_col,
                        'old_value': old_value,
                        'new_value': new_value,
                        'bidding_scene_data': bidding_scene_data,
                        'field_name': field_name
                    })

        if not changes:
            self.statusMessageChanged.emit("No changes to paste", False)
            return

        # Create paste command
        command = PasteCommand(changes, self.model, self.sg_session, field_schema=self.model.field_schema, entity_type=self.model.entity_type)

        try:
            # Execute paste
            command.redo()

            # Add to undo stack
            self.model.undo_stack.append(command)
            self.model.redo_stack.clear()

            self.statusMessageChanged.emit(f"✓ Pasted {len(changes)} cell(s) to ShotGrid", False)
            logger.info(f"Successfully pasted {len(changes)} cells")

        except Exception as e:
            logger.error(f"Failed to paste cells: {e}", exc_info=True)
            self.statusMessageChanged.emit(f"Failed to paste cells", True)
            QtWidgets.QMessageBox.critical(
                self,
                "Paste Failed",
                f"Failed to paste cells:\n{str(e)}"
            )

    def _on_context_menu(self, position):
        """Handle right-click context menu."""
        index = self.table_view.indexAt(position)
        if not index.isValid():
            return

        row = index.row()

        # Create context menu
        menu = QtWidgets.QMenu(self)

        # Add bidding scene above
        add_above_action = menu.addAction("Add Bidding Scene Above")
        add_above_action.triggered.connect(lambda: self._add_bidding_scene_above(row))

        # Add bidding scene below
        add_below_action = menu.addAction("Add Bidding Scene Below")
        add_below_action.triggered.connect(lambda: self._add_bidding_scene_below(row))

        menu.addSeparator()

        # Delete bidding scene
        delete_action = menu.addAction("Delete Bidding Scene")
        delete_action.triggered.connect(lambda: self._delete_bidding_scene(row))

        # Show menu
        menu.exec(self.table_view.viewport().mapToGlobal(position))

    def _add_bidding_scene_above(self, row):
        """Add a new bidding scene above the specified row."""
        # This requires access to parent context (project, breakdown, etc.)
        # Signal to parent to handle
        self.statusMessageChanged.emit("Add bidding scene functionality requires parent tab context", False)

    def _add_bidding_scene_below(self, row):
        """Add a new bidding scene below the specified row."""
        # This requires access to parent context
        self.statusMessageChanged.emit("Add bidding scene functionality requires parent tab context", False)

    def _delete_bidding_scene(self, row):
        """Delete the specified bidding scene."""
        # This requires access to parent context
        self.statusMessageChanged.emit("Delete bidding scene functionality requires parent tab context", False)

    def _autosize_columns(self, min_px=80, max_px=700, extra_padding=28):
        """Auto-size columns to fit content.

        For text columns, limits width to 200 characters or the longest string if shorter.
        """
        if not self.table_view or self.model.rowCount() == 0:
            return

        # First, use Qt's built-in resize to content
        self.table_view.resizeColumnsToContents()

        fm = self.table_view.fontMetrics()

        # Calculate width of 200 characters for text column limit
        sample_text = "M" * 200  # Use 'M' as it's typically the widest character
        text_column_max_px = fm.horizontalAdvance(sample_text) + extra_padding

        logger.info(f"Auto-sizing {self.model.columnCount()} columns for {self.model.rowCount()} rows")

        # Now apply our constraints on top
        for col in range(self.model.columnCount()):
            # Get field information
            field_name = self.model.column_fields[col] if col < len(self.model.column_fields) else None
            is_text_field = False
            data_type = "unknown"

            # Check if this is a text field
            if field_name and hasattr(self.model, 'field_schema') and self.model.field_schema:
                field_info = self.model.field_schema.get(field_name, {})
                data_type = field_info.get("data_type", "")
                is_text_field = data_type in ["text", "multi_entity"]

            # Get current width after resizeColumnsToContents
            current_width = self.table_view.columnWidth(col)

            # Apply constraints
            if is_text_field:
                # For text fields, cap at 200 characters
                if current_width > text_column_max_px:
                    self.table_view.setColumnWidth(col, text_column_max_px)
                    logger.info(f"Column {col} ({field_name}): text field capped at {text_column_max_px}px (~200 chars), was {current_width}px")
                elif current_width < min_px:
                    self.table_view.setColumnWidth(col, min_px)
                    logger.info(f"Column {col} ({field_name}): text field expanded to min {min_px}px")
                else:
                    logger.info(f"Column {col} ({field_name}): text field at {current_width}px")
            else:
                # For other fields, use standard constraints
                if current_width > max_px:
                    self.table_view.setColumnWidth(col, max_px)
                    logger.debug(f"Column {col} ({field_name}, {data_type}): capped at {max_px}px, was {current_width}px")
                elif current_width < min_px:
                    self.table_view.setColumnWidth(col, min_px)
                    logger.debug(f"Column {col} ({field_name}, {data_type}): expanded to min {min_px}px")
                else:
                    logger.debug(f"Column {col} ({field_name}, {data_type}): at {current_width}px")


    def _on_model_status_changed(self, message, is_error):
        """Handle status message from model."""
        self.statusMessageChanged.emit(message, is_error)

    def _on_model_row_count_changed(self, shown_rows, total_rows):
        """Handle row count change from model."""
        if self.row_count_label:
            self.row_count_label.setText(f"Showing {shown_rows} of {total_rows} rows")

    def _on_model_data_changed(self, top_left, bottom_right, roles):
        """Handle data changes from model (e.g., during undo/redo).

        Args:
            top_left: Top-left QModelIndex of changed region
            bottom_right: Bottom-right QModelIndex of changed region
            roles: List of changed roles
        """
        # Check if any of the changed cells are sg_bid_assets columns
        try:
            assets_col_idx = self.model.column_fields.index("sg_bid_assets")
        except ValueError:
            # Column not present in this table
            return

        # Update widgets for all changed sg_bid_assets cells
        for row in range(top_left.row(), bottom_right.row() + 1):
            for col in range(top_left.column(), bottom_right.column() + 1):
                if col == assets_col_idx:
                    # Get the widget for this cell
                    index = self.model.index(row, col)
                    widget = self.table_view.indexWidget(index)

                    if isinstance(widget, MultiEntityReferenceWidget):
                        # Get the updated entities from the model
                        data_row = self.model.filtered_row_indices[row]
                        bidding_scene_data = self.model.all_bidding_scenes_data[data_row]
                        entities = bidding_scene_data.get("sg_bid_assets", [])
                        if not isinstance(entities, list):
                            entities = [entities] if entities else []

                        # Update the widget with the new entities
                        widget.set_entities(entities)
                        logger.info(f"Refreshed sg_bid_assets widget for row {row} after data change")
