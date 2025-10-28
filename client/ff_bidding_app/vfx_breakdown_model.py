"""
VFX Breakdown Model
Qt Model/View pattern implementation for VFX Breakdown data management.
"""

from PySide6 import QtCore, QtGui
import json
import logging
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


class EditCommand:
    """Command pattern for undo/redo of cell edits."""

    def __init__(self, model, row, col, old_value, new_value, bidding_scene_data, field_name, sg_session, field_schema=None):
        self.model = model
        self.row = row
        self.col = col
        self.old_value = old_value
        self.new_value = new_value
        self.bidding_scene_data = bidding_scene_data
        self.field_name = field_name
        self.sg_session = sg_session
        self.field_schema = field_schema or {}

    def undo(self):
        """Undo the edit."""
        # Update model data
        self.model.setData(self.model.index(self.row, self.col), self.old_value, QtCore.Qt.EditRole)
        # Update ShotGrid
        self._update_shotgrid(self.old_value)

    def redo(self):
        """Redo the edit."""
        # Update model data
        self.model.setData(self.model.index(self.row, self.col), self.new_value, QtCore.Qt.EditRole)
        # Update ShotGrid
        self._update_shotgrid(self.new_value)

    def _update_shotgrid(self, value):
        """Update ShotGrid with the value."""
        bidding_scene_id = self.bidding_scene_data.get("id")
        if not bidding_scene_id:
            logger.error("No bidding scene ID found for update")
            raise ValueError("No bidding scene ID found for update")

        # Convert string value back to appropriate type
        update_value = self._parse_value(value, self.field_name)

        # Update on ShotGrid
        self.sg_session.sg.update("CustomEntity02", bidding_scene_id, {self.field_name: update_value})
        logger.info(f"Updated Bidding Scene {bidding_scene_id} field '{self.field_name}' to: {update_value}")

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

    def __init__(self, changes, model, sg_session, field_schema=None):
        """
        Initialize paste command.

        Args:
            changes: List of dicts with keys: row, col, old_value, new_value, bidding_scene_data, field_name
            model: VFXBreakdownModel instance
            sg_session: ShotGrid session object
            field_schema: Field schema information
        """
        self.changes = changes
        self.model = model
        self.sg_session = sg_session
        self.field_schema = field_schema or {}

    def undo(self):
        """Undo all paste changes."""
        for change in self.changes:
            self.model.setData(self.model.index(change['row'], change['col']), change['old_value'], QtCore.Qt.EditRole)
            # Update ShotGrid
            self._update_shotgrid(change['old_value'], change['bidding_scene_data'], change['field_name'])

    def redo(self):
        """Redo all paste changes."""
        for change in self.changes:
            self.model.setData(self.model.index(change['row'], change['col']), change['new_value'], QtCore.Qt.EditRole)
            # Update ShotGrid
            self._update_shotgrid(change['new_value'], change['bidding_scene_data'], change['field_name'])

    def _update_shotgrid(self, value, bidding_scene_data, field_name):
        """Update ShotGrid with the value."""
        bidding_scene_id = bidding_scene_data.get("id")
        if not bidding_scene_id:
            logger.error("No bidding scene ID found for update")
            raise ValueError("No bidding scene ID found for update")

        # Convert string value back to appropriate type
        update_value = self._parse_value(value, field_name)

        # Update on ShotGrid
        self.sg_session.sg.update("CustomEntity02", bidding_scene_id, {field_name: update_value})
        logger.info(f"Updated Bidding Scene {bidding_scene_id} field '{field_name}' to: {update_value}")

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

        # Column configuration - matches import mapping fields
        self.column_fields = [
            "code",
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
        ]

        # Default headers (will be replaced with display names from ShotGrid)
        self.column_headers = self.column_fields.copy()

        # Read-only columns
        self.readonly_columns = []

        # Data storage
        self.all_bidding_scenes_data = []  # Original unfiltered bidding scene data
        self.filtered_row_indices = []  # Indices into all_bidding_scenes_data that pass filters
        self.display_row_to_data_row = {}  # Maps displayed row -> index in all_bidding_scenes_data

        # Field schema information
        self.field_schema = {}

        # Undo/Redo stack
        self.undo_stack = []
        self.redo_stack = []

        # Sorting state
        self.sort_column = None
        self.sort_direction = None
        self.compound_sort_columns = []

        # Filtering state
        self.global_search_text = ""

        # Settings for templates
        self.app_settings = AppSettings()
        self.sort_templates = self.app_settings.get_sort_templates()

        # Flag to prevent recursive updates
        self._updating = False

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
        value = bidding_scene_data.get(field_name)

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
            if field_name in self.readonly_columns:
                return QtGui.QColor("#888888")

        return None

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        """Set data for the given index."""
        if not index.isValid() or role != QtCore.Qt.EditRole:
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

        # Get old value
        old_value_raw = bidding_scene_data.get(field_name)
        old_value = self._format_sg_value(old_value_raw)

        new_value = value

        # Check if value actually changed
        if new_value == old_value:
            return False

        # Create undo command
        command = EditCommand(
            self,
            row,
            col,
            old_value,
            new_value,
            bidding_scene_data,
            field_name,
            self.sg_session,
            field_schema=self.field_schema
        )

        # Execute the command (update ShotGrid)
        try:
            self._updating = True
            command._update_shotgrid(new_value)

            # Update the bidding_scene_data with new value
            parsed_value = command._parse_value(new_value, field_name)
            bidding_scene_data[field_name] = parsed_value

            # Emit data changed
            self.dataChanged.emit(index, index, [QtCore.Qt.DisplayRole, QtCore.Qt.EditRole])

            # Add to undo stack
            self.undo_stack.append(command)
            # Clear redo stack on new edit
            self.redo_stack.clear()

            self._updating = False

            self.statusMessageChanged.emit(f"✓ Updated {field_name} on ShotGrid", False)
            logger.info(f"Successfully updated Bidding Scene {bidding_scene_data.get('id')} field '{field_name}' to '{new_value}'")

            return True

        except Exception as e:
            self._updating = False
            logger.error(f"Failed to update ShotGrid field '{field_name}': {e}", exc_info=True)
            self.statusMessageChanged.emit(f"Failed to update {field_name}", True)
            return False

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        """Return header data."""
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal and 0 <= section < len(self.column_headers):
                return self.column_headers[section]
            elif orientation == QtCore.Qt.Vertical:
                return str(section + 1)
        return None

    def flags(self, index):
        """Return item flags for the given index."""
        if not index.isValid():
            return QtCore.Qt.NoItemFlags

        field_name = self.column_fields[index.column()]

        if field_name in self.readonly_columns:
            return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        else:
            return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEditable

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
        self.sort_column = None
        self.sort_direction = None
        self.endResetModel()
        self.rowCountChanged.emit(0, 0)

    def set_field_schema(self, field_schema):
        """Set the field schema for type conversions.

        Args:
            field_schema: Dictionary mapping field names to schema info
        """
        self.field_schema = field_schema

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

        # Notify views
        self.beginResetModel()
        self.endResetModel()

        # Emit row count changed
        total_rows = len(self.all_bidding_scenes_data)
        shown_rows = len(self.filtered_row_indices)
        self.rowCountChanged.emit(shown_rows, total_rows)

        logger.info(f"Filters applied: showing {shown_rows} of {total_rows} rows")

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
            logger.info("Nothing to undo")
            return False

        command = self.undo_stack.pop()
        self._updating = True
        command.undo()
        self._updating = False
        self.redo_stack.append(command)
        logger.info(f"Undone edit at row {command.row}, col {command.col}")
        self.statusMessageChanged.emit(f"Undone change to {self.column_fields[command.col]}", False)
        return True

    def redo(self):
        """Redo the last undone change."""
        if not self.redo_stack:
            logger.info("Nothing to redo")
            return False

        command = self.redo_stack.pop()
        self._updating = True
        command.redo()
        self._updating = False
        self.undo_stack.append(command)
        logger.info(f"Redone edit at row {command.row}, col {command.col}")
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
