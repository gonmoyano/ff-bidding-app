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

        # Get current selection
        current = self.currentIndex()
        selection = self.selectionModel().selectedIndexes() if self.selectionModel() else []

        if not current.isValid() and not selection:
            return

        painter = QtGui.QPainter(self.viewport())

        # If dragging fill handle, draw preview of fill range
        if self._is_dragging_fill_handle and self._drag_start_index and self._drag_current_index and self._drag_current_index != self._drag_start_index:
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

        # Draw border around all selected cells
        if selection:
            # Find bounding rectangle of selection
            min_row = min(idx.row() for idx in selection)
            max_row = max(idx.row() for idx in selection)
            min_col = min(idx.column() for idx in selection)
            max_col = max(idx.column() for idx in selection)

            # Get visual rect of bounding selection
            top_left_rect = self.visualRect(self.model().index(min_row, min_col))
            bottom_right_rect = self.visualRect(self.model().index(max_row, max_col))

            if not top_left_rect.isEmpty() and not bottom_right_rect.isEmpty():
                # Combine into selection bounding rect
                selection_rect = top_left_rect.united(bottom_right_rect)

                # Draw blue border around entire selection
                painter.setPen(QtGui.QPen(QtGui.QColor("#4472C4"), 2))
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(selection_rect.adjusted(1, 1, -1, -1))

                # Draw fill handle at bottom-right of selection
                handle_size = 6
                handle_x = selection_rect.right() - handle_size // 2
                handle_y = selection_rect.bottom() - handle_size // 2
                self._fill_handle_rect = QtCore.QRect(handle_x, handle_y, handle_size, handle_size)

                painter.setBrush(QtGui.QColor("#4472C4"))
                painter.setPen(Qt.NoPen)
                painter.drawRect(self._fill_handle_rect)
        elif current.isValid():
            # Single cell selected - draw border around it
            rect = self.visualRect(current)
            if not rect.isEmpty():
                painter.setPen(QtGui.QPen(QtGui.QColor("#4472C4"), 2))
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(rect.adjusted(1, 1, -1, -1))

                # Draw fill handle
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
        """Handle keyboard events for copy/cut/paste/undo/redo operations."""
        key = event.key()
        modifiers = event.modifiers()

        # Check for Ctrl+Z (Undo)
        if key == Qt.Key_Z and (modifiers & Qt.ControlModifier):
            logger.info("Ctrl+Z detected - undoing")
            self._undo()
            event.accept()
            return

        # Check for Ctrl+Y (Redo)
        if key == Qt.Key_Y and (modifiers & Qt.ControlModifier):
            logger.info("Ctrl+Y detected - redoing")
            self._redo()
            event.accept()
            return

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

    def _undo(self):
        """Undo the last change."""
        model = self.model()
        if model and hasattr(model, 'undo'):
            model.undo()

    def _redo(self):
        """Redo the last undone change."""
        model = self.model()
        if model and hasattr(model, 'redo'):
            model.redo()

    def _copy_selection(self):
        """Copy selected cells to clipboard."""
        selection = self.selectionModel().selectedIndexes() if self.selectionModel() else []
        if not selection:
            return

        model = self.model()
        if not model:
            return

        # Sort by row then column
        selection = sorted(selection, key=lambda idx: (idx.row(), idx.column()))

        # Find bounding rectangle
        min_row = min(idx.row() for idx in selection)
        max_row = max(idx.row() for idx in selection)
        min_col = min(idx.column() for idx in selection)
        max_col = max(idx.column() for idx in selection)

        # Build clipboard data structure: dict of relative (row, col) -> value
        clipboard_cells = {}
        clipboard_text_rows = []

        for row in range(min_row, max_row + 1):
            row_values = []
            for col in range(min_col, max_col + 1):
                index = model.index(row, col)
                # Check if this cell is in selection
                if index in selection:
                    value = model.data(index, Qt.EditRole)
                    if value is None:
                        value = ""
                    clipboard_cells[(row - min_row, col - min_col)] = value
                    display_value = model.data(index, Qt.DisplayRole)
                    row_values.append(str(display_value) if display_value else "")
                else:
                    row_values.append("")
            clipboard_text_rows.append("\t".join(row_values))

        # Store in internal clipboard
        self._clipboard_data = {
            'cells': clipboard_cells,
            'rows': max_row - min_row + 1,
            'cols': max_col - min_col + 1,
            'source_row': min_row,
            'source_col': min_col
        }
        self._clipboard_is_cut = False

        # Also copy to system clipboard as tab-separated text
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText("\n".join(clipboard_text_rows))

        logger.info(f"Copied {len(clipboard_cells)} cells from ({min_row},{min_col}) to ({max_row},{max_col})")

    def _cut_selection(self):
        """Cut selected cells to clipboard."""
        selection = self.selectionModel().selectedIndexes() if self.selectionModel() else []
        if not selection:
            return

        # First copy the data
        self._copy_selection()

        # Mark as cut operation
        self._clipboard_is_cut = True

        # Store the original selection for clearing after paste
        self._cut_selection_indexes = list(selection)

        logger.info(f"Cut {len(selection)} cells")

    def _paste_selection(self):
        """Paste clipboard data to current cell or selection."""
        current = self.currentIndex()
        if not current.isValid():
            return

        model = self.model()
        if not model:
            return

        # Collect all changes for a single undo command
        changes = []

        # Try internal clipboard first (multi-cell)
        if self._clipboard_data and 'cells' in self._clipboard_data:
            cells = self._clipboard_data['cells']
            source_row = self._clipboard_data.get('source_row', 0)
            source_col = self._clipboard_data.get('source_col', 0)

            target_row = current.row()
            target_col = current.column()

            # Calculate offset from source to target
            row_offset = target_row - source_row
            col_offset = target_col - source_col

            # Collect paste changes
            for (rel_row, rel_col), value in cells.items():
                paste_row = target_row + rel_row
                paste_col = target_col + rel_col

                # Check bounds
                if paste_row >= model.rowCount() or paste_col >= model.columnCount():
                    continue

                # If it's a formula, adjust references
                new_formula = None
                new_value = None
                if isinstance(value, str) and value.startswith('='):
                    new_formula = self._adjust_formula_for_paste(value, row_offset + rel_row, col_offset + rel_col)
                else:
                    new_value = value

                # Get old values
                old_value = model._data.get((paste_row, paste_col), None)
                old_formula = model._formulas.get((paste_row, paste_col), None)

                changes.append({
                    'row': paste_row,
                    'col': paste_col,
                    'old_value': old_value,
                    'new_value': new_value,
                    'old_formula': old_formula,
                    'new_formula': new_formula
                })

            # If it was a cut operation, also add deletions for source cells
            if self._clipboard_is_cut and hasattr(self, '_cut_selection_indexes'):
                for source_index in self._cut_selection_indexes:
                    src_row, src_col = source_index.row(), source_index.column()
                    old_value = model._data.get((src_row, src_col), None)
                    old_formula = model._formulas.get((src_row, src_col), None)
                    changes.append({
                        'row': src_row,
                        'col': src_col,
                        'old_value': old_value,
                        'new_value': None,
                        'old_formula': old_formula,
                        'new_formula': None
                    })
                self._clipboard_is_cut = False
                self._cut_selection_indexes = []

        else:
            # Try system clipboard (tab-separated text)
            clipboard = QtWidgets.QApplication.clipboard()
            text = clipboard.text()
            if text:
                # Parse tab-separated values
                rows = text.split('\n')
                # Remove trailing empty row if present
                if rows and rows[-1] == '':
                    rows = rows[:-1]

                target_row = current.row()
                target_col = current.column()

                for row_offset, row_text in enumerate(rows):
                    cols = row_text.split('\t')
                    for col_offset, cell_value in enumerate(cols):
                        paste_row = target_row + row_offset
                        paste_col = target_col + col_offset

                        # Check bounds
                        if paste_row >= model.rowCount() or paste_col >= model.columnCount():
                            continue

                        # Get old values
                        old_value = model._data.get((paste_row, paste_col), None)
                        old_formula = model._formulas.get((paste_row, paste_col), None)

                        # Determine if new value is formula or value
                        new_formula = None
                        new_value = None
                        if cell_value.startswith('='):
                            new_formula = cell_value
                        else:
                            new_value = cell_value

                        changes.append({
                            'row': paste_row,
                            'col': paste_col,
                            'old_value': old_value,
                            'new_value': new_value,
                            'old_formula': old_formula,
                            'new_formula': new_formula
                        })

        # Execute paste via command
        if changes:
            command = SpreadsheetPasteCommand(changes, model)
            model._in_undo_redo = True
            try:
                command.redo()
            finally:
                model._in_undo_redo = False

            # Add to undo stack
            model.undo_stack.append(command)
            model.redo_stack.clear()

            # Clear dependent cache
            model._clear_dependent_cache()

            logger.info(f"Pasted {len(changes)} cells")

    def _delete_selection(self):
        """Delete the content of selected cells."""
        selection = self.selectionModel().selectedIndexes() if self.selectionModel() else []
        if not selection:
            return

        model = self.model()
        if not model:
            return

        # Collect deletions for a single undo command
        deletions = []
        for index in selection:
            row, col = index.row(), index.column()
            old_value = model._data.get((row, col), None)
            old_formula = model._formulas.get((row, col), None)

            # Only include cells that have content
            if old_value is not None or old_formula is not None:
                deletions.append({
                    'row': row,
                    'col': col,
                    'old_value': old_value,
                    'old_formula': old_formula
                })

        if not deletions:
            return

        # Execute delete via command
        command = SpreadsheetDeleteCommand(deletions, model)
        model._in_undo_redo = True
        try:
            command.redo()
        finally:
            model._in_undo_redo = False

        # Add to undo stack
        model.undo_stack.append(command)
        model.redo_stack.clear()

        # Clear dependent cache
        model._clear_dependent_cache()

        logger.info(f"Deleted {len(deletions)} cells")

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


class SpreadsheetEditCommand:
    """Command pattern for undo/redo of single cell edits in spreadsheet."""

    def __init__(self, model, row, col, old_value, new_value, old_formula, new_formula):
        """Initialize the edit command.

        Args:
            model: SpreadsheetModel instance
            row: Row index
            col: Column index
            old_value: Previous value in _data
            new_value: New value in _data
            old_formula: Previous formula in _formulas (or None)
            new_formula: New formula in _formulas (or None)
        """
        self.model = model
        self.row = row
        self.col = col
        self.old_value = old_value
        self.new_value = new_value
        self.old_formula = old_formula
        self.new_formula = new_formula

    def undo(self):
        """Undo the edit - restore old value/formula."""
        self._apply_cell_data(self.old_value, self.old_formula)

    def redo(self):
        """Redo the edit - apply new value/formula."""
        self._apply_cell_data(self.new_value, self.new_formula)

    def _apply_cell_data(self, value, formula):
        """Apply value or formula to the cell."""
        # Clear cache
        self.model._evaluated_cache.pop((self.row, self.col), None)

        if formula:
            # It's a formula
            self.model._formulas[(self.row, self.col)] = formula
            self.model._data.pop((self.row, self.col), None)
        else:
            # It's a value
            if value:
                self.model._data[(self.row, self.col)] = value
            else:
                self.model._data.pop((self.row, self.col), None)
            self.model._formulas.pop((self.row, self.col), None)

        # Clear dependent cache and emit change
        self.model._clear_dependent_cache()
        index = self.model.index(self.row, self.col)
        self.model.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])


class SpreadsheetPasteCommand:
    """Command pattern for undo/redo of paste operations in spreadsheet."""

    def __init__(self, changes, model):
        """Initialize paste command.

        Args:
            changes: List of dicts with keys: row, col, old_value, new_value,
                    old_formula, new_formula
            model: SpreadsheetModel instance
        """
        self.changes = changes
        self.model = model

    def undo(self):
        """Undo all paste changes."""
        for change in self.changes:
            self._apply_cell_data(
                change['row'], change['col'],
                change['old_value'], change['old_formula']
            )

    def redo(self):
        """Redo all paste changes."""
        for change in self.changes:
            self._apply_cell_data(
                change['row'], change['col'],
                change['new_value'], change['new_formula']
            )

    def _apply_cell_data(self, row, col, value, formula):
        """Apply value or formula to a cell."""
        # Clear cache
        self.model._evaluated_cache.pop((row, col), None)

        if formula:
            # It's a formula
            self.model._formulas[(row, col)] = formula
            self.model._data.pop((row, col), None)
        else:
            # It's a value
            if value:
                self.model._data[(row, col)] = value
            else:
                self.model._data.pop((row, col), None)
            self.model._formulas.pop((row, col), None)

        # Emit change for this cell
        index = self.model.index(row, col)
        self.model.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])


class SpreadsheetDeleteCommand:
    """Command pattern for undo/redo of delete operations in spreadsheet."""

    def __init__(self, deletions, model):
        """Initialize delete command.

        Args:
            deletions: List of dicts with keys: row, col, old_value, old_formula
            model: SpreadsheetModel instance
        """
        self.deletions = deletions
        self.model = model

    def undo(self):
        """Undo deletions - restore old values."""
        for deletion in self.deletions:
            self._apply_cell_data(
                deletion['row'], deletion['col'],
                deletion['old_value'], deletion['old_formula']
            )

    def redo(self):
        """Redo deletions - clear cells again."""
        for deletion in self.deletions:
            self._apply_cell_data(
                deletion['row'], deletion['col'],
                None, None
            )

    def _apply_cell_data(self, row, col, value, formula):
        """Apply value or formula to a cell."""
        self.model._evaluated_cache.pop((row, col), None)

        if formula:
            self.model._formulas[(row, col)] = formula
            self.model._data.pop((row, col), None)
        else:
            if value:
                self.model._data[(row, col)] = value
            else:
                self.model._data.pop((row, col), None)
            self.model._formulas.pop((row, col), None)

        index = self.model.index(row, col)
        self.model.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])


class SpreadsheetModel(QtCore.QAbstractTableModel):
    """Model for spreadsheet data with formula support and undo/redo."""

    # Signal emitted when status messages should be shown
    statusMessageChanged = QtCore.Signal(str, bool)  # message, is_error

    # Special marker for text values that should be detected in numeric columns
    TEXT_VALUE_MARKER = "__TEXT_VALUE__"

    # Excel-compatible format codes
    FORMAT_GENERAL = "General"
    FORMAT_NUMBER = "#,##0.00"
    FORMAT_NUMBER_NO_DECIMAL = "#,##0"
    FORMAT_CURRENCY_USD = "$#,##0.00"
    FORMAT_CURRENCY_EUR = "[$€]#,##0.00"
    FORMAT_CURRENCY_GBP = "[$£]#,##0.00"
    FORMAT_PERCENTAGE = "0.00%"
    FORMAT_PERCENTAGE_NO_DECIMAL = "0%"
    FORMAT_DATE_MDY = "mm/dd/yyyy"
    FORMAT_DATE_DMY = "dd/mm/yyyy"
    FORMAT_DATE_YMD = "yyyy-mm-dd"
    FORMAT_TIME = "hh:mm:ss"
    FORMAT_DATETIME = "yyyy-mm-dd hh:mm:ss"
    FORMAT_TEXT = "@"
    FORMAT_ACCOUNTING = '_($* #,##0.00_);_($* (#,##0.00);_($* "-"??_);_(@_)'

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
        self._formats = {}  # Dict of (row, col) -> Excel-compatible format string
        self._evaluated_cache = {}  # Dict of (row, col) -> evaluated result
        self.formula_evaluator = None

        # Column type configuration
        self._numeric_only_columns = set()  # Columns that only allow numeric values
        self._no_conversion_columns = set()  # Columns where data should not be converted

        # Undo/redo stacks
        self.undo_stack = []
        self.redo_stack = []
        self._in_undo_redo = False  # Flag to prevent creating undo commands during undo/redo

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

    def set_numeric_only_columns(self, columns):
        """Set which columns should only allow numeric values.

        Args:
            columns: List or set of column indices that only allow numbers
        """
        self._numeric_only_columns = set(columns)

    def set_no_conversion_columns(self, columns):
        """Set which columns should not have data type conversion.

        Args:
            columns: List or set of column indices where data should stay as-is
        """
        self._no_conversion_columns = set(columns)

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
            result_str = str(result) if result is not None else ""

            # Check if result contains text value marker
            if self.TEXT_VALUE_MARKER in result_str:
                if col in self._numeric_only_columns:
                    # Numeric column - show error for text values
                    formatted = "#TYPE! (text not allowed in this column)"
                    self._evaluated_cache[(row, col)] = formatted
                    return formatted
                else:
                    # Non-numeric column - extract and return the actual text value
                    # Format is "__TEXT_VALUE__:actual_value" or quoted version
                    import re
                    # Match pattern like "__TEXT_VALUE__:value" or "\"__TEXT_VALUE__:value\""
                    match = re.search(r'__TEXT_VALUE__:(.+?)(?:"|$)', result_str)
                    if match:
                        formatted = match.group(1)
                    else:
                        # Fallback: just remove the marker prefix
                        formatted = result_str.replace(f'"{self.TEXT_VALUE_MARKER}:', '').rstrip('"')
                    self._evaluated_cache[(row, col)] = formatted
                    return formatted

            # For numeric-only columns, validate that result is actually numeric
            if col in self._numeric_only_columns:
                try:
                    if result_str and not result_str.startswith('#'):
                        float(str(result).replace(',', '').replace('$', ''))
                except (ValueError, TypeError):
                    formatted = "#TYPE! (text not allowed in this column)"
                    self._evaluated_cache[(row, col)] = formatted
                    return formatted

            # For no-conversion columns, return as-is without formatting
            if col in self._no_conversion_columns:
                formatted = str(result) if result is not None else ""
                self._evaluated_cache[(row, col)] = formatted
                return formatted

            # Apply cell format if set, otherwise use auto-detection
            cell_format = self._formats.get((row, col))
            formatted = self._apply_format(result, cell_format)

            # Cache the result
            self._evaluated_cache[(row, col)] = formatted
            return formatted

        except Exception:
            return "#ERROR"

    def _apply_format(self, value, cell_format=None):
        """Apply Excel-compatible format to a value.

        Args:
            value: The value to format
            cell_format: Excel-compatible format string (or None for auto-detection)

        Returns:
            Formatted string
        """
        if value is None or value == "":
            return ""

        # If no format specified, auto-detect based on value type
        if not cell_format or cell_format == self.FORMAT_GENERAL:
            if isinstance(value, (int, float)):
                # Default number format with commas and 2 decimals
                return f"{value:,.2f}"
            return str(value)

        # Apply specific formats
        try:
            if cell_format == self.FORMAT_TEXT:
                return str(value)

            # Convert to number if needed
            if isinstance(value, str):
                try:
                    value = float(value.replace(',', '').replace('$', '').replace('%', ''))
                except ValueError:
                    return str(value)

            if cell_format == self.FORMAT_NUMBER:
                return f"{value:,.2f}"
            elif cell_format == self.FORMAT_NUMBER_NO_DECIMAL:
                return f"{value:,.0f}"
            elif cell_format == self.FORMAT_CURRENCY_USD:
                return f"${value:,.2f}"
            elif cell_format == self.FORMAT_CURRENCY_EUR:
                return f"€{value:,.2f}"
            elif cell_format == self.FORMAT_CURRENCY_GBP:
                return f"£{value:,.2f}"
            elif cell_format == self.FORMAT_PERCENTAGE:
                return f"{value * 100:.2f}%"
            elif cell_format == self.FORMAT_PERCENTAGE_NO_DECIMAL:
                return f"{value * 100:.0f}%"
            elif cell_format == self.FORMAT_ACCOUNTING:
                if value >= 0:
                    return f"$ {value:,.2f} "
                else:
                    return f"$ ({abs(value):,.2f})"
            elif cell_format.startswith("#") or cell_format.startswith("0"):
                # Generic number format - use default
                return f"{value:,.2f}"
            else:
                return f"{value:,.2f}"
        except (ValueError, TypeError):
            return str(value)

    def get_cell_format(self, row, col):
        """Get the format for a cell.

        Args:
            row: Row index
            col: Column index

        Returns:
            Excel-compatible format string or None
        """
        return self._formats.get((row, col))

    def set_cell_format(self, row, col, cell_format):
        """Set the format for a cell.

        Args:
            row: Row index
            col: Column index
            cell_format: Excel-compatible format string (or None to clear)
        """
        if cell_format:
            self._formats[(row, col)] = cell_format
        else:
            self._formats.pop((row, col), None)

        # Clear cache to force re-formatting
        self._evaluated_cache.pop((row, col), None)

        # Emit dataChanged to refresh display
        index = self.index(row, col)
        self.dataChanged.emit(index, index, [Qt.DisplayRole])

    def detect_format(self, value):
        """Auto-detect format based on value content.

        Args:
            value: The value to analyze

        Returns:
            Suggested Excel-compatible format string
        """
        if value is None or value == "":
            return self.FORMAT_GENERAL

        value_str = str(value).strip()

        # Check for percentage
        if value_str.endswith('%'):
            return self.FORMAT_PERCENTAGE

        # Check for currency symbols
        if value_str.startswith('$') or '$' in value_str:
            return self.FORMAT_CURRENCY_USD
        if value_str.startswith('€') or '€' in value_str:
            return self.FORMAT_CURRENCY_EUR
        if value_str.startswith('£') or '£' in value_str:
            return self.FORMAT_CURRENCY_GBP

        # Check if numeric
        try:
            cleaned = value_str.replace(',', '').replace('$', '').replace('€', '').replace('£', '')
            float(cleaned)
            return self.FORMAT_NUMBER
        except ValueError:
            pass

        return self.FORMAT_GENERAL

    def setData(self, index, value, role=Qt.EditRole):
        """Set data for the given index."""
        if not index.isValid():
            return False

        if role == Qt.EditRole:
            row, col = index.row(), index.column()

            # Get old values for undo
            old_value = self._data.get((row, col), None)
            old_formula = self._formulas.get((row, col), None)

            # Clear the cache for this cell
            self._evaluated_cache.pop((row, col), None)

            # Check if it's a formula (starts with =)
            value_str = str(value).strip() if value else ""
            new_formula = None
            new_value = None

            if value_str.startswith('='):
                # Store as formula
                new_formula = value_str
                self._formulas[(row, col)] = value_str
                self._data.pop((row, col), None)
            else:
                # Store as regular value
                new_value = value_str
                if value_str:
                    self._data[(row, col)] = value_str
                else:
                    self._data.pop((row, col), None)
                self._formulas.pop((row, col), None)

            # Create undo command (if not in undo/redo operation)
            if not self._in_undo_redo:
                # Only create command if there's an actual change
                if old_value != new_value or old_formula != new_formula:
                    command = SpreadsheetEditCommand(
                        self, row, col,
                        old_value, new_value,
                        old_formula, new_formula
                    )
                    self.undo_stack.append(command)
                    self.redo_stack.clear()  # Clear redo stack on new edit

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

    def undo(self):
        """Undo the last change."""
        if not self.undo_stack:
            return False

        command = self.undo_stack.pop()
        self._in_undo_redo = True
        try:
            command.undo()
        finally:
            self._in_undo_redo = False

        self.redo_stack.append(command)

        # Clear cache after undo
        self._clear_dependent_cache()

        self.statusMessageChanged.emit("Undone", False)
        return True

    def redo(self):
        """Redo the last undone change."""
        if not self.redo_stack:
            return False

        command = self.redo_stack.pop()
        self._in_undo_redo = True
        try:
            command.redo()
        finally:
            self._in_undo_redo = False

        self.undo_stack.append(command)

        # Clear cache after redo
        self._clear_dependent_cache()

        self.statusMessageChanged.emit("Redone", False)
        return True

    def clear_undo_history(self):
        """Clear the undo/redo history."""
        self.undo_stack.clear()
        self.redo_stack.clear()


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
        self.table_view.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)  # Multi-cell selection

        # Custom selection styling - blue background with white text
        self.table_view.setStyleSheet("""
            QTableView {
                selection-background-color: transparent;
                selection-color: white;
            }
            QTableView::item {
                color: white;
            }
            QTableView::item:selected {
                background-color: transparent;
                color: white;
            }
            QTableView::item:focus {
                color: white;
            }
            QTableView QLineEdit {
                color: white;
                background-color: #3d3d3d;
                selection-background-color: #4472C4;
                selection-color: white;
            }
        """)

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
        menu.addSeparator()

        # Format submenu
        format_menu = menu.addMenu("Format")

        # General format
        format_general = format_menu.addAction("General")
        format_menu.addSeparator()

        # Number formats
        number_menu = format_menu.addMenu("Number")
        format_number = number_menu.addAction("1,234.56  (#,##0.00)")
        format_number_no_dec = number_menu.addAction("1,235  (#,##0)")

        # Currency formats
        currency_menu = format_menu.addMenu("Currency")
        format_currency_usd = currency_menu.addAction("$1,234.56  ($#,##0.00)")
        format_currency_eur = currency_menu.addAction("€1,234.56  ([$€]#,##0.00)")
        format_currency_gbp = currency_menu.addAction("£1,234.56  ([$£]#,##0.00)")

        # Accounting format
        format_accounting = format_menu.addAction("Accounting")
        format_menu.addSeparator()

        # Percentage formats
        percentage_menu = format_menu.addMenu("Percentage")
        format_percentage = percentage_menu.addAction("12.34%  (0.00%)")
        format_percentage_no_dec = percentage_menu.addAction("12%  (0%)")
        format_menu.addSeparator()

        # Text format
        format_text = format_menu.addAction("Text  (@)")

        # Show current format with checkmark
        current_format = self.model.get_cell_format(index.row(), index.column())
        format_actions = {
            SpreadsheetModel.FORMAT_GENERAL: format_general,
            SpreadsheetModel.FORMAT_NUMBER: format_number,
            SpreadsheetModel.FORMAT_NUMBER_NO_DECIMAL: format_number_no_dec,
            SpreadsheetModel.FORMAT_CURRENCY_USD: format_currency_usd,
            SpreadsheetModel.FORMAT_CURRENCY_EUR: format_currency_eur,
            SpreadsheetModel.FORMAT_CURRENCY_GBP: format_currency_gbp,
            SpreadsheetModel.FORMAT_ACCOUNTING: format_accounting,
            SpreadsheetModel.FORMAT_PERCENTAGE: format_percentage,
            SpreadsheetModel.FORMAT_PERCENTAGE_NO_DECIMAL: format_percentage_no_dec,
            SpreadsheetModel.FORMAT_TEXT: format_text,
        }
        if current_format in format_actions:
            format_actions[current_format].setCheckable(True)
            format_actions[current_format].setChecked(True)

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
        # Format actions
        elif action == format_general:
            self._set_cell_format(index, SpreadsheetModel.FORMAT_GENERAL)
        elif action == format_number:
            self._set_cell_format(index, SpreadsheetModel.FORMAT_NUMBER)
        elif action == format_number_no_dec:
            self._set_cell_format(index, SpreadsheetModel.FORMAT_NUMBER_NO_DECIMAL)
        elif action == format_currency_usd:
            self._set_cell_format(index, SpreadsheetModel.FORMAT_CURRENCY_USD)
        elif action == format_currency_eur:
            self._set_cell_format(index, SpreadsheetModel.FORMAT_CURRENCY_EUR)
        elif action == format_currency_gbp:
            self._set_cell_format(index, SpreadsheetModel.FORMAT_CURRENCY_GBP)
        elif action == format_accounting:
            self._set_cell_format(index, SpreadsheetModel.FORMAT_ACCOUNTING)
        elif action == format_percentage:
            self._set_cell_format(index, SpreadsheetModel.FORMAT_PERCENTAGE)
        elif action == format_percentage_no_dec:
            self._set_cell_format(index, SpreadsheetModel.FORMAT_PERCENTAGE_NO_DECIMAL)
        elif action == format_text:
            self._set_cell_format(index, SpreadsheetModel.FORMAT_TEXT)

    def _set_cell_format(self, index, cell_format):
        """Set the format for a cell.

        Args:
            index: QModelIndex of the cell
            cell_format: Excel-compatible format string
        """
        self.model.set_cell_format(index.row(), index.column(), cell_format)
        logger.info(f"Set cell ({index.row()},{index.column()}) format to: {cell_format}")

    def _insert_row_above(self, row):
        """Insert a new row above the specified row."""
        self.model.beginInsertRows(QtCore.QModelIndex(), row, row)

        # Shift all data down
        self.model._rows += 1
        new_data = {}
        new_formulas = {}
        new_formats = {}

        for (r, c), value in self.model._data.items():
            if r >= row:
                new_data[(r + 1, c)] = value
            else:
                new_data[(r, c)] = value

        for (r, c), formula in self.model._formulas.items():
            # Update formula references to account for the inserted row
            updated_formula = self._update_formula_for_row_insertion(formula, row)
            if r >= row:
                new_formulas[(r + 1, c)] = updated_formula
            else:
                new_formulas[(r, c)] = updated_formula

        # Shift formats
        for (r, c), fmt in self.model._formats.items():
            if r >= row:
                new_formats[(r + 1, c)] = fmt
            else:
                new_formats[(r, c)] = fmt

        self.model._data = new_data
        self.model._formulas = new_formulas
        self.model._formats = new_formats
        self.model._evaluated_cache.clear()

        self.model.endInsertRows()

        # Emit dataChanged to trigger save to ShotGrid
        self.model.dataChanged.emit(
            self.model.index(0, 0),
            self.model.index(self.model.rowCount() - 1, self.model.columnCount() - 1),
            [QtCore.Qt.DisplayRole, QtCore.Qt.EditRole]
        )
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
        new_formats = {}

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

        # Shift formats
        for (r, c), fmt in self.model._formats.items():
            if r == row:
                continue  # Skip the deleted row
            elif r > row:
                new_formats[(r - 1, c)] = fmt
            else:
                new_formats[(r, c)] = fmt

        self.model._data = new_data
        self.model._formulas = new_formulas
        self.model._formats = new_formats
        self.model._evaluated_cache.clear()

        self.model.endRemoveRows()

        # Emit dataChanged to trigger save to ShotGrid
        self.model.dataChanged.emit(
            self.model.index(0, 0),
            self.model.index(self.model.rowCount() - 1, self.model.columnCount() - 1),
            [QtCore.Qt.DisplayRole, QtCore.Qt.EditRole]
        )
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
        new_formats = {}

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

        # Shift formats
        for (r, c), fmt in self.model._formats.items():
            if c == col:
                continue  # Skip the deleted column
            elif c > col:
                new_formats[(r, c - 1)] = fmt
            else:
                new_formats[(r, c)] = fmt

        self.model._data = new_data
        self.model._formulas = new_formulas
        self.model._formats = new_formats
        self.model._evaluated_cache.clear()

        self.model.endRemoveColumns()

        # Emit dataChanged to trigger save to ShotGrid
        self.model.dataChanged.emit(
            self.model.index(0, 0),
            self.model.index(self.model.rowCount() - 1, self.model.columnCount() - 1),
            [QtCore.Qt.DisplayRole, QtCore.Qt.EditRole]
        )
        logger.info(f"Deleted column {self.model._column_name(col)}")

    def _insert_column_left(self, col):
        """Insert a new column to the left of the specified column."""
        self.model.beginInsertColumns(QtCore.QModelIndex(), col, col)

        # Shift all data right
        self.model._cols += 1
        new_data = {}
        new_formulas = {}
        new_formats = {}

        for (r, c), value in self.model._data.items():
            if c >= col:
                new_data[(r, c + 1)] = value
            else:
                new_data[(r, c)] = value

        for (r, c), formula in self.model._formulas.items():
            # Update formula references to account for the inserted column
            updated_formula = self._update_formula_for_column_insertion(formula, col)
            if c >= col:
                new_formulas[(r, c + 1)] = updated_formula
            else:
                new_formulas[(r, c)] = updated_formula

        # Shift formats
        for (r, c), fmt in self.model._formats.items():
            if c >= col:
                new_formats[(r, c + 1)] = fmt
            else:
                new_formats[(r, c)] = fmt

        self.model._data = new_data
        self.model._formulas = new_formulas
        self.model._formats = new_formats
        self.model._evaluated_cache.clear()

        self.model.endInsertColumns()

        # Emit dataChanged to trigger save to ShotGrid
        self.model.dataChanged.emit(
            self.model.index(0, 0),
            self.model.index(self.model.rowCount() - 1, self.model.columnCount() - 1),
            [QtCore.Qt.DisplayRole, QtCore.Qt.EditRole]
        )
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

    def _update_formula_for_row_insertion(self, formula, inserted_row):
        """Update cell references in a formula after a row insertion.

        Args:
            formula: The formula string (e.g., "=SUM(A1:A10)")
            inserted_row: The row where a new row was inserted (0-based)

        Returns:
            Updated formula string with row references shifted down
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

            # If not absolute row reference and row >= inserted_row, increment
            if not row_abs and row_idx >= inserted_row:
                new_row_num = row_num + 1
                return f"{col_abs}{col_letter}{row_abs}{new_row_num}"

            return match.group(0)

        return re.sub(pattern, replace_ref, formula)

    def _update_formula_for_column_insertion(self, formula, inserted_col):
        """Update cell references in a formula after a column insertion.

        Args:
            formula: The formula string (e.g., "=SUM(A1:B10)")
            inserted_col: The column where a new column was inserted (0-based)

        Returns:
            Updated formula string with column references shifted right
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

            # If not absolute column reference and col >= inserted_col, shift right
            if not col_abs and col_idx >= inserted_col:
                new_col_letter = self.model._column_name(col_idx + 1)
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
        """Export all data as a dictionary including formats."""
        data = {}
        for row in range(self.model.rowCount()):
            for col in range(self.model.columnCount()):
                value = self.model._data.get((row, col))
                formula = self.model._formulas.get((row, col))
                cell_format = self.model._formats.get((row, col))
                if value or formula or cell_format:
                    cell_data = {
                        'value': value,
                        'formula': formula,
                    }
                    if cell_format:
                        cell_data['format'] = cell_format
                    data[(row, col)] = cell_data
        return data

    def load_data_from_dict(self, data):
        """Load data from a dictionary including formats."""
        self.model._data.clear()
        self.model._formulas.clear()
        self.model._formats.clear()
        self.model._evaluated_cache.clear()

        for (row, col), cell_data in data.items():
            if cell_data.get('formula'):
                self.model._formulas[(row, col)] = cell_data['formula']
            elif cell_data.get('value'):
                self.model._data[(row, col)] = cell_data['value']

            # Load format if present
            if cell_data.get('format'):
                self.model._formats[(row, col)] = cell_data['format']

        # Refresh the view
        self.model.layoutChanged.emit()
