"""
Table with Totals Bar Component
Wrapper that adds a frozen totals bar to an existing QTableWidget or QTableView.
"""

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt
import logging

try:
    from .logger import logger
except ImportError:
    logger = logging.getLogger("FFPackageManager")


class TableWithTotalsBar(QtWidgets.QWidget):
    """
    Wrapper that adds a frozen totals bar to an existing QTableWidget or QTableView.

    Usage:
        # Your existing table
        existing_table = QTableView()
        # ... configure table, add data, etc.

        # Wrap it to add totals bar
        table_with_totals = TableWithTotalsBar(existing_table)

        # Add wrapped version to your layout
        layout.addWidget(table_with_totals)

        # Calculate totals
        table_with_totals.calculate_totals()
    """

    def __init__(self, existing_table, parent=None, formula_evaluator=None, app_settings=None, bid_id=None):
        """
        Wrap an existing table and add totals bar.

        Args:
            existing_table: Your existing QTableWidget or QTableView (already configured)
            parent: Optional parent widget
            formula_evaluator: Optional FormulaEvaluator for evaluating formula cells in totals
            app_settings: Optional AppSettings for currency symbol
            bid_id: Optional bid ID for bid-specific currency settings
        """
        super().__init__(parent)

        # Store reference to existing table
        self.table = existing_table

        # Determine if it's a QTableWidget or QTableView
        self.is_table_widget = isinstance(existing_table, QtWidgets.QTableWidget)

        # Get column count
        if self.is_table_widget:
            self.cols = existing_table.columnCount()
        else:
            # For QTableView, get column count from model
            model = existing_table.model()
            self.cols = model.columnCount() if model else 0

        # Track which columns have highlighted styling
        self.blue_columns = set()

        # Custom highlight color (default blue, can be changed to purple)
        self.highlight_color = "#0078d4"

        # Formula evaluator for calculating totals from formula cells
        self.formula_evaluator = formula_evaluator

        # App settings for currency formatting
        self.app_settings = app_settings
        self.bid_id = bid_id

        # Layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Add existing table (don't recreate it!)
        layout.addWidget(self.table)

        # Create and add totals bar (QTableWidget for simplicity)
        self.totals_bar = QtWidgets.QTableWidget(1, self.cols)
        self._setup_totals_bar()
        layout.addWidget(self.totals_bar)

        # Set up synchronization
        self._setup_synchronization()
        self._sync_all_column_widths()  # Initial sync
        self._update_totals_alignment()

        logger.info(f"TableWithTotalsBar initialized with {self.cols} columns")

    @property
    def main_table(self):
        """Access the wrapped table."""
        return self.table

    def set_total(self, col, value):
        """
        Set a total value for a specific column.

        Args:
            col: Column index
            value: Total value to display (will be converted to string)
        """
        is_blue_column = col in self.blue_columns

        item = self.totals_bar.item(0, col)
        if item:
            item.setText(str(value))
        else:
            item = QtWidgets.QTableWidgetItem(str(value))
            item.setTextAlignment(Qt.AlignCenter)
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            self.totals_bar.setItem(0, col, item)

        # Apply styling based on whether it's a blue column
        # Always reapply styling to ensure blue columns are correctly styled
        if is_blue_column:
            item.setBackground(QtGui.QColor("#0078d4"))
            item.setForeground(QtGui.QColor("white"))
        else:
            item.setBackground(QtGui.QColor("#3a3a3a"))
            item.setForeground(QtGui.QColor("#ffffff"))

    def get_total(self, col):
        """
        Get total value for a column.

        Args:
            col: Column index

        Returns:
            str: Total value as string
        """
        item = self.totals_bar.item(0, col)
        return item.text() if item else ""

    def set_blue_columns(self, column_indices):
        """
        Mark specific columns to have highlighted background in totals bar.

        Args:
            column_indices: List of column indices that should be highlighted
        """
        self.blue_columns = set(column_indices)

        # Reapply styling to all existing cells to update highlighted columns
        for col in range(self.cols):
            item = self.totals_bar.item(0, col)
            if item:
                is_highlighted = col in self.blue_columns
                if is_highlighted:
                    item.setBackground(QtGui.QColor(self.highlight_color))
                    item.setForeground(QtGui.QColor("white"))
                else:
                    item.setBackground(QtGui.QColor("#3a3a3a"))  # Standard dark
                    item.setForeground(QtGui.QColor("#ffffff"))

    def set_highlight_color(self, color):
        """
        Set the highlight color for marked columns in the totals bar.

        Args:
            color: Color string (e.g., "#6b5b95" for purple)
        """
        self.highlight_color = color
        # Reapply styling to update color on highlighted columns
        self.set_blue_columns(self.blue_columns)

    def set_formula_evaluator(self, formula_evaluator):
        """
        Set the formula evaluator for calculating totals from formula cells.

        Args:
            formula_evaluator: FormulaEvaluator instance
        """
        self.formula_evaluator = formula_evaluator

    def set_app_settings(self, app_settings):
        """
        Set the app settings for currency formatting.

        Args:
            app_settings: AppSettings instance
        """
        self.app_settings = app_settings

    def set_bid_id(self, bid_id):
        """
        Set the bid ID for bid-specific currency settings.

        Args:
            bid_id: Bid ID
        """
        self.bid_id = bid_id

    def set_currency_symbol(self, symbol):
        """
        Set the currency symbol directly.

        Args:
            symbol: Currency symbol (e.g., "$", "€", "£")
        """
        self._currency_symbol = symbol

    def _format_currency(self, value):
        """
        Format a numeric value with currency symbol based on bid settings.

        Args:
            value: Numeric value to format

        Returns:
            str: Formatted currency string
        """
        # Use directly set currency symbol if available
        if hasattr(self, '_currency_symbol') and self._currency_symbol:
            currency_symbol = self._currency_symbol
        elif self.app_settings:
            currency_symbol = self.app_settings.get_currency() or "$"
        else:
            currency_symbol = "$"

        # Get position from local settings
        currency_position = "prepend"
        if self.app_settings and self.bid_id:
            currency_position = self.app_settings.get_bid_currency_position(self.bid_id)

        # Format based on position
        if currency_position == "append":
            return f"{value:,.2f}{currency_symbol}"
        else:
            return f"{currency_symbol}{value:,.2f}"

    def calculate_totals(self, columns=None, skip_first_col=True, number_format="{:,.0f}"):
        """
        Auto-calculate totals by summing numeric columns.

        Args:
            columns: List of column indices to calculate totals for. If None, calculate for all columns.
            skip_first_col: If True, skip column 0 (usually labels/identifiers)
            number_format: Format string for displaying numbers (default: comma-separated integers)
        """
        # Determine which columns to process
        if columns is not None:
            cols_to_process = columns
        else:
            start_col = 1 if skip_first_col else 0
            cols_to_process = range(start_col, self.cols)

        if self.is_table_widget:
            self._calculate_totals_widget(cols_to_process, number_format, skip_first_col)
        else:
            self._calculate_totals_view(cols_to_process, number_format, skip_first_col)

    def _calculate_totals_widget(self, cols_to_process, number_format, skip_first_col):
        """Calculate totals for QTableWidget."""
        for col in cols_to_process:
            total = 0
            count = 0

            for row in range(self.table.rowCount()):
                item = self.table.item(row, col)
                if item:
                    try:
                        # Remove commas and currency symbols before parsing
                        text = item.text().replace(',', '').replace('$', '').replace('€', '').strip()
                        value = float(text)
                        total += value
                        count += 1
                    except (ValueError, AttributeError):
                        pass

            if count > 0:
                self.set_total(col, number_format.format(total))

        # Set label in first column
        if skip_first_col:
            self.set_total(0, "TOTAL")

    def _calculate_totals_view(self, cols_to_process, number_format, skip_first_col):
        """Calculate totals for QTableView with model."""
        model = self.table.model()
        if not model:
            return

        for col in cols_to_process:
            total = 0
            count = 0

            for row in range(model.rowCount()):
                index = model.index(row, col)
                data = model.data(index, Qt.DisplayRole)

                if data is not None:
                    try:
                        # Handle various data types
                        if isinstance(data, (int, float)):
                            value = float(data)
                        elif isinstance(data, str):
                            text = data.strip()
                            # Handle formulas that start with '=' using formula evaluator
                            if text.startswith('='):
                                if self.formula_evaluator:
                                    try:
                                        # Evaluate the formula to get numeric result
                                        result = self.formula_evaluator.evaluate(text, row, col)
                                        if isinstance(result, (int, float)):
                                            value = float(result)
                                        else:
                                            # Skip non-numeric formula results
                                            continue
                                    except Exception:
                                        continue
                                else:
                                    # No formula evaluator, skip formulas
                                    continue
                            else:
                                # Remove commas and currency symbols before parsing
                                text = text.replace(',', '').replace('$', '').replace('€', '').replace('£', '').replace('¥', '').replace('₹', '').replace('₽', '').strip()
                                value = float(text)
                        else:
                            continue

                        total += value
                        count += 1
                    except (ValueError, AttributeError, TypeError):
                        pass

            if count > 0:
                # Format with currency symbol if this is a blue column (price column)
                if col in self.blue_columns:
                    formatted_total = self._format_currency(total)
                else:
                    formatted_total = number_format.format(total)
                self.set_total(col, formatted_total)

        # Set label in first column
        if skip_first_col:
            self.set_total(0, "TOTAL")

    def clear_totals(self):
        """Clear all totals."""
        for col in range(self.cols):
            self.set_total(col, "")

    def _setup_totals_bar(self):
        """Configure the totals bar appearance."""
        # Configure vertical header to match main table
        v_header = self.totals_bar.verticalHeader()
        v_header.setVisible(True)  # Keep visible to maintain spacing
        v_header.setDefaultSectionSize(self.table.verticalHeader().defaultSectionSize())

        # Match the width of the main table's vertical header
        main_v_header_width = self.table.verticalHeader().width()
        v_header.setFixedWidth(main_v_header_width)
        v_header.setMinimumWidth(main_v_header_width)
        v_header.setMaximumWidth(main_v_header_width)

        # Configure horizontal header to match main table behavior
        h_header = self.totals_bar.horizontalHeader()
        h_header.setVisible(False)

        # Match the main table's header resize mode
        main_h_header = self.table.horizontalHeader()
        if main_h_header:
            h_header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
            # Always disable stretch on last section to prevent disappearing cells during resize
            h_header.setStretchLastSection(False)

        # Set fixed height
        row_height = self.totals_bar.verticalHeader().defaultSectionSize()
        self.totals_bar.setFixedHeight(row_height + 4)

        # No scrollbars
        self.totals_bar.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.totals_bar.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Disable gridlines for continuous bar appearance
        self.totals_bar.setShowGrid(False)

        # Styling - default dark theme
        self.totals_bar.setStyleSheet("""
            QTableWidget {
                background-color: #3a3a3a;
                border-top: 2px solid #505050;
                font-weight: bold;
            }
            QHeaderView::section {
                background-color: #3a3a3a;
                color: #cccccc;
                border: none;
            }
        """)

        # Disable editing
        self.totals_bar.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        # Disable cell selection
        self.totals_bar.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.totals_bar.setFocusPolicy(Qt.NoFocus)

        # Initialize cells with default dark theme background
        for col in range(self.cols):
            item = QtWidgets.QTableWidgetItem("")
            item.setTextAlignment(Qt.AlignCenter)
            item.setBackground(QtGui.QColor("#3a3a3a"))
            item.setForeground(QtGui.QColor("#ffffff"))
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            self.totals_bar.setItem(0, col, item)

    def _setup_synchronization(self):
        """Set up sync between existing table and totals bar."""
        # Horizontal scroll sync
        h_scrollbar = self.table.horizontalScrollBar()
        if h_scrollbar:
            h_scrollbar.valueChanged.connect(self._sync_horizontal_scroll)

        # Column width sync
        h_header = self.table.horizontalHeader()
        if h_header:
            h_header.sectionResized.connect(self._sync_column_width)

        # Vertical header width sync
        v_header = self.table.verticalHeader()
        if v_header:
            v_header.sectionResized.connect(self._update_totals_alignment)

        # Alignment updates on scroll changes
        v_scrollbar = self.table.verticalScrollBar()
        if v_scrollbar:
            v_scrollbar.rangeChanged.connect(self._update_totals_alignment)
            v_scrollbar.valueChanged.connect(self._update_totals_alignment)

    def _sync_horizontal_scroll(self, value):
        """Sync horizontal scrolling."""
        self.totals_bar.blockSignals(True)
        self.totals_bar.horizontalScrollBar().setValue(value)
        self.totals_bar.blockSignals(False)

    def _sync_column_width(self, col_index, old_width, new_width):
        """Sync column width when user resizes.

        When any column is resized, we sync ALL columns to ensure perfect alignment.
        This prevents index offset issues that can occur when resizing affects multiple columns.
        """
        # Sync all column widths instead of just the changed one
        # This ensures the totals bar perfectly mirrors the main table's column structure
        self._sync_all_column_widths()

        self._update_totals_alignment()

        # Force immediate visual update
        self.totals_bar.viewport().update()

    def _sync_all_column_widths(self):
        """Initial sync of all column widths."""
        totals_h_header = self.totals_bar.horizontalHeader()

        if self.is_table_widget:
            for col in range(self.cols):
                width = self.table.columnWidth(col)
                if totals_h_header:
                    totals_h_header.resizeSection(col, width)
                else:
                    self.totals_bar.setColumnWidth(col, width)
        else:
            # For QTableView, get widths from the horizontal header
            header = self.table.horizontalHeader()
            if header:
                for col in range(self.cols):
                    width = header.sectionSize(col)
                    if totals_h_header:
                        totals_h_header.resizeSection(col, width)
                    else:
                        self.totals_bar.setColumnWidth(col, width)

    def _update_totals_alignment(self):
        """
        CRITICAL: Keep totals columns aligned with table columns.
        Sync vertical header width to ensure proper alignment.
        """
        # Update the totals bar's vertical header width to match the main table
        main_v_header_width = self.table.verticalHeader().width()
        totals_v_header = self.totals_bar.verticalHeader()

        if totals_v_header.width() != main_v_header_width:
            totals_v_header.setFixedWidth(main_v_header_width)
            totals_v_header.setMinimumWidth(main_v_header_width)
            totals_v_header.setMaximumWidth(main_v_header_width)

    def refresh_totals(self):
        """Refresh totals - recalculate based on current table data."""
        self.calculate_totals()

    def set_totals_visible(self, visible):
        """
        Show or hide the totals bar.

        Args:
            visible: True to show, False to hide
        """
        self.totals_bar.setVisible(visible)

    def update_column_count(self):
        """
        Update the totals bar to match the current column count of the main table.

        This should be called after adding or removing columns from the model.
        """
        # Get the current column count from the main table
        if self.is_table_widget:
            new_cols = self.table.columnCount()
        else:
            model = self.table.model()
            new_cols = model.columnCount() if model else 0

        if new_cols == self.cols:
            # No change in column count
            return

        old_cols = self.cols
        self.cols = new_cols

        # Update the totals bar column count
        self.totals_bar.setColumnCount(new_cols)

        # Initialize any new cells with default styling
        for col in range(old_cols, new_cols):
            item = QtWidgets.QTableWidgetItem("")
            item.setTextAlignment(Qt.AlignCenter)
            item.setBackground(QtGui.QColor("#3a3a3a"))
            item.setForeground(QtGui.QColor("#ffffff"))
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            self.totals_bar.setItem(0, col, item)

        # Re-sync all column widths to ensure alignment
        self._sync_all_column_widths()

        logger.info(f"Updated totals bar column count from {old_cols} to {new_cols}")

    def collapse_table(self):
        """
        Collapse the view to show only the totals bar, hiding the main table.

        This is useful for compact views where only totals are needed.
        """
        self.table.setVisible(False)

    def expand_table(self):
        """
        Expand the view to show both the main table and totals bar.
        """
        self.table.setVisible(True)

    def is_table_collapsed(self):
        """
        Check if the main table is currently collapsed.

        Returns:
            bool: True if table is hidden, False if visible
        """
        return not self.table.isVisible()
