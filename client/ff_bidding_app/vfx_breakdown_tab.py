from PySide6 import QtWidgets, QtCore, QtGui
import json
import logging
import random
import string
from datetime import datetime, date

try:
    from .logger import logger
    from .settings import AppSettings
except ImportError:
    logger = logging.getLogger("FFPackageManager")
    from settings import AppSettings


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


class PasteCommand:
    """Command pattern for undo/redo of paste operations."""

    def __init__(self, changes, sg_session, field_schema=None):
        """
        Initialize paste command.

        Args:
            changes: List of dicts with keys: table, row, col, old_value, new_value, beat_data, field_name
            sg_session: ShotGrid session object
            field_schema: Field schema information
        """
        self.changes = changes
        self.sg_session = sg_session
        self.field_schema = field_schema or {}

    def undo(self):
        """Undo all paste changes."""
        for change in self.changes:
            item = change['table'].item(change['row'], change['col'])
            if item:
                item.setText(change['old_value'])
                # Update ShotGrid
                self._update_shotgrid(change['old_value'], change['beat_data'], change['field_name'])

    def redo(self):
        """Redo all paste changes."""
        for change in self.changes:
            item = change['table'].item(change['row'], change['col'])
            if item:
                item.setText(change['new_value'])
                # Update ShotGrid
                self._update_shotgrid(change['new_value'], change['beat_data'], change['field_name'])

    def _update_shotgrid(self, value, beat_data, field_name):
        """Update ShotGrid with the value."""
        beat_id = beat_data.get("id")
        if not beat_id:
            logger.error("No beat ID found for update")
            raise ValueError("No beat ID found for update")

        # Convert string value back to appropriate type
        update_value = self._parse_value(value, field_name)

        # Update on ShotGrid
        self.sg_session.sg.update("CustomEntity02", beat_id, {field_name: update_value})
        logger.info(f"Updated Beat {beat_id} field '{field_name}' to: {update_value}")

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
                if "." in text:
                    return float(text)
                else:
                    return int(text)
            except ValueError:
                logger.warning(f"Could not parse '{text}' as number for field '{field_name}'")
                return None

        elif data_type == "float":
            try:
                return float(text)
            except ValueError:
                logger.warning(f"Could not parse '{text}' as float for field '{field_name}'")
                return None

        elif data_type == "checkbox":
            return text.lower() in ("yes", "true", "1")

        elif data_type == "date":
            if text == "-" or text == "":
                return None
            try:
                return datetime.strptime(text, "%Y-%m-%d").date()
            except ValueError:
                logger.warning(f"Could not parse '{text}' as date for field '{field_name}'")
                return None

        # Default: return as string
        return text


class AddBeatCommand:
    """Command pattern for undo/redo of beat addition."""

    def __init__(self, tab, row, beat_data, sg_beat_id):
        """Initialize the add beat command.

        Args:
            tab: VFXBreakdownTab instance
            row: Row index where beat was inserted
            beat_data: Beat data dictionary from ShotGrid
            sg_beat_id: ShotGrid ID of the created beat
        """
        self.tab = tab
        self.row = row
        self.beat_data = beat_data
        self.sg_beat_id = sg_beat_id

    def undo(self):
        """Undo the beat addition (delete it)."""
        try:
            # Delete from ShotGrid
            self.tab.sg_session.sg.delete("CustomEntity02", self.sg_beat_id)
            logger.info(f"Deleted beat {self.sg_beat_id} from ShotGrid (undo)")

            # Remove from table
            self.tab.vfx_breakdown_table.blockSignals(True)
            self.tab.vfx_breakdown_table.removeRow(self.row)
            self.tab.vfx_breakdown_table.blockSignals(False)

            # Update beat_data_by_row mapping
            self.tab._rebuild_beat_data_mapping()

        except Exception as e:
            logger.error(f"Failed to undo beat addition: {e}", exc_info=True)

    def redo(self):
        """Redo the beat addition."""
        try:
            # Re-create in ShotGrid
            result = self.tab.sg_session.sg.create("CustomEntity02", self.beat_data)
            self.sg_beat_id = result["id"]
            logger.info(f"Re-created beat {self.sg_beat_id} in ShotGrid (redo)")

            # Re-insert in table
            self.tab._insert_beat_row(self.row, result)

        except Exception as e:
            logger.error(f"Failed to redo beat addition: {e}", exc_info=True)


class DeleteBeatCommand:
    """Command pattern for undo/redo of beat deletion."""

    def __init__(self, tab, row, beat_data):
        """Initialize the delete beat command.

        Args:
            tab: VFXBreakdownTab instance
            row: Row index that was deleted
            beat_data: Beat data dictionary from ShotGrid
        """
        self.tab = tab
        self.row = row
        self.beat_data = beat_data
        self.sg_beat_id = beat_data.get("id")

    def undo(self):
        """Undo the beat deletion (re-create it)."""
        try:
            # Re-create in ShotGrid
            result = self.tab.sg_session.sg.create("CustomEntity02", self.beat_data)
            self.sg_beat_id = result["id"]
            logger.info(f"Re-created beat {self.sg_beat_id} in ShotGrid (undo delete)")

            # Re-insert in table
            self.tab._insert_beat_row(self.row, result)

        except Exception as e:
            logger.error(f"Failed to undo beat deletion: {e}", exc_info=True)

    def redo(self):
        """Redo the beat deletion."""
        try:
            # Delete from ShotGrid
            self.tab.sg_session.sg.delete("CustomEntity02", self.sg_beat_id)
            logger.info(f"Deleted beat {self.sg_beat_id} from ShotGrid (redo)")

            # Remove from table
            self.tab.vfx_breakdown_table.blockSignals(True)
            self.tab.vfx_breakdown_table.removeRow(self.row)
            self.tab.vfx_breakdown_table.blockSignals(False)

            # Update beat_data_by_row mapping
            self.tab._rebuild_beat_data_mapping()

        except Exception as e:
            logger.error(f"Failed to redo beat deletion: {e}", exc_info=True)


class AddVFXBreakdownDialog(QtWidgets.QDialog):
    """Dialog for creating a new VFX Breakdown."""

    def __init__(self, existing_breakdowns, parent=None):
        """Initialize the dialog.

        Args:
            existing_breakdowns: List of existing VFX Breakdown dicts with 'id' and 'code'
            parent: Parent widget
        """
        super().__init__(parent)
        self.existing_breakdowns = existing_breakdowns
        self.setWindowTitle("Add VFX Breakdown")
        self.setModal(True)
        self.setMinimumWidth(400)

        self._build_ui()

    def _build_ui(self):
        """Build the dialog UI."""
        layout = QtWidgets.QVBoxLayout(self)

        # Creation mode
        mode_layout = QtWidgets.QHBoxLayout()
        mode_label = QtWidgets.QLabel("Mode:")
        mode_layout.addWidget(mode_label)

        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItem("Create empty")
        self.mode_combo.addItem("Copy from existing")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self.mode_combo, stretch=1)

        layout.addLayout(mode_layout)

        # Name field
        name_layout = QtWidgets.QHBoxLayout()
        name_label = QtWidgets.QLabel("Name:")
        name_layout.addWidget(name_label)

        self.name_field = QtWidgets.QLineEdit()
        self.name_field.setPlaceholderText("Enter VFX Breakdown name...")
        name_layout.addWidget(self.name_field, stretch=1)

        layout.addLayout(name_layout)

        # Copy from dropdown
        copy_layout = QtWidgets.QHBoxLayout()
        copy_label = QtWidgets.QLabel("Copy from:")
        copy_layout.addWidget(copy_label)

        self.copy_combo = QtWidgets.QComboBox()
        self.copy_combo.addItem("-- Select VFX Breakdown --", None)
        for breakdown in self.existing_breakdowns:
            label = breakdown.get("code") or breakdown.get("name") or f"ID {breakdown.get('id', 'N/A')}"
            self.copy_combo.addItem(label, breakdown)
        copy_layout.addWidget(self.copy_combo, stretch=1)

        layout.addLayout(copy_layout)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()

        self.ok_button = QtWidgets.QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_button)

        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

        # Initial state
        self._on_mode_changed(0)

    def _on_mode_changed(self, index):
        """Handle mode change."""
        is_copy_mode = (index == 1)
        self.copy_combo.setEnabled(is_copy_mode)

    def get_result(self):
        """Get the dialog result.

        Returns:
            dict: {"mode": "empty" or "copy", "name": str, "source": breakdown_dict or None}
        """
        mode = "empty" if self.mode_combo.currentIndex() == 0 else "copy"
        name = self.name_field.text().strip()
        source = self.copy_combo.currentData() if mode == "copy" else None

        return {
            "mode": mode,
            "name": name,
            "source": source
        }


class RemoveVFXBreakdownDialog(QtWidgets.QDialog):
    """Dialog for removing a VFX Breakdown."""

    def __init__(self, existing_breakdowns, parent=None):
        """Initialize the dialog.

        Args:
            existing_breakdowns: List of existing VFX Breakdown dicts with 'id' and 'code'
            parent: Parent widget
        """
        super().__init__(parent)
        self.existing_breakdowns = existing_breakdowns
        self.setWindowTitle("Remove VFX Breakdown")
        self.setModal(True)
        self.setMinimumWidth(450)

        # Generate random confirmation string
        self.confirmation_string = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

        self._build_ui()

    def _build_ui(self):
        """Build the dialog UI."""
        layout = QtWidgets.QVBoxLayout(self)

        # Warning message
        warning_label = QtWidgets.QLabel(
            "⚠️ WARNING: This action cannot be undone!\n"
            "Deleting a VFX Breakdown will also delete all associated Beats."
        )
        warning_label.setStyleSheet("color: #ff6666; font-weight: bold; padding: 10px;")
        warning_label.setWordWrap(True)
        layout.addWidget(warning_label)

        # Select breakdown to delete
        select_layout = QtWidgets.QHBoxLayout()
        select_label = QtWidgets.QLabel("Select VFX Breakdown:")
        select_layout.addWidget(select_label)

        self.breakdown_combo = QtWidgets.QComboBox()
        self.breakdown_combo.addItem("-- Select VFX Breakdown --", None)
        for breakdown in self.existing_breakdowns:
            label = breakdown.get("code") or breakdown.get("name") or f"ID {breakdown.get('id', 'N/A')}"
            self.breakdown_combo.addItem(label, breakdown)
        select_layout.addWidget(self.breakdown_combo, stretch=1)

        layout.addLayout(select_layout)

        # Confirmation section
        layout.addSpacing(20)

        confirm_label = QtWidgets.QLabel(
            f"To confirm deletion, type the following string:\n\n{self.confirmation_string}"
        )
        confirm_label.setStyleSheet("font-weight: bold; padding: 10px;")
        confirm_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(confirm_label)

        # Confirmation input
        confirm_layout = QtWidgets.QHBoxLayout()
        confirm_input_label = QtWidgets.QLabel("Confirmation:")
        confirm_layout.addWidget(confirm_input_label)

        self.confirmation_field = QtWidgets.QLineEdit()
        self.confirmation_field.setPlaceholderText("Type confirmation string here...")
        self.confirmation_field.textChanged.connect(self._on_confirmation_changed)
        confirm_layout.addWidget(self.confirmation_field, stretch=1)

        layout.addLayout(confirm_layout)

        # Buttons
        layout.addSpacing(20)
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()

        self.delete_button = QtWidgets.QPushButton("Delete")
        self.delete_button.setEnabled(False)
        self.delete_button.setStyleSheet("background-color: #ff6666; color: white; font-weight: bold;")
        self.delete_button.clicked.connect(self.accept)
        button_layout.addWidget(self.delete_button)

        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def _on_confirmation_changed(self, text):
        """Handle confirmation text change."""
        is_valid = (text == self.confirmation_string)
        self.delete_button.setEnabled(is_valid)

    def get_selected_breakdown(self):
        """Get the selected breakdown to delete.

        Returns:
            dict: The selected breakdown or None
        """
        return self.breakdown_combo.currentData()


class RenameVFXBreakdownDialog(QtWidgets.QDialog):
    """Dialog for renaming a VFX Breakdown."""

    def __init__(self, current_name, parent=None):
        """Initialize the dialog.

        Args:
            current_name: Current name of the VFX Breakdown
            parent: Parent widget
        """
        super().__init__(parent)
        self.current_name = current_name
        self.setWindowTitle("Rename VFX Breakdown")
        self.setModal(True)
        self.setMinimumWidth(400)

        self._build_ui()

    def _build_ui(self):
        """Build the dialog UI."""
        layout = QtWidgets.QVBoxLayout(self)

        # Name field
        name_layout = QtWidgets.QHBoxLayout()
        name_label = QtWidgets.QLabel("New Name:")
        name_layout.addWidget(name_label)

        self.name_field = QtWidgets.QLineEdit()
        self.name_field.setText(self.current_name)
        self.name_field.selectAll()  # Select all text for easy editing
        self.name_field.setPlaceholderText("Enter new VFX Breakdown name...")
        name_layout.addWidget(self.name_field, stretch=1)

        layout.addLayout(name_layout)

        # Buttons
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

    def get_new_name(self):
        """Get the new name from the dialog.

        Returns:
            str: The new name
        """
        return self.name_field.text().strip()


class CompoundSortDialog(QtWidgets.QDialog):
    """Dialog for setting up compound (multi-column) sorting."""

    def __init__(self, column_names, current_sort=None, templates=None, parent=None):
        """Initialize the compound sort dialog.

        Args:
            column_names: List of column display names
            current_sort: Current sort configuration [(col_idx, direction), ...]
            templates: Dictionary of saved templates {name: [(col_idx, direction), ...]}
            parent: Parent widget
        """
        super().__init__(parent)
        self.column_names = column_names
        self.current_sort = current_sort or []
        self.templates = templates or {}
        self.applied_template_name = None  # Track which template was applied

        self.setWindowTitle("Compound Sorting")
        self.setModal(True)
        self.setMinimumWidth(500)

        self._build_ui()
        self._load_current_sort()

    def _build_ui(self):
        """Build the dialog UI."""
        layout = QtWidgets.QVBoxLayout(self)

        # Template section
        template_group = QtWidgets.QGroupBox("Sort Templates")
        template_layout = QtWidgets.QVBoxLayout(template_group)

        # Template selection
        template_row = QtWidgets.QHBoxLayout()
        template_label = QtWidgets.QLabel("Template:")
        template_row.addWidget(template_label)

        self.template_combo = QtWidgets.QComboBox()
        self.template_combo.addItem("(None)")
        for template_name in sorted(self.templates.keys()):
            self.template_combo.addItem(template_name)
        self.template_combo.currentTextChanged.connect(self._on_template_selected)
        template_row.addWidget(self.template_combo, stretch=1)

        self.delete_template_btn = QtWidgets.QPushButton("Delete")
        self.delete_template_btn.clicked.connect(self._delete_template)
        template_row.addWidget(self.delete_template_btn)

        template_layout.addLayout(template_row)

        # Save new template
        save_row = QtWidgets.QHBoxLayout()
        save_label = QtWidgets.QLabel("Save as:")
        save_row.addWidget(save_label)

        self.template_name_field = QtWidgets.QLineEdit()
        self.template_name_field.setPlaceholderText("Enter template name...")
        save_row.addWidget(self.template_name_field, stretch=1)

        self.save_template_btn = QtWidgets.QPushButton("Save Template")
        self.save_template_btn.clicked.connect(self._save_template)
        save_row.addWidget(self.save_template_btn)

        template_layout.addLayout(save_row)
        layout.addWidget(template_group)

        # Sorting criteria section
        sort_group = QtWidgets.QGroupBox("Sorting Criteria")
        sort_layout = QtWidgets.QVBoxLayout(sort_group)

        # Create 3 sort level dropdowns
        self.sort_widgets = []
        for i in range(3):
            level_layout = QtWidgets.QHBoxLayout()

            label = QtWidgets.QLabel(f"Level {i+1}:")
            label.setFixedWidth(60)
            level_layout.addWidget(label)

            # Column dropdown
            column_combo = QtWidgets.QComboBox()
            column_combo.addItem("(None)")
            for col_name in self.column_names:
                column_combo.addItem(col_name)
            level_layout.addWidget(column_combo, stretch=2)

            # Direction dropdown
            direction_combo = QtWidgets.QComboBox()
            direction_combo.addItem("Ascending", "asc")
            direction_combo.addItem("Descending", "desc")
            level_layout.addWidget(direction_combo, stretch=1)

            sort_layout.addLayout(level_layout)
            self.sort_widgets.append((column_combo, direction_combo))

        layout.addWidget(sort_group)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()

        self.apply_btn = QtWidgets.QPushButton("Apply")
        self.apply_btn.clicked.connect(self.accept)
        self.apply_btn.setDefault(True)
        button_layout.addWidget(self.apply_btn)

        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

    def _load_current_sort(self):
        """Load the current sort configuration into the dropdowns."""
        for i, (column_combo, direction_combo) in enumerate(self.sort_widgets):
            if i < len(self.current_sort):
                col_idx, direction = self.current_sort[i]
                # Set column (add 1 because index 0 is "(None)")
                column_combo.setCurrentIndex(col_idx + 1)
                # Set direction
                direction_combo.setCurrentIndex(0 if direction == "asc" else 1)
            else:
                column_combo.setCurrentIndex(0)
                direction_combo.setCurrentIndex(0)

    def _on_template_selected(self, template_name):
        """Handle template selection - auto-load the template."""
        self.delete_template_btn.setEnabled(template_name != "(None)")
        # Auto-load the template when selected
        if template_name != "(None)" and template_name in self.templates:
            self._load_template_config(self.templates[template_name])

    def _load_template_config(self, sort_config):
        """Load a sort configuration into the UI.

        Args:
            sort_config: List of (col_idx, direction) tuples
        """
        for i, (column_combo, direction_combo) in enumerate(self.sort_widgets):
            if i < len(sort_config):
                col_idx, direction = sort_config[i]
                column_combo.setCurrentIndex(col_idx + 1)
                direction_combo.setCurrentIndex(0 if direction == "asc" else 1)
            else:
                column_combo.setCurrentIndex(0)
                direction_combo.setCurrentIndex(0)

    def _save_template(self):
        """Save the current configuration as a template."""
        template_name = self.template_name_field.text().strip()
        if not template_name:
            QtWidgets.QMessageBox.warning(self, "No Name", "Please enter a template name.")
            return

        # Get current sort configuration
        sort_config = self.get_sort_configuration()
        if not sort_config:
            QtWidgets.QMessageBox.warning(self, "No Criteria", "Please configure at least one sort level.")
            return

        # Save template
        self.templates[template_name] = sort_config

        # Update combo box
        if self.template_combo.findText(template_name) == -1:
            self.template_combo.addItem(template_name)

        self.template_combo.setCurrentText(template_name)
        self.template_name_field.clear()

        # Mark this template as the one to apply
        self.applied_template_name = template_name

    def _delete_template(self):
        """Delete the selected template."""
        template_name = self.template_combo.currentText()
        if template_name == "(None)" or template_name not in self.templates:
            return

        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete template '{template_name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            del self.templates[template_name]
            index = self.template_combo.findText(template_name)
            if index >= 0:
                self.template_combo.removeItem(index)
            self.template_combo.setCurrentIndex(0)

    def get_sort_configuration(self):
        """Get the configured sort criteria.

        Returns:
            List of (column_index, direction) tuples
        """
        sort_config = []
        for column_combo, direction_combo in self.sort_widgets:
            col_idx = column_combo.currentIndex()
            if col_idx > 0:  # 0 is "(None)"
                col_idx -= 1  # Adjust for "(None)" item
                direction = direction_combo.currentData()
                sort_config.append((col_idx, direction))

        return sort_config

    def get_applied_template_name(self):
        """Get the name of the template that was applied.

        Returns:
            Template name or None
        """
        return self.applied_template_name


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

        # Undo/Redo stack
        self.undo_stack = []
        self.redo_stack = []

        # Store beat data for each row
        self.beat_data_by_row = {}

        # Settings manager for persistent storage
        self.app_settings = AppSettings()

        # Sorting and filtering state
        self.sort_column = None  # Currently sorted column index (for single-column sort)
        self.sort_direction = None  # 'asc' or 'desc' (for single-column sort)
        self.compound_sort_columns = []  # List of (column_index, direction) tuples for compound sorting
        self.sort_templates = self.app_settings.get_sort_templates()  # Load saved templates from settings
        self.all_beats_data = []  # Original unfiltered beat data
        self.filtered_row_indices = []  # Indices into all_beats_data that pass filters
        self.display_row_to_data_row = {}  # Maps displayed row -> index in all_beats_data

        # UI widgets for search/filter
        self.global_search_box = None
        self.clear_filters_btn = None
        self.compound_sort_btn = None
        self.template_dropdown = None
        self.row_count_label = None

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

        self.vfx_breakdown_add_btn = QtWidgets.QPushButton("Add")
        self.vfx_breakdown_add_btn.clicked.connect(self._on_add_vfx_breakdown)
        selector_row.addWidget(self.vfx_breakdown_add_btn)

        self.vfx_breakdown_remove_btn = QtWidgets.QPushButton("Remove")
        self.vfx_breakdown_remove_btn.clicked.connect(self._on_remove_vfx_breakdown)
        selector_row.addWidget(self.vfx_breakdown_remove_btn)

        self.vfx_breakdown_rename_btn = QtWidgets.QPushButton("Rename")
        self.vfx_breakdown_rename_btn.clicked.connect(self._on_rename_vfx_breakdown)
        selector_row.addWidget(self.vfx_breakdown_rename_btn)

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

        # Compound Sorting button
        self.compound_sort_btn = QtWidgets.QPushButton("Compound Sorting")
        self.compound_sort_btn.clicked.connect(self._open_compound_sort_dialog)
        filter_controls.addWidget(self.compound_sort_btn)

        # Template dropdown
        filter_controls.addWidget(QtWidgets.QLabel("Template:"))
        self.template_dropdown = QtWidgets.QComboBox()
        self.template_dropdown.addItem("(No Template)")
        self.template_dropdown.setMinimumWidth(150)
        self.template_dropdown.currentTextChanged.connect(self._apply_sort_template)
        filter_controls.addWidget(self.template_dropdown)

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

        # Set cell selection mode (like Excel)
        self.vfx_breakdown_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectItems)
        self.vfx_breakdown_table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

        # Enable context menu
        self.vfx_breakdown_table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.vfx_breakdown_table.customContextMenuRequested.connect(self._on_table_context_menu)

        # Connect vertical header (row headers) click to select entire row
        self.vfx_breakdown_table.verticalHeader().sectionClicked.connect(self._on_row_header_clicked)

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
            elif event.key() == QtCore.Qt.Key_Delete:
                # Delete key pressed - use context menu delete functionality
                # Get the currently selected rows
                selected_rows = set()
                for item in self.vfx_breakdown_table.selectedItems():
                    selected_rows.add(item.row())
                if selected_rows:
                    # Delete the first selected row using existing delete method
                    self._delete_beat(min(selected_rows))
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

    def _on_header_clicked(self, column_index):
        """Handle header click for sorting.

        Args:
            column_index: Index of the clicked column
        """
        # Block single-column sorting if compound sorting is active
        if self.compound_sort_columns:
            logger.info("Single-column sorting disabled while compound sorting template is active")
            return

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
                # Remove existing indicators (including numbered ones like "1↑")
                import re
                original_text = re.sub(r'\s*\d*[↑↓]', '', original_text)

                # Check if this column is in compound sorting
                if self.compound_sort_columns:
                    for priority, (sort_col, sort_dir) in enumerate(self.compound_sort_columns, 1):
                        if col_idx == sort_col:
                            arrow = "↑" if sort_dir == "asc" else "↓"
                            header_item.setText(f"{original_text} {priority}{arrow}")
                            break
                    else:
                        # Not in compound sort
                        header_item.setText(original_text)
                # Check single-column sorting
                elif col_idx == self.sort_column and self.sort_direction:
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
        self.compound_sort_columns = []
        self.template_dropdown.setCurrentIndex(0)  # Reset to "(No Template)"
        self._update_header_sort_indicators()

        # Re-apply (which will show all rows)
        self._apply_filters()

        logger.info("Search and sorting cleared")

    def _open_compound_sort_dialog(self):
        """Open the compound sorting dialog."""
        # Get column headers for the dialog
        headers = [
            "ID", "Code", "Beat ID", "Scene", "Page",
            "Script Excerpt", "Description", "VFX Type", "Complexity",
            "Category", "VFX Description", "# Shots",
            "Updated At", "Updated By"
        ]

        # Open dialog
        dialog = CompoundSortDialog(
            column_names=headers,
            current_sort=self.compound_sort_columns.copy(),
            templates=self.sort_templates.copy(),
            parent=self
        )

        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            # Get the sort configuration
            sort_config = dialog.get_sort_configuration()
            self.compound_sort_columns = sort_config

            # Update templates if they were modified and save to persistent storage
            self.sort_templates = dialog.templates.copy()
            self.app_settings.set_sort_templates(self.sort_templates)
            self._update_template_dropdown()

            # Check if a template was applied in the dialog
            applied_template = dialog.get_applied_template_name()
            if applied_template:
                # Select the applied template in the main dropdown
                index = self.template_dropdown.findText(applied_template)
                if index >= 0:
                    self.template_dropdown.blockSignals(True)
                    self.template_dropdown.setCurrentIndex(index)
                    self.template_dropdown.blockSignals(False)
                logger.info(f"Applied template: {applied_template}")

            # Clear single-column sort when using compound sort
            if self.compound_sort_columns:
                self.sort_column = None
                self.sort_direction = None
            else:
                # If no compound sort, reset template dropdown to "(No Template)"
                self.template_dropdown.setCurrentIndex(0)

            # Apply the new sorting
            self._update_header_sort_indicators()
            self._apply_filters()

            logger.info(f"Compound sort applied: {len(sort_config)} levels")

    def _apply_sort_template(self, template_name):
        """Apply a saved sort template."""
        if template_name == "(No Template)" or not template_name:
            # Clear compound sorting to allow single-column sorting
            if self.compound_sort_columns:
                self.compound_sort_columns = []
                self._update_header_sort_indicators()
                self._apply_filters()
                logger.info("Compound sorting cleared - single-column sorting enabled")
            return

        if template_name in self.sort_templates:
            self.compound_sort_columns = self.sort_templates[template_name].copy()

            # Clear single-column sort when using template
            self.sort_column = None
            self.sort_direction = None

            # Apply the template
            self._update_header_sort_indicators()
            self._apply_filters()

            logger.info(f"Sort template applied: {template_name}")

    def _update_template_dropdown(self):
        """Update the template dropdown with current templates."""
        current_text = self.template_dropdown.currentText()
        self.template_dropdown.blockSignals(True)
        self.template_dropdown.clear()
        self.template_dropdown.addItem("(No Template)")

        for template_name in sorted(self.sort_templates.keys()):
            self.template_dropdown.addItem(template_name)

        # Try to restore previous selection
        index = self.template_dropdown.findText(current_text)
        if index >= 0:
            self.template_dropdown.setCurrentIndex(index)

        self.template_dropdown.blockSignals(False)

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

        # Apply sorting (compound sorting takes priority over single-column sorting)
        if self.compound_sort_columns:
            self.filtered_row_indices.sort(key=lambda idx: self._get_compound_sort_key(self.all_beats_data[idx]))
        elif self.sort_column is not None and self.sort_direction:
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
            return (0, 0)

        field_name = self.vfx_beat_columns[self.sort_column]
        value = beat_data.get(field_name)

        # Check if this is a known numeric field
        is_numeric_field = (
            field_name in ("id", "sg_page", "sg_number_of_shots") or
            (field_name in self.field_schema and
             self.field_schema[field_name].get("data_type") in ("number", "float"))
        )

        # Determine the type and convert to sortable value
        if value is None:
            # None values: use a marker to sort them first or last
            if is_numeric_field:
                # For numeric fields, treat as very small or very large number
                sort_type = 0  # numeric type
                if self.sort_direction == "desc":
                    sort_value = float('inf')
                else:
                    sort_value = float('-inf')
            else:
                # For text fields, empty string sorts first
                sort_type = 1  # text type
                if self.sort_direction == "desc":
                    sort_value = ""  # Empty strings will be reversed to sort last
                else:
                    sort_value = ""  # Empty strings sort first
        elif isinstance(value, (int, float)):
            # Numeric values
            sort_type = 0
            sort_value = float(value)
            if self.sort_direction == "desc":
                sort_value = -sort_value
        elif isinstance(value, datetime):
            # Date values
            sort_type = 0
            sort_value = value.timestamp() if hasattr(value, 'timestamp') else 0
            if self.sort_direction == "desc":
                sort_value = -sort_value
        elif isinstance(value, dict):
            # Entity references - extract string value
            sort_type = 1
            str_value = (value.get("name", "") or value.get("code", "") or "").lower()
            if self.sort_direction == "desc":
                sort_value = ReverseString(str_value)
            else:
                sort_value = str_value
        else:
            # Text values - try to detect if it's numeric
            sort_type = 1
            str_value = str(value).strip()

            # Try to convert to number for numeric sorting
            if is_numeric_field or str_value.replace('.', '', 1).replace('-', '', 1).isdigit():
                try:
                    # It's a numeric string
                    sort_type = 0
                    sort_value = float(str_value)
                    if self.sort_direction == "desc":
                        sort_value = -sort_value
                except (ValueError, TypeError):
                    # Fall back to string sorting
                    sort_type = 1
                    if self.sort_direction == "desc":
                        sort_value = ReverseString(str_value.lower())
                    else:
                        sort_value = str_value.lower()
            else:
                # String sorting
                if self.sort_direction == "desc":
                    sort_value = ReverseString(str_value.lower())
                else:
                    sort_value = str_value.lower()

        # Return tuple with type marker to ensure consistent comparisons
        return (sort_type, sort_value)

    def _get_compound_sort_key(self, beat_data):
        """Get compound sort key for a beat based on multiple sort columns.

        Returns a tuple of sort keys, one for each sorting level.
        """
        sort_keys = []

        for col_idx, direction in self.compound_sort_columns:
            if col_idx >= len(self.vfx_beat_columns):
                continue

            # Temporarily set the sort column and direction to reuse _get_sort_key logic
            old_column = self.sort_column
            old_direction = self.sort_direction

            self.sort_column = col_idx
            self.sort_direction = direction

            # Get the sort key for this column
            sort_key = self._get_sort_key(beat_data)
            sort_keys.append(sort_key)

            # Restore original values
            self.sort_column = old_column
            self.sort_direction = old_direction

        # Return tuple of all sort keys
        return tuple(sort_keys) if sort_keys else ((0, 0),)

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

        # Set up item delegates for List fields (once per column, not per row)
        for c, field in enumerate(self.vfx_beat_columns):
            if field in self.field_schema:
                field_info = self.field_schema[field]
                if field_info.get("data_type") == "list":
                    list_values = field_info.get("list_values", [])
                    if list_values:
                        delegate = ComboBoxDelegate(field, list_values, self.vfx_breakdown_table)
                        self.vfx_breakdown_table.setItemDelegateForColumn(c, delegate)

        for display_row, data_idx in enumerate(self.filtered_row_indices):
            # Store mapping
            self.display_row_to_data_row[display_row] = data_idx
            self.beat_data_by_row[display_row] = self.all_beats_data[data_idx]

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

        # Unblock signals
        self.vfx_breakdown_table.blockSignals(False)

    def _on_row_header_clicked(self, row):
        """Handle row header click to select entire row."""
        self.vfx_breakdown_table.selectRow(row)

    def _copy_selection(self):
        """Copy selected cells to clipboard."""
        selection = self.vfx_breakdown_table.selectedRanges()
        if not selection:
            return

        # Get the bounding rectangle of the selection
        rows = set()
        cols = set()
        for sel_range in selection:
            for row in range(sel_range.topRow(), sel_range.bottomRow() + 1):
                rows.add(row)
            for col in range(sel_range.leftColumn(), sel_range.rightColumn() + 1):
                cols.add(col)

        if not rows or not cols:
            return

        min_row = min(rows)
        max_row = max(rows)
        min_col = min(cols)
        max_col = max(cols)

        # Build the clipboard text (tab-separated for cells, newline for rows)
        clipboard_text = []
        for row in range(min_row, max_row + 1):
            row_data = []
            for col in range(min_col, max_col + 1):
                item = self.vfx_breakdown_table.item(row, col)
                text = item.text() if item else ""
                row_data.append(text)
            clipboard_text.append("\t".join(row_data))

        final_text = "\n".join(clipboard_text)

        # Copy to clipboard
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(final_text)

        num_cells = len(rows) * len(cols)
        self._set_vfx_breakdown_status(f"Copied {num_cells} cell(s) to clipboard")
        logger.info(f"Copied {len(rows)} row(s) × {len(cols)} col(s) to clipboard")

    def _paste_selection(self):
        """Paste from clipboard to selected cells with undo/redo support."""
        clipboard = QtWidgets.QApplication.clipboard()
        text = clipboard.text()

        if not text:
            return

        # Get selected items
        selected_items = self.vfx_breakdown_table.selectedItems()

        # Parse clipboard text (tab-separated for cells, newline for rows)
        rows_data = text.split("\n")
        if rows_data and rows_data[-1] == "":  # Remove trailing empty line
            rows_data = rows_data[:-1]

        # Check if clipboard contains a single value (no tabs or newlines)
        is_single_value = len(rows_data) == 1 and "\t" not in rows_data[0]

        # Collect all changes
        changes = []
        num_cells = 0

        # If single value and multiple cells selected, paste to all selected cells
        if is_single_value and len(selected_items) > 1:
            paste_value = rows_data[0]

            for item in selected_items:
                target_row = item.row()
                target_col = item.column()

                # Get the field name for this column
                field_name = self.vfx_beat_columns[target_col]

                # Skip read-only columns
                readonly_columns = ["id", "updated_at", "updated_by"]
                if field_name in readonly_columns:
                    continue

                # Get beat data for this row
                beat_data = self.beat_data_by_row.get(target_row)
                if not beat_data:
                    logger.warning(f"No beat data found for row {target_row}")
                    continue

                if not (item.flags() & QtCore.Qt.ItemIsEditable):
                    continue

                # Get old value
                old_value = item.text()

                # Check if value actually changed
                if paste_value == old_value:
                    continue

                # Add to changes list
                changes.append({
                    'table': self.vfx_breakdown_table,
                    'row': target_row,
                    'col': target_col,
                    'old_value': old_value,
                    'new_value': paste_value,
                    'beat_data': beat_data,
                    'field_name': field_name
                })
                num_cells += 1

        else:
            # Standard paste behavior: paste starting from current cell
            current_item = self.vfx_breakdown_table.currentItem()
            if not current_item:
                return

            start_row = current_item.row()
            start_col = current_item.column()

            for row_offset, row_text in enumerate(rows_data):
                cells = row_text.split("\t")
                for col_offset, cell_value in enumerate(cells):
                    target_row = start_row + row_offset
                    target_col = start_col + col_offset

                    # Check bounds
                    if target_row >= self.vfx_breakdown_table.rowCount():
                        break
                    if target_col >= self.vfx_breakdown_table.columnCount():
                        continue

                    # Get the field name for this column
                    field_name = self.vfx_beat_columns[target_col]

                    # Skip read-only columns
                    readonly_columns = ["id", "updated_at", "updated_by"]
                    if field_name in readonly_columns:
                        continue

                    # Get beat data for this row
                    beat_data = self.beat_data_by_row.get(target_row)
                    if not beat_data:
                        logger.warning(f"No beat data found for row {target_row}")
                        continue

                    item = self.vfx_breakdown_table.item(target_row, target_col)
                    if not item or not (item.flags() & QtCore.Qt.ItemIsEditable):
                        continue

                    # Get old value
                    old_value = item.text()

                    # Check if value actually changed
                    if cell_value == old_value:
                        continue

                    # Add to changes list
                    changes.append({
                        'table': self.vfx_breakdown_table,
                        'row': target_row,
                        'col': target_col,
                        'old_value': old_value,
                        'new_value': cell_value,
                        'beat_data': beat_data,
                        'field_name': field_name
                    })
                    num_cells += 1

        if not changes:
            self._set_vfx_breakdown_status("No changes to paste")
            return

        # Create paste command
        command = PasteCommand(changes, self.sg_session, field_schema=self.field_schema)

        # Execute the paste (update UI and ShotGrid)
        try:
            self._updating = True

            # Update UI
            for change in changes:
                item = change['table'].item(change['row'], change['col'])
                if item:
                    item.setText(change['new_value'])

            # Update ShotGrid for all changes
            command.redo()

            self._updating = False

            # Add to undo stack
            self.undo_stack.append(command)
            # Clear redo stack on new paste
            self.redo_stack.clear()

            # Update beat_data with new values
            for change in changes:
                parsed_value = command._parse_value(change['new_value'], change['field_name'])
                change['beat_data'][change['field_name']] = parsed_value

            self._set_vfx_breakdown_status(f"✓ Pasted {num_cells} cell(s) to ShotGrid")
            logger.info(f"Successfully pasted {num_cells} cells")

        except Exception as e:
            logger.error(f"Failed to paste cells: {e}", exc_info=True)
            # Revert the changes in UI
            self._updating = True
            for change in changes:
                item = change['table'].item(change['row'], change['col'])
                if item:
                    item.setText(change['old_value'])
            self._updating = False
            self._set_vfx_breakdown_status(f"Failed to paste cells", is_error=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Paste Failed",
                f"Failed to paste cells:\n{str(e)}\n\nChanges have been reverted."
            )

    def _on_table_context_menu(self, position):
        """Handle right-click context menu on table."""
        # Get the item at the position
        item = self.vfx_breakdown_table.itemAt(position)
        if not item:
            return

        row = item.row()

        # Create context menu
        menu = QtWidgets.QMenu(self)

        # Add beat above
        add_above_action = menu.addAction("Add Beat Above")
        add_above_action.triggered.connect(lambda: self._add_beat_above(row))

        # Add beat below
        add_below_action = menu.addAction("Add Beat Below")
        add_below_action.triggered.connect(lambda: self._add_beat_below(row))

        menu.addSeparator()

        # Delete beat
        delete_action = menu.addAction("Delete Beat")
        delete_action.triggered.connect(lambda: self._delete_beat(row))

        # Show menu at cursor position
        menu.exec(self.vfx_breakdown_table.viewport().mapToGlobal(position))

    def _add_beat_above(self, row):
        """Add a new beat above the specified row."""
        self._add_beat_at_row(row)

    def _add_beat_below(self, row):
        """Add a new beat below the specified row."""
        self._add_beat_at_row(row + 1)

    def _add_beat_at_row(self, row):
        """Add a new beat at the specified row."""
        try:
            # Get current breakdown
            breakdown = self.vfx_breakdown_combo.currentData()
            if not breakdown:
                QtWidgets.QMessageBox.warning(self, "No Breakdown", "Please select a VFX Breakdown first.")
                return

            breakdown_id = breakdown["id"]
            entity_type = self.sg_session.get_vfx_breakdown_entity_type()

            # Get current project
            proj = self.parent_app.sg_project_combo.itemData(self.parent_app.sg_project_combo.currentIndex()) if self.parent_app else None
            if not proj:
                QtWidgets.QMessageBox.warning(self, "No Project", "No project selected.")
                return

            project_id = proj["id"]

            # Create new beat data
            new_beat_data = {
                "project": {"type": "Project", "id": project_id},
                "sg_parent": {"type": entity_type, "id": breakdown_id},
                "code": f"New Beat"
            }

            # Create beat in ShotGrid
            result = self.sg_session.sg.create("CustomEntity02", new_beat_data)
            beat_id = result["id"]

            logger.info(f"Created new beat {beat_id} at row {row}")

            # Insert row in table
            self._insert_beat_row(row, result)

            # Create command for undo/redo
            command = AddBeatCommand(self, row, new_beat_data, beat_id)
            self.undo_stack.append(command)
            self.redo_stack.clear()

            self._set_vfx_breakdown_status(f"Added new beat at row {row + 1}")

        except Exception as e:
            logger.error(f"Failed to add beat: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to add beat:\n{str(e)}")

    def _delete_beat(self, row):
        """Delete the beat at the specified row."""
        try:
            # Get beat data
            beat_data = self.beat_data_by_row.get(row)
            if not beat_data:
                QtWidgets.QMessageBox.warning(self, "No Beat", "No beat found at this row.")
                return

            beat_id = beat_data.get("id")
            beat_name = beat_data.get("code") or f"Beat ID {beat_id}"

            # Confirmation dialog
            reply = QtWidgets.QMessageBox.question(
                self,
                "Confirm Deletion",
                f"Are you sure you want to delete beat '{beat_name}'?\n\nThis action can be undone with Ctrl+Z.",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )

            if reply != QtWidgets.QMessageBox.Yes:
                return

            # Delete from ShotGrid
            self.sg_session.sg.delete("CustomEntity02", beat_id)
            logger.info(f"Deleted beat {beat_id} from ShotGrid")

            # Remove from table
            self.vfx_breakdown_table.blockSignals(True)
            self.vfx_breakdown_table.removeRow(row)
            self.vfx_breakdown_table.blockSignals(False)

            # Update beat_data_by_row mapping
            self._rebuild_beat_data_mapping()

            # Create command for undo/redo
            command = DeleteBeatCommand(self, row, beat_data)
            self.undo_stack.append(command)
            self.redo_stack.clear()

            self._set_vfx_breakdown_status(f"Deleted beat '{beat_name}'")

        except Exception as e:
            logger.error(f"Failed to delete beat: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to delete beat:\n{str(e)}")

    def _insert_beat_row(self, row, beat):
        """Insert a beat row at the specified position.

        Args:
            row: Row index to insert at
            beat: Beat data dictionary from ShotGrid
        """
        self.vfx_breakdown_table.blockSignals(True)

        self.vfx_breakdown_table.insertRow(row)

        # Populate the row
        readonly_columns = ["id", "updated_at", "updated_by"]

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

            self.vfx_breakdown_table.setItem(row, c, it)

            # Set item delegate for List fields
            if field in self.field_schema:
                field_info = self.field_schema[field]
                if field_info.get("data_type") == "list":
                    list_values = field_info.get("list_values", [])
                    if list_values:
                        delegate = ComboBoxDelegate(field, list_values, self.vfx_breakdown_table)
                        self.vfx_breakdown_table.setItemDelegateForColumn(c, delegate)

        self.vfx_breakdown_table.blockSignals(False)

        # Update beat_data_by_row mapping
        self._rebuild_beat_data_mapping()

    def _rebuild_beat_data_mapping(self):
        """Rebuild the beat_data_by_row mapping after row insertion/deletion."""
        # Clear existing mapping
        old_mapping = self.beat_data_by_row.copy()
        self.beat_data_by_row.clear()

        # Rebuild based on current table rows
        for row in range(self.vfx_breakdown_table.rowCount()):
            # Try to find the beat data by ID from the first column
            id_item = self.vfx_breakdown_table.item(row, 0)
            if id_item:
                try:
                    beat_id = int(id_item.text())
                    # Find the beat data with this ID from old mapping
                    for old_row, beat_data in old_mapping.items():
                        if beat_data.get("id") == beat_id:
                            self.beat_data_by_row[row] = beat_data
                            break
                except ValueError:
                    pass

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

    def _on_add_vfx_breakdown(self):
        """Handle Add VFX Breakdown button click."""
        if not self.parent_app:
            return

        # Get current project
        proj = self.parent_app.sg_project_combo.itemData(self.parent_app.sg_project_combo.currentIndex())
        if not proj:
            QtWidgets.QMessageBox.warning(self, "No Project Selected", "Please select a project first.")
            return

        # Get existing breakdowns for the dialog
        try:
            existing_breakdowns = self.sg_session.get_vfx_breakdowns(proj["id"], fields=["id", "code", "name"])
        except Exception as e:
            logger.error(f"Failed to fetch existing breakdowns: {e}", exc_info=True)
            existing_breakdowns = []

        # Show dialog
        dialog = AddVFXBreakdownDialog(existing_breakdowns, parent=self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return

        # Get dialog result
        result = dialog.get_result()
        name = result["name"]
        mode = result["mode"]
        source = result["source"]

        # Validate name
        if not name:
            QtWidgets.QMessageBox.warning(self, "Invalid Name", "Please enter a name for the VFX Breakdown.")
            return

        # Validate source for copy mode
        if mode == "copy" and not source:
            QtWidgets.QMessageBox.warning(self, "No Source Selected", "Please select a VFX Breakdown to copy from.")
            return

        # Create the VFX Breakdown
        try:
            if mode == "empty":
                new_breakdown = self._create_empty_vfx_breakdown(proj["id"], name)
            else:  # copy
                # Show progress dialog for copy operation
                progress = QtWidgets.QProgressDialog(
                    "Copying VFX Breakdown...",
                    "Cancel",
                    0,
                    100,
                    self
                )
                progress.setWindowTitle("Copying VFX Breakdown")
                progress.setWindowModality(QtCore.Qt.WindowModal)
                progress.setMinimumDuration(0)  # Show immediately
                progress.setValue(0)

                # Create callback for progress updates
                def update_progress(current, total, message=""):
                    if progress.wasCanceled():
                        return False
                    percent = int((current / total) * 100) if total > 0 else 0
                    progress.setValue(percent)
                    if message:
                        progress.setLabelText(message)
                    QtWidgets.QApplication.processEvents()
                    return True

                new_breakdown = self._copy_vfx_breakdown(
                    source["id"],
                    name,
                    proj["id"],
                    progress_callback=update_progress
                )

                progress.setValue(100)
                progress.close()

            logger.info(f"Created VFX Breakdown: {new_breakdown}")

            # Refresh the combo box
            self._refresh_vfx_breakdowns()

            # Select the newly created breakdown
            if new_breakdown:
                self._select_vfx_breakdown_by_id(new_breakdown.get("id"))

            QtWidgets.QMessageBox.information(
                self,
                "Success",
                f"VFX Breakdown '{name}' created successfully."
            )

        except Exception as e:
            error_msg = str(e)
            # Check if operation was cancelled
            if "cancelled by user" in error_msg.lower():
                logger.info("VFX Breakdown creation cancelled by user")
                QtWidgets.QMessageBox.information(
                    self,
                    "Cancelled",
                    "VFX Breakdown creation was cancelled."
                )
            else:
                logger.error(f"Failed to create VFX Breakdown: {e}", exc_info=True)
                QtWidgets.QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to create VFX Breakdown:\n{error_msg}"
                )

    def _on_remove_vfx_breakdown(self):
        """Handle Remove VFX Breakdown button click."""
        if not self.parent_app:
            return

        # Get current project
        proj = self.parent_app.sg_project_combo.itemData(self.parent_app.sg_project_combo.currentIndex())
        if not proj:
            QtWidgets.QMessageBox.warning(self, "No Project Selected", "Please select a project first.")
            return

        # Get existing breakdowns for the dialog
        try:
            existing_breakdowns = self.sg_session.get_vfx_breakdowns(proj["id"], fields=["id", "code", "name"])
        except Exception as e:
            logger.error(f"Failed to fetch existing breakdowns: {e}", exc_info=True)
            existing_breakdowns = []

        if not existing_breakdowns:
            QtWidgets.QMessageBox.information(self, "No Breakdowns", "There are no VFX Breakdowns to remove.")
            return

        # Show dialog
        dialog = RemoveVFXBreakdownDialog(existing_breakdowns, parent=self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return

        # Get selected breakdown
        breakdown = dialog.get_selected_breakdown()
        if not breakdown:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Please select a VFX Breakdown to remove.")
            return

        # Delete the VFX Breakdown
        try:
            breakdown_id = breakdown["id"]
            breakdown_name = breakdown.get("code") or breakdown.get("name") or f"ID {breakdown_id}"
            entity_type = self.sg_session.get_vfx_breakdown_entity_type()

            logger.info(f"Deleting VFX Breakdown: {breakdown_name} (ID: {breakdown_id})")

            # Delete from ShotGrid
            self.sg_session.sg.delete(entity_type, breakdown_id)

            logger.info(f"Successfully deleted VFX Breakdown {breakdown_id}")

            # Clear the table if this was the currently selected breakdown
            current_breakdown = self.vfx_breakdown_combo.currentData()
            if current_breakdown and current_breakdown.get("id") == breakdown_id:
                self._clear_vfx_breakdown_table()

            # Refresh the combo box
            self._refresh_vfx_breakdowns()

            QtWidgets.QMessageBox.information(
                self,
                "Success",
                f"VFX Breakdown '{breakdown_name}' has been deleted."
            )

        except Exception as e:
            logger.error(f"Failed to delete VFX Breakdown: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to delete VFX Breakdown:\n{str(e)}"
            )

    def _on_rename_vfx_breakdown(self):
        """Handle Rename VFX Breakdown button click."""
        if not self.parent_app:
            return

        # Get currently selected breakdown
        breakdown = self.vfx_breakdown_combo.currentData()
        if not breakdown:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Please select a VFX Breakdown to rename.")
            return

        # Get current name
        current_name = breakdown.get("code") or breakdown.get("name") or f"ID {breakdown.get('id', 'N/A')}"

        # Show dialog
        dialog = RenameVFXBreakdownDialog(current_name, parent=self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return

        # Get new name
        new_name = dialog.get_new_name()
        if not new_name:
            QtWidgets.QMessageBox.warning(self, "Invalid Name", "Please enter a valid name.")
            return

        # Check if name actually changed
        if new_name == current_name:
            return

        # Rename the VFX Breakdown
        try:
            breakdown_id = breakdown["id"]
            entity_type = self.sg_session.get_vfx_breakdown_entity_type()

            logger.info(f"Renaming VFX Breakdown {breakdown_id}: '{current_name}' -> '{new_name}'")

            # Update in ShotGrid
            self.sg_session.sg.update(entity_type, breakdown_id, {"code": new_name})

            logger.info(f"Successfully renamed VFX Breakdown {breakdown_id}")

            # Refresh the combo box and maintain selection
            self._refresh_vfx_breakdowns()
            self._select_vfx_breakdown_by_id(breakdown_id)

            # Update RFQ label if this breakdown is currently set for the RFQ
            if self.parent_app:
                rfq = self.parent_app.rfq_combo.itemData(self.parent_app.rfq_combo.currentIndex())
                if rfq:
                    linked = rfq.get("sg_vfx_breakdown")
                    linked_id = None
                    if isinstance(linked, dict):
                        linked_id = linked.get("id")
                    elif isinstance(linked, list) and linked:
                        linked_id = linked[0].get("id") if linked[0] else None

                    if linked_id == breakdown_id:
                        # This breakdown is the current one for the RFQ, update the label
                        if hasattr(self.parent_app, "rfq_vfx_breakdown_label"):
                            self.parent_app.rfq_vfx_breakdown_label.setText(new_name)
                        logger.info(f"Updated RFQ label to show new breakdown name: '{new_name}'")

            QtWidgets.QMessageBox.information(
                self,
                "Success",
                f"VFX Breakdown renamed to '{new_name}'."
            )

        except Exception as e:
            logger.error(f"Failed to rename VFX Breakdown: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to rename VFX Breakdown:\n{str(e)}"
            )

    def _create_empty_vfx_breakdown(self, project_id, name):
        """Create an empty VFX Breakdown.

        Args:
            project_id: Project ID
            name: Name for the new VFX Breakdown

        Returns:
            dict: The created VFX Breakdown entity
        """
        entity_type = self.sg_session.get_vfx_breakdown_entity_type()

        data = {
            "code": name,
            "project": {"type": "Project", "id": project_id}
        }

        logger.info(f"Creating empty VFX Breakdown: {data}")
        result = self.sg_session.sg.create(entity_type, data)
        logger.info(f"Created VFX Breakdown: {result}")

        return result

    def _copy_vfx_breakdown(self, source_id, new_name, project_id, progress_callback=None):
        """Copy an existing VFX Breakdown with all its Beats.

        Args:
            source_id: ID of the VFX Breakdown to copy from
            new_name: Name for the new VFX Breakdown
            project_id: Project ID
            progress_callback: Optional callback function(current, total, message) -> bool

        Returns:
            dict: The created VFX Breakdown entity
        """
        entity_type = self.sg_session.get_vfx_breakdown_entity_type()

        # Report initial progress
        if progress_callback:
            if not progress_callback(0, 100, "Creating VFX Breakdown..."):
                raise Exception("Operation cancelled by user")

        # First, create the new VFX Breakdown
        new_breakdown = self._create_empty_vfx_breakdown(project_id, new_name)
        new_breakdown_id = new_breakdown["id"]

        logger.info(f"Copying beats from VFX Breakdown {source_id} to {new_breakdown_id}")

        # Report progress after creating breakdown
        if progress_callback:
            if not progress_callback(10, 100, "Fetching beats from source..."):
                raise Exception("Operation cancelled by user")

        # Fetch all beats from the source breakdown
        try:
            source_beats = self.sg_session.get_beats_for_vfx_breakdown(
                source_id,
                fields=[
                    "code", "sg_beat_id", "sg_vfx_breakdown_scene", "sg_page",
                    "sg_script_excerpt", "description", "sg_vfx_type", "sg_complexity",
                    "sg_category", "sg_vfx_description", "sg_number_of_shots"
                ]
            )

            logger.info(f"Found {len(source_beats)} beats to copy")

            total_beats = len(source_beats)
            if total_beats == 0:
                if progress_callback:
                    progress_callback(100, 100, "No beats to copy")
                return new_breakdown

            # Report progress after fetching beats
            if progress_callback:
                if not progress_callback(20, 100, f"Copying {total_beats} beat(s)..."):
                    raise Exception("Operation cancelled by user")

            # Copy each beat
            for i, beat in enumerate(source_beats):
                # Check for cancellation
                if progress_callback:
                    current_progress = 20 + int((i / total_beats) * 80)
                    if not progress_callback(
                        current_progress,
                        100,
                        f"Copying beat {i + 1} of {total_beats}..."
                    ):
                        raise Exception("Operation cancelled by user")
                new_beat_data = {
                    "project": {"type": "Project", "id": project_id},
                    "sg_parent": {"type": entity_type, "id": new_breakdown_id}
                }

                # Copy all fields except id and system fields
                copy_fields = [
                    "code", "sg_beat_id", "sg_vfx_breakdown_scene", "sg_page",
                    "sg_script_excerpt", "description", "sg_vfx_type", "sg_complexity",
                    "sg_category", "sg_vfx_description", "sg_number_of_shots"
                ]

                for field in copy_fields:
                    if field in beat and beat[field] is not None:
                        new_beat_data[field] = beat[field]

                # Create the new beat
                self.sg_session.sg.create("CustomEntity02", new_beat_data)

            # Report completion
            if progress_callback:
                progress_callback(100, 100, f"Successfully copied {total_beats} beat(s)")

            logger.info(f"Successfully copied {len(source_beats)} beats")

        except Exception as e:
            logger.error(f"Error copying beats: {e}", exc_info=True)
            # Even if beat copying fails, we still return the created breakdown
            QtWidgets.QMessageBox.warning(
                self,
                "Partial Success",
                f"VFX Breakdown created but failed to copy beats:\n{str(e)}"
            )

        return new_breakdown

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
