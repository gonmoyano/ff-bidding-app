"""
VFX Breakdown Model
Qt Model/View pattern implementation for VFX Breakdown data management.
"""

from PySide6 import QtCore, QtGui, QtWidgets
import json
import logging
from datetime import datetime, date

try:
    from .logger import logger
    from .settings import AppSettings
except ImportError:
    logger = logging.getLogger("FFPackageManager")
    from settings import AppSettings


class ShotGridUpdateSignals(QtCore.QObject):
    """Signals for async ShotGrid updates."""
    success = QtCore.Signal(int, int, object)  # row, col, new_value
    failed = QtCore.Signal(int, int, object, str)  # row, col, old_value, error_message


class ShotGridUpdateRunnable(QtCore.QRunnable):
    """Runnable for async ShotGrid updates with rollback on failure."""

    def __init__(self, sg_session, entity_type, entity_id, field_name, update_value,
                 row, col, old_value, new_value):
        """Initialize the runnable.

        Args:
            sg_session: ShotGrid session
            entity_type: Entity type (e.g., "CustomEntity02")
            entity_id: Entity ID to update
            field_name: Field name to update
            update_value: Parsed value to send to ShotGrid
            row: Row index in model
            col: Column index in model
            old_value: Original value for rollback
            new_value: New value being set
        """
        super().__init__()
        self.sg_session = sg_session
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.field_name = field_name
        self.update_value = update_value
        self.row = row
        self.col = col
        self.old_value = old_value
        self.new_value = new_value
        self.signals = ShotGridUpdateSignals()

    def run(self):
        """Execute the ShotGrid update in background thread."""
        try:
            self.sg_session.sg.update(
                self.entity_type,
                self.entity_id,
                {self.field_name: self.update_value}
            )
            self.signals.success.emit(self.row, self.col, self.new_value)
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[ASYNC] Failed to update ShotGrid - Entity: {self.entity_type}, "
                        f"ID: {self.entity_id}, Field: {self.field_name}, Value: {self.update_value}")
            logger.error(f"[ASYNC] Error: {error_msg}")
            self.signals.failed.emit(self.row, self.col, self.old_value, error_msg)


class CheckBoxDelegate(QtWidgets.QStyledItemDelegate):
    """Custom delegate for rendering checkboxes with custom styling."""

    def __init__(self, parent=None):
        """Initialize the delegate."""
        super().__init__(parent)

    def paint(self, painter, option, index):
        """Paint the checkbox with custom styling."""
        # Get the check state from the model
        check_state = index.data(QtCore.Qt.CheckStateRole)

        # Only paint custom checkbox if this cell has a check state
        if check_state is not None:
            painter.save()

            # Calculate checkbox rect (centered in the cell) with DPI scaling
            # Try to get DPI scale from active app (for live preview), fall back to settings
            try:
                from .app import PackageManagerApp
                dpi_scale = getattr(PackageManagerApp, '_active_dpi_scale', None)
            except ImportError:
                dpi_scale = None

            if dpi_scale is None:
                app_settings = AppSettings()
                dpi_scale = app_settings.get_dpi_scale()

            checkbox_size = int(20 * dpi_scale)
            checkbox_rect = QtCore.QRect(
                option.rect.center().x() - checkbox_size // 2,
                option.rect.center().y() - checkbox_size // 2,
                checkbox_size,
                checkbox_size
            )

            # Draw background if selected
            if option.state & QtWidgets.QStyle.State_Selected:
                painter.fillRect(option.rect, option.palette.highlight())

            # Determine if checked
            is_checked = (check_state == QtCore.Qt.Checked)

            # Scale pen width and corner radius with DPI
            pen_width = max(1, int(2 * dpi_scale))
            corner_radius = max(2, int(3 * dpi_scale))

            # Set up pen and brush for border
            if is_checked:
                # Checked: blue border
                pen = QtGui.QPen(QtGui.QColor("#0078d4"), pen_width)
                painter.setPen(pen)
                painter.setBrush(QtGui.QColor("#2b2b2b"))
            else:
                # Unchecked: gray border
                pen = QtGui.QPen(QtGui.QColor("#555555"), pen_width)
                painter.setPen(pen)
                painter.setBrush(QtGui.QColor("#2b2b2b"))

            # Draw rounded rectangle
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            painter.drawRoundedRect(checkbox_rect, corner_radius, corner_radius)

            # Draw tick if checked
            if is_checked:
                painter.setPen(QtGui.QPen(QtGui.QColor("#0078d4"), pen_width))
                font = painter.font()
                font.setPixelSize(int(16 * dpi_scale))
                font.setBold(True)
                painter.setFont(font)
                painter.drawText(checkbox_rect, QtCore.Qt.AlignCenter, "✓")

            painter.restore()
        else:
            # Not a checkbox, use default painting
            super().paint(painter, option, index)

    def editorEvent(self, event, model, option, index):
        """Handle mouse events for toggling checkboxes."""
        # Get the check state from the model
        check_state = index.data(QtCore.Qt.CheckStateRole)

        # Only handle checkbox events if this cell has a check state
        if check_state is not None:
            if event.type() == QtCore.QEvent.MouseButtonRelease:
                if event.button() == QtCore.Qt.LeftButton:
                    # Toggle the check state
                    new_state = QtCore.Qt.Unchecked if check_state == QtCore.Qt.Checked else QtCore.Qt.Checked
                    return model.setData(index, new_state, QtCore.Qt.CheckStateRole)
            return True

        # Not a checkbox, use default behavior
        return super().editorEvent(event, model, option, index)


class ValidatedComboBoxDelegate(QtWidgets.QStyledItemDelegate):
    """Custom delegate for combo box cells with List field values and validation coloring.

    Based on ComboBoxDelegate from vfx_breakdown_tab.py, with added paint() method
    for validation coloring (blue for valid, red for invalid values).
    """

    def __init__(self, list_values, parent=None):
        """Initialize the delegate.

        Args:
            list_values: List of valid string values for the dropdown
            parent: Parent widget
        """
        super().__init__(parent)
        self.list_values = list_values or []
        # Store normalized versions for validation
        self.normalized_valid_values = {str(v).strip(): v for v in self.list_values if v}

    def update_valid_values(self, valid_values):
        """Update the list of valid values and trigger repaint.

        Args:
            valid_values: New list of valid string values
        """
        self.list_values = valid_values if valid_values else []
        self.normalized_valid_values = {str(v).strip(): v for v in self.list_values if v}

    def paint(self, painter, option, index):
        """Paint the cell with validation coloring matching Asset pill colors."""
        painter.save()

        # Get the cell value
        value = index.data(QtCore.Qt.DisplayRole)

        # Determine background color based on validation
        # Colors match the Asset pills in VFX Breakdown table
        if value and str(value).strip():
            # Normalize the value for comparison (strip whitespace)
            normalized_value = str(value).strip()
            if normalized_value in self.normalized_valid_values:
                # Valid value - blue background matching Asset pill
                bg_color = QtGui.QColor("#4a90e2")  # Same as valid Asset pill
            else:
                # Invalid value - red background matching invalid Asset pill
                bg_color = QtGui.QColor("#e74c3c")  # Same as invalid Asset pill
        else:
            # Empty value - default background
            bg_color = option.palette.base().color()

        # Draw background
        painter.fillRect(option.rect, bg_color)

        # Draw selection highlight if selected
        if option.state & QtWidgets.QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        # Draw the text - use white text for colored backgrounds
        if value and str(value).strip():
            painter.setPen(QtGui.QColor("#ffffff"))  # White text on colored background
        else:
            painter.setPen(option.palette.text().color())  # Default text color for empty cells

        text_rect = option.rect.adjusted(4, 0, -4, 0)  # Add padding
        painter.drawText(text_rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, str(value) if value else "")

        painter.restore()

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


class EditCommand:
    """Command pattern for undo/redo of cell edits."""

    def __init__(self, model, row, col, old_value, new_value, bidding_scene_data, field_name, sg_session, field_schema=None, entity_type="CustomEntity02"):
        self.model = model
        self.row = row
        self.col = col
        self.old_value = old_value
        self.new_value = new_value
        self.bidding_scene_data = bidding_scene_data
        self.field_name = field_name
        self.sg_session = sg_session
        self.field_schema = field_schema or {}
        self.entity_type = entity_type

    def undo(self):
        """Undo the edit."""
        # Update ShotGrid
        self._update_shotgrid(self.old_value)

        # Update the bidding_scene_data directly (can't use setData due to _updating flag)
        parsed_value = self._parse_value(self.old_value, self.field_name)
        self.bidding_scene_data[self.field_name] = parsed_value

        # Emit data changed to refresh the view
        index = self.model.index(self.row, self.col)
        self.model.dataChanged.emit(index, index, [QtCore.Qt.DisplayRole, QtCore.Qt.EditRole])

    def redo(self):
        """Redo the edit."""
        # Update ShotGrid
        self._update_shotgrid(self.new_value)

        # Update the bidding_scene_data directly (can't use setData due to _updating flag)
        parsed_value = self._parse_value(self.new_value, self.field_name)
        self.bidding_scene_data[self.field_name] = parsed_value

        # Emit data changed to refresh the view
        index = self.model.index(self.row, self.col)
        self.model.dataChanged.emit(index, index, [QtCore.Qt.DisplayRole, QtCore.Qt.EditRole])

    def _update_shotgrid(self, value):
        """Update ShotGrid with the value."""
        bidding_scene_id = self.bidding_scene_data.get("id")
        if not bidding_scene_id:
            logger.error(f"No entity ID found for update ({self.entity_type})")
            raise ValueError(f"No entity ID found for update ({self.entity_type})")

        # Convert string value back to appropriate type
        update_value = self._parse_value(value, self.field_name)

        # Update on ShotGrid using the configured entity type
        self.sg_session.sg.update(self.entity_type, bidding_scene_id, {self.field_name: update_value})

    def _parse_value(self, text, field_name):
        """Parse text value to appropriate type based on ShotGrid schema."""
        # Get field schema info
        field_info = self.field_schema.get(field_name, {})
        data_type = field_info.get("data_type")


        # Special handling for rate and mandays fields - always convert to float
        if field_name.endswith("_rate") or field_name.endswith("_mandays"):
            if not text or text == "-" or text == "":
                return None
            try:
                value = float(text)
                return value
            except (ValueError, TypeError):
                logger.warning(f"Failed to parse '{text}' as float for field '{field_name}'")
                raise ValueError(f"Invalid number format for rate/mandays field: '{text}'")

        # Handle checkbox/boolean type
        if data_type == "checkbox":
            # If already a boolean, return it
            if isinstance(text, bool):
                return text
            # Handle empty/None values
            if not text or text == "-" or text == "":
                return False
            # Parse string representations
            if isinstance(text, str):
                return text.lower() in ["true", "yes", "1", "checked", "x"]
            # Try to convert to boolean
            return bool(text)

        # Handle multi-entity type (lists of entity dictionaries)
        if data_type == "multi_entity":
            # If already a list, return it as-is
            if isinstance(text, list):
                return text
            # Handle empty values
            if not text or text == "-" or text == "":
                return []
            # If it's a single entity dict, wrap it in a list
            if isinstance(text, dict) and "type" in text and "id" in text:
                return [text]
            # Otherwise return empty list
            logger.warning(f"Unexpected value type for multi_entity field '{field_name}': {type(text)}")
            return []

        # Handle empty values for other types
        if not text or text == "-" or text == "":
            return None

        # Parse based on ShotGrid data type
        if data_type == "number":
            try:
                # Try int first
                if '.' not in str(text):
                    value = int(text)
                    return value
                else:
                    value = float(text)
                    return value
            except ValueError:
                logger.warning(f"Failed to parse '{text}' as number for field '{field_name}'")
                raise ValueError(f"Invalid number format: '{text}'")

        elif data_type == "float":
            try:
                value = float(text)
                return value
            except ValueError:
                logger.warning(f"Failed to parse '{text}' as float for field '{field_name}'")
                raise ValueError(f"Invalid float format: '{text}'")

        elif data_type == "currency":
            try:
                # Currency fields must be float or int, not string
                value = float(text)
                return value
            except ValueError:
                logger.warning(f"Failed to parse '{text}' as currency for field '{field_name}'")
                raise ValueError(f"Invalid currency format: '{text}'")

        # For all other types (text, list, entity, etc.), return as string
        return str(text)


class PasteCommand:
    """Command pattern for undo/redo of paste operations."""

    def __init__(self, changes, model, sg_session, field_schema=None, entity_type="CustomEntity02"):
        """
        Initialize paste command.

        Args:
            changes: List of dicts with keys: row, col, old_value, new_value, bidding_scene_data, field_name
            model: VFXBreakdownModel instance
            sg_session: ShotGrid session object
            field_schema: Field schema information
            entity_type: ShotGrid entity type to update
        """
        self.changes = changes
        self.model = model
        self.sg_session = sg_session
        self.field_schema = field_schema or {}
        self.entity_type = entity_type

    def undo(self):
        """Undo all paste changes."""
        for change in self.changes:
            # Update ShotGrid
            self._update_shotgrid(change['old_value'], change['bidding_scene_data'], change['field_name'])

            # Update the bidding_scene_data directly (can't use setData due to _updating flag)
            parsed_value = self._parse_value(change['old_value'], change['field_name'])
            change['bidding_scene_data'][change['field_name']] = parsed_value

            # Emit data changed to refresh the view
            index = self.model.index(change['row'], change['col'])
            self.model.dataChanged.emit(index, index, [QtCore.Qt.DisplayRole, QtCore.Qt.EditRole])

    def redo(self):
        """Redo all paste changes."""
        for change in self.changes:
            # Update ShotGrid
            self._update_shotgrid(change['new_value'], change['bidding_scene_data'], change['field_name'])

            # Update the bidding_scene_data directly (can't use setData due to _updating flag)
            parsed_value = self._parse_value(change['new_value'], change['field_name'])
            change['bidding_scene_data'][change['field_name']] = parsed_value

            # Emit data changed to refresh the view
            index = self.model.index(change['row'], change['col'])
            self.model.dataChanged.emit(index, index, [QtCore.Qt.DisplayRole, QtCore.Qt.EditRole])

    def _update_shotgrid(self, value, bidding_scene_data, field_name):
        """Update ShotGrid with the value."""
        bidding_scene_id = bidding_scene_data.get("id")
        if not bidding_scene_id:
            logger.error(f"No entity ID found for update ({self.entity_type})")
            raise ValueError(f"No entity ID found for update ({self.entity_type})")

        # Convert string value back to appropriate type
        update_value = self._parse_value(value, field_name)

        # Update on ShotGrid using the configured entity type
        self.sg_session.sg.update(self.entity_type, bidding_scene_id, {field_name: update_value})

    def _parse_value(self, text, field_name):
        """Parse text value to appropriate type based on ShotGrid schema."""
        # Special handling for rate and mandays fields - always convert to float
        if field_name.endswith("_rate") or field_name.endswith("_mandays"):
            if not text or text == "-" or text == "":
                return None
            try:
                value = float(text)
                return value
            except (ValueError, TypeError):
                logger.warning(f"Failed to parse '{text}' as float for field '{field_name}'")
                return None

        # Get field schema info first to check for multi_entity
        field_info = self.field_schema.get(field_name, {})
        data_type = field_info.get("data_type")

        # Handle multi-entity type (lists of entity dictionaries)
        if data_type == "multi_entity":
            # If already a list, return it as-is
            if isinstance(text, list):
                return text
            # Handle empty values
            if not text or text == "-" or text == "":
                return []
            # If it's a single entity dict, wrap it in a list
            if isinstance(text, dict) and "type" in text and "id" in text:
                return [text]
            # Otherwise return empty list
            logger.warning(f"Unexpected value type for multi_entity field '{field_name}': {type(text)}")
            return []

        # Handle empty values for other types
        if not text or text == "-" or text == "":
            return None


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

        elif data_type == "currency":
            try:
                # Currency fields must be float or int, not string
                return float(text)
            except ValueError:
                logger.warning(f"Could not parse '{text}' as currency for field '{field_name}'")
                return None

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


class VFXBreakdownModel(QtCore.QAbstractTableModel):
    """Model for VFX Breakdown bidding scenes data using Qt Model/View pattern."""

    # Custom signals
    statusMessageChanged = QtCore.Signal(str, bool)  # message, is_error
    rowCountChanged = QtCore.Signal(int, int)  # shown_rows, total_rows

    def __init__(self, sg_session, parent=None):
        """Initialize the model.

        Args:
            sg_session: ShotGrid session for API access
            parent: Parent QObject
        """
        super().__init__(parent)
        self.sg_session = sg_session

        # Entity type for ShotGrid updates (can be overridden for different entity types)
        self.entity_type = "CustomEntity02"  # Default: Bidding Scenes

        # Column configuration - matches import mapping fields
        self.column_fields = [
            "id",
            "code",
            "sg_bid_assets",
            "sg_sequence_code",
            "sg_vfx_breakdown_scene",
            "sg_interior_exterior",
            "sg_number_of_shots",
            "sg_on_set_vfx_needs",
            "sg_page_eights",
            "sg_previs",
            "sg_script_excerpt",
            "sg_set",
            "sg_sim",
            "sg_sorting_priority",
            "sg_team_notes",
            "sg_time_of_day",
            "sg_unit",
            "sg_vfx_assumptions",
            "sg_vfx_description",
            "sg_vfx_questions",
            "sg_vfx_supervisor_notes",
            "sg_vfx_type",
            "sg_vfx_shot_work",
        ]

        # Default headers (will be replaced with display names from ShotGrid)
        self.column_headers = self.column_fields.copy()

        # Read-only columns
        self.readonly_columns = []

        # Data storage
        self.all_bidding_scenes_data = []  # Original unfiltered bidding scene data
        self.filtered_row_indices = []  # Indices into all_bidding_scenes_data that pass filters
        self.display_row_to_data_row = {}  # Maps displayed row -> index in all_bidding_scenes_data

        # Export selection state (separate from bidding scene data)
        # Maps data row index -> bool (whether to export to Excel)
        self.export_selection = {}

        # Field schema information
        self.field_schema = {}

        # Add virtual field schema for export checkbox
        self.field_schema["_export_to_excel"] = {
            "data_type": "checkbox",
            "name": {"value": "Export"},
            "editable": True
        }

        # Undo/Redo stack
        self.undo_stack = []
        self.redo_stack = []

        # Sorting state
        self.sort_column = None
        self.sort_direction = None

        # Formula evaluator for calculated fields
        self.formula_evaluator = None
        self.compound_sort_columns = []

        # Filtering state
        self.global_search_text = ""

        # Settings for templates
        self.app_settings = AppSettings()
        self.sort_templates = self.app_settings.get_sort_templates()

        # Flag to prevent recursive updates
        self._updating = False

        # Flag to indicate when undo/redo is in progress
        self._in_undo_redo = False

        # Flag to skip undo command creation for automatic updates (e.g., Price Static)
        self._skip_undo_command = False

        # Thread pool for async ShotGrid updates (optimistic updates)
        self._update_thread_pool = QtCore.QThreadPool.globalInstance()

        # Flag to enable/disable optimistic updates (update UI first, then sync to SG)
        # NOTE: Disabled by default because ShotGrid API connection is not thread-safe
        # The SSL connection cannot be shared across threads
        self._use_optimistic_updates = False

        # Track pending updates for potential rollback (key: (row, col), value: old_value)
        self._pending_updates = {}

    def rowCount(self, parent=QtCore.QModelIndex()):
        """Return the number of rows (filtered bidding scenes)."""
        if parent.isValid():
            return 0
        return len(self.filtered_row_indices)

    def columnCount(self, parent=QtCore.QModelIndex()):
        """Return the number of columns."""
        if parent.isValid():
            return 0
        return len(self.column_fields)

    def data(self, index, role=QtCore.Qt.DisplayRole):
        """Return data for the given index and role."""
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        if row < 0 or row >= len(self.filtered_row_indices):
            return None

        # Get the actual data row
        data_row = self.filtered_row_indices[row]
        bidding_scene_data = self.all_bidding_scenes_data[data_row]
        field_name = self.column_fields[col]

        # Handle virtual export checkbox column
        if field_name == "_export_to_excel":
            value = self.export_selection.get(data_row, False)
            if role == QtCore.Qt.CheckStateRole:
                return QtCore.Qt.Checked if value else QtCore.Qt.Unchecked
            elif role == QtCore.Qt.DisplayRole:
                return ""
            elif role == QtCore.Qt.EditRole:
                return value
            return None

        value = bidding_scene_data.get(field_name)

        # Check if this is a checkbox field
        is_checkbox = False
        if field_name in self.field_schema:
            field_info = self.field_schema[field_name]
            is_checkbox = field_info.get("data_type") == "checkbox"

        # Handle checkbox fields specially
        if is_checkbox:
            if role == QtCore.Qt.CheckStateRole:
                # Return checkbox state
                if isinstance(value, bool):
                    return QtCore.Qt.Checked if value else QtCore.Qt.Unchecked
                elif value is None:
                    return QtCore.Qt.Unchecked
                else:
                    # Try to interpret as boolean
                    return QtCore.Qt.Checked if value else QtCore.Qt.Unchecked
            elif role == QtCore.Qt.DisplayRole:
                # Don't show text for checkbox columns
                return ""
            elif role == QtCore.Qt.EditRole:
                # Return the actual boolean value for editing
                return value

        # Handle sg_bid_assets field specially (uses custom widget)
        if field_name == "sg_bid_assets":
            if role == QtCore.Qt.DisplayRole:
                # Don't show text - custom widget will display the entities
                return ""
            elif role == QtCore.Qt.EditRole:
                # Return the actual list for editing
                return value

        # Handle non-checkbox fields normally
        if role == QtCore.Qt.DisplayRole or role == QtCore.Qt.EditRole:
            return self._format_sg_value(value)

        elif role == QtCore.Qt.TextAlignmentRole:
            if field_name in ("id", "sg_page", "sg_number_of_shots"):
                return QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter
            elif field_name == "updated_at":
                return QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter
            else:
                return QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter

        elif role == QtCore.Qt.ForegroundRole:
            # White text for Price column (on blue background)
            if field_name == "_calc_price":
                return QtGui.QColor("#ffffff")
            if field_name in self.readonly_columns:
                return QtGui.QColor("#888888")

        elif role == QtCore.Qt.BackgroundRole:
            # Blue background for calculated Price field (matching tab blue)
            if field_name == "_calc_price":
                return QtGui.QColor("#0078d4")

        elif role == QtCore.Qt.ToolTipRole:
            # Show cell reference (e.g., A1, B2, C3)
            column_letter = self._column_index_to_letter(col)
            row_number = row + 1  # 1-based for display
            return f"{column_letter}{row_number}"

        return None

    def _on_async_update_success(self, row, col, new_value):
        """Handle successful async ShotGrid update."""
        key = (row, col)
        if key in self._pending_updates:
            del self._pending_updates[key]

        # Get field name for logging
        if 0 <= col < len(self.column_fields):
            field_name = self.column_fields[col]
            self.statusMessageChanged.emit(f"✓ Updated {field_name} on ShotGrid", False)

    def _on_async_update_failed(self, row, col, old_value, error_msg):
        """Handle failed async ShotGrid update - rollback to previous value."""
        key = (row, col)

        # Log the error prominently
        logger.error("=" * 80)
        logger.error(f"[ROLLBACK] ShotGrid update failed - reverting local change")
        logger.error(f"[ROLLBACK] Row: {row}, Col: {col}, Error: {error_msg}")
        logger.error("=" * 80)

        # Get the data row index
        if row not in self.display_row_to_data_row:
            logger.error(f"[ROLLBACK] Cannot find data row for display row {row}")
            if key in self._pending_updates:
                del self._pending_updates[key]
            return

        data_row_idx = self.display_row_to_data_row[row]
        if data_row_idx >= len(self.all_bidding_scenes_data):
            logger.error(f"[ROLLBACK] Data row index {data_row_idx} out of range")
            if key in self._pending_updates:
                del self._pending_updates[key]
            return

        bidding_scene_data = self.all_bidding_scenes_data[data_row_idx]
        if not bidding_scene_data:
            if key in self._pending_updates:
                del self._pending_updates[key]
            return

        if 0 <= col < len(self.column_fields):
            field_name = self.column_fields[col]

            # Rollback to old value
            bidding_scene_data[field_name] = old_value
            logger.error(f"[ROLLBACK] Reverted {field_name} to: {old_value}")

            # Emit data changed to refresh the view with the old value
            index = self.index(row, col)
            self.dataChanged.emit(index, index, [QtCore.Qt.DisplayRole, QtCore.Qt.EditRole])

            # Emit status message
            self.statusMessageChanged.emit(f"✗ Failed to update {field_name}: {error_msg}", True)

        # Clean up pending updates
        if key in self._pending_updates:
            del self._pending_updates[key]

    def _queue_async_update(self, row, col, old_value, new_value, parsed_value,
                            bidding_scene_data, field_name):
        """Queue an async ShotGrid update with rollback on failure.

        Args:
            row: Display row index
            col: Column index
            old_value: Original value for rollback
            new_value: New display value
            parsed_value: Parsed value to send to ShotGrid
            bidding_scene_data: Data dict for this row
            field_name: Field name being updated
        """
        entity_id = bidding_scene_data.get("id")
        if not entity_id:
            logger.error(f"[ASYNC] No entity ID found for update ({self.entity_type})")
            self.statusMessageChanged.emit(f"Failed to update {field_name}: No entity ID", True)
            return False

        # Track pending update for potential rollback
        key = (row, col)
        self._pending_updates[key] = old_value

        # Create the runnable
        runnable = ShotGridUpdateRunnable(
            sg_session=self.sg_session,
            entity_type=self.entity_type,
            entity_id=entity_id,
            field_name=field_name,
            update_value=parsed_value,
            row=row,
            col=col,
            old_value=old_value,
            new_value=new_value
        )

        # Connect signals
        runnable.signals.success.connect(self._on_async_update_success)
        runnable.signals.failed.connect(self._on_async_update_failed)

        # Queue for execution
        self._update_thread_pool.start(runnable)
        return True

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        """Set data for the given index."""
        if not index.isValid():
            return False

        # Handle checkbox state changes
        if role == QtCore.Qt.CheckStateRole:
            # Convert checkbox state to boolean
            value = (value == QtCore.Qt.Checked)
            # Continue processing with EditRole
            role = QtCore.Qt.EditRole
        elif role != QtCore.Qt.EditRole:
            return False

        if self._updating:
            # Prevent recursive updates
            return False

        row = index.row()
        col = index.column()
        field_name = self.column_fields[col]

        # Check if field is read-only
        if field_name in self.readonly_columns:
            return False

        # Get the actual data row
        data_row = self.filtered_row_indices[row]
        bidding_scene_data = self.all_bidding_scenes_data[data_row]

        # Handle virtual export checkbox column specially
        if field_name == "_export_to_excel":
            old_value = self.export_selection.get(data_row, False)
            new_value = bool(value)

            if new_value == old_value:
                return False

            # Update export selection state
            self.export_selection[data_row] = new_value

            # Emit data changed
            self.dataChanged.emit(index, index, [QtCore.Qt.DisplayRole, QtCore.Qt.EditRole, QtCore.Qt.CheckStateRole])
            return True

        # Get old value
        old_value_raw = bidding_scene_data.get(field_name)
        old_value = self._format_sg_value(old_value_raw)

        new_value = value

        # Check if value actually changed
        if new_value == old_value:
            return False

        # Check if this is an unsaved item (no ID yet)
        is_unsaved = bidding_scene_data.get("_is_unsaved", False) or bidding_scene_data.get("id") is None

        if is_unsaved:
            # Unsaved items are not stored in ShotGrid yet, only update locally
            try:
                self._updating = True

                # Update the bidding_scene_data with new value
                bidding_scene_data[field_name] = new_value

                # Emit data changed - this will trigger the widget's handler to save to ShotGrid
                self.dataChanged.emit(index, index, [QtCore.Qt.DisplayRole, QtCore.Qt.EditRole])

                self._updating = False


                return True

            except Exception as e:
                self._updating = False
                logger.error(f"Failed to update unsaved item field '{field_name}': {e}", exc_info=True)
                return False

        # Check if this is a virtual field (starts with underscore)
        is_virtual_field = field_name.startswith("_")

        if is_virtual_field:
            # Virtual fields are not stored in ShotGrid, only update locally
            try:
                self._updating = True

                # Update the bidding_scene_data with new value
                bidding_scene_data[field_name] = new_value

                # Emit data changed
                self.dataChanged.emit(index, index, [QtCore.Qt.DisplayRole, QtCore.Qt.EditRole])

                self._updating = False


                # Recalculate dependent cells if formula evaluator is available
                if self.formula_evaluator:
                    self.formula_evaluator.recalculate_dependents(row, col)

                return True

            except Exception as e:
                self._updating = False
                logger.error(f"Failed to update virtual field '{field_name}': {e}", exc_info=True)
                return False
        else:
            # Regular field - update ShotGrid
            # Execute the command (update ShotGrid)
            try:
                self._updating = True

                # During undo/redo or automatic updates, we want to update the field but not create new undo commands
                # This allows cascading updates (e.g., Price Static) without interfering with undo/redo history
                if self._in_undo_redo or self._skip_undo_command:
                    # Direct update without creating EditCommand
                    # Create a temporary command object just for the helper methods
                    temp_command = EditCommand(
                        self,
                        row,
                        col,
                        old_value,
                        new_value,
                        bidding_scene_data,
                        field_name,
                        self.sg_session,
                        field_schema=self.field_schema,
                        entity_type=self.entity_type
                    )

                    # Step 1: Parse and update local data first
                    parsed_value = temp_command._parse_value(new_value, field_name)
                    bidding_scene_data[field_name] = parsed_value

                    # Step 2: Emit data changed immediately (UI updates, Costs tab refreshes)
                    self.dataChanged.emit(index, index, [QtCore.Qt.DisplayRole, QtCore.Qt.EditRole])

                    # Step 3: Recalculate dependent cells if formula evaluator is available
                    if self.formula_evaluator:
                        self.formula_evaluator.recalculate_dependents(row, col)

                    # Step 4: Process pending events to ensure UI updates are visible
                    QtWidgets.QApplication.processEvents()

                    # Step 5: Sync to ShotGrid (blocking but UI already updated)
                    temp_command._update_shotgrid(new_value)

                    self._updating = False
                    return True
                else:
                    # Normal edit - create undo command
                    command = EditCommand(
                        self,
                        row,
                        col,
                        old_value,
                        new_value,
                        bidding_scene_data,
                        field_name,
                        self.sg_session,
                        field_schema=self.field_schema,
                        entity_type=self.entity_type
                    )

                    # Parse the new value
                    parsed_value = command._parse_value(new_value, field_name)

                    # OPTIMISTIC UPDATE: Update local data first, then sync to SG async
                    if self._use_optimistic_updates:
                        # Update the bidding_scene_data with new value immediately
                        bidding_scene_data[field_name] = parsed_value

                        # Emit data changed immediately (optimistic UI update)
                        self.dataChanged.emit(index, index, [QtCore.Qt.DisplayRole, QtCore.Qt.EditRole])

                        # Add to undo stack
                        self.undo_stack.append(command)
                        # Clear redo stack on new edit
                        self.redo_stack.clear()

                        self._updating = False

                        # Queue async ShotGrid update with rollback on failure
                        self._queue_async_update(
                            row, col, old_value_raw, new_value, parsed_value,
                            bidding_scene_data, field_name
                        )

                        # Recalculate dependent cells if formula evaluator is available
                        if self.formula_evaluator:
                            self.formula_evaluator.recalculate_dependents(row, col)

                        return True
                    else:
                        # Synchronous update - update local first, then sync to ShotGrid
                        # This ensures Costs tab sees changes immediately before SG sync

                        # Step 1: Update local data immediately
                        bidding_scene_data[field_name] = parsed_value

                        # Step 2: Emit data changed immediately (UI updates, Costs tab refreshes)
                        self.dataChanged.emit(index, index, [QtCore.Qt.DisplayRole, QtCore.Qt.EditRole])

                        # Step 3: Recalculate dependent cells if formula evaluator is available
                        if self.formula_evaluator:
                            self.formula_evaluator.recalculate_dependents(row, col)

                        # Step 4: Process pending events to ensure UI updates are visible
                        QtWidgets.QApplication.processEvents()

                        # Step 5: Sync to ShotGrid (blocking but UI already updated)
                        try:
                            command._update_shotgrid(new_value)

                            # Add to undo stack only after successful SG update
                            self.undo_stack.append(command)
                            # Clear redo stack on new edit
                            self.redo_stack.clear()

                            self._updating = False
                            self.statusMessageChanged.emit(f"✓ Updated {field_name} on ShotGrid", False)
                            return True

                        except Exception as sg_error:
                            # ShotGrid update failed - rollback local change
                            logger.error(f"[ROLLBACK] ShotGrid sync failed: {sg_error}")
                            bidding_scene_data[field_name] = old_value_raw
                            self.dataChanged.emit(index, index, [QtCore.Qt.DisplayRole, QtCore.Qt.EditRole])

                            # Recalculate dependents with rolled back value
                            if self.formula_evaluator:
                                self.formula_evaluator.recalculate_dependents(row, col)

                            self._updating = False
                            self.statusMessageChanged.emit(f"✗ Failed to update {field_name}: {sg_error}", True)
                            return False

            except Exception as e:
                self._updating = False
                error_msg = str(e)
                logger.error(f"Failed to update ShotGrid field '{field_name}': {error_msg}", exc_info=True)
                logger.error(f"Entity type: {self.entity_type}, Entity ID: {bidding_scene_data.get('id')}, Field: {field_name}, Value: {new_value}")
                self.statusMessageChanged.emit(f"Failed to update {field_name}: {error_msg}", True)
                return False

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        """Return header data."""
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal and 0 <= section < len(self.column_headers):
                return self.column_headers[section]
            elif orientation == QtCore.Qt.Vertical:
                return str(section + 1)
        elif role == QtCore.Qt.ToolTipRole:
            # Show column letter for calculated fields in horizontal headers
            if orientation == QtCore.Qt.Horizontal and 0 <= section < len(self.column_fields):
                field_name = self.column_fields[section]
                # Show column letter for virtual/calculated fields
                if field_name.startswith("_"):
                    column_letter = self._column_index_to_letter(section)
                    return f"Column {column_letter}"
        return None

    def _column_index_to_letter(self, index):
        """Convert column index to Excel-style letter (0=A, 1=B, 25=Z, 26=AA, etc.)."""
        result = ""
        index += 1  # Convert to 1-based
        while index > 0:
            index -= 1
            result = chr(65 + (index % 26)) + result
            index //= 26
        return result

    def flags(self, index):
        """Return item flags for the given index."""
        if not index.isValid():
            return QtCore.Qt.NoItemFlags

        field_name = self.column_fields[index.column()]

        # Check if this is a checkbox field
        is_checkbox = False
        if field_name in self.field_schema:
            field_info = self.field_schema[field_name]
            is_checkbox = field_info.get("data_type") == "checkbox"

        base_flags = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

        if field_name in self.readonly_columns:
            return base_flags
        else:
            if is_checkbox:
                # Checkbox fields are user-checkable instead of editable
                return base_flags | QtCore.Qt.ItemIsUserCheckable
            else:
                return base_flags | QtCore.Qt.ItemIsEditable

    def load_bidding_scenes(self, bidding_scenes):
        """Load bidding scenes data into the model.

        Args:
            bidding_scenes: List of bidding scene dictionaries from ShotGrid
        """
        self.beginResetModel()

        self.all_bidding_scenes_data = bidding_scenes.copy() if bidding_scenes else []
        self.filtered_row_indices.clear()
        self.display_row_to_data_row.clear()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.export_selection.clear()

        # Initialize all rows as unselected for export by default
        for i in range(len(self.all_bidding_scenes_data)):
            self.export_selection[i] = False

        # Apply filters and sorting
        self.apply_filters()

        self.endResetModel()

        self.rowCountChanged.emit(len(self.filtered_row_indices), len(self.all_bidding_scenes_data))

        if bidding_scenes:
            self.statusMessageChanged.emit(f"Loaded {len(bidding_scenes)} Bidding Scene(s)", False)
        else:
            self.statusMessageChanged.emit("No Bidding Scenes found", False)

    def clear_data(self):
        """Clear all data from the model."""
        self.beginResetModel()
        self.all_bidding_scenes_data.clear()
        self.filtered_row_indices.clear()
        self.display_row_to_data_row.clear()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.export_selection.clear()
        self.sort_column = None
        self.sort_direction = None
        self.endResetModel()
        self.rowCountChanged.emit(0, 0)

    def set_field_schema(self, field_schema):
        """Set the field schema for type conversions.

        Args:
            field_schema: Dictionary mapping field names to schema info
        """
        # Preserve virtual field schemas (fields starting with _)
        virtual_schemas = {k: v for k, v in self.field_schema.items() if k.startswith("_")}

        self.field_schema = field_schema

        # Restore virtual field schemas
        for field_name, schema in virtual_schemas.items():
            self.field_schema[field_name] = schema

    def set_column_headers(self, display_names):
        """Set the column headers from ShotGrid display names.

        Args:
            display_names: Dictionary mapping field names to display names
        """
        # Update column headers with display names
        self.column_headers = []
        for field in self.column_fields:
            display_name = display_names.get(field, field)
            self.column_headers.append(display_name)

        # Emit header data changed signal
        self.headerDataChanged.emit(QtCore.Qt.Horizontal, 0, len(self.column_fields) - 1)

    def set_formula_evaluator(self, formula_evaluator):
        """Set the formula evaluator for calculated fields.

        Args:
            formula_evaluator: FormulaEvaluator instance
        """
        self.formula_evaluator = formula_evaluator

    def set_global_search(self, search_text):
        """Set the global search filter text.

        Args:
            search_text: Search string to filter rows
        """
        self.global_search_text = search_text.lower().strip()
        self.apply_filters()

    def set_sort(self, column_index, direction):
        """Set single-column sorting.

        Args:
            column_index: Column index to sort by
            direction: 'asc' or 'desc'
        """
        self.sort_column = column_index
        self.sort_direction = direction
        self.compound_sort_columns = []
        self.apply_filters()

    def set_compound_sort(self, sort_columns):
        """Set compound sorting.

        Args:
            sort_columns: List of (column_index, direction) tuples
        """
        self.compound_sort_columns = sort_columns
        self.sort_column = None
        self.sort_direction = None
        self.apply_filters()

    def clear_sorting(self):
        """Clear all sorting."""
        self.sort_column = None
        self.sort_direction = None
        self.compound_sort_columns = []
        self.apply_filters()

    def apply_filters(self):
        """Apply search and sorting to the data."""
        if not self.all_bidding_scenes_data:
            self.beginResetModel()
            self.filtered_row_indices = []
            self.display_row_to_data_row.clear()
            self.endResetModel()
            self.rowCountChanged.emit(0, 0)
            return

        # Notify views that model is being reset
        self.beginResetModel()

        # Start with all rows
        self.filtered_row_indices = list(range(len(self.all_bidding_scenes_data)))

        # Apply global search filter
        if self.global_search_text:
            self.filtered_row_indices = [
                idx for idx in self.filtered_row_indices
                if self._matches_global_search(self.all_bidding_scenes_data[idx], self.global_search_text)
            ]

        # Apply sorting
        if self.compound_sort_columns:
            self.filtered_row_indices.sort(key=lambda idx: self._get_compound_sort_key(self.all_bidding_scenes_data[idx]))
        elif self.sort_column is not None and self.sort_direction:
            self.filtered_row_indices.sort(key=lambda idx: self._get_sort_key(self.all_bidding_scenes_data[idx]))

        # Rebuild display mapping
        self.display_row_to_data_row.clear()
        for display_row, data_idx in enumerate(self.filtered_row_indices):
            self.display_row_to_data_row[display_row] = data_idx
        self.endResetModel()

        # Emit row count changed
        total_rows = len(self.all_bidding_scenes_data)
        shown_rows = len(self.filtered_row_indices)
        self.rowCountChanged.emit(shown_rows, total_rows)


    def _matches_global_search(self, bidding_scene_data, search_text):
        """Check if bidding scene data matches global search text."""
        for field in self.column_fields:
            value = bidding_scene_data.get(field)
            if value:
                if isinstance(value, dict):
                    value_str = value.get("name", "") or value.get("code", "")
                else:
                    value_str = str(value)

                if search_text in value_str.lower():
                    return True
        return False

    def _get_sort_key(self, bidding_scene_data):
        """Get sort key for a bidding scene based on current sort column."""
        if self.sort_column is None or self.sort_column >= len(self.column_fields):
            return (0, 0)

        field_name = self.column_fields[self.sort_column]
        value = bidding_scene_data.get(field_name)

        # Check if this is a numeric field
        is_numeric_field = (
            field_name in ("id", "sg_page", "sg_number_of_shots") or
            (field_name in self.field_schema and
             self.field_schema[field_name].get("data_type") in ("number", "float"))
        )

        # Determine the type and convert to sortable value
        if value is None:
            if is_numeric_field:
                sort_type = 0
                if self.sort_direction == "desc":
                    sort_value = float('inf')
                else:
                    sort_value = float('-inf')
            else:
                sort_type = 1
                sort_value = ""
        elif isinstance(value, (int, float)):
            sort_type = 0
            sort_value = float(value)
            if self.sort_direction == "desc":
                sort_value = -sort_value
        elif isinstance(value, datetime):
            sort_type = 0
            sort_value = value.timestamp() if hasattr(value, 'timestamp') else 0
            if self.sort_direction == "desc":
                sort_value = -sort_value
        elif isinstance(value, dict):
            sort_type = 1
            str_value = (value.get("name", "") or value.get("code", "") or "").lower()
            if self.sort_direction == "desc":
                sort_value = ReverseString(str_value)
            else:
                sort_value = str_value
        else:
            sort_type = 1
            str_value = str(value).strip()

            # Try to convert to number for numeric sorting
            if is_numeric_field or str_value.replace('.', '', 1).replace('-', '', 1).isdigit():
                try:
                    sort_type = 0
                    sort_value = float(str_value)
                    if self.sort_direction == "desc":
                        sort_value = -sort_value
                except (ValueError, TypeError):
                    sort_type = 1
                    if self.sort_direction == "desc":
                        sort_value = ReverseString(str_value.lower())
                    else:
                        sort_value = str_value.lower()
            else:
                if self.sort_direction == "desc":
                    sort_value = ReverseString(str_value.lower())
                else:
                    sort_value = str_value.lower()

        return (sort_type, sort_value)

    def _get_compound_sort_key(self, bidding_scene_data):
        """Get compound sort key for a bidding scene based on multiple sort columns."""
        sort_keys = []

        for col_idx, direction in self.compound_sort_columns:
            if col_idx >= len(self.column_fields):
                continue

            # Temporarily set the sort column and direction
            old_column = self.sort_column
            old_direction = self.sort_direction

            self.sort_column = col_idx
            self.sort_direction = direction

            # Get the sort key for this column
            sort_key = self._get_sort_key(bidding_scene_data)
            sort_keys.append(sort_key)

            # Restore original values
            self.sort_column = old_column
            self.sort_direction = old_direction

        return tuple(sort_keys) if sort_keys else ((0, 0),)

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

    def get_bidding_scene_data_for_row(self, row):
        """Get the bidding scene data dictionary for a display row.

        Args:
            row: Display row index

        Returns:
            dict: Bidding scene data dictionary or None
        """
        if row < 0 or row >= len(self.filtered_row_indices):
            return None

        data_row = self.filtered_row_indices[row]
        return self.all_bidding_scenes_data[data_row]

    def undo(self):
        """Undo the last change."""
        if not self.undo_stack:
            return False

        command = self.undo_stack.pop()
        self._updating = True
        self._in_undo_redo = True
        command.undo()
        self._in_undo_redo = False
        self._updating = False
        self.redo_stack.append(command)

        # Recalculate dependent cells AFTER flags are cleared
        if self.formula_evaluator:
            self.formula_evaluator.recalculate_dependents(command.row, command.col)

        self.statusMessageChanged.emit(f"Undone change to {self.column_fields[command.col]}", False)
        return True

    def redo(self):
        """Redo the last undone change."""
        if not self.redo_stack:
            return False

        command = self.redo_stack.pop()
        self._updating = True
        self._in_undo_redo = True
        command.redo()
        self._in_undo_redo = False
        self._updating = False
        self.undo_stack.append(command)

        # Recalculate dependent cells AFTER flags are cleared
        if self.formula_evaluator:
            self.formula_evaluator.recalculate_dependents(command.row, command.col)

        self.statusMessageChanged.emit(f"Redone change to {self.column_fields[command.col]}", False)
        return True

    def get_sort_templates(self):
        """Get saved sort templates."""
        return self.sort_templates.copy()

    def set_sort_templates(self, templates):
        """Save sort templates.

        Args:
            templates: Dictionary mapping template names to sort configurations
        """
        self.sort_templates = templates.copy()
        self.app_settings.set_sort_templates(self.sort_templates)

    def get_scenes_selected_for_export(self):
        """Get the bidding scenes that are selected for Excel export.

        Returns:
            List of bidding scene dictionaries that are selected for export
        """
        selected_scenes = []
        for data_row_idx in range(len(self.all_bidding_scenes_data)):
            if self.export_selection.get(data_row_idx, False):
                selected_scenes.append(self.all_bidding_scenes_data[data_row_idx])
        return selected_scenes

    def select_all_for_export(self):
        """Select all scenes for Excel export."""
        for i in range(len(self.all_bidding_scenes_data)):
            self.export_selection[i] = True
        # Emit data changed for the first column (export checkbox)
        if len(self.filtered_row_indices) > 0:
            top_left = self.index(0, 0)
            bottom_right = self.index(len(self.filtered_row_indices) - 1, 0)
            self.dataChanged.emit(top_left, bottom_right, [QtCore.Qt.CheckStateRole])

    def deselect_all_for_export(self):
        """Deselect all scenes for Excel export."""
        for i in range(len(self.all_bidding_scenes_data)):
            self.export_selection[i] = False
        # Emit data changed for the first column (export checkbox)
        if len(self.filtered_row_indices) > 0:
            top_left = self.index(0, 0)
            bottom_right = self.index(len(self.filtered_row_indices) - 1, 0)
            self.dataChanged.emit(top_left, bottom_right, [QtCore.Qt.CheckStateRole])
