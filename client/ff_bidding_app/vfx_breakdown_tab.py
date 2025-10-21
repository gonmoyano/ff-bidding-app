from PySide6 import QtWidgets, QtCore
import json
import logging
from datetime import datetime, date

try:
    from .logger import logger
except ImportError:
    logger = logging.getLogger("FFPackageManager")


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

        layout.addWidget(self.vfx_breakdown_table)

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
            rfq: RFQ data dict (optional)
            auto_select: Whether to auto-select a breakdown (default: True)
        """
        if not self.parent_app:
            return

        self.vfx_breakdown_combo.blockSignals(True)
        self.vfx_breakdown_combo.clear()
        self.vfx_breakdown_combo.addItem("-- Select VFX Breakdown --", None)

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
        rfq_selected = bool(self.parent_app.rfq_combo.itemData(self.parent_app.rfq_combo.currentIndex())) if self.parent_app else False
        self.vfx_breakdown_set_btn.setEnabled(rfq_selected and len(breakdowns) > 0)

        # Status & selection
        if breakdowns:
            self._set_vfx_breakdown_status(f"Loaded {len(breakdowns)} VFX Breakdown(s) in project.")
            # Optionally auto-select the currently linked one if RFQ has it
            if rfq:
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
        table = self.vfx_breakdown_table
        table.setRowCount(0)

        if not beats:
            self._set_vfx_breakdown_status("No Beats linked to this VFX Breakdown.")
            return

        table.setRowCount(len(beats))

        def _shots_value(row):
            val = row.get("sg_numer_of_shots")
            if val is None:
                val = row.get("sg_number_of_shots")
            return val

        for r, beat in enumerate(beats):
            for c, field in enumerate(self.vfx_beat_columns):
                if field == "sg_numer_of_shots":
                    value = _shots_value(beat)
                else:
                    value = beat.get(field)
                text = self._format_sg_value(value)

                it = QtWidgets.QTableWidgetItem(text)
                it.setFlags(it.flags() ^ QtCore.Qt.ItemIsEditable)

                # alignment
                if field in ("id", "sg_page", "sg_numer_of_shots"):
                    it.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                elif field == "updated_at":
                    it.setTextAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
                else:
                    it.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

                table.setItem(r, c, it)

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
