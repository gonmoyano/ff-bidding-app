"""
VFX Breakdown Widget
Reusable widget component for displaying and editing VFX bidding scenes data using Qt Model/View pattern.
"""

from PySide6 import QtWidgets, QtCore, QtGui
import logging
import json
import re

try:
    from .logger import logger
    from .vfx_breakdown_model import VFXBreakdownModel, PasteCommand, CheckBoxDelegate
    from .settings import AppSettings
    from .multi_entity_reference_widget import MultiEntityReferenceWidget
    from .formula_evaluator import FormulaEvaluator
    from .bid_selector_widget import CollapsibleGroupBox
except ImportError:
    logger = logging.getLogger("FFPackageManager")
    from vfx_breakdown_model import VFXBreakdownModel, PasteCommand, CheckBoxDelegate
    from settings import AppSettings
    from multi_entity_reference_widget import MultiEntityReferenceWidget
    from formula_evaluator import FormulaEvaluator
    from bid_selector_widget import CollapsibleGroupBox


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


class FormulaDelegate(NoElideDelegate):
    """Delegate for editing formula cells - displays calculated value, edits formula."""

    def __init__(self, formula_evaluator, app_settings=None, parent=None):
        super().__init__(parent)
        self.formula_evaluator = formula_evaluator
        self.app_settings = app_settings

    def _get_currency_symbol(self):
        """Get the current currency symbol from app settings."""
        if self.app_settings:
            symbol = self.app_settings.get_currency()
            return symbol if symbol else ""
        return ""

    def paint(self, painter, option, index):
        """Paint the cell with calculated value."""
        # Get the value
        value = index.model().data(index, QtCore.Qt.DisplayRole)

        # Get background color from model and apply it
        bg_color = index.data(QtCore.Qt.BackgroundRole)
        if bg_color:
            painter.fillRect(option.rect, bg_color)

        # If it's a formula, show the calculated result
        if isinstance(value, str) and value.startswith('='):
            try:
                # Pass row and col for circular reference detection
                result = self.formula_evaluator.evaluate(value, index.row(), index.column())
                # Format the result
                if isinstance(result, float):
                    currency_symbol = self._get_currency_symbol()
                    display_text = f"{currency_symbol}{result:,.2f}"
                elif isinstance(result, int):
                    currency_symbol = self._get_currency_symbol()
                    display_text = f"{currency_symbol}{result:,.2f}"
                else:
                    display_text = str(result)

                # Set text color based on result type
                if isinstance(result, str) and (result.startswith('#ERROR') or result.startswith('#CIRCULAR') or result.startswith('#PARSE') or result.startswith('#NOT_SUPPORTED')):
                    option.palette.setColor(QtGui.QPalette.Text, QtGui.QColor("#ff6b6b"))
                else:
                    # Right-align numbers
                    option.displayAlignment = QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter

                # Create a new option with the calculated value
                new_option = QtWidgets.QStyleOptionViewItem(option)
                new_option.text = display_text
                QtWidgets.QApplication.style().drawControl(
                    QtWidgets.QStyle.CE_ItemViewItem, new_option, painter
                )
                return
            except Exception as e:
                # Continue with default painting on error
                pass

        # Default painting
        super().paint(painter, option, index)

    def displayText(self, value, locale):
        """Display the calculated value instead of the formula."""
        if not value:
            return ""

        # If it's a formula, evaluate and display the result
        if isinstance(value, str) and value.startswith('='):
            try:
                result = self.formula_evaluator.evaluate(value)
                # Format the result nicely
                if isinstance(result, (float, int)):
                    currency_symbol = self._get_currency_symbol()
                    return f"{currency_symbol}{result:,.2f}"
                return str(result)
            except Exception as e:
                return "#ERROR"

        return str(value)

    def createEditor(self, parent, option, index):
        """Create a line edit for formula editing."""
        editor = QtWidgets.QLineEdit(parent)
        editor.setFrame(False)
        editor.setStyleSheet("""
            QLineEdit {
                background-color: #ffffff;
                color: #000000;
                padding: 2px;
                border: 2px solid #0078d4;
            }
        """)
        return editor

    def setEditorData(self, editor, index):
        """Set the editor to show the formula, not the calculated value."""
        value = index.model().data(index, QtCore.Qt.EditRole)
        if value is None:
            value = ""
        editor.setText(str(value))

    def setModelData(self, editor, model, index):
        """Save the formula to the model."""
        formula = editor.text()
        model.setData(index, formula, QtCore.Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        """Update the editor geometry."""
        editor.setGeometry(option.rect)


class ConfigColumnsDialog(QtWidgets.QDialog):
    """Dialog for configuring column visibility and dropdown lists in VFX Breakdown table."""

    def __init__(self, column_fields, column_headers, current_visibility, current_dropdowns,
                 on_visibility_changed=None, on_dropdown_changed=None, parent=None):
        """Initialize the dialog.

        Args:
            column_fields: List of field names
            column_headers: List of display names for the fields
            current_visibility: Dictionary mapping field names to visibility (bool)
            current_dropdowns: Dictionary mapping field names to dropdown enabled (bool)
            on_visibility_changed: Callback function(field, is_visible) called when visibility changes
            on_dropdown_changed: Callback function(field, has_dropdown) called when dropdown setting changes
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Configure Columns")
        self.setModal(True)

        self.column_fields = column_fields
        self.column_headers = column_headers
        self.visibility_checkboxes = {}
        self.dropdown_checkboxes = {}
        self.on_visibility_changed = on_visibility_changed
        self.on_dropdown_changed = on_dropdown_changed

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

            # Connect to callbacks for immediate application
            if self.on_visibility_changed:
                visible_checkbox.toggled.connect(
                    lambda checked, f=field: self.on_visibility_changed(f, checked)
                )
            if self.on_dropdown_changed:
                dropdown_checkbox.toggled.connect(
                    lambda checked, f=field: self.on_dropdown_changed(f, checked)
                )

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

        # Close button (changes are applied immediately)
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()

        self.close_button = QtWidgets.QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        self.close_button.setDefault(True)
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

    def _create_custom_checkbox(self, checked=False):
        """Create a checkbox with custom tick icon indicator.

        Args:
            checked: Initial checked state

        Returns:
            tuple: (indicator_label, checkbox)
        """
        # Get DPI scale factor from settings
        dpi_scale = self.app_settings.get_dpi_scale() if hasattr(self, 'app_settings') else 1.0
        indicator_size = int(20 * dpi_scale)

        # Custom checkbox indicator
        indicator_label = QtWidgets.QLabel()
        indicator_label.setFixedSize(indicator_size, indicator_size)
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
        # Scale all visual elements
        border_width = max(1, int(2 * dpi_scale))
        border_radius = max(2, int(3 * dpi_scale))
        font_size = max(10, int(16 * dpi_scale))

        def update_indicator(is_checked):
            if is_checked:
                # Checked state: show tick icon
                indicator_label.setStyleSheet(f"""
                    QLabel {{
                        border: {border_width}px solid #0078d4;
                        border-radius: {border_radius}px;
                        background-color: #2b2b2b;
                        color: #0078d4;
                        font-size: {font_size}px;
                        font-weight: bold;
                    }}
                """)
                indicator_label.setText("✓")
            else:
                # Unchecked state: empty box
                indicator_label.setStyleSheet(f"""
                    QLabel {{
                        border: {border_width}px solid #555;
                        border-radius: {border_radius}px;
                        background-color: #2b2b2b;
                    }}
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

    def __init__(self, sg_session, show_toolbar=True, entity_name="Bidding Scene", settings_key="vfx_breakdown", parent=None):
        """Initialize the widget.

        Args:
            sg_session: ShotGrid session for API access
            show_toolbar: Whether to show the search/filter toolbar
            entity_name: Display name for the entity type in context menus (default: "Bidding Scene")
            settings_key: Unique key for saving/loading settings (default: "vfx_breakdown")
            parent: Parent widget
        """
        super().__init__(parent)
        self.sg_session = sg_session
        self.show_toolbar = show_toolbar
        self.entity_name = entity_name  # Entity display name for context menus
        self.settings_key = settings_key  # Unique settings key for this widget instance
        self.current_bid = None  # Store reference to current Bid
        self.current_breakdown = None  # Store reference to current VFX Breakdown (for adding rows)
        self.current_bid_assets = None  # Store reference to current Bid Assets (for adding asset items)
        self._asset_menu_open = False  # Guard to prevent re-entry
        self.context_provider = None  # Widget that provides context (price_list_id, project_id, etc.)

        # Pending unsaved item save (debounced)
        self._pending_unsaved_save = None  # (data_row, name) tuple
        self._unsaved_save_timer = QtCore.QTimer()
        self._unsaved_save_timer.setSingleShot(True)
        self._unsaved_save_timer.timeout.connect(self._process_pending_unsaved_save)

        # Create the model
        self.model = VFXBreakdownModel(sg_session, parent=self)

        # Connect model signals
        self.model.statusMessageChanged.connect(self._on_model_status_changed)
        self.model.rowCountChanged.connect(self._on_model_row_count_changed)
        self.model.dataChanged.connect(self._on_model_data_changed)
        self.model.modelReset.connect(self._on_model_reset)

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
        # Create toolbar widget that parent can add to their own layouts
        self.toolbar_widget = None
        if self.show_toolbar:
            # Create a container widget for the toolbar contents
            self.toolbar_widget = QtWidgets.QWidget()
            toolbar_layout = QtWidgets.QHBoxLayout(self.toolbar_widget)
            toolbar_layout.setContentsMargins(0, 0, 0, 0)

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

        # Enable tooltips for column headers (shows column letter for calculated fields)
        h_header.setToolTip("")  # Enable tooltip support
        h_header.viewport().setMouseTracking(True)  # Required for tooltips to work

        v_header = self.table_view.verticalHeader()
        v_header.sectionClicked.connect(self._on_row_header_clicked)
        v_header.sectionResized.connect(self._on_row_resized)

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


    def eventFilter(self, obj, event):
        """Event filter to handle Enter/Delete keys and double-clicks on index widgets."""
        # Handle double-click on MultiEntityReferenceWidget (sg_bid_assets cells)
        if isinstance(obj, MultiEntityReferenceWidget) and event.type() == QtCore.QEvent.MouseButtonDblClick:
            # Get the stored model index
            index = obj.property("modelIndex")
            if index and index.isValid():
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
            for col_idx, field_name in enumerate(self.model.column_fields):
                if field_name in field_schema:
                    field_info = field_schema[field_name]
                    data_type = field_info.get("data_type")
                    if data_type == "list":
                        list_values = field_info.get("list_values", [])

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
        saved_widths = self.app_settings.get_column_widths(self.settings_key)

        if saved_widths:
            # If we have saved widths, use them (skip auto-sizing)
            self._load_column_widths()
        else:
            # First time: auto-size columns to content
            self._autosize_columns()
            # Save the auto-sized widths so they persist
            widths = self._get_current_column_widths()
            self.app_settings.set_column_widths(self.settings_key, widths)

        # Apply dropdown delegates to columns marked for dropdowns
        self._apply_column_dropdowns()

        # Note: VFX Shot Work delegate is applied by VFXBreakdownTab after this method

        # Set up MultiEntityReferenceWidget for sg_bid_assets column
        self._setup_bid_assets_widgets()

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

        if len(unique_entities) < len(entities):
            pass

        return unique_entities

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

        # Create widget for each row
        for row in range(self.model.rowCount()):
            # Get the model index for this cell
            index = self.model.index(row, assets_col_idx)

            # Check if widget already exists - if so, skip recreation
            existing_widget = self.table_view.indexWidget(index)
            if isinstance(existing_widget, MultiEntityReferenceWidget):
                continue

            # Get the actual data row index
            data_row = self.model.filtered_row_indices[row]
            bidding_scene_data = self.model.all_bidding_scenes_data[data_row]

            # Get current entities for this row
            entities = bidding_scene_data.get("sg_bid_assets", [])
            if not isinstance(entities, list):
                entities = [entities] if entities else []

            # Deduplicate entities by ID before creating widget
            entities = self._deduplicate_entities(entities)

            # Update the model data with deduplicated entities
            if entities != bidding_scene_data.get("sg_bid_assets", []):
                bidding_scene_data["sg_bid_assets"] = entities

            # Create the widget with validation
            widget = MultiEntityReferenceWidget(
                entities=entities,
                allow_add=False,
                valid_entity_ids=valid_entity_ids
            )
            # Set height to match current row height setting
            current_row_height = self.app_settings.get("vfx_breakdown_row_height", 80)
            widget.setFixedHeight(current_row_height)
            # Explicitly update pill heights for the initial height
            widget.update_for_height(current_row_height)

            # Connect signal to update model when entities change
            # Use functools.partial to properly bind the widget so we can look up its position dynamically
            widget.entitiesChanged.connect(
                lambda ents, w=widget: self._on_bid_assets_changed_from_widget(w, ents)
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

    def _on_bid_assets_changed_from_widget(self, widget, entities):
        """Handle when bid assets are changed in a cell widget, looking up position dynamically.

        Args:
            widget: The MultiEntityReferenceWidget that emitted the signal
            entities: Updated list of entity dicts
        """
        # Find the widget's current position in the table by searching all cells
        try:
            assets_col_idx = self.model.column_fields.index("sg_bid_assets")
        except ValueError:
            logger.error("sg_bid_assets column not found")
            return

        # Search for the widget in the table
        row = None
        for r in range(self.model.rowCount()):
            index = self.model.index(r, assets_col_idx)
            if self.table_view.indexWidget(index) == widget:
                row = r
                break

        if row is None:
            logger.error("Could not find widget in table")
            return

        # Now call the original handler with the correct current row
        self._on_bid_assets_changed(row, assets_col_idx, entities)

    def _on_bid_assets_changed(self, row, col, entities):
        """Handle when bid assets are changed in a cell widget.

        Args:
            row: Table row index
            col: Column index
            entities: Updated list of entity dicts
        """
        # Deduplicate entities before saving
        entities = self._deduplicate_entities(entities)

        # Get the model index
        index = self.model.index(row, col)

        # Update the model data
        # The model expects the list of entity dicts
        self.model.setData(index, entities, QtCore.Qt.EditRole)


    def set_current_bid(self, bid):
        """Set the current Bid for this widget.

        Args:
            bid: Bid dictionary from ShotGrid
        """
        self.current_bid = bid

        # Refresh asset widgets with new validation when bid changes
        self._refresh_asset_widgets_validation()

    def set_current_breakdown(self, breakdown):
        """Set the current VFX Breakdown for this widget.

        This is required for adding new rows to the breakdown.

        Args:
            breakdown: VFX Breakdown dictionary from ShotGrid with 'id', 'type', 'code' keys
        """
        self.current_breakdown = breakdown

    def set_current_bid_assets(self, bid_assets):
        """Set the current Bid Assets for this widget.

        This is required for adding new asset items to the Bid Assets.

        Args:
            bid_assets: Bid Assets dictionary from ShotGrid with 'id', 'type', 'code' keys
        """
        self.current_bid_assets = bid_assets

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

        # Update all existing asset widgets
        for row in range(self.model.rowCount()):
            index = self.model.index(row, assets_col_idx)
            widget = self.table_view.indexWidget(index)

            if isinstance(widget, MultiEntityReferenceWidget):
                # Update the validation IDs for this widget
                widget.set_valid_entity_ids(valid_entity_ids)

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
                        widget.set_selected(False)

        # Update selected widgets
        for index in selected.indexes():
            if index.column() < len(self.model.column_fields):
                field_name = self.model.column_fields[index.column()]
                if field_name == "sg_bid_assets":
                    widget = self.table_view.indexWidget(index)
                    if isinstance(widget, MultiEntityReferenceWidget):
                        widget.set_selected(True)

    def _on_cell_double_clicked(self, index):
        """Handle double-click on a cell.

        Shows a dropdown menu for:
            pass
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
                if list_values:
                    self._show_list_selection_menu(index, field_name, list_values)
                    return
                else:
                    logger.warning(f"List field {field_name} has no list_values")
            else:
                pass
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
                return

            # Persist selected value (may be None for cleared option)
            if selected_value is None:
                self.model.setData(index, None, QtCore.Qt.EditRole)
            else:
                self.model.setData(index, selected_value, QtCore.Qt.EditRole)

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

            return assets

        except Exception as e:
            logger.error(f"Failed to query Asset items: {e}", exc_info=True)
            return []

    def _get_valid_asset_ids(self):
        """Get the set of valid asset names from the current bid's Assets tab.

        Returns:
            set: Set of asset names (strings) that are valid for the current bid.
                 Returns None if no bid is selected (meaning all assets are valid/no validation).
        Note:
            Despite the method name, this returns names for name-based matching,
            allowing assets to be validated across different Bid Assets versions.
        """
        if not self.current_bid:
            # No bid selected - no validation
            return None

        # Get all assets from the current bid
        assets = self._get_available_bid_assets()

        # Extract names into a set (use 'code' first, then 'name' as fallback)
        valid_names = set()
        for asset in assets:
            name = asset.get('code') or asset.get('name')
            if name:
                valid_names.add(name)

        return valid_names

    def clear_data(self):
        """Clear all data from the widget."""
        self.model.clear_data()
        if self.row_count_label:
            self.row_count_label.setText("Showing 0 of 0 rows")

    def update_column_widths_for_dpi(self):
        """Update column widths based on current DPI scale."""
        if self.model.rowCount() > 0:
            # Recalculate column widths with new DPI scale
            self._autosize_columns()

    def _on_search_changed(self, text):
        """Handle search text change."""
        self.model.set_global_search(text)

    def _on_header_clicked(self, column_index):
        """Handle header click for sorting."""
        # Block single-column sorting if compound sorting is active
        if self.model.compound_sort_columns:
            return

        # Toggle sort direction
        if self.model.sort_column == column_index:
            direction = "desc" if self.model.sort_direction == "asc" else "asc"
        else:
            direction = "asc"

        self.model.set_sort(column_index, direction)
        self._update_header_sort_indicators()


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

        # Define callback functions for immediate application
        def on_visibility_changed(field, is_visible):
            """Called when a visibility checkbox is toggled."""
            self.column_visibility[field] = is_visible
            # Apply the change immediately
            col_index = self.model.column_fields.index(field)
            self.table_view.setColumnHidden(col_index, not is_visible)

            # Link Price and Line Item Price column visibility
            # When one is hidden, the other should also be hidden
            if field == '_calc_price' and '_line_item_price' in self.model.column_fields:
                try:
                    line_item_idx = self.model.column_fields.index('_line_item_price')
                    self.column_visibility['_line_item_price'] = is_visible
                    self.table_view.setColumnHidden(line_item_idx, not is_visible)
                    logger.info(f"Linked visibility: {'showing' if is_visible else 'hiding'} Line Item Price with Price column")
                except ValueError:
                    pass
            elif field == '_line_item_price' and '_calc_price' in self.model.column_fields:
                try:
                    calc_price_idx = self.model.column_fields.index('_calc_price')
                    self.column_visibility['_calc_price'] = is_visible
                    self.table_view.setColumnHidden(calc_price_idx, not is_visible)
                    logger.info(f"Linked visibility: {'showing' if is_visible else 'hiding'} Price with Line Item Price column")
                except ValueError:
                    pass

            # Save to settings
            self.app_settings.set_column_visibility(self.settings_key, self.column_visibility)

        def on_dropdown_changed(field, has_dropdown):
            """Called when a dropdown checkbox is toggled."""
            self.column_dropdowns[field] = has_dropdown
            # Apply the change immediately
            self._apply_column_dropdowns()
            # Save to settings
            self.app_settings.set_column_dropdowns(self.settings_key, self.column_dropdowns)

        # Open dialog with columns in visual order and callbacks
        dialog = ConfigColumnsDialog(
            column_fields=ordered_fields,
            column_headers=ordered_headers,
            current_visibility=current_visibility,
            current_dropdowns=current_dropdowns,
            on_visibility_changed=on_visibility_changed,
            on_dropdown_changed=on_dropdown_changed,
            parent=self
        )

        # Just execute the dialog - changes are already applied via callbacks
        dialog.exec_()

    def _load_column_visibility(self):
        """Load column visibility settings from AppSettings."""
        saved_visibility = self.app_settings.get_column_visibility(self.settings_key)

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
        saved_dropdowns = self.app_settings.get_column_dropdowns(self.settings_key)

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
                        # Explicitly update pill heights (resize event may not fire immediately)
                        if hasattr(widget, 'update_for_height'):
                            widget.update_for_height(saved_height)
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
                        # Explicitly update pill heights (resize event may not fire immediately)
                        if hasattr(widget, 'update_for_height'):
                            widget.update_for_height(value)
                        widget.updateGeometry()

                    # Force the row to resize
                    v_header.resizeSection(row, value)
            except (ValueError, AttributeError):
                # Column not present or other issue - skip widget updates
                pass

        # Save to settings
        self.app_settings.set("vfx_breakdown_row_height", value)

    def _on_row_resized(self, row, old_size, new_size):
        """Handle individual row resize (e.g., when user drags row edge)."""
        if not self.table_view:
            return

        # Get the current default row height from slider (this is the pill's current height)
        default_row_height = self.app_settings.get("vfx_breakdown_row_height", 80)

        # If trying to resize smaller than the default pill height, force row back to default
        if new_size < default_row_height:
            v_header = self.table_view.verticalHeader()
            v_header.resizeSection(row, default_row_height)
            return  # The signal will fire again with the corrected size

        # Update pill widget height when row is made larger (expanding beyond default)
        try:
            assets_col_idx = self.model.column_fields.index("sg_bid_assets")
            index = self.model.index(row, assets_col_idx)
            widget = self.table_view.indexWidget(index)
            if widget:
                # Update widget height to match row height
                widget.setMinimumHeight(new_size)
                widget.setMaximumHeight(new_size)
                widget.setFixedHeight(new_size)
                # Update pill heights when expanding beyond default
                if hasattr(widget, 'update_for_height'):
                    widget.update_for_height(new_size)
                widget.updateGeometry()
        except (ValueError, AttributeError):
            # Column not present or other issue - skip widget updates
            pass

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
        header = self.table_view.horizontalHeader()

        # Prevent moving virtual price columns - they should stay at the end
        if logical_index < len(self.model.column_fields):
            field_name = self.model.column_fields[logical_index]
            if field_name in ('_calc_price', '_line_item_price'):
                # Restore the original position
                header.moveSection(new_visual_index, old_visual_index)
                logger.info(f"Prevented moving {field_name} column - it must stay at the end")
                return

        # Prevent moving other columns after the virtual price columns
        # Find the visual indices of the price columns
        calc_price_idx = -1
        line_item_price_idx = -1

        try:
            calc_price_logical = self.model.column_fields.index('_calc_price')
            calc_price_idx = header.visualIndex(calc_price_logical)
        except (ValueError, AttributeError):
            pass

        try:
            line_item_price_logical = self.model.column_fields.index('_line_item_price')
            line_item_price_idx = header.visualIndex(line_item_price_logical)
        except (ValueError, AttributeError):
            pass

        # Get the minimum visual index of price columns (they should be at the end)
        min_price_visual_idx = min([idx for idx in [calc_price_idx, line_item_price_idx] if idx >= 0], default=-1)

        # If trying to move a non-price column to a position at or after the price columns, prevent it
        if min_price_visual_idx >= 0 and new_visual_index >= min_price_visual_idx:
            header.moveSection(new_visual_index, old_visual_index)
            logger.info(f"Prevented moving column to position after price columns")
            return

        # Get the current visual order of columns
        column_order = self._get_current_column_order()

        # Save to settings
        self.app_settings.set_column_order(self.settings_key, column_order)


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
        saved_order = self.app_settings.get_column_order(self.settings_key)

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
        self.app_settings.set_column_widths(self.settings_key, widths)


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
        saved_widths = self.app_settings.get_column_widths(self.settings_key)

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


        finally:
            header.blockSignals(False)

    def _apply_sort_template(self, template_name):
        """Apply a saved sort template."""
        if template_name == "(No Template)" or not template_name:
            if self.model.compound_sort_columns:
                self.model.clear_sorting()
                self._update_header_sort_indicators()
            return

        templates = self.model.get_sort_templates()
        if template_name in templates:
            self.model.set_compound_sort(templates[template_name])
            self._update_header_sort_indicators()

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
        col = index.column()

        # Create context menu
        menu = QtWidgets.QMenu(self)

        # Check if this is the Export to Excel column
        field_name = self.model.column_fields[col] if col < len(self.model.column_fields) else None
        if field_name == "_export_to_excel":
            # Special context menu for Export column
            select_all_action = menu.addAction("Select All for Export")
            select_all_action.triggered.connect(self.model.select_all_for_export)

            deselect_all_action = menu.addAction("Deselect All for Export")
            deselect_all_action.triggered.connect(self.model.deselect_all_for_export)
        else:
            # For Line Items (CustomEntity03), show simplified menu
            if self.model.entity_type == "CustomEntity03":
                # Add Line Item (no above/below, just add)
                add_action = menu.addAction(f"Add {self.entity_name}")
                add_action.triggered.connect(lambda: self._add_line_item_local(row))

                menu.addSeparator()

                # Delete item
                delete_action = menu.addAction(f"Delete {self.entity_name}")
                delete_action.triggered.connect(lambda: self._delete_bidding_scene(row))
            else:
                # For other entity types (CustomEntity02 - Bidding Scenes)
                # Add row at the end
                add_row_action = menu.addAction(f"Add Row")
                add_row_action.triggered.connect(self._add_row)

                menu.addSeparator()

                # Delete item
                delete_action = menu.addAction(f"Delete {self.entity_name}")
                delete_action.triggered.connect(lambda: self._delete_bidding_scene(row))

        # Show menu
        menu.exec(self.table_view.viewport().mapToGlobal(position))

    def _add_bidding_scene_above(self, row):
        """Add a new item above the specified row."""
        entity_type = self.model.entity_type

        if entity_type == "CustomEntity03":
            # Line Items - we can handle this directly
            self._add_line_item_above(row)
        else:
            # Other types require parent context
            self.statusMessageChanged.emit(f"Add {self.entity_name} functionality requires parent tab context", False)

    def _add_bidding_scene_below(self, row):
        """Add a new item below the specified row."""
        entity_type = self.model.entity_type

        if entity_type == "CustomEntity03":
            # Line Items - we can handle this directly
            self._add_line_item_below(row)
        else:
            # Other types require parent context
            self.statusMessageChanged.emit(f"Add {self.entity_name} functionality requires parent tab context", False)

    def _add_row(self):
        """Add a new row at the end of the table and save to ShotGrid.

        Supports:
        - CustomEntity02 (Bidding Scenes) linked to VFX Breakdown
        - CustomEntity07 (Asset Items) linked to Bid Assets
        """
        entity_type = self.model.entity_type

        if entity_type == "CustomEntity02":
            self._add_bidding_scene_row()
        elif entity_type == "CustomEntity07":
            self._add_asset_item_row()
        else:
            self.statusMessageChanged.emit(f"Add Row not supported for {self.entity_name}", False)

    def _add_bidding_scene_row(self):
        """Add a new Bidding Scene (CustomEntity02) row linked to current breakdown."""
        # Check if we have a current breakdown to link to
        if not self.current_breakdown:
            QtWidgets.QMessageBox.warning(
                self,
                "No VFX Breakdown",
                "Please select a VFX Breakdown first before adding rows."
            )
            return

        breakdown_id = self.current_breakdown.get("id")
        breakdown_type = self.current_breakdown.get("type", "CustomEntity01")

        if not breakdown_id:
            QtWidgets.QMessageBox.warning(
                self,
                "Invalid Breakdown",
                "The current VFX Breakdown is invalid (no ID)."
            )
            return

        # Get project context
        project_id = self._get_project_id()
        if not project_id:
            QtWidgets.QMessageBox.warning(
                self,
                "No Project",
                "No project selected. Cannot add row."
            )
            return

        try:
            # Create new bidding scene data
            new_row_data = {
                "project": {"type": "Project", "id": project_id},
                "sg_parent": {"type": breakdown_type, "id": breakdown_id},
                "code": "New Row"
            }

            # Create in ShotGrid
            result = self.sg_session.sg.create("CustomEntity02", new_row_data)

            if not result:
                raise Exception("ShotGrid returned empty result")

            self._add_row_to_model(result)
            self.statusMessageChanged.emit(f"Added new row", False)

        except Exception as e:
            logger.error(f"Failed to add row: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to add row:\n{str(e)}"
            )
            self.statusMessageChanged.emit(f"Failed to add row: {str(e)}", True)

    def _add_asset_item_row(self):
        """Add a new Asset Item (CustomEntity07) row linked to current Bid Assets."""
        # Check if we have a current bid assets to link to
        if not self.current_bid_assets:
            QtWidgets.QMessageBox.warning(
                self,
                "No Bid Assets",
                "Please select a Bid Assets first before adding rows."
            )
            return

        bid_assets_id = self.current_bid_assets.get("id")

        if not bid_assets_id:
            QtWidgets.QMessageBox.warning(
                self,
                "Invalid Bid Assets",
                "The current Bid Assets is invalid (no ID)."
            )
            return

        # Get project context
        project_id = self._get_project_id()
        if not project_id:
            QtWidgets.QMessageBox.warning(
                self,
                "No Project",
                "No project selected. Cannot add row."
            )
            return

        try:
            # Create new asset item data
            new_row_data = {
                "project": {"type": "Project", "id": project_id},
                "sg_bid_assets": {"type": "CustomEntity08", "id": bid_assets_id},
                "code": "New Asset"
            }

            # Create in ShotGrid
            result = self.sg_session.sg.create("CustomEntity07", new_row_data)

            if not result:
                raise Exception("ShotGrid returned empty result")

            self._add_row_to_model(result)
            self.statusMessageChanged.emit(f"Added new asset item", False)

        except Exception as e:
            logger.error(f"Failed to add asset item: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to add asset item:\n{str(e)}"
            )
            self.statusMessageChanged.emit(f"Failed to add asset item: {str(e)}", True)

    def _get_project_id(self):
        """Get the current project ID from context.

        Returns:
            int: Project ID or None if not available
        """
        context = self.context_provider if self.context_provider else self.parent()
        project_id = None

        if context and hasattr(context, 'current_project_id'):
            project_id = context.current_project_id
        elif context and hasattr(context, 'parent_app') and context.parent_app:
            # Try to get from parent_app's project combo
            parent_app = context.parent_app
            if hasattr(parent_app, 'sg_project_combo'):
                proj = parent_app.sg_project_combo.itemData(parent_app.sg_project_combo.currentIndex())
                if proj:
                    project_id = proj.get("id")

        return project_id

    def _add_row_to_model(self, result):
        """Add a new row result to the model and scroll to edit it.

        Args:
            result: The created entity dict from ShotGrid
        """
        # Add the result to the model data
        self.model.all_bidding_scenes_data.append(result)

        # Rebuild display mappings and notify views
        self.model.apply_filters()

        # Find the display row for the new item and start editing
        new_data_idx = len(self.model.all_bidding_scenes_data) - 1
        for display_row, data_idx in self.model.display_row_to_data_row.items():
            if data_idx == new_data_idx:
                # Get the index for the 'code' column (or first column)
                code_col = self.model.column_fields.index('code') if 'code' in self.model.column_fields else 0
                code_index = self.model.index(display_row, code_col)

                # Scroll to and edit the cell
                self.table_view.scrollTo(code_index)
                self.table_view.setCurrentIndex(code_index)
                self.table_view.edit(code_index)
                break

    def _delete_bidding_scene(self, row):
        """Delete the specified row."""
        entity_type = self.model.entity_type

        if entity_type == "CustomEntity07":
            # Asset item deletion - we can handle this directly
            self._delete_asset_item(row)
        elif entity_type == "CustomEntity03":
            # Line Item deletion - we can handle this directly
            self._delete_line_item(row)
        elif entity_type == "CustomEntity02":
            # Bidding Scene deletion
            self._delete_bidding_scene_row(row)
        else:
            # Other types require parent context
            self.statusMessageChanged.emit(f"Delete {self.entity_name} functionality requires parent tab context", False)

    def _delete_bidding_scene_row(self, row):
        """Delete the specified bidding scene row (CustomEntity02).

        Args:
            row: Display row index to delete
        """
        # Check if this is the last row - at least one row must remain
        if len(self.model.all_bidding_scenes_data) <= 1:
            QtWidgets.QMessageBox.warning(
                self,
                "Cannot Delete",
                "The last row cannot be removed. At least one row must remain in the VFX Breakdown."
            )
            return

        # Get the actual data row index
        if row not in self.model.display_row_to_data_row:
            logger.error(f"Invalid row index for deletion: {row}")
            return

        data_row = self.model.display_row_to_data_row[row]
        row_data = self.model.all_bidding_scenes_data[data_row]

        row_id = row_data.get("id")
        row_code = row_data.get("code", "Unknown")

        if not row_id:
            logger.error("Cannot delete row: missing ID")
            self.statusMessageChanged.emit("Cannot delete row: missing ID", True)
            return

        # Confirm deletion
        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete '{row_code}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply != QtWidgets.QMessageBox.Yes:
            return

        try:
            # Delete from ShotGrid
            self.sg_session.sg.delete("CustomEntity02", row_id)

            # Remove from model data
            self.model.all_bidding_scenes_data.pop(data_row)

            # Reapply filters to update the view
            self.model.apply_filters()

            self.statusMessageChanged.emit(f"Deleted '{row_code}'.", False)

        except Exception as e:
            logger.error(f"Failed to delete row: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to delete row:\n{str(e)}"
            )
            self.statusMessageChanged.emit(f"Failed to delete row: {str(e)}", True)

    def _delete_asset_item(self, row):
        """Delete the specified asset item (CustomEntity07).

        Args:
            row: Display row index to delete
        """
        # Get the actual data row index
        if row not in self.model.display_row_to_data_row:
            logger.error(f"Invalid row index for deletion: {row}")
            return

        data_row = self.model.display_row_to_data_row[row]
        asset_data = self.model.all_bidding_scenes_data[data_row]

        asset_id = asset_data.get("id")
        asset_code = asset_data.get("code", "Unknown")

        if not asset_id:
            logger.error("Cannot delete asset: missing ID")
            self.statusMessageChanged.emit("Cannot delete asset: missing ID", True)
            return

        # Prevent deleting the last row - at least one Asset must remain
        if len(self.model.all_bidding_scenes_data) <= 1:
            QtWidgets.QMessageBox.warning(
                self,
                "Cannot Delete",
                "Cannot delete the last Asset item. At least one Asset must remain in the Bid Assets."
            )
            return

        # Confirm deletion
        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete Asset item '{asset_code}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply != QtWidgets.QMessageBox.Yes:
            return

        try:
            # Delete from ShotGrid
            self.sg_session.sg.delete("CustomEntity07", asset_id)

            # Remove from model data
            self.model.all_bidding_scenes_data.pop(data_row)

            # Reapply filters to update the view
            self.model.apply_filters()

            self.statusMessageChanged.emit(f"Deleted Asset item '{asset_code}'.", False)

        except Exception as e:
            logger.error(f"Failed to delete Asset item: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to delete Asset item:\n{str(e)}"
            )
            self.statusMessageChanged.emit(f"Failed to delete Asset item: {str(e)}", True)

    def _add_line_item_above(self, row):
        """Add a new Line Item (CustomEntity03) above the specified row.

        Args:
            row: Display row index to add above
        """
        self._add_line_item_at_position(row, insert_below=False)

    def _add_line_item_below(self, row):
        """Add a new Line Item (CustomEntity03) below the specified row.

        Args:
            row: Display row index to add below
        """
        self._add_line_item_at_position(row, insert_below=True)

    def _add_line_item_at_position(self, row, insert_below=True):
        """Add a new Line Item (CustomEntity03) at the specified position.

        Args:
            row: Display row index
            insert_below: If True, insert below; if False, insert above
        """
        # Get context from context_provider (preferred) or parent widget (fallback)
        context = self.context_provider if self.context_provider else self.parent()

        if not context or not hasattr(context, 'current_price_list_id') or not hasattr(context, 'current_project_id'):
            QtWidgets.QMessageBox.warning(self, "No Context", "Cannot add Line Item: no Price List selected.")
            return

        price_list_id = context.current_price_list_id
        project_id = context.current_project_id

        if not price_list_id or not project_id:
            QtWidgets.QMessageBox.warning(self, "No Context", "Cannot add Line Item: no Price List selected.")
            return

        try:
            # Create new Line Item in ShotGrid with link to Price List
            sg_data = {
                "project": {"type": "Project", "id": project_id},
                "code": "New Line Item",
                "sg_parent_pricelist": {"type": "CustomEntity10", "id": price_list_id}
            }

            new_line_item = self.sg_session.sg.create("CustomEntity03", sg_data)

            # Link it to the Price List
            # Get current sg_line_items
            current_line_items = []
            if hasattr(context, 'current_price_list_data'):
                sg_line_items = context.current_price_list_data.get("sg_line_items")
                if sg_line_items:
                    if isinstance(sg_line_items, list):
                        current_line_items = [{"type": "CustomEntity03", "id": item.get("id")} for item in sg_line_items if isinstance(item, dict) and item.get("id")]
                    elif isinstance(sg_line_items, dict) and sg_line_items.get("id"):
                        current_line_items = [{"type": "CustomEntity03", "id": sg_line_items.get("id")}]

            # Insert new line item at appropriate position
            data_row = self.model.display_row_to_data_row.get(row)
            if data_row is not None and data_row < len(self.model.all_bidding_scenes_data):
                target_item_data = self.model.all_bidding_scenes_data[data_row]
                target_item_id = target_item_data.get("id")

                # Find position in current_line_items
                insert_index = 0
                for i, item in enumerate(current_line_items):
                    if item["id"] == target_item_id:
                        insert_index = i + 1 if insert_below else i
                        break

                current_line_items.insert(insert_index, {"type": "CustomEntity03", "id": new_line_item["id"]})
            else:
                # Add to end if can't find position
                current_line_items.append({"type": "CustomEntity03", "id": new_line_item["id"]})

            # Update Price List with new line items list
            self.sg_session.sg.update(
                "CustomEntity10",
                price_list_id,
                {"sg_line_items": current_line_items}
            )

            # Reload data
            if hasattr(context, '_load_line_items'):
                context._load_line_items()
            self.statusMessageChanged.emit(f"Added new Line Item", False)

            # Notify other tabs that Line Items have changed
            self._notify_line_items_changed()

        except Exception as e:
            logger.error(f"Failed to add Line Item: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to add Line Item:\n{str(e)}"
            )
            self.statusMessageChanged.emit(f"Failed to add Line Item: {str(e)}", True)

    def _add_line_item_local(self, row):
        """Add a new Line Item locally (not saved to ShotGrid yet).

        Creates an empty row at the bottom of the table. The item will be saved to ShotGrid
        when the user enters a name and presses Enter.

        Args:
            row: Display row index (not used - always adds to bottom)
        """
        # Create empty line item data with a special marker indicating it's unsaved
        new_item_data = {
            "id": None,  # No ID yet - will be assigned when saved to ShotGrid
            "code": "",  # Empty name
            "type": "CustomEntity03",
            "_is_unsaved": True,  # Special marker for unsaved items
        }

        # Add empty values for all other fields
        if hasattr(self.model, 'column_fields'):
            for field in self.model.column_fields:
                if field not in new_item_data:
                    new_item_data[field] = ""

        # Add to model data at the end
        self.model.all_bidding_scenes_data.append(new_item_data)

        # Rebuild display mappings and notify views
        self.model.apply_filters()

        # Find the display row for the new item (should be at the end after apply_filters)
        # The new item is at index = len(all_bidding_scenes_data) - 1
        new_data_idx = len(self.model.all_bidding_scenes_data) - 1

        for display_row, data_idx in self.model.display_row_to_data_row.items():
            if data_idx == new_data_idx:
                # Get the index for the 'code' column
                code_col = self.model.column_fields.index('code') if 'code' in self.model.column_fields else 0
                code_index = self.model.index(display_row, code_col)

                # Scroll to and edit the cell
                self.table_view.scrollTo(code_index)
                self.table_view.setCurrentIndex(code_index)
                self.table_view.edit(code_index)
                break

        self.statusMessageChanged.emit(f"Added new Line Item (not saved yet)", False)

    def _process_pending_unsaved_save(self):
        """Process the pending unsaved Line Item save (called by timer after debounce period)."""
        if self._pending_unsaved_save:
            data_row, name = self._pending_unsaved_save
            self._pending_unsaved_save = None
            self._save_unsaved_line_item(data_row, name)

    def _save_unsaved_line_item(self, data_row, name):
        """Save an unsaved Line Item to ShotGrid after name validation.

        Args:
            data_row: Index in all_bidding_scenes_data
            name: The name entered by the user
        """

        # Get context
        context = self.context_provider if self.context_provider else self.parent()

        if not context or not hasattr(context, 'current_price_list_id') or not hasattr(context, 'current_project_id'):
            QtWidgets.QMessageBox.warning(self, "No Context", "Cannot save Line Item: no Price List selected.")
            # Reset the name to empty
            self.model.all_bidding_scenes_data[data_row]["code"] = ""
            self.model.layoutChanged.emit()
            return

        price_list_id = context.current_price_list_id
        project_id = context.current_project_id

        if not price_list_id or not project_id:
            QtWidgets.QMessageBox.warning(self, "No Context", "Cannot save Line Item: no Price List selected.")
            # Reset the name to empty
            self.model.all_bidding_scenes_data[data_row]["code"] = ""
            self.model.layoutChanged.emit()
            return

        try:
            # Check if a Line Item with this name already exists in this project
            existing_items = self.sg_session.sg.find(
                "CustomEntity03",
                [
                    ["project", "is", {"type": "Project", "id": project_id}],
                    ["code", "is", name]
                ],
                ["id", "code"]
            )

            if existing_items:
                # Name already exists - show dialog and reset
                logger.warning(f"Line Item name '{name}' already exists")
                QtWidgets.QMessageBox.warning(
                    self,
                    "Duplicate Name",
                    f"A Line Item with the name '{name}' already exists.\nPlease enter a different name."
                )
                # Reset the name to empty so user can try again
                self.model.all_bidding_scenes_data[data_row]["code"] = ""
                self.model.layoutChanged.emit()

                # Re-trigger editing on the code field
                for display_row, data_idx in self.model.display_row_to_data_row.items():
                    if data_idx == data_row:
                        code_col = self.model.column_fields.index('code') if 'code' in self.model.column_fields else 0
                        code_index = self.model.index(display_row, code_col)
                        self.table_view.edit(code_index)
                        break
                return

            # Name is unique - create in ShotGrid with link to Price List
            sg_data = {
                "project": {"type": "Project", "id": project_id},
                "code": name,
                "sg_parent_pricelist": {"type": "CustomEntity10", "id": price_list_id}
            }

            new_line_item = self.sg_session.sg.create("CustomEntity03", sg_data)

            # Update the local data with the new ID and remove the unsaved marker
            self.model.all_bidding_scenes_data[data_row]["id"] = new_line_item["id"]
            self.model.all_bidding_scenes_data[data_row]["_is_unsaved"] = False

            # Link it to the Price List
            current_line_items = []
            if hasattr(context, 'current_price_list_data'):
                sg_line_items = context.current_price_list_data.get("sg_line_items")
                if sg_line_items:
                    if isinstance(sg_line_items, list):
                        current_line_items = [{"type": "CustomEntity03", "id": item.get("id")} for item in sg_line_items if isinstance(item, dict) and item.get("id")]
                    elif isinstance(sg_line_items, dict) and sg_line_items.get("id"):
                        current_line_items = [{"type": "CustomEntity03", "id": sg_line_items.get("id")}]

            # Add the new line item
            current_line_items.append({"type": "CustomEntity03", "id": new_line_item["id"]})

            # Update Price List with new line items list
            self.sg_session.sg.update(
                "CustomEntity10",
                price_list_id,
                {"sg_line_items": current_line_items}
            )

            self.statusMessageChanged.emit(f"Created Line Item '{name}'", False)

            # Notify other tabs that Line Items have changed
            self._notify_line_items_changed()

        except Exception as e:
            logger.error(f"Failed to save Line Item: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to save Line Item:\n{str(e)}"
            )
            # Reset the name to empty so user can try again
            self.model.all_bidding_scenes_data[data_row]["code"] = ""
            self.model.layoutChanged.emit()
            self.statusMessageChanged.emit(f"Failed to save Line Item: {str(e)}", True)

    def _delete_line_item(self, row):
        """Delete the specified Line Item (CustomEntity03).

        Args:
            row: Display row index to delete
        """
        # Get the actual data row index
        if row not in self.model.display_row_to_data_row:
            logger.error(f"Invalid row index for deletion: {row}")
            return

        data_row = self.model.display_row_to_data_row[row]
        line_item_data = self.model.all_bidding_scenes_data[data_row]

        line_item_id = line_item_data.get("id")
        line_item_code = line_item_data.get("code", "Unknown")
        is_unsaved = line_item_data.get("_is_unsaved", False)

        # If it's an unsaved local item, just remove it from the model
        if not line_item_id or is_unsaved:
            self.model.all_bidding_scenes_data.pop(data_row)
            # Rebuild display mappings and notify views
            self.model.apply_filters()
            self.statusMessageChanged.emit(f"Removed unsaved Line Item", False)
            return

        # Get context from context_provider (preferred) or parent widget (fallback)
        context = self.context_provider if self.context_provider else self.parent()

        if not context or not hasattr(context, 'current_price_list_id'):
            QtWidgets.QMessageBox.warning(self, "No Context", "Cannot delete Line Item: no Price List context found.")
            return

        price_list_id = context.current_price_list_id

        # Check if this is the last Line Item - prevent deletion if so
        line_item_count = len(self.model.all_bidding_scenes_data)
        if line_item_count <= 1:
            QtWidgets.QMessageBox.warning(
                self,
                "Cannot Delete",
                "Cannot delete the last Line Item. A Price List must have at least one Line Item."
            )
            return

        # Confirm deletion
        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete Line Item '{line_item_code}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply != QtWidgets.QMessageBox.Yes:
            return

        try:

            # Remove from Price List's sg_line_items
            current_line_items = []
            if hasattr(context, 'current_price_list_data'):
                sg_line_items = context.current_price_list_data.get("sg_line_items")
                if sg_line_items:
                    if isinstance(sg_line_items, list):
                        current_line_items = [{"type": "CustomEntity03", "id": item.get("id")} for item in sg_line_items if isinstance(item, dict) and item.get("id") and item.get("id") != line_item_id]
                    elif isinstance(sg_line_items, dict) and sg_line_items.get("id") and sg_line_items.get("id") != line_item_id:
                        # Don't include the deleted item
                        pass

            # Update Price List
            self.sg_session.sg.update(
                "CustomEntity10",
                price_list_id,
                {"sg_line_items": current_line_items if current_line_items else None}
            )

            # Delete from ShotGrid
            self.sg_session.sg.delete("CustomEntity03", line_item_id)

            # Reload data
            if hasattr(context, '_load_line_items'):
                context._load_line_items()
            self.statusMessageChanged.emit(f"Deleted Line Item '{line_item_code}'.", False)

            # Notify other tabs that Line Items have changed
            self._notify_line_items_changed()

        except Exception as e:
            logger.error(f"Failed to delete Line Item: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to delete Line Item:\n{str(e)}"
            )
            self.statusMessageChanged.emit(f"Failed to delete Line Item: {str(e)}", True)

    def _notify_line_items_changed(self):
        """Notify other tabs that Line Items have changed so they can update their dropdowns.

        This method delegates to the context provider (RatesTab) which has access to the main app.
        """
        try:
            # Get context from context_provider (preferred) or parent widget (fallback)
            context = self.context_provider if self.context_provider else self.parent()

            if context and hasattr(context, '_notify_line_items_changed'):
                context._notify_line_items_changed()
        except Exception as e:
            logger.error(f"Failed to notify Line Items changed: {e}", exc_info=True)

    def _autosize_columns(self, min_px=80, max_px=700, extra_padding=28):
        """Auto-size columns to fit content.

        For text columns, limits width to 200 characters or the longest string if shorter.
        """
        if not self.table_view or self.model.rowCount() == 0:
            return

        # Scale parameters with DPI
        dpi_scale = self.app_settings.get_dpi_scale()
        min_px = int(min_px * dpi_scale)
        max_px = int(max_px * dpi_scale)
        extra_padding = int(extra_padding * dpi_scale)

        # First, use Qt's built-in resize to content
        self.table_view.resizeColumnsToContents()

        fm = self.table_view.fontMetrics()

        # Calculate width of 200 characters for text column limit
        sample_text = "M" * 200  # Use 'M' as it's typically the widest character
        text_column_max_px = fm.horizontalAdvance(sample_text) + extra_padding


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
                elif current_width < min_px:
                    self.table_view.setColumnWidth(col, min_px)
                else:
                    pass
            else:
                # For other fields, use standard constraints
                if current_width > max_px:
                    self.table_view.setColumnWidth(col, max_px)
                elif current_width < min_px:
                    self.table_view.setColumnWidth(col, min_px)
                else:
                    pass


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
        # Check for unsaved Line Item name changes
        if self.model.entity_type == "CustomEntity03":
            try:
                code_col_idx = self.model.column_fields.index("code")
            except ValueError:
                code_col_idx = None

            if code_col_idx is not None:
                for row in range(top_left.row(), bottom_right.row() + 1):
                    for col in range(top_left.column(), bottom_right.column() + 1):
                        if col == code_col_idx:
                            # Check if this is an unsaved item
                            data_row = self.model.display_row_to_data_row.get(row)
                            if data_row is not None and data_row < len(self.model.all_bidding_scenes_data):
                                item_data = self.model.all_bidding_scenes_data[data_row]
                                if item_data.get("_is_unsaved"):
                                    # This is an unsaved item and the name was just changed
                                    new_name = item_data.get("code", "").strip()
                                    if new_name:  # Only process if name is not empty
                                        # Debounce: wait 500ms after last keystroke before saving
                                        self._pending_unsaved_save = (data_row, new_name)
                                        self._unsaved_save_timer.start(500)  # 500ms delay

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

    def _on_model_reset(self):
        """Handle model reset (e.g., after sorting or filtering).

        Recreates the bid assets widgets since they are cleared when the model resets.
        """
        # Use QTimer to defer widget creation until after the view has processed the model reset
        # This ensures the view's internal state is fully updated before we create widgets
        QtCore.QTimer.singleShot(0, self._setup_bid_assets_widgets)
