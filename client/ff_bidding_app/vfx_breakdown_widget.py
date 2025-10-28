"""
VFX Breakdown Widget
Reusable widget component for displaying and editing VFX bidding scenes data using Qt Model/View pattern.
"""

from PySide6 import QtWidgets, QtCore, QtGui
import logging

try:
    from .logger import logger
    from .vfx_breakdown_model import VFXBreakdownModel, PasteCommand, CheckBoxDelegate
    from .settings import AppSettings
except ImportError:
    logger = logging.getLogger("FFPackageManager")
    from vfx_breakdown_model import VFXBreakdownModel, PasteCommand, CheckBoxDelegate
    from settings import AppSettings


class ComboBoxDelegate(QtWidgets.QStyledItemDelegate):
    """Custom delegate for combo box cells with List field values."""

    def __init__(self, field_name, list_values, parent=None):
        super().__init__(parent)
        self.field_name = field_name
        self.list_values = list_values or []

    def createEditor(self, parent, option, index):
        """Create a combo box editor."""
        combo = QtWidgets.QComboBox(parent)
        combo.addItem("")  # Empty option
        for value in self.list_values:
            combo.addItem(value)
        combo.setFrame(False)
        return combo

    def setEditorData(self, editor, index):
        """Set the current value in the combo box."""
        value = index.model().data(index, QtCore.Qt.EditRole)
        if value:
            index_pos = editor.findText(value)
            if index_pos >= 0:
                editor.setCurrentIndex(index_pos)

    def setModelData(self, editor, model, index):
        """Save the selected value back to the model."""
        value = editor.currentText()
        model.setData(index, value, QtCore.Qt.EditRole)


class ConfigColumnsDialog(QtWidgets.QDialog):
    """Dialog for configuring column visibility in VFX Breakdown table."""

    def __init__(self, column_fields, column_headers, current_visibility, parent=None):
        """Initialize the dialog.

        Args:
            column_fields: List of field names
            column_headers: List of display names for the fields
            current_visibility: Dictionary mapping field names to visibility (bool)
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Configure Visible Columns")
        self.setModal(True)

        self.column_fields = column_fields
        self.column_headers = column_headers
        self.checkboxes = {}

        self._build_ui(current_visibility)

        # Adjust size to content
        self.adjustSize()
        # Set a reasonable minimum but allow it to grow
        self.setMinimumWidth(350)

    def _build_ui(self, current_visibility):
        """Build the dialog UI."""
        layout = QtWidgets.QVBoxLayout(self)

        # Instructions
        instructions = QtWidgets.QLabel(
            "Select which columns to display in the VFX Breakdown table:"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("padding: 10px; background-color: #2b2b2b; border-radius: 4px;")
        layout.addWidget(instructions)

        # Scroll area for checkboxes
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_widget)

        # Create checkbox for each column with custom tick icon
        for field, header in zip(self.column_fields, self.column_headers):
            # Create a container with custom styling
            row_widget = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(8)

            # Custom checkbox indicator
            indicator_label = QtWidgets.QLabel()
            indicator_label.setFixedSize(20, 20)
            indicator_label.setAlignment(QtCore.Qt.AlignCenter)

            # Checkbox
            checkbox = QtWidgets.QCheckBox(header)
            checkbox.setChecked(current_visibility.get(field, True))

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
            def make_update_indicator(indicator, cb):
                def update_indicator(checked):
                    if checked:
                        # Checked state: show tick icon
                        indicator.setStyleSheet("""
                            QLabel {
                                border: 2px solid #0078d4;
                                border-radius: 3px;
                                background-color: #2b2b2b;
                                color: #0078d4;
                                font-size: 16px;
                                font-weight: bold;
                            }
                        """)
                        indicator.setText("✓")
                    else:
                        # Unchecked state: empty box
                        indicator.setStyleSheet("""
                            QLabel {
                                border: 2px solid #555;
                                border-radius: 3px;
                                background-color: #2b2b2b;
                            }
                        """)
                        indicator.setText("")
                return update_indicator

            # Connect checkbox to update indicator
            update_func = make_update_indicator(indicator_label, checkbox)
            checkbox.toggled.connect(update_func)
            update_func(checkbox.isChecked())  # Set initial state

            # Make indicator clickable
            def make_indicator_click(cb):
                return lambda event: cb.setChecked(not cb.isChecked())

            indicator_label.mousePressEvent = make_indicator_click(checkbox)
            indicator_label.setCursor(QtCore.Qt.PointingHandCursor)

            row_layout.addWidget(indicator_label)
            row_layout.addWidget(checkbox)
            row_layout.addStretch()

            self.checkboxes[field] = checkbox
            scroll_layout.addWidget(row_widget)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll, stretch=1)

        # Select/Deselect All buttons
        button_row = QtWidgets.QHBoxLayout()

        select_all_btn = QtWidgets.QPushButton("Select All")
        select_all_btn.clicked.connect(self._select_all)
        button_row.addWidget(select_all_btn)

        deselect_all_btn = QtWidgets.QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(self._deselect_all)
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

    def _select_all(self):
        """Select all checkboxes."""
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(True)

    def _deselect_all(self):
        """Deselect all checkboxes."""
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(False)

    def get_column_visibility(self):
        """Get the column visibility settings.

        Returns:
            dict: Mapping of field names to visibility (bool)
        """
        visibility = {}
        for field, checkbox in self.checkboxes.items():
            visibility[field] = checkbox.isChecked()
        return visibility


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

        # Create the model
        self.model = VFXBreakdownModel(sg_session, parent=self)

        # Connect model signals
        self.model.statusMessageChanged.connect(self._on_model_status_changed)
        self.model.rowCountChanged.connect(self._on_model_row_count_changed)

        # UI widgets
        self.table_view = None
        self.global_search_box = None
        self.clear_filters_btn = None
        self.compound_sort_btn = None
        self.config_columns_btn = None
        self.template_dropdown = None
        self.row_count_label = None

        # Settings for column visibility
        self.app_settings = AppSettings()
        self.column_visibility = {}  # field_name -> bool

        # Build UI
        self._build_ui()
        self._setup_shortcuts()

        # Load and apply column settings
        self._load_column_order()  # Load column order first
        self._load_column_visibility()  # Then apply visibility

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

        # Configure table view
        self.table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectItems)
        self.table_view.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.table_view.setAlternatingRowColors(False)
        self.table_view.setWordWrap(True)

        # Configure headers
        h_header = self.table_view.horizontalHeader()
        h_header.setStretchLastSection(False)
        h_header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        h_header.setSectionsClickable(True)
        h_header.setSectionsMovable(True)  # Enable draggable columns
        h_header.sectionClicked.connect(self._on_header_clicked)
        h_header.sectionMoved.connect(self._on_column_moved)  # Save order when moved

        v_header = self.table_view.verticalHeader()
        v_header.sectionClicked.connect(self._on_row_header_clicked)

        # Context menu
        self.table_view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._on_context_menu)

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
        """Event filter to handle Enter and Delete key presses."""
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

            # Set up delegates for list fields and checkbox fields
            for col_idx, field_name in enumerate(self.model.column_fields):
                if field_name in field_schema:
                    field_info = field_schema[field_name]
                    if field_info.get("data_type") == "list":
                        list_values = field_info.get("list_values", [])
                        if list_values:
                            delegate = ComboBoxDelegate(field_name, list_values, self.table_view)
                            self.table_view.setItemDelegateForColumn(col_idx, delegate)
                    elif field_info.get("data_type") == "checkbox":
                        # Use custom checkbox delegate for checkbox fields
                        delegate = CheckBoxDelegate(self.table_view)
                        self.table_view.setItemDelegateForColumn(col_idx, delegate)

        self.model.load_bidding_scenes(bidding_scenes)

        # Ensure table is updated before auto-sizing
        QtWidgets.QApplication.processEvents()
        self._autosize_columns()

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

        # Ensure all fields have a visibility setting
        for field in self.model.column_fields:
            if field not in current_visibility:
                current_visibility[field] = True

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
            parent=self
        )

        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            # Get the new visibility settings
            new_visibility = dialog.get_column_visibility()

            # Save to settings
            self.app_settings.set_column_visibility("vfx_breakdown", new_visibility)

            # Update local state
            self.column_visibility = new_visibility

            # Apply visibility to table
            self._apply_column_visibility()

            logger.info(f"Column visibility updated: {sum(new_visibility.values())} of {len(new_visibility)} visible")

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

                old_value = self.model.data(index, QtCore.Qt.EditRole) or ""
                if paste_value == old_value:
                    continue

                bidding_scene_data = self.model.get_bidding_scene_data_for_row(index.row())
                if not bidding_scene_data:
                    continue

                field_name = self.model.column_fields[index.column()]
                changes.append({
                    'row': index.row(),
                    'col': index.column(),
                    'old_value': old_value,
                    'new_value': paste_value,
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

                    old_value = self.model.data(index, QtCore.Qt.EditRole) or ""
                    if cell_value == old_value:
                        continue

                    bidding_scene_data = self.model.get_bidding_scene_data_for_row(target_row)
                    if not bidding_scene_data:
                        continue

                    field_name = self.model.column_fields[target_col]
                    changes.append({
                        'row': target_row,
                        'col': target_col,
                        'old_value': old_value,
                        'new_value': cell_value,
                        'bidding_scene_data': bidding_scene_data,
                        'field_name': field_name
                    })

        if not changes:
            self.statusMessageChanged.emit("No changes to paste", False)
            return

        # Create paste command
        command = PasteCommand(changes, self.model, self.sg_session, field_schema=self.model.field_schema)

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
            # Skip hidden columns
            if self.table_view.isColumnHidden(col):
                continue

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
