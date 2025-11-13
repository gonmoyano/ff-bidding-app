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

    def __init__(self, existing_table, parent=None):
        """
        Wrap an existing table and add totals bar.

        Args:
            existing_table: Your existing QTableWidget or QTableView (already configured)
            parent: Optional parent widget
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

        # Track which columns have blue styling
        self.blue_columns = set()

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
        item = self.totals_bar.item(0, col)
        is_blue_column = col in self.blue_columns

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
        Mark specific columns to have blue background in totals bar.

        Args:
            column_indices: List of column indices that should be blue
        """
        self.blue_columns = set(column_indices)

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
                            # Remove commas, currency symbols, and formulas
                            text = data.replace(',', '').replace('$', '').replace('€', '').strip()
                            # Skip formulas that start with '='
                            if text.startswith('='):
                                continue
                            value = float(text)
                        else:
                            continue

                        total += value
                        count += 1
                    except (ValueError, AttributeError, TypeError):
                        pass

            if count > 0:
                self.set_total(col, number_format.format(total))

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
            h_header.setStretchLastSection(main_h_header.stretchLastSection())

        # Set fixed height
        row_height = self.totals_bar.verticalHeader().defaultSectionSize()
        self.totals_bar.setFixedHeight(row_height + 4)

        # No scrollbars
        self.totals_bar.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.totals_bar.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Disable gridlines for continuous bar appearance
        self.totals_bar.setShowGrid(False)

        # Styling - Dark theme matching VFX table
        self.totals_bar.setStyleSheet("""
            QTableWidget {
                background-color: #3a3a3a;
                border-top: 2px solid #555555;
                font-weight: bold;
            }
        """)

        # Disable editing
        self.totals_bar.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        # Initialize cells with default dark gray background
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
