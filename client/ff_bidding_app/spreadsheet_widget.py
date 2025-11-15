"""
Spreadsheet Widget
A full-featured spreadsheet widget inspired by Google Sheets with Excel formula support.
"""

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt
import string

try:
    from .logger import logger
    from .formula_evaluator import FormulaEvaluator
except ImportError:
    import logging
    logger = logging.getLogger("FFPackageManager")
    from formula_evaluator import FormulaEvaluator


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

        elif role == Qt.BackgroundRole:
            # Formulas have a light blue background
            if (row, col) in self._formulas:
                return QtGui.QColor("#e8f4f8")

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

    def get_cell_value(self, row, col):
        """Get the raw value of a cell (not the formula)."""
        if (row, col) in self._formulas:
            # Evaluate the formula
            formula = self._formulas[(row, col)]
            return self._get_evaluated_value(row, col, formula)
        else:
            return self._data.get((row, col), "")

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

    def __init__(self, rows=100, cols=26, app_settings=None, parent=None):
        """Initialize the spreadsheet widget.

        Args:
            rows: Number of rows
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

        # Create table view FIRST (before toolbar)
        self.table_view = QtWidgets.QTableView()
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectItems)
        self.table_view.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

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
