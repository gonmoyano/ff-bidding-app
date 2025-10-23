from PySide6 import QtWidgets, QtCore, QtGui
import json
import logging
from datetime import datetime, date

try:
    from .logger import logger
except ImportError:
    logger = logging.getLogger("FFPackageManager")


class ReverseString:
    """Wrapper for strings to enable reverse sorting in tuples."""

    def __init__(self, s):
        self.s = s

    def __lt__(self, other):
        if isinstance(other, ReverseString):
            return self.s > other.s
        return True

    def __le__(self, other):
        if isinstance(other, ReverseString):
            return self.s >= other.s
        return True

    def __gt__(self, other):
        if isinstance(other, ReverseString):
            return self.s < other.s
        return False

    def __ge__(self, other):
        if isinstance(other, ReverseString):
            return self.s <= other.s
        return False

    def __eq__(self, other):
        if isinstance(other, ReverseString):
            return self.s == other.s
        return False

    def __ne__(self, other):
        if isinstance(other, ReverseString):
            return self.s != other.s
        return True


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


class EditCommand:
    """Command pattern for undo/redo of cell edits."""

    def __init__(self, table, row, col, old_value, new_value, beat_data, field_name, sg_session, field_schema=None):
        self.table = table
        self.row = row
        self.col = col
        self.old_value = old_value
        self.new_value = new_value
        self.beat_data = beat_data
        self.field_name = field_name
        self.sg_session = sg_session
        self.field_schema = field_schema or {}

    def undo(self):
        """Undo the edit."""
        item = self.table.item(self.row, self.col)
        if item:
            item.setText(self.old_value)
            # Update ShotGrid
            self._update_shotgrid(self.old_value)

    def redo(self):
        """Redo the edit."""
        item = self.table.item(self.row, self.col)
        if item:
            item.setText(self.new_value)
            # Update ShotGrid
            self._update_shotgrid(self.new_value)

    def _update_shotgrid(self, value):
        """Update ShotGrid with the value."""
        beat_id = self.beat_data.get("id")
        if not beat_id:
            logger.error("No beat ID found for update")
            raise ValueError("No beat ID found for update")

        # Convert string value back to appropriate type
        update_value = self._parse_value(value, self.field_name)

        # Update on ShotGrid
        self.sg_session.sg.update("CustomEntity02", beat_id, {self.field_name: update_value})
        logger.info(f"Updated Beat {beat_id} field '{self.field_name}' to: {update_value}")

    def _parse_value(self, text, field_name):
        """Parse text value to appropriate type based on ShotGrid schema."""
        if not text or text == "-" or text == "":
            return None

        # Get field schema info
        field_info = self.field_schema.get(field_name, {})
        data_type = field_info.get("data_type")

        logger.debug(f"Parsing field '{field_name}' with data_type '{data_type}': '{text}'")

        # Parse based on ShotGrid data type
        if data_type == "number":
            try:
                # Try int first
                if '.' not in str(text):
                    value = int(text)
                    logger.debug(f"Parsed '{text}' as int: {value}")
                    return value
                else:
                    value = float(text)
                    logger.debug(f"Parsed '{text}' as float: {value}")
                    return value
            except ValueError:
                logger.warning(f"Failed to parse '{text}' as number for field '{field_name}'")
                raise ValueError(f"Invalid number format: '{text}'")

        elif data_type == "float":
            try:
                value = float(text)
                logger.debug(f"Parsed '{text}' as float: {value}")
                return value
            except ValueError:
                logger.warning(f"Failed to parse '{text}' as float for field '{field_name}'")
                raise ValueError(f"Invalid float format: '{text}'")

        # For all other types (text, list, entity, etc.), return as string
        return str(text)


class VFXBreakdownTab(QtWidgets.QWidget):
    """VFX Breakdown tab widget for managing VFX Breakdowns and Beats."""

    def __init__(self, sg_session, parent=None):
        """Initialize the VFX Breakdown tab.

        Args:
            sg_session: ShotgridClient instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.sg_session = sg_session
        self.parent_app = parent

        # Cached schema information for VFX Breakdowns
        self.vfx_breakdown_entity_type = None
        self.vfx_breakdown_field_names = []
        self.vfx_breakdown_field_labels = {}

        # Field schema information (data types and list values)
        self.field_schema = {}  # {field_name: {"data_type": ..., "properties": {...}}}

        # Fields to display for VFX Breakdown, in order
        self.vfx_breakdown_field_allowlist = [
            "id",
            "code",
            "sg_beat_id",
            "sg_vfx_breakdown_scene",
            "sg_page",
            "sg_script_excerpt",
            "description",
            "sg_vfx_type",
            "sg_complexity",
            "sg_category",
            "sg_vfx_description",
            "sg_number_of_shots",
        ]

        # Human-friendly labels for the table
        self.vfx_breakdown_label_overrides = {
            "id": "ID",
            "code": "Code",
            "sg_beat_id": "Beat ID",
            "sg_vfx_breakdown_scene": "Scene",
            "sg_page": "Page",
            "sg_script_excerpt": "Script Excerpt",
            "description": "Description",
            "sg_vfx_type": "VFX Type",
            "sg_complexity": "Complexity",
            "sg_category": "Category",
            "sg_vfx_description": "VFX Description",
            "sg_number_of_shots": "# Shots",
        }

        # UI widgets
        self.vfx_breakdown_combo = None
        self.vfx_breakdown_set_btn = None
        self.vfx_breakdown_refresh_btn = None
        self.vfx_breakdown_status_label = None
        self.vfx_breakdown_table = None
        self.vfx_beat_columns = []
        self.global_search_box = None
        self.clear_filters_btn = None
        self.row_count_label = None

        # Undo/Redo stack
        self.undo_stack = []
        self.redo_stack = []

        # Store beat data for each row (keyed by original data row index)
        self.beat_data_by_row = {}

        # Sorting and filtering state
        self.sort_column = None  # Currently sorted column index
        self.sort_direction = None  # 'asc' or 'desc'
        self.all_beats_data = []  # Original unfiltered beat data
        self.filtered_row_indices = []  # Indices into all_beats_data that pass filters
        self.display_row_to_data_row = {}  # Maps displayed row -> index in all_beats_data

        # Flag to prevent recursive updates
        self._updating = False

        self._build_ui()

    def _build_ui(self):
        """Build the VFX Breakdown tab UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        # Selector group
        selector_group = QtWidgets.QGroupBox("VFX Breakdowns")
        selector_layout = QtWidgets.QVBoxLayout(selector_group)

        selector_row = QtWidgets.QHBoxLayout()
        selector_label = QtWidgets.QLabel("Select VFX Breakdown:")
        selector_row.addWidget(selector_label)

        self.vfx_breakdown_combo = QtWidgets.QComboBox()
        self.vfx_breakdown_combo.setMinimumWidth(250)
        self.vfx_breakdown_combo.currentIndexChanged.connect(self._on_vfx_breakdown_changed)
        selector_row.addWidget(self.vfx_breakdown_combo, stretch=1)

        self.vfx_breakdown_set_btn = QtWidgets.QPushButton("Set as Current")
        self.vfx_breakdown_set_btn.setEnabled(False)
        self.vfx_breakdown_set_btn.clicked.connect(self._on_set_current_vfx_breakdown)
        selector_row.addWidget(self.vfx_breakdown_set_btn)

        self.vfx_breakdown_refresh_btn = QtWidgets.QPushButton("Refresh")
        self.vfx_breakdown_refresh_btn.clicked.connect(self._refresh_vfx_breakdowns)
        selector_row.addWidget(self.vfx_breakdown_refresh_btn)

        selector_layout.addLayout(selector_row)

        self.vfx_breakdown_status_label = QtWidgets.QLabel("Select an RFQ to view VFX Breakdowns.")
        self.vfx_breakdown_status_label.setObjectName("vfxBreakdownStatusLabel")
        self.vfx_breakdown_status_label.setStyleSheet("color: #a0a0a0; padding: 2px 0;")
        selector_layout.addWidget(self.vfx_breakdown_status_label)

        layout.addWidget(selector_group)

        # Global search and filter controls
        filter_controls = QtWidgets.QHBoxLayout()

        # Global search box
        search_label = QtWidgets.QLabel("Search:")
        filter_controls.addWidget(search_label)

        self.global_search_box = QtWidgets.QLineEdit()
        self.global_search_box.setPlaceholderText("Search across all columns...")
        self.global_search_box.textChanged.connect(self._apply_filters)
        filter_controls.addWidget(self.global_search_box, stretch=2)

        # Clear filters button
        self.clear_filters_btn = QtWidgets.QPushButton("Clear")
        self.clear_filters_btn.clicked.connect(self._clear_filters)
        filter_controls.addWidget(self.clear_filters_btn)

        # Row count label
        self.row_count_label = QtWidgets.QLabel("Showing 0 of 0 rows")
        self.row_count_label.setStyleSheet("color: #606060; padding: 2px 4px;")
        filter_controls.addWidget(self.row_count_label)

        layout.addLayout(filter_controls)

        # Table for beats
        self.vfx_beat_columns = [
            "id", "code", "sg_beat_id", "sg_vfx_breakdown_scene", "sg_page",
            "sg_script_excerpt", "description", "sg_vfx_type", "sg_complexity",
            "sg_category", "sg_vfx_description", "sg_number_of_shots",
            "updated_at", "updated_by"
        ]

        headers = [
            "ID", "Code", "Beat ID", "Scene", "Page",
            "Script Excerpt", "Description", "VFX Type", "Complexity",
            "Category", "VFX Description", "# Shots",
            "Updated At", "Updated By"
        ]

        self.vfx_breakdown_table = QtWidgets.QTableWidget()
        self.vfx_breakdown_table.setColumnCount(len(self.vfx_beat_columns))
        self.vfx_breakdown_table.setHorizontalHeaderLabels(headers)
        self.vfx_breakdown_table.horizontalHeader().setStretchLastSection(False)
        self.vfx_breakdown_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        self.vfx_breakdown_table.setAlternatingRowColors(False)
        self.vfx_breakdown_table.setWordWrap(True)

        hdr = self.vfx_breakdown_table.horizontalHeader()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        hdr.setSectionsClickable(True)
        hdr.sectionClicked.connect(self._on_header_clicked)

        # Connect item changed signal
        self.vfx_breakdown_table.itemChanged.connect(self._on_item_changed)

        # Install event filter to catch Enter key
        self.vfx_breakdown_table.installEventFilter(self)

        layout.addWidget(self.vfx_breakdown_table)

        # Setup keyboard shortcuts
        self._setup_shortcuts()

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts for undo/redo."""
        # Undo shortcut (Ctrl+Z)
        undo_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Z"), self)
        undo_shortcut.activated.connect(self._undo)

        # Redo shortcut (Ctrl+Y)
        redo_shortcut = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Y"), self)
        redo_shortcut.activated.connect(self._redo)

        logger.info("Keyboard shortcuts set up: Ctrl+Z (undo), Ctrl+Y (redo)")

    def _on_header_clicked(self, column_index):
        """Handle header click for sorting.

        Args:
            column_index: Index of the clicked column
        """
        # Simple single-column sorting
        if self.sort_column == column_index:
            # Toggle direction if clicking the same column
            self.sort_direction = "desc" if self.sort_direction == "asc" else "asc"
        else:
            # New column - start with ascending
            self.sort_column = column_index
            self.sort_direction = "asc"

        # Update header to show sort indicator
        self._update_header_sort_indicators()

        # Re-apply filters and sorting
        self._apply_filters()

        logger.info(f"Sorting by column {column_index} ({self.vfx_beat_columns[column_index]}): {self.sort_direction}")

    def _update_header_sort_indicators(self):
        """Update table headers to show sort indicators."""
        for col_idx in range(self.vfx_breakdown_table.columnCount()):
            header_item = self.vfx_breakdown_table.horizontalHeaderItem(col_idx)
            if header_item:
                # Get original text without indicators
                original_text = header_item.text()
                # Remove existing indicators
                for indicator in [" ↑", " ↓"]:
                    original_text = original_text.replace(indicator, "")

                # Add indicator if this is the sorted column
                if col_idx == self.sort_column and self.sort_direction:
                    arrow = " ↑" if self.sort_direction == "asc" else " ↓"
                    header_item.setText(f"{original_text}{arrow}")
                else:
                    header_item.setText(original_text)

    def _clear_filters(self):
        """Clear search and sorting."""
        # Clear global search
        self.global_search_box.clear()

        # Clear sorting
        self.sort_column = None
        self.sort_direction = None
        self._update_header_sort_indicators()

        # Re-apply (which will show all rows)
        self._apply_filters()

        logger.info("Search and sorting cleared")

    def _apply_filters(self):
        """Apply search and sorting to the table."""
        if not self.all_beats_data:
            return

        # Start with all rows
        self.filtered_row_indices = list(range(len(self.all_beats_data)))

        # Apply global search filter
        global_search = self.global_search_box.text().lower().strip()
        if global_search:
            self.filtered_row_indices = [
                idx for idx in self.filtered_row_indices
                if self._matches_global_search(self.all_beats_data[idx], global_search)
            ]

        # Apply sorting
        if self.sort_column is not None and self.sort_direction:
            self.filtered_row_indices.sort(key=lambda idx: self._get_sort_key(self.all_beats_data[idx]))

        # Refresh table display
        self._refresh_table_display()

        # Update row count label
        total_rows = len(self.all_beats_data)
        shown_rows = len(self.filtered_row_indices)
        self.row_count_label.setText(f"Showing {shown_rows} of {total_rows} rows")

        logger.info(f"Search applied: showing {shown_rows} of {total_rows} rows")

    def _matches_global_search(self, beat_data, search_text):
        """Check if beat data matches global search text."""
        # Search in all fields
        for field in self.vfx_beat_columns:
            value = beat_data.get(field)
            if value:
                # Handle different value types
                if isinstance(value, dict):
                    # Extract readable value from dict (entity references)
                    value_str = value.get("name", "") or value.get("code", "")
                else:
                    value_str = str(value)

                if search_text in value_str.lower():
                    return True
        return False

    def _get_sort_key(self, beat_data):
        """Get sort key for a beat based on current sort column."""
        if self.sort_column is None or self.sort_column >= len(self.vfx_beat_columns):
            return (0,)

        field_name = self.vfx_beat_columns[self.sort_column]
        value = beat_data.get(field_name)

        # Handle None values
        if value is None:
            # Empty values sort first (using negative infinity for numeric comparison)
            if self.sort_direction == "desc":
                return (float('inf'),)
            else:
                return (float('-inf'),)

        # Check if this is a known numeric field
        is_numeric_field = (
            field_name in ("id", "sg_page", "sg_number_of_shots") or
            (field_name in self.field_schema and
             self.field_schema[field_name].get("data_type") in ("number", "float"))
        )

        # Convert to sortable type
        if isinstance(value, (int, float)):
            # Already numeric
            sort_value = float(value)
        elif isinstance(value, datetime):
            # For dates, convert to timestamp for sorting
            sort_value = value.timestamp() if hasattr(value, 'timestamp') else 0
        elif isinstance(value, dict):
            # For dicts (entity references), extract string value
            sort_value = (value.get("name", "") or value.get("code", "") or "").lower()
        else:
            # For strings - try to detect if it's a numeric value
            str_value = str(value).strip()

            # Try to convert to number for numeric sorting
            if is_numeric_field or str_value.replace('.', '', 1).replace('-', '', 1).isdigit():
                try:
                    sort_value = float(str_value)
                except (ValueError, TypeError):
                    # If conversion fails, use string sorting
                    sort_value = str_value.lower()
            else:
                # Use string sorting
                sort_value = str_value.lower()

        # Apply direction
        if self.sort_direction == "desc":
            if isinstance(sort_value, (int, float)):
                sort_value = -sort_value
            elif isinstance(sort_value, str):
                sort_value = ReverseString(sort_value)

        return (sort_value,)

    def _refresh_table_display(self):
        """Refresh the table display based on filtered and sorted data."""
        # Block signals during refresh
        self.vfx_breakdown_table.blockSignals(True)

        table = self.vfx_breakdown_table
        table.setRowCount(len(self.filtered_row_indices))

        # Clear display mapping
        self.display_row_to_data_row.clear()

        # Read-only columns
        readonly_columns = ["id", "updated_at", "updated_by"]

        for display_row, data_idx in enumerate(self.filtered_row_indices):
            # Store mapping
            self.display_row_to_data_row[display_row] = data_idx

            beat = self.all_beats_data[data_idx]

            for c, field in enumerate(self.vfx_beat_columns):
                value = beat.get(field)
                text = self._format_sg_value(value)

                it = QtWidgets.QTableWidgetItem(text)

                # Make read-only columns non-editable
                if field in readonly_columns:
                    it.setFlags(it.flags() & ~QtCore.Qt.ItemIsEditable)
                    it.setForeground(QtGui.QColor("#888888"))
                else:
                    it.setFlags(it.flags() | QtCore.Qt.ItemIsEditable)

                # Alignment
                if field in ("id", "sg_page", "sg_number_of_shots"):
                    it.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                elif field == "updated_at":
                    it.setTextAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
                else:
                    it.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

                table.setItem(display_row, c, it)

                # Set item delegate for List fields
                if field in self.field_schema:
                    field_info = self.field_schema[field]
                    if field_info.get("data_type") == "list":
                        list_values = field_info.get("list_values", [])
                        if list_values:
                            delegate = ComboBoxDelegate(field, list_values, self.vfx_breakdown_table)
                            self.vfx_breakdown_table.setItemDelegateForColumn(c, delegate)

        # Unblock signals
        self.vfx_breakdown_table.blockSignals(False)

    def eventFilter(self, obj, event):
        """Event filter to handle Enter key press."""
        if obj == self.vfx_breakdown_table and event.type() == QtCore.QEvent.KeyPress:
            if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                # Enter pressed - move to next row
                current_item = self.vfx_breakdown_table.currentItem()
                if current_item:
                    row = current_item.row()
                    col = current_item.column()

                    # Move to next row
                    next_row = row + 1
                    if next_row < self.vfx_breakdown_table.rowCount():
                        self.vfx_breakdown_table.setCurrentCell(next_row, col)
                return True

        return super().eventFilter(obj, event)

    def _undo(self):
        """Undo the last change."""
        if not self.undo_stack:
            logger.info("Nothing to undo")
            return

        command = self.undo_stack.pop()
        self._updating = True
        command.undo()
        self._updating = False
        self.redo_stack.append(command)
        logger.info(f"Undone edit at row {command.row}, col {command.col}")
        self._set_vfx_breakdown_status(f"Undone change to {self.vfx_beat_columns[command.col]}")

    def _redo(self):
        """Redo the last undone change."""
        if not self.redo_stack:
            logger.info("Nothing to redo")
            return

        command = self.redo_stack.pop()
        self._updating = True
        command.redo()
        self._updating = False
        self.undo_stack.append(command)
        logger.info(f"Redone edit at row {command.row}, col {command.col}")
        self._set_vfx_breakdown_status(f"Redone change to {self.vfx_beat_columns[command.col]}")

    def _on_item_changed(self, item):
        """Handle item changed in the table."""
        if self._updating:
            return

        display_row = item.row()
        col = item.column()
        field_name = self.vfx_beat_columns[col]

        # Map display row to data row
        data_row = self.display_row_to_data_row.get(display_row)
        if data_row is None:
            logger.warning(f"No data row mapping found for display row {display_row}")
            return

        # Get beat data from all_beats_data
        if data_row >= len(self.all_beats_data):
            logger.warning(f"Data row {data_row} out of range")
            return

        beat_data = self.all_beats_data[data_row]
        if not beat_data:
            logger.warning(f"No beat data found for data row {data_row}")
            return

        new_value = item.text()

        # Get old value from beat_data
        old_value_raw = beat_data.get(field_name)
        old_value = self._format_sg_value(old_value_raw)

        # Check if value actually changed
        if new_value == old_value:
            logger.debug(f"No change detected for display row {display_row}, col {col} ({field_name})")
            return

        logger.info(f"Cell changed at display row {display_row} (data row {data_row}), col {col} ({field_name}): '{old_value}' -> '{new_value}'")
        logger.info(f"Beat ID: {beat_data.get('id')}, Field type: {type(old_value_raw).__name__}")

        # Create undo command
        command = EditCommand(
            self.vfx_breakdown_table,
            display_row,
            col,
            old_value,
            new_value,
            beat_data,
            field_name,
            self.sg_session,
            field_schema=self.field_schema
        )

        # Execute the command (update ShotGrid)
        try:
            self._updating = True
            command._update_shotgrid(new_value)
            self._updating = False

            # Add to undo stack
            self.undo_stack.append(command)
            # Clear redo stack on new edit
            self.redo_stack.clear()

            # Update the beat_data with new value (in all_beats_data)
            parsed_value = command._parse_value(new_value, field_name)
            beat_data[field_name] = parsed_value

            self._set_vfx_breakdown_status(f"✓ Updated {field_name} on ShotGrid")
            logger.info(f"Successfully updated Beat {beat_data.get('id')} field '{field_name}' to '{new_value}'")

        except Exception as e:
            logger.error(f"Failed to update ShotGrid field '{field_name}': {e}", exc_info=True)
            # Revert the change in UI
            self._updating = True
            item.setText(old_value)
            self._updating = False
            self._set_vfx_breakdown_status(f"Failed to update {field_name}", is_error=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Update Failed",
                f"Failed to update field '{field_name}':\n{str(e)}\n\nValue has been reverted."
            )

    def _fetch_beats_schema(self):
        """Fetch schema information for Beat entity (CustomEntity02)."""
        try:
            schema = self.sg_session.sg.schema_field_read("CustomEntity02")

            for field_name, field_info in schema.items():
                data_type = field_info.get("data_type", {})
                properties = field_info.get("properties", {})

                self.field_schema[field_name] = {
                    "data_type": data_type.get("value") if isinstance(data_type, dict) else data_type,
                    "properties": properties
                }

                # Extract list values if it's a list field
                if self.field_schema[field_name]["data_type"] == "list":
                    valid_values = properties.get("valid_values", {})
                    if isinstance(valid_values, dict):
                        # Extract just the display values
                        list_values = list(valid_values.get("value", []))
                    else:
                        list_values = []
                    self.field_schema[field_name]["list_values"] = list_values
                    logger.info(f"Field '{field_name}' is a list with values: {list_values}")

            logger.info(f"Fetched schema for {len(self.field_schema)} fields")
            return True

        except Exception as e:
            logger.error(f"Failed to fetch schema: {e}", exc_info=True)
            return False

    def _on_set_current_vfx_breakdown(self):
        """Set the selected VFX Breakdown as the current one for the selected RFQ."""
        if not self.parent_app:
            return

        rfq = self.parent_app.rfq_combo.itemData(self.parent_app.rfq_combo.currentIndex())
        if not rfq:
            QtWidgets.QMessageBox.warning(self, "No RFQ selected", "Please select an RFQ first.")
            return

        idx = self.vfx_breakdown_combo.currentIndex()
        breakdown = self.vfx_breakdown_combo.itemData(idx)
        if not breakdown:
            QtWidgets.QMessageBox.warning(self, "No Breakdown selected", "Please select a VFX Breakdown from the list.")
            return

        rfq_id = rfq["id"]
        br_id = breakdown.get("id")
        br_type = breakdown.get("type", "CustomEntity01")
        logger.info(f"Updating RFQ {rfq_id} sg_vfx_breakdown -> {br_type}({br_id})")

        try:
            # Update on ShotGrid
            self.sg_session.update_rfq_vfx_breakdown(rfq_id, breakdown)
        except Exception as e:
            logger.error(f"Failed to update RFQ sg_vfx_breakdown: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to set current VFX Breakdown:\n{e}")
            return

        # Refresh this RFQ from SG to keep local data accurate
        try:
            updated_rfq = self.sg_session.get_entity_by_id(
                "CustomEntity04",
                rfq_id,
                fields=["id", "code", "sg_vfx_breakdown", "sg_status_list", "created_at"]
            )
            # Replace combo item data with the fresh dict
            self.parent_app.rfq_combo.setItemData(self.parent_app.rfq_combo.currentIndex(), updated_rfq)
            rfq = updated_rfq  # use fresh one below
            logger.info(f"RFQ {rfq_id} refreshed with latest sg_vfx_breakdown link.")
        except Exception as e:
            logger.warning(f"Failed to refresh RFQ after update: {e}")

        # Update label under RFQ combo
        linked = rfq.get("sg_vfx_breakdown")
        if isinstance(linked, dict):
            label_text = linked.get("code") or linked.get("name") or f"ID {linked.get('id')}"
        elif isinstance(linked, list) and linked:
            item = linked[0]
            label_text = item.get("code") or item.get("name") or f"ID {item.get('id')}"
        else:
            label_text = "-"
        if hasattr(self.parent_app, "rfq_vfx_breakdown_label"):
            self.parent_app.rfq_vfx_breakdown_label.setText(label_text)

        # Re-run the RFQ change flow to sync combo default selection & Beats table
        self.parent_app._on_rfq_changed(self.parent_app.rfq_combo.currentIndex())

        QtWidgets.QMessageBox.information(self, "Updated", "Current VFX Breakdown set for this RFQ.")

    def _autosize_beat_columns(self, min_px=60, max_px=600, extra_padding=24):
        """Size each Beats table column to fit its content (header + cells)."""
        table = self.vfx_breakdown_table
        fm = table.fontMetrics()
        header = table.horizontalHeader()

        # Loop columns
        for c in range(table.columnCount()):
            # Start with header text width
            header_text = table.horizontalHeaderItem(c).text() if table.horizontalHeaderItem(c) else ""
            max_w = fm.horizontalAdvance(header_text)

            # Consider all row items in this column
            for r in range(table.rowCount()):
                it = table.item(r, c)
                if it:
                    # account for multi-line text roughly by measuring each line
                    text = it.text()
                    # quick split on '\n' to avoid underestimating long wrapped cells
                    for line in text.splitlines() or [""]:
                        max_w = max(max_w, fm.horizontalAdvance(line))

            # Add padding for cell margins + sort indicator etc.
            target = max(min_px, min(max_w + extra_padding, max_px))
            table.setColumnWidth(c, target)

    def _normalize_label(self, raw):
        """Normalize a label value to a string."""
        if raw is None:
            return ""
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            for k in ("label", "display_name", "name", "title", "value"):
                v = raw.get(k)
                if isinstance(v, str) and v.strip():
                    return v
            try:
                return json.dumps(raw, default=str)
            except Exception:
                return str(raw)
        return str(raw)

    def _refresh_vfx_breakdowns(self):
        """Reload the VFX Breakdown list for the current RFQ."""
        if not self.parent_app:
            return

        current_data = self.vfx_breakdown_combo.currentData()
        current_id = current_data.get("id") if isinstance(current_data, dict) else None

        rfq = self.parent_app.rfq_combo.itemData(self.parent_app.rfq_combo.currentIndex()) if self.parent_app.rfq_combo else None
        self.populate_vfx_breakdown_combo(rfq, auto_select=False)

        if current_id:
            self._select_vfx_breakdown_by_id(current_id)

    def _select_vfx_breakdown_by_id(self, entity_id):
        """Select a VFX Breakdown by its ID."""
        if not entity_id:
            return False

        for index in range(self.vfx_breakdown_combo.count()):
            breakdown = self.vfx_breakdown_combo.itemData(index)
            if isinstance(breakdown, dict) and breakdown.get("id") == entity_id:
                self.vfx_breakdown_combo.setCurrentIndex(index)
                return True
        return False

    def populate_vfx_breakdown_combo(self, rfq=None, auto_select=True):
        """Populate the VFX Breakdown combo box.

        Args:
            rfq: RFQ data dict (optional, if None clears the selection)
            auto_select: Whether to auto-select a breakdown (default: True)
        """
        if not self.parent_app:
            return

        self.vfx_breakdown_combo.blockSignals(True)
        self.vfx_breakdown_combo.clear()
        self.vfx_breakdown_combo.addItem("-- Select VFX Breakdown --", None)

        # If no RFQ selected, clear everything and return
        if not rfq:
            self.vfx_breakdown_combo.blockSignals(False)
            self.vfx_breakdown_set_btn.setEnabled(False)
            self._clear_vfx_breakdown_table()
            self._set_vfx_breakdown_status("Select an RFQ to view VFX Breakdowns.")
            return

        breakdowns = []
        try:
            proj = self.parent_app.sg_project_combo.itemData(self.parent_app.sg_project_combo.currentIndex())
            if proj:
                logger.info(f"Loading ALL VFX Breakdowns in Project {proj.get('code')} (ID {proj.get('id')})")
                breakdowns = self.sg_session.get_vfx_breakdowns(proj["id"], fields=["id", "code", "name", "updated_at"])
            else:
                logger.info("No project selected; cannot load project breakdowns.")
        except Exception as e:
            logger.error(f"Error populating VFX Breakdown list: {e}", exc_info=True)
            breakdowns = []

        for breakdown in breakdowns:
            label = breakdown.get("code") or breakdown.get("name") or f"ID {breakdown.get('id', 'N/A')}"
            self.vfx_breakdown_combo.addItem(label, breakdown)

        self.vfx_breakdown_combo.blockSignals(False)

        # Enable Set button only if there are options and an RFQ is selected
        self.vfx_breakdown_set_btn.setEnabled(len(breakdowns) > 0)

        # Status & selection
        if breakdowns:
            self._set_vfx_breakdown_status(f"Loaded {len(breakdowns)} VFX Breakdown(s) in project.")
            # Optionally auto-select the currently linked one if RFQ has it
            linked = rfq.get("sg_vfx_breakdown")
            linked_id = linked.get("id") if isinstance(linked, dict) else None
            if isinstance(linked, list) and linked:
                linked_id = (linked[0] or {}).get("id")

            if linked_id:
                # try select it
                if not self._select_vfx_breakdown_by_id(linked_id):
                    if auto_select and self.vfx_breakdown_combo.count() > 1:
                        self.vfx_breakdown_combo.setCurrentIndex(1)
            else:
                if auto_select and self.vfx_breakdown_combo.count() > 1:
                    self.vfx_breakdown_combo.setCurrentIndex(1)
        else:
            self._set_vfx_breakdown_status("No VFX Breakdowns found in this project.")
            self._clear_vfx_breakdown_table()

    def _set_vfx_breakdown_status(self, message, is_error=False):
        """Set the status message.

        Args:
            message: Status message to display
            is_error: Whether this is an error message (changes color)
        """
        color = "#ff8080" if is_error else "#a0a0a0"
        self.vfx_breakdown_status_label.setStyleSheet(f"color: {color}; padding: 2px 0;")
        self.vfx_breakdown_status_label.setText(message)

    def _clear_vfx_breakdown_table(self):
        """Clear the VFX Breakdown table."""
        self.vfx_breakdown_table.setRowCount(0)
        self.beat_data_by_row.clear()
        self.all_beats_data.clear()
        self.filtered_row_indices.clear()
        self.display_row_to_data_row.clear()
        self.sort_column = None
        self.sort_direction = None
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.row_count_label.setText("Showing 0 of 0 rows")
        self._update_header_sort_indicators()

    def _on_vfx_breakdown_changed(self, index):
        """Handle VFX Breakdown selection change."""
        breakdown = self.vfx_breakdown_combo.itemData(index)
        if not breakdown:
            self._clear_vfx_breakdown_table()
            if index == 0:
                self._set_vfx_breakdown_status("Select a VFX Breakdown to view its details.")
            return
        try:
            self._load_vfx_breakdown_details(breakdown)
        except Exception as exc:
            logger.error(f"Failed to load VFX Breakdown details: {exc}", exc_info=True)
            self._clear_vfx_breakdown_table()
            self._set_vfx_breakdown_status("Failed to load VFX Breakdown details.", is_error=True)

    def _get_vfx_breakdown_fields_to_fetch(self, entity_type):
        """Return the actual fields to fetch based on our allowlist and SG schema."""
        try:
            schema = self.sg_session.get_entity_schema(entity_type) or {}
        except Exception:
            schema = {}

        schema_fields = set(schema.keys())

        fields_to_fetch = []
        for f in self.vfx_breakdown_field_allowlist:
            if f == "id":
                continue  # id is always returned
            if f in schema_fields:
                fields_to_fetch.append(f)

        return fields_to_fetch

    def _populate_vfx_breakdown_table_filtered(self, field_map, label_overrides=None):
        """Populate the table with only our selected fields."""
        self._clear_vfx_breakdown_table()

        label_overrides = label_overrides or {}
        rows = []

        for field_name, value in field_map.items():
            if value is None:
                continue
            label = (
                    label_overrides.get(field_name)
                    or self.vfx_breakdown_field_labels.get(field_name)
                    or field_name
            )
            rows.append((label, self._format_sg_value(value)))

        self.vfx_breakdown_table.setRowCount(len(rows))
        for row_index, (field_label, value) in enumerate(rows):
            field_item = QtWidgets.QTableWidgetItem(field_label)
            field_item.setFlags(field_item.flags() ^ QtCore.Qt.ItemIsEditable)

            value_item = QtWidgets.QTableWidgetItem(value)
            value_item.setFlags(value_item.flags() ^ QtCore.Qt.ItemIsEditable)
            value_item.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

            self.vfx_breakdown_table.setItem(row_index, 0, field_item)
            self.vfx_breakdown_table.setItem(row_index, 1, value_item)

        display_name = self.vfx_breakdown_combo.currentText()
        self._set_vfx_breakdown_status(f"Loaded details for '{display_name}'.")
        self.vfx_breakdown_table.resizeColumnsToContents()
        self.vfx_breakdown_table.horizontalHeader().setStretchLastSection(True)

    def _ensure_vfx_breakdown_schema(self, breakdown):
        """Ensure VFX Breakdown schema is cached."""
        if not breakdown:
            return None

        entity_type = breakdown.get("type") or self.vfx_breakdown_entity_type
        if not entity_type:
            entity_type = self.sg_session.get_vfx_breakdown_entity_type()

        # Refresh cache if type changed or empty cache
        if entity_type != self.vfx_breakdown_entity_type or not self.vfx_breakdown_field_names:
            field_names, labels = self.sg_session.get_entity_fields_with_labels(entity_type)
            if not field_names:
                raise ValueError(f"No schema fields returned for entity type {entity_type}")

            labels = labels or {}
            # Normalize labels
            clean_labels = {str(k): self._normalize_label(v) for k, v in labels.items()}
            clean_field_names = [str(f) for f in field_names]

            def sort_key(field):
                return (clean_labels.get(field) or field).casefold()

            sorted_fields = sorted(clean_field_names, key=sort_key)

            self.vfx_breakdown_entity_type = entity_type
            self.vfx_breakdown_field_names = sorted_fields
            self.vfx_breakdown_field_labels = clean_labels

        return self.vfx_breakdown_entity_type

    def _load_vfx_breakdown_details(self, breakdown):
        """Load VFX Breakdown details (beats)."""
        if not breakdown or "id" not in breakdown:
            self._clear_vfx_breakdown_table()
            self._set_vfx_breakdown_status("Invalid VFX Breakdown selection.", is_error=True)
            return

        # Fetch schema for Beat entity
        if not self.field_schema:
            self._fetch_beats_schema()

        breakdown_id = int(breakdown["id"])

        base_fields = [
            "id", "code", "sg_beat_id", "sg_vfx_breakdown_scene", "sg_page",
            "sg_script_excerpt", "description", "sg_vfx_type", "sg_complexity",
            "sg_category", "sg_vfx_description", "sg_number_of_shots"
        ]
        extra_fields = ["updated_at", "updated_by"]
        fields = base_fields + extra_fields

        order = [
            {"field_name": "sg_page", "direction": "asc"},
            {"field_name": "code", "direction": "asc"},
        ]

        # Log query
        logger.info("=" * 60)
        logger.info("Fetching Beats for VFX Breakdown…")
        logger.info(f"  Entity      : CustomEntity02")
        logger.info(f"  Parent field: sg_parent -> CustomEntity01({breakdown_id})")
        logger.info(f"  Fields      : {fields}")
        logger.info(f"  Order       : {order}")
        logger.info("=" * 60)

        beats = []
        try:
            beats = self.sg_session.get_beats_for_vfx_breakdown(breakdown_id, fields=fields, order=order)
        except Exception as e:
            logger.warning(f"Primary query failed ({e}). Retrying without extra fields…")
            try:
                beats = self.sg_session.get_beats_for_vfx_breakdown(breakdown_id, fields=base_fields, order=order)
            except Exception as e2:
                logger.error(f"ShotGrid query for Beats failed: {e2}", exc_info=True)
                self._clear_vfx_breakdown_table()
                self._set_vfx_breakdown_status("Failed to load Beats for this Breakdown.", is_error=True)
                return

        self._populate_beats_table(beats)

    def _populate_beats_table(self, beats):
        """Populate the beats table."""
        # Clear existing data
        self.all_beats_data = beats.copy() if beats else []
        self.filtered_row_indices.clear()
        self.display_row_to_data_row.clear()
        self.beat_data_by_row.clear()
        self.undo_stack.clear()
        self.redo_stack.clear()

        if not beats:
            self._set_vfx_breakdown_status("No Beats linked to this VFX Breakdown.")
            self.vfx_breakdown_table.setRowCount(0)
            self.row_count_label.setText("Showing 0 of 0 rows")
            return

        # Apply filters and sorting (which will populate the table)
        self._apply_filters()

        # Use autosizer
        self._autosize_beat_columns(min_px=80, max_px=700, extra_padding=28)

        display_name = self.vfx_breakdown_combo.currentText()
        self._set_vfx_breakdown_status(f"Loaded {len(beats)} Beat(s) for '{display_name}'.")

    def _format_sg_value(self, value):
        """Format a ShotGrid value for display."""
        if value is None:
            return ""

        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")

        if isinstance(value, date):
            return value.strftime("%Y-%m-%d")

        if isinstance(value, list):
            formatted_items = [self._format_sg_value(item) for item in value if item is not None]
            formatted_items = [item for item in formatted_items if item]
            return ", ".join(formatted_items) if formatted_items else "-"

        if isinstance(value, dict):
            for key in ("name", "code", "content", "title", "description"):
                if key in value and value[key]:
                    return str(value[key])

            if "id" in value and "type" in value:
                return f"{value['type']} {value['id']}"

            try:
                return json.dumps(value, default=str)
            except TypeError:
                return str(value)

        if isinstance(value, bool):
            return "Yes" if value else "No"

        return str(value)
