"""
Spreadsheet Widget
A full-featured spreadsheet widget inspired by Google Sheets with Excel formula support.
"""

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt
import string
import re

try:
    from .logger import logger
    from .formula_evaluator import FormulaEvaluator
except ImportError:
    import logging
    logger = logging.getLogger("FFPackageManager")
    from formula_evaluator import FormulaEvaluator


class SpreadsheetTableView(QtWidgets.QTableView):
    """Custom table view with Excel-like selection and fill handle."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fill_handle_rect = QtCore.QRect()
        self._is_dragging_fill_handle = False
        self._drag_start_index = None
        self._drag_current_index = None
        self.setMouseTracking(True)

        # Clipboard data for cut/copy/paste
        self._clipboard_data = None
        self._clipboard_is_cut = False

        # Ensure the table view can receive keyboard events
        self.setFocusPolicy(Qt.StrongFocus)

    def paintEvent(self, event):
        """Paint the table and add blue border with fill handle."""
        super().paintEvent(event)

        # Get current selection (use drag start if dragging, otherwise use current)
        if self._is_dragging_fill_handle and self._drag_start_index:
            current = self._drag_start_index
        else:
            current = self.currentIndex()

        if not current.isValid():
            return

        # Get the visual rect of the current cell
        rect = self.visualRect(current)
        if rect.isEmpty():
            return

        painter = QtGui.QPainter(self.viewport())

        # If dragging, draw preview of fill range
        if self._is_dragging_fill_handle and self._drag_current_index and self._drag_current_index != self._drag_start_index:
            # Draw light gray overlay on cells being filled
            start_row = self._drag_start_index.row()
            start_col = self._drag_start_index.column()
            end_row = self._drag_current_index.row()
            end_col = self._drag_current_index.column()

            # Only support vertical fill (same column)
            if start_col == end_col and end_row > start_row:
                painter.setBrush(QtGui.QColor(68, 114, 196, 30))  # Light blue with alpha
                painter.setPen(Qt.NoPen)

                for row in range(start_row + 1, end_row + 1):
                    cell_rect = self.visualRect(self.model().index(row, start_col))
                    if not cell_rect.isEmpty():
                        painter.drawRect(cell_rect)

        # Draw blue border around selected cell
        painter.setPen(QtGui.QPen(QtGui.QColor("#4472C4"), 2))
        painter.drawRect(rect.adjusted(1, 1, -1, -1))

        # Draw fill handle (small square at bottom-right)
        handle_size = 6
        handle_x = rect.right() - handle_size // 2
        handle_y = rect.bottom() - handle_size // 2
        self._fill_handle_rect = QtCore.QRect(handle_x, handle_y, handle_size, handle_size)

        painter.setBrush(QtGui.QColor("#4472C4"))
        painter.setPen(Qt.NoPen)
        painter.drawRect(self._fill_handle_rect)

        painter.end()

    def mousePressEvent(self, event):
        """Handle mouse press for fill handle dragging."""
        if event.button() == Qt.LeftButton:
            # Check if clicked on fill handle
            if self._fill_handle_rect.contains(event.pos()):
                self._is_dragging_fill_handle = True
                self._drag_start_index = self.currentIndex()
                self._drag_current_index = self._drag_start_index
                # Don't call super() - we don't want to change selection
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move for fill handle dragging."""
        if self._is_dragging_fill_handle and self._drag_start_index:
            # During drag, update cursor and track position
            self.setCursor(Qt.CrossCursor)

            # Get the index under the mouse
            index = self.indexAt(event.pos())
            if index.isValid() and index != self._drag_current_index:
                self._drag_current_index = index
                self.viewport().update()

            # Don't call super() - we don't want selection to change
            event.accept()
            return

        # Update cursor when hovering over fill handle (not dragging)
        if self._fill_handle_rect.contains(event.pos()):
            self.setCursor(Qt.CrossCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release to complete fill operation."""
        if self._is_dragging_fill_handle and self._drag_start_index and self._drag_current_index:
            if self._drag_current_index != self._drag_start_index:
                self._perform_fill_operation()

            self._is_dragging_fill_handle = False
            self._drag_start_index = None
            self._drag_current_index = None
            self.setCursor(Qt.ArrowCursor)  # Reset cursor
            self.viewport().update()
            # Don't call super() - we handled the event
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def _perform_fill_operation(self):
        """Perform the fill operation from start to current cell."""
        if not self._drag_start_index or not self._drag_current_index:
            return

        model = self.model()
        if not model:
            return

        start_row = self._drag_start_index.row()
        start_col = self._drag_start_index.column()
        end_row = self._drag_current_index.row()
        end_col = self._drag_current_index.column()

        # Only support vertical fill for now (same column)
        if start_col != end_col:
            return

        # Ensure we're dragging down
        if end_row <= start_row:
            return

        # Get the source cell's data
        source_data = model.data(self._drag_start_index, Qt.EditRole)
        source_formula = None

        if hasattr(model, '_formulas'):
            source_formula = model._formulas.get((start_row, start_col))

        # Fill the cells
        for row in range(start_row + 1, end_row + 1):
            if source_formula:
                # It's a formula - adjust row references
                row_offset = row - start_row
                new_formula = self._adjust_formula_for_fill(source_formula, row_offset)
                target_index = model.index(row, start_col)
                model.setData(target_index, new_formula, Qt.EditRole)
            else:
                # It's a value - copy as is
                target_index = model.index(row, start_col)
                model.setData(target_index, source_data, Qt.EditRole)

        logger.info(f"Filled cells from ({start_row},{start_col}) to ({end_row},{end_col})")

    def _adjust_formula_for_fill(self, formula, row_offset):
        """Adjust formula references when filling down.

        Args:
            formula: Original formula string
            row_offset: Number of rows to offset (positive = down)

        Returns:
            Adjusted formula string
        """
        # Pattern to match cell references like A1, B2, $A$1, etc.
        pattern = r'(\$?)([A-Z]+)(\$?)(\d+)'

        def replace_ref(match):
            col_abs = match.group(1)  # $ before column
            col_letter = match.group(2)
            row_abs = match.group(3)  # $ before row
            row_num = int(match.group(4))

            # If not absolute row reference, adjust the row
            if not row_abs:
                new_row_num = row_num + row_offset
                return f"{col_abs}{col_letter}{row_abs}{new_row_num}"

            return match.group(0)

        return re.sub(pattern, replace_ref, formula)

    def keyPressEvent(self, event):
        """Handle keyboard events for copy/cut/paste operations."""
        key = event.key()
        modifiers = event.modifiers()

        logger.debug(f"KeyPress: key={key}, modifiers={modifiers}")

        # Check for Ctrl+C (Copy)
        if key == Qt.Key_C and (modifiers & Qt.ControlModifier):
            logger.info("Ctrl+C detected - copying")
            self._copy_selection()
            event.accept()
            return

        # Check for Ctrl+X (Cut)
        if key == Qt.Key_X and (modifiers & Qt.ControlModifier):
            logger.info("Ctrl+X detected - cutting")
            self._cut_selection()
            event.accept()
            return

        # Check for Ctrl+V (Paste)
        if key == Qt.Key_V and (modifiers & Qt.ControlModifier):
            logger.info("Ctrl+V detected - pasting")
            self._paste_selection()
            event.accept()
            return

        # Check for Delete key
        if key == Qt.Key_Delete:
            logger.info("Delete key detected")
            self._delete_selection()
            event.accept()
            return

        super().keyPressEvent(event)

    def _copy_selection(self):
        """Copy the current cell to clipboard."""
        current = self.currentIndex()
        if not current.isValid():
            logger.debug("Copy: No valid cell selected")
            return

        model = self.model()
        if not model:
            logger.debug("Copy: No model available")
            return

        # Get the cell's formula or value (EditRole shows formula if present)
        value = model.data(current, Qt.EditRole)
        if value is None:
            value = ""

        # Store in internal clipboard
        self._clipboard_data = {
            'value': value,
            'row': current.row(),
            'col': current.column()
        }
        self._clipboard_is_cut = False

        # Also copy to system clipboard as text
        clipboard = QtWidgets.QApplication.clipboard()
        display_value = model.data(current, Qt.DisplayRole)
        clipboard.setText(str(display_value) if display_value else "")

        logger.info(f"Copied cell ({current.row()},{current.column()}): {value}")

    def _cut_selection(self):
        """Cut the current cell to clipboard."""
        current = self.currentIndex()
        if not current.isValid():
            logger.debug("Cut: No valid cell selected")
            return

        # First copy the data
        self._copy_selection()

        # Mark as cut operation
        self._clipboard_is_cut = True

        logger.info(f"Cut cell ({current.row()},{current.column()})")

    def _paste_selection(self):
        """Paste clipboard data to the current cell."""
        current = self.currentIndex()
        if not current.isValid():
            logger.debug("Paste: No valid cell selected")
            return

        model = self.model()
        if not model:
            logger.debug("Paste: No model available")
            return

        # Try internal clipboard first
        if self._clipboard_data:
            source_row = self._clipboard_data.get('row', 0)
            source_col = self._clipboard_data.get('col', 0)
            value = self._clipboard_data.get('value', '')

            logger.info(f"Pasting from internal clipboard: {value}")

            # If it's a formula and we're pasting to a different cell, adjust references
            if isinstance(value, str) and value.startswith('='):
                row_offset = current.row() - source_row
                col_offset = current.column() - source_col

                if row_offset != 0 or col_offset != 0:
                    adjusted_value = self._adjust_formula_for_paste(value, row_offset, col_offset)
                    logger.info(f"Adjusted formula from {value} to {adjusted_value}")
                    value = adjusted_value

            # Set the data
            model.setData(current, value, Qt.EditRole)

            # If it was a cut operation, clear the source cell
            if self._clipboard_is_cut and self._clipboard_data:
                source_index = model.index(source_row, source_col)
                model.setData(source_index, "", Qt.EditRole)
                self._clipboard_is_cut = False
                logger.info(f"Cleared source cell ({source_row},{source_col}) after cut")

            logger.info(f"Pasted to cell ({current.row()},{current.column()}): {value}")
        else:
            # Try system clipboard
            clipboard = QtWidgets.QApplication.clipboard()
            text = clipboard.text()
            if text:
                model.setData(current, text, Qt.EditRole)
                logger.info(f"Pasted from system clipboard to ({current.row()},{current.column()}): {text}")
            else:
                logger.debug("Paste: No data in clipboard")

    def _delete_selection(self):
        """Delete the content of the current cell."""
        current = self.currentIndex()
        if not current.isValid():
            logger.debug("Delete: No valid cell selected")
            return

        model = self.model()
        if not model:
            logger.debug("Delete: No model available")
            return

        # Clear the cell
        model.setData(current, "", Qt.EditRole)
        logger.info(f"Deleted cell ({current.row()},{current.column()})")

    def _adjust_formula_for_paste(self, formula, row_offset, col_offset):
        """Adjust formula references when pasting to a different cell.

        Args:
            formula: Original formula string
            row_offset: Number of rows to offset (positive = down, negative = up)
            col_offset: Number of columns to offset (positive = right, negative = left)

        Returns:
            Adjusted formula string
        """
        # Pattern to match cell references like A1, B2, $A$1, etc.
        pattern = r'(\$?)([A-Z]+)(\$?)(\d+)'

        def replace_ref(match):
            col_abs = match.group(1)  # $ before column
            col_letter = match.group(2)
            row_abs = match.group(3)  # $ before row
            row_num = int(match.group(4))

            # Adjust row if not absolute
            if not row_abs:
                new_row_num = row_num + row_offset
                if new_row_num < 1:
                    new_row_num = 1
            else:
                new_row_num = row_num

            # Adjust column if not absolute
            if not col_abs:
                # Convert column letter to index, adjust, and convert back
                col_idx = 0
                for char in col_letter:
                    col_idx = col_idx * 26 + (ord(char) - 65 + 1)
                col_idx -= 1  # Make 0-based

                new_col_idx = col_idx + col_offset
                if new_col_idx < 0:
                    new_col_idx = 0

                # Convert back to letter
                new_col_letter = ""
                temp_idx = new_col_idx + 1
                while temp_idx > 0:
                    temp_idx -= 1
                    new_col_letter = chr(65 + (temp_idx % 26)) + new_col_letter
                    temp_idx //= 26
            else:
                new_col_letter = col_letter

            return f"{col_abs}{new_col_letter}{row_abs}{new_row_num}"

        return re.sub(pattern, replace_ref, formula)


class SpreadsheetModel(QtCore.QAbstractTableModel):
    """Model for spreadsheet data with formula support."""

    def __init__(self, rows=100, cols=26, parent=None):
        """Initialize the spreadsheet model.

        Args:
            rows: Number of rows
            cols: Number of columns
            parent: Parent widget
        """
        super().__init__(parent)
        self._rows = rows
        self._cols = cols
        self._data = {}  # Dict of (row, col) -> value
        self._formulas = {}  # Dict of (row, col) -> formula string
        self._evaluated_cache = {}  # Dict of (row, col) -> evaluated result
        self.formula_evaluator = None

    def rowCount(self, parent=QtCore.QModelIndex()):
        """Return the number of rows."""
        return self._rows

    def columnCount(self, parent=QtCore.QModelIndex()):
        """Return the number of columns."""
        return self._cols

    def data(self, index, role=Qt.DisplayRole):
        """Return data for the given index and role."""
        if not index.isValid():
            return None

        row, col = index.row(), index.column()

        if role == Qt.DisplayRole or role == Qt.EditRole:
            # Check if there's a formula
            if (row, col) in self._formulas:
                formula = self._formulas[(row, col)]
                if role == Qt.EditRole:
                    # When editing, show the formula
                    return formula
                else:
                    # When displaying, show the evaluated result
                    return self._get_evaluated_value(row, col, formula)
            else:
                # Regular value
                return self._data.get((row, col), "")

        elif role == Qt.TextAlignmentRole:
            # Check if the cell contains a number
            value = self._data.get((row, col), "")
            if (row, col) in self._formulas:
                # Formulas are right-aligned
                return Qt.AlignRight | Qt.AlignVCenter
            try:
                float(str(value).replace(',', '').replace('$', ''))
                return Qt.AlignRight | Qt.AlignVCenter
            except (ValueError, AttributeError):
                return Qt.AlignLeft | Qt.AlignVCenter

        return None

    def _get_evaluated_value(self, row, col, formula):
        """Evaluate a formula and return the result."""
        if not self.formula_evaluator:
            return formula

        try:
            # Check cache first
            if (row, col) in self._evaluated_cache:
                return self._evaluated_cache[(row, col)]

            # Evaluate the formula
            result = self.formula_evaluator.evaluate(formula, row, col)

            # Format the result
            if isinstance(result, (int, float)):
                formatted = f"{result:,.2f}"
            else:
                formatted = str(result)

            # Cache the result
            self._evaluated_cache[(row, col)] = formatted
            return formatted

        except Exception as e:
            logger.debug(f"Error evaluating formula at ({row}, {col}): {e}")
            return f"#ERROR: {str(e)[:20]}"

    def setData(self, index, value, role=Qt.EditRole):
        """Set data for the given index."""
        if not index.isValid():
            return False

        if role == Qt.EditRole:
            row, col = index.row(), index.column()

            # Clear the cache for this cell
            self._evaluated_cache.pop((row, col), None)

            # Check if it's a formula (starts with =)
            value_str = str(value).strip()
            if value_str.startswith('='):
                # Store as formula
                self._formulas[(row, col)] = value_str
                self._data.pop((row, col), None)
            else:
                # Store as regular value
                self._data[(row, col)] = value_str
                self._formulas.pop((row, col), None)

            # Clear cache for dependent cells
            self._clear_dependent_cache()

            self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
            return True

        return False

    def _clear_dependent_cache(self):
        """Clear the evaluation cache for cells that depend on changed cells."""
        # For simplicity, clear the entire cache
        # A more sophisticated implementation would track dependencies
        self._evaluated_cache.clear()

    def flags(self, index):
        """Return item flags for the given index."""
        if not index.isValid():
            return Qt.NoItemFlags

        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        """Return header data."""
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                # Column headers: A, B, C, ..., Z, AA, AB, ...
                return self._column_name(section)
            else:
                # Row headers: 1, 2, 3, ...
                return str(section + 1)
        return None

    def _column_name(self, index):
        """Convert column index to spreadsheet column name (A, B, C, ..., AA, AB, ...)."""
        name = ""
        index += 1  # Make it 1-based
        while index > 0:
            index -= 1
            name = chr(65 + (index % 26)) + name
            index //= 26
        return name

    @staticmethod
    def letter_to_col(letter):
        """Convert column letter to index (A->0, B->1, ..., Z->25, AA->26)."""
        col = 0
        for char in letter:
            col = col * 26 + (ord(char) - 65 + 1)
        return col - 1

    def get_cell_value(self, row, col):
        """Get the raw value of a cell (not the formula)."""
        if (row, col) in self._formulas:
            # Evaluate the formula
            formula = self._formulas[(row, col)]
            return self._get_evaluated_value(row, col, formula)
        else:
            value = self._data.get((row, col), "")
            # Try to convert to number if possible
            try:
                return float(str(value).replace(',', '').replace('$', ''))
            except (ValueError, AttributeError):
                return value if value else ""

    def get_cell_formula(self, row, col):
        """Get the formula of a cell if it exists."""
        return self._formulas.get((row, col), None)

    def set_formula_evaluator(self, evaluator):
        """Set the formula evaluator."""
        self.formula_evaluator = evaluator
        # Clear cache when evaluator changes
        self._evaluated_cache.clear()


class SpreadsheetWidget(QtWidgets.QWidget):
    """Full-featured spreadsheet widget with Excel formula support."""

    def __init__(self, rows=10, cols=26, app_settings=None, parent=None):
        """Initialize the spreadsheet widget.

        Args:
            rows: Number of rows (default: 10)
            cols: Number of columns
            app_settings: AppSettings instance for currency formatting
            parent: Parent widget
        """
        super().__init__(parent)
        self.app_settings = app_settings

        # Create layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Create custom table view FIRST (before toolbar)
        self.table_view = SpreadsheetTableView()
        self.table_view.setAlternatingRowColors(False)  # Disable alternating colors
        self.table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectItems)
        self.table_view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)  # Single selection for fill handle

        # Enable context menu
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._show_context_menu)

        # Create model
        self.model = SpreadsheetModel(rows, cols)
        self.table_view.setModel(self.model)

        # Configure table view
        self.table_view.horizontalHeader().setDefaultSectionSize(100)
        self.table_view.horizontalHeader().setStretchLastSection(False)
        self.table_view.verticalHeader().setDefaultSectionSize(25)

        # Enable grid
        self.table_view.setShowGrid(True)
        self.table_view.setGridStyle(Qt.SolidLine)

        # Create toolbar (after table_view exists)
        self._create_toolbar()
        layout.addWidget(self.toolbar)

        # Add table view
        layout.addWidget(self.table_view)

        # Create formula evaluator
        self.formula_evaluator = None

        logger.info(f"SpreadsheetWidget initialized with {rows} rows and {cols} columns")

    def _create_toolbar(self):
        """Create the toolbar with spreadsheet controls."""
        self.toolbar = QtWidgets.QWidget()
        toolbar_layout = QtWidgets.QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(5, 5, 5, 5)
        toolbar_layout.setSpacing(5)

        # Formula bar label
        formula_label = QtWidgets.QLabel("fx")
        formula_label.setStyleSheet("font-weight: bold; padding: 2px;")
        toolbar_layout.addWidget(formula_label)

        # Formula bar
        self.formula_bar = QtWidgets.QLineEdit()
        self.formula_bar.setPlaceholderText("Enter formula or value...")
        self.formula_bar.returnPressed.connect(self._on_formula_bar_enter)
        toolbar_layout.addWidget(self.formula_bar, 1)

        # Connect selection change to update formula bar
        self.table_view.selectionModel().currentChanged.connect(self._on_selection_changed)

    def _on_selection_changed(self, current, previous):
        """Update formula bar when selection changes."""
        if not current.isValid():
            self.formula_bar.clear()
            return

        # Get the cell's content (formula or value)
        value = self.model.data(current, Qt.EditRole)
        self.formula_bar.setText(str(value) if value else "")

    def _on_formula_bar_enter(self):
        """Handle Enter key in formula bar."""
        # Get current selection
        current = self.table_view.currentIndex()
        if not current.isValid():
            return

        # Set the value
        value = self.formula_bar.text()
        self.model.setData(current, value, Qt.EditRole)

        # Move to next row
        next_row = current.row() + 1
        if next_row < self.model.rowCount():
            next_index = self.model.index(next_row, current.column())
            self.table_view.setCurrentIndex(next_index)

    def _show_context_menu(self, position):
        """Show context menu on right-click."""
        # Get the index at the clicked position
        index = self.table_view.indexAt(position)
        if not index.isValid():
            return

        # Create context menu
        menu = QtWidgets.QMenu(self)

        # Row operations
        insert_row_above = menu.addAction("Insert Row Above")
        insert_row_below = menu.addAction("Insert Row Below")
        delete_row = menu.addAction("Delete Row")
        menu.addSeparator()

        # Column operations
        insert_col_left = menu.addAction("Insert Column Left")
        insert_col_right = menu.addAction("Insert Column Right")
        delete_column = menu.addAction("Delete Column")

        # Show menu and get action
        action = menu.exec_(self.table_view.viewport().mapToGlobal(position))

        if action == insert_row_above:
            self._insert_row_above(index.row())
        elif action == insert_row_below:
            self._insert_row_below(index.row())
        elif action == delete_row:
            self._delete_row(index.row())
        elif action == insert_col_left:
            self._insert_column_left(index.column())
        elif action == insert_col_right:
            self._insert_column_right(index.column())
        elif action == delete_column:
            self._delete_column(index.column())

    def _insert_row_above(self, row):
        """Insert a new row above the specified row."""
        self.model.beginInsertRows(QtCore.QModelIndex(), row, row)

        # Shift all data down
        self.model._rows += 1
        new_data = {}
        new_formulas = {}

        for (r, c), value in self.model._data.items():
            if r >= row:
                new_data[(r + 1, c)] = value
            else:
                new_data[(r, c)] = value

        for (r, c), formula in self.model._formulas.items():
            if r >= row:
                new_formulas[(r + 1, c)] = formula
            else:
                new_formulas[(r, c)] = formula

        self.model._data = new_data
        self.model._formulas = new_formulas
        self.model._evaluated_cache.clear()

        self.model.endInsertRows()
        logger.info(f"Inserted row above row {row + 1}")

    def _insert_row_below(self, row):
        """Insert a new row below the specified row."""
        self._insert_row_above(row + 1)

    def _delete_row(self, row):
        """Delete the specified row."""
        if self.model._rows <= 1:
            logger.warning("Cannot delete the last row")
            return

        self.model.beginRemoveRows(QtCore.QModelIndex(), row, row)

        # Shift all data up
        self.model._rows -= 1
        new_data = {}
        new_formulas = {}

        for (r, c), value in self.model._data.items():
            if r == row:
                continue  # Skip the deleted row
            elif r > row:
                new_data[(r - 1, c)] = value
            else:
                new_data[(r, c)] = value

        for (r, c), formula in self.model._formulas.items():
            if r == row:
                continue  # Skip the deleted row
            elif r > row:
                # Update formula to adjust for row shift
                updated_formula = self._update_formula_for_row_deletion(formula, row)
                new_formulas[(r - 1, c)] = updated_formula
            else:
                # Update formula even if not shifting position
                updated_formula = self._update_formula_for_row_deletion(formula, row)
                new_formulas[(r, c)] = updated_formula

        self.model._data = new_data
        self.model._formulas = new_formulas
        self.model._evaluated_cache.clear()

        self.model.endRemoveRows()
        logger.info(f"Deleted row {row + 1}")

    def _delete_column(self, col):
        """Delete the specified column."""
        if self.model._cols <= 1:
            logger.warning("Cannot delete the last column")
            return

        self.model.beginRemoveColumns(QtCore.QModelIndex(), col, col)

        # Shift all data left
        self.model._cols -= 1
        new_data = {}
        new_formulas = {}

        for (r, c), value in self.model._data.items():
            if c == col:
                continue  # Skip the deleted column
            elif c > col:
                new_data[(r, c - 1)] = value
            else:
                new_data[(r, c)] = value

        for (r, c), formula in self.model._formulas.items():
            if c == col:
                continue  # Skip the deleted column
            elif c > col:
                # Update formula to adjust for column shift
                updated_formula = self._update_formula_for_column_deletion(formula, col)
                new_formulas[(r, c - 1)] = updated_formula
            else:
                # Update formula even if not shifting position
                updated_formula = self._update_formula_for_column_deletion(formula, col)
                new_formulas[(r, c)] = updated_formula

        self.model._data = new_data
        self.model._formulas = new_formulas
        self.model._evaluated_cache.clear()

        self.model.endRemoveColumns()
        logger.info(f"Deleted column {self.model._column_name(col)}")

    def _insert_column_left(self, col):
        """Insert a new column to the left of the specified column."""
        self.model.beginInsertColumns(QtCore.QModelIndex(), col, col)

        # Shift all data right
        self.model._cols += 1
        new_data = {}
        new_formulas = {}

        for (r, c), value in self.model._data.items():
            if c >= col:
                new_data[(r, c + 1)] = value
            else:
                new_data[(r, c)] = value

        for (r, c), formula in self.model._formulas.items():
            if c >= col:
                new_formulas[(r, c + 1)] = formula
            else:
                new_formulas[(r, c)] = formula

        self.model._data = new_data
        self.model._formulas = new_formulas
        self.model._evaluated_cache.clear()

        self.model.endInsertColumns()
        logger.info(f"Inserted column left of {self.model._column_name(col)}")

    def _insert_column_right(self, col):
        """Insert a new column to the right of the specified column."""
        self._insert_column_left(col + 1)

    def _update_formula_for_row_deletion(self, formula, deleted_row):
        """Update cell references in a formula after a row deletion.

        Args:
            formula: The formula string (e.g., "=SUM(A1:A10)")
            deleted_row: The row that was deleted (0-based)

        Returns:
            Updated formula string
        """
        import re

        # Pattern to match cell references like A1, B2, $A$1, etc.
        pattern = r'(\$?)([A-Z]+)(\$?)(\d+)'

        def replace_ref(match):
            col_abs = match.group(1)  # $ before column
            col_letter = match.group(2)
            row_abs = match.group(3)  # $ before row
            row_num = int(match.group(4))

            # Convert to 0-based
            row_idx = row_num - 1

            # If not absolute row reference and row > deleted_row, decrement
            if not row_abs and row_idx > deleted_row:
                new_row_num = row_num - 1
                return f"{col_abs}{col_letter}{row_abs}{new_row_num}"

            return match.group(0)

        return re.sub(pattern, replace_ref, formula)

    def _update_formula_for_column_deletion(self, formula, deleted_col):
        """Update cell references in a formula after a column deletion.

        Args:
            formula: The formula string (e.g., "=SUM(A1:B10)")
            deleted_col: The column that was deleted (0-based)

        Returns:
            Updated formula string
        """
        import re

        # Pattern to match cell references like A1, B2, $A$1, etc.
        pattern = r'(\$?)([A-Z]+)(\$?)(\d+)'

        def replace_ref(match):
            col_abs = match.group(1)  # $ before column
            col_letter = match.group(2)
            row_abs = match.group(3)  # $ before row
            row_num = match.group(4)

            # Convert column letter to index
            col_idx = self.model.letter_to_col(col_letter)

            # If not absolute column reference and col > deleted_col, shift left
            if not col_abs and col_idx > deleted_col:
                new_col_letter = self.model._column_name(col_idx - 1)
                return f"{col_abs}{new_col_letter}{row_abs}{row_num}"

            return match.group(0)

        return re.sub(pattern, replace_ref, formula)

    def set_formula_evaluator(self, evaluator):
        """Set the formula evaluator."""
        self.formula_evaluator = evaluator
        self.model.set_formula_evaluator(evaluator)

    def get_cell_value(self, row, col):
        """Get the evaluated value of a cell."""
        return self.model.get_cell_value(row, col)

    def set_cell_value(self, row, col, value):
        """Set the value of a cell."""
        index = self.model.index(row, col)
        self.model.setData(index, value, Qt.EditRole)

    def get_data_as_dict(self):
        """Export all data as a dictionary."""
        data = {}
        for row in range(self.model.rowCount()):
            for col in range(self.model.columnCount()):
                value = self.model._data.get((row, col))
                formula = self.model._formulas.get((row, col))
                if value or formula:
                    data[(row, col)] = {
                        'value': value,
                        'formula': formula,
                    }
        return data

    def load_data_from_dict(self, data):
        """Load data from a dictionary."""
        self.model._data.clear()
        self.model._formulas.clear()
        self.model._evaluated_cache.clear()

        for (row, col), cell_data in data.items():
            if cell_data.get('formula'):
                self.model._formulas[(row, col)] = cell_data['formula']
            elif cell_data.get('value'):
                self.model._data[(row, col)] = cell_data['value']

        # Refresh the view
        self.model.layoutChanged.emit()
