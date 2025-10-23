from PySide6 import QtWidgets, QtCore, QtGui
import json
import logging
from datetime import datetime, date

try:
    from .logger import logger
except ImportError:
    logger = logging.getLogger("FFPackageManager")


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

    def __init__(self, table, row, col, old_value, new_value, beat_data, field_name, sg_session):
        self.table = table
        self.row = row
        self.col = col
        self.old_value = old_value
        self.new_value = new_value
        self.beat_data = beat_data
        self.field_name = field_name
        self.sg_session = sg_session

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
        """Parse text value to appropriate type based on field name."""
        if not text or text == "-" or text == "":
            return None

        # Number fields
        if field_name in ("sg_page", "sg_numer_of_shots", "sg_number_of_shots", "sg_beat_id"):
            try:
                value = int(text)
                logger.debug(f"Parsed '{text}' as int: {value} for field '{field_name}'")
                return value
            except ValueError:
                try:
                    value = float(text)
                    logger.debug(f"Parsed '{text}' as float: {value} for field '{field_name}'")
                    return value
                except ValueError:
                    logger.warning(f"Failed to parse '{text}' as number for field '{field_name}'")
                    raise ValueError(f"Invalid number format: '{text}'")

        # Text fields
        return text


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
            "sg_numer_of_shots",  # your original spelling
            "sg_number_of_shots",  # fallback if schema uses this spelling
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
            "sg_numer_of_shots": "# Shots",
            "sg_number_of_shots": "# Shots",
        }

        # UI widgets
        self.vfx_breakdown_combo = None
        self.vfx_breakdown_set_btn = None
        self.vfx_breakdown_refresh_btn = None
        self.vfx_breakdown_status_label = None
        self.vfx_breakdown_table = None
        self.vfx_beat_columns = []

        # Undo/Redo stack
        self.undo_stack = []
        self.redo_stack = []

        # Store beat data for each row
        self.beat_data_by_row = {}

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

        # Table for beats
        self.vfx_beat_columns = [
            "id", "code", "sg_beat_id", "sg_vfx_breakdown_scene", "sg_page",
            "sg_script_excerpt", "description", "sg_vfx_type", "sg_complexity",
            "sg_category", "sg_vfx_description", "sg_numer_of_shots",
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

        row = item.row()
        col = item.column()
        field_name = self.vfx_beat_columns[col]

        # Get beat data for this row
        beat_data = self.beat_data_by_row.get(row)
        if not beat_data:
            logger.warning(f"No beat data found for row {row}")
            return

        new_value = item.text()

        # Get old value from beat_data
        old_value_raw = beat_data.get(field_name)
        if field_name == "sg_numer_of_shots":
            if old_value_raw is None:
                old_value_raw = beat_data.get("sg_number_of_shots")
        old_value = self._format_sg_value(old_value_raw)

        # Check if value actually changed
        if new_value == old_value:
            logger.debug(f"No change detected for row {row}, col {col} ({field_name})")
            return

        logger.info(f"Cell changed at row {row}, col {col} ({field_name}): '{old_value}' -> '{new_value}'")
        logger.info(f"Beat ID: {beat_data.get('id')}, Field type: {type(old_value_raw).__name__}")

        # Create undo command
        command = EditCommand(
            self.vfx_breakdown_table,
            row,
            col,
            old_value,
            new_value,
            beat_data,
            field_name,
            self.sg_session
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

            # Update the beat_data with new value
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
        self.undo_stack.clear()
        self.redo_stack.clear()

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

        shots_field = None
        if "sg_numer_of_shots" in schema_fields:
            shots_field = "sg_numer_of_shots"
        elif "sg_number_of_shots" in schema_fields:
            shots_field = "sg_number_of_shots"

        fields_to_fetch = []
        for f in self.vfx_breakdown_field_allowlist:
            if f == "id":
                continue  # id is always returned
            if f in schema_fields:
                fields_to_fetch.append(f)

        if shots_field and shots_field not in fields_to_fetch:
            fields_to_fetch.append(shots_field)

        return fields_to_fetch, shots_field

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
            "sg_category", "sg_vfx_description", "sg_numer_of_shots", "sg_number_of_shots"
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
        # Block signals during population
        self.vfx_breakdown_table.blockSignals(True)

        table = self.vfx_breakdown_table
        table.setRowCount(0)
        self.beat_data_by_row.clear()
        self.undo_stack.clear()
        self.redo_stack.clear()

        if not beats:
            self._set_vfx_breakdown_status("No Beats linked to this VFX Breakdown.")
            self.vfx_breakdown_table.blockSignals(False)
            return

        table.setRowCount(len(beats))

        def _shots_value(row):
            val = row.get("sg_numer_of_shots")
            if val is None:
                val = row.get("sg_number_of_shots")
            return val

        # Read-only columns (should not be editable)
        readonly_columns = ["id", "updated_at", "updated_by"]

        for r, beat in enumerate(beats):
            # Store beat data for this row
            self.beat_data_by_row[r] = beat

            for c, field in enumerate(self.vfx_beat_columns):
                if field == "sg_numer_of_shots":
                    value = _shots_value(beat)
                else:
                    value = beat.get(field)
                text = self._format_sg_value(value)

                it = QtWidgets.QTableWidgetItem(text)

                # Make read-only columns non-editable
                if field in readonly_columns:
                    it.setFlags(it.flags() & ~QtCore.Qt.ItemIsEditable)
                    # Add visual indicator for read-only
                    it.setForeground(QtGui.QColor("#888888"))
                else:
                    # Make editable
                    it.setFlags(it.flags() | QtCore.Qt.ItemIsEditable)

                # alignment
                if field in ("id", "sg_page", "sg_numer_of_shots"):
                    it.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                elif field == "updated_at":
                    it.setTextAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
                else:
                    it.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

                table.setItem(r, c, it)

                # Set item delegate for List fields
                if field in self.field_schema:
                    field_info = self.field_schema[field]
                    if field_info.get("data_type") == "list":
                        list_values = field_info.get("list_values", [])
                        if list_values:
                            delegate = ComboBoxDelegate(field, list_values, self.vfx_breakdown_table)
                            self.vfx_breakdown_table.setItemDelegateForColumn(c, delegate)
                            logger.info(f"Set combo box delegate for column {c} ({field}) with values: {list_values}")

        # Unblock signals
        self.vfx_breakdown_table.blockSignals(False)

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
