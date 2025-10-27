"""
Bid Selector Widget
Reusable widget component for selecting and managing Bids (CustomEntity06).
"""

from PySide6 import QtWidgets, QtCore, QtGui

try:
    from .logger import logger
except ImportError:
    import logging
    logger = logging.getLogger("FFPackageManager")


class CollapsibleGroupBox(QtWidgets.QWidget):
    """A collapsible group box that hides/shows content without disabling it."""

    def __init__(self, title="", parent=None):
        """Initialize the collapsible group box.

        Args:
            title: The title for the group
            parent: Parent widget
        """
        super().__init__(parent)
        self.is_collapsed = False

        # Main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Toggle button with arrow
        self.toggle_button = QtWidgets.QPushButton()
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(True)
        self.toggle_button.setStyleSheet("""
            QPushButton {
                text-align: left;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 3px 5px;
                background-color: #2b2b2b;
                color: #e0e0e0;
                font-weight: bold;
                font-size: 11px;
            }
        """)
        self.toggle_button.clicked.connect(self._on_toggle)
        self._update_button_text(title)
        main_layout.addWidget(self.toggle_button)

        # Content frame
        self.content_frame = QtWidgets.QFrame()
        self.content_frame.setObjectName("collapsibleContent")
        self.content_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.content_frame.setStyleSheet("""
            QFrame#collapsibleContent {
                border: 1px solid #555555;
                border-radius: 4px;
            }
        """)
        self.content_layout = QtWidgets.QVBoxLayout(self.content_frame)
        main_layout.addWidget(self.content_frame)

    def _update_button_text(self, title):
        """Update button text with arrow indicator."""
        arrow = "▼" if not self.is_collapsed else "▶"
        self.toggle_button.setText(f"{arrow} {title}")

    def _on_toggle(self):
        """Toggle the visibility of the content."""
        self.is_collapsed = not self.is_collapsed
        self.content_frame.setVisible(not self.is_collapsed)
        self._update_button_text(self.toggle_button.text().split(" ", 1)[1])

    def setTitle(self, title):
        """Set the title of the group box."""
        self._update_button_text(title)

    def addWidget(self, widget):
        """Add a widget to the content area."""
        self.content_layout.addWidget(widget)

    def addLayout(self, layout):
        """Add a layout to the content area."""
        self.content_layout.addLayout(layout)


class AddBidDialog(QtWidgets.QDialog):
    """Dialog for adding a new Bid."""

    def __init__(self, parent=None):
        """Initialize the dialog."""
        super().__init__(parent)
        self.setWindowTitle("Add New Bid")
        self.setModal(True)
        self.setMinimumWidth(400)

        self._build_ui()

    def _build_ui(self):
        """Build the dialog UI."""
        layout = QtWidgets.QVBoxLayout(self)

        # Bid name field
        name_layout = QtWidgets.QHBoxLayout()
        name_label = QtWidgets.QLabel("Bid Name:")
        name_layout.addWidget(name_label)

        self.name_field = QtWidgets.QLineEdit()
        self.name_field.setPlaceholderText("Enter bid name...")
        name_layout.addWidget(self.name_field, stretch=1)

        layout.addLayout(name_layout)

        # Bid type selection
        type_layout = QtWidgets.QHBoxLayout()
        type_label = QtWidgets.QLabel("Bid Type:")
        type_layout.addWidget(type_label)

        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.addItem("Early Bid")
        self.type_combo.addItem("Turnover Bid")
        type_layout.addWidget(self.type_combo, stretch=1)

        layout.addLayout(type_layout)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()

        self.ok_button = QtWidgets.QPushButton("Create")
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setDefault(True)
        button_layout.addWidget(self.ok_button)

        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def get_bid_name(self):
        """Get the bid name from the dialog."""
        return self.name_field.text().strip()

    def get_bid_type(self):
        """Get the selected bid type."""
        return self.type_combo.currentText()


class RenameBidDialog(QtWidgets.QDialog):
    """Dialog for renaming a Bid."""

    def __init__(self, current_name, parent=None):
        """Initialize the dialog."""
        super().__init__(parent)
        self.current_name = current_name
        self.setWindowTitle("Rename Bid")
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
        self.name_field.setPlaceholderText("Enter new bid name...")
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
        """Get the new name from the dialog."""
        return self.name_field.text().strip()


class ImportBidDialog(QtWidgets.QDialog):
    """Dialog for importing bid data from an Excel file with tabs for different data types."""

    def __init__(self, parent=None):
        """Initialize the dialog."""
        super().__init__(parent)
        self.setWindowTitle("Import Bid Data")
        self.setModal(True)
        self.setMinimumSize(900, 700)

        # Data storage
        self.excel_file_path = None
        self.sheet_names = []

        # Tab configuration: tab_name -> (sheet_match_keywords, data)
        self.tab_config = {
            "VFX Breakdown": (["vfx", "breakdown", "break"], None),
            "Assets": (["asset", "assets"], None),
            "Scene": (["scene", "scenes"], None),
            "Rates": (["rate", "rates", "pricing", "price"], None)
        }

        # UI components for each tab
        self.tab_widgets = {}  # tab_name -> {"combo": combo, "table": table}

        self._build_ui()

    def _build_ui(self):
        """Build the dialog UI."""
        layout = QtWidgets.QVBoxLayout(self)

        # Drag and drop area
        self.drop_area = DragDropArea()
        self.drop_area.fileDropped.connect(self._on_file_dropped)
        layout.addWidget(self.drop_area)

        # Tab widget (initially hidden)
        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.hide()

        # Create tabs
        for tab_name in self.tab_config.keys():
            tab = self._create_tab(tab_name)
            self.tab_widget.addTab(tab, tab_name)

        layout.addWidget(self.tab_widget, stretch=1)

        # Status label
        self.status_label = QtWidgets.QLabel("")
        self.status_label.setStyleSheet("color: #a0a0a0; padding: 5px;")
        layout.addWidget(self.status_label)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()

        self.import_button = QtWidgets.QPushButton("Import")
        self.import_button.setMinimumHeight(40)
        self.import_button.setMinimumWidth(120)
        self.import_button.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                font-weight: bold;
            }
        """)
        self.import_button.clicked.connect(self.accept)
        self.import_button.setEnabled(False)
        button_layout.addWidget(self.import_button)

        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def _create_tab(self, tab_name):
        """Create a tab with sheet selector and table."""
        tab_widget = QtWidgets.QWidget()
        tab_layout = QtWidgets.QVBoxLayout(tab_widget)

        # Sheet selection row
        sheet_layout = QtWidgets.QHBoxLayout()
        sheet_label = QtWidgets.QLabel("Select Sheet:")
        sheet_layout.addWidget(sheet_label)

        sheet_combo = QtWidgets.QComboBox()
        sheet_combo.currentIndexChanged.connect(lambda idx, tn=tab_name: self._on_sheet_changed(tn, idx))
        sheet_layout.addWidget(sheet_combo, stretch=1)

        # Row selection buttons
        select_all_btn = QtWidgets.QPushButton("Select All")
        select_all_btn.clicked.connect(lambda checked, tn=tab_name: self._select_all_rows(tn, True))
        sheet_layout.addWidget(select_all_btn)

        deselect_all_btn = QtWidgets.QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(lambda checked, tn=tab_name: self._select_all_rows(tn, False))
        sheet_layout.addWidget(deselect_all_btn)

        tab_layout.addLayout(sheet_layout)

        # Table for displaying data
        table = QtWidgets.QTableWidget()
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectItems)
        table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        table.setAlternatingRowColors(False)
        table.setWordWrap(True)
        table.horizontalHeader().setStretchLastSection(False)
        table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        table.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        table.itemChanged.connect(lambda item, tn=tab_name: self._on_table_item_changed(tn, item))
        tab_layout.addWidget(table, stretch=1)

        # Store references
        self.tab_widgets[tab_name] = {
            "combo": sheet_combo,
            "table": table
        }

        return tab_widget

    def _find_best_match_sheet(self, tab_name):
        """Find the best matching sheet name for a tab using fuzzy matching.

        Args:
            tab_name: The tab name to match against

        Returns:
            str: Best matching sheet name or None
        """
        if not self.sheet_names:
            return None

        keywords, _ = self.tab_config[tab_name]

        # Try exact match first (case insensitive)
        tab_lower = tab_name.lower()
        for sheet in self.sheet_names:
            sheet_lower = sheet.lower()
            if sheet_lower == tab_lower:
                return sheet

        # Try keyword matching
        best_match = None
        best_score = 0

        for sheet in self.sheet_names:
            sheet_lower = sheet.lower()
            score = 0

            # Check if any keyword is in the sheet name
            for keyword in keywords:
                if keyword in sheet_lower:
                    score += len(keyword)

            # Check if sheet name is in tab name
            if sheet_lower in tab_lower or tab_lower in sheet_lower:
                score += 10

            if score > best_score:
                best_score = score
                best_match = sheet

        return best_match if best_score > 0 else None

    def _on_file_dropped(self, file_path):
        """Handle file drop event."""
        if not file_path.lower().endswith(('.xlsx', '.xls')):
            self._set_status("Error: Please drop an Excel file (.xlsx or .xls)", is_error=True)
            return

        self.excel_file_path = file_path
        self._set_status(f"Loading file: {file_path}")

        try:
            # Try to import pandas
            import pandas as pd

            # Read Excel file to get sheet names
            excel_file = pd.ExcelFile(file_path)
            self.sheet_names = excel_file.sheet_names

            # Populate all sheet combos and auto-select best matches
            for tab_name, widgets in self.tab_widgets.items():
                combo = widgets["combo"]
                combo.blockSignals(True)
                combo.clear()
                combo.addItem("-- Select Sheet --", None)
                for sheet in self.sheet_names:
                    combo.addItem(sheet)
                combo.blockSignals(False)

                # Auto-select best match
                best_match = self._find_best_match_sheet(tab_name)
                if best_match:
                    index = combo.findText(best_match)
                    if index >= 0:
                        combo.setCurrentIndex(index)
                        # Load the sheet
                        self._load_sheet_for_tab(tab_name, best_match)

            # Show tabs and hide drop area
            self.tab_widget.show()
            self.drop_area.hide()
            self.import_button.setEnabled(True)

            self._set_status(f"Loaded: {file_path} ({len(self.sheet_names)} sheets)")

        except ImportError:
            self._set_status("Error: pandas library not installed. Please install with: pip install pandas openpyxl", is_error=True)
        except Exception as e:
            self._set_status(f"Error loading file: {str(e)}", is_error=True)
            logger.error(f"Error loading Excel file: {e}", exc_info=True)

    def _on_sheet_changed(self, tab_name, index):
        """Handle sheet selection change for a specific tab."""
        widgets = self.tab_widgets.get(tab_name)
        if not widgets:
            return

        combo = widgets["combo"]
        sheet_name = combo.currentText()

        if sheet_name and sheet_name != "-- Select Sheet --":
            self._load_sheet_for_tab(tab_name, sheet_name)

    def _load_sheet_for_tab(self, tab_name, sheet_name):
        """Load and display a specific sheet in a specific tab."""
        try:
            import pandas as pd

            # Read the specific sheet
            df = pd.read_excel(self.excel_file_path, sheet_name=sheet_name)

            # Store data
            keywords, _ = self.tab_config[tab_name]
            self.tab_config[tab_name] = (keywords, df)

            # Display in table
            widgets = self.tab_widgets[tab_name]
            self._populate_table(widgets["table"], df)

            logger.info(f"Loaded sheet '{sheet_name}' for tab '{tab_name}': {len(df)} rows, {len(df.columns)} columns")

        except Exception as e:
            self._set_status(f"Error loading sheet: {str(e)}", is_error=True)
            logger.error(f"Error loading sheet {sheet_name} for tab {tab_name}: {e}", exc_info=True)

    def _populate_table(self, table, df):
        """Populate a table widget with dataframe data, with checkbox column for selection."""
        import pandas as pd

        # Block signals while populating to avoid triggering itemChanged
        table.blockSignals(True)

        # Set dimensions - add 1 column for checkbox
        table.setRowCount(len(df))
        table.setColumnCount(len(df.columns) + 1)

        # Set headers - checkbox column first
        headers = ["Import"] + [str(col) for col in df.columns]
        table.setHorizontalHeaderLabels(headers)

        # Populate data
        for i in range(len(df)):
            # Add checkbox in first column
            checkbox_item = QtWidgets.QTableWidgetItem()
            checkbox_item.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            checkbox_item.setCheckState(QtCore.Qt.Checked)  # Checked by default
            table.setItem(i, 0, checkbox_item)

            # Add data in remaining columns
            for j in range(len(df.columns)):
                value = df.iloc[i, j]
                # Handle None/NaN values
                if pd.isna(value):
                    value = ""
                else:
                    value = str(value)

                item = QtWidgets.QTableWidgetItem(value)
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)  # Make read-only
                table.setItem(i, j + 1, item)

        # Resize columns to content
        table.resizeColumnsToContents()
        # Make checkbox column narrower
        table.setColumnWidth(0, 60)

        # Unblock signals
        table.blockSignals(False)

    def _select_all_rows(self, tab_name, select):
        """Select or deselect all rows in a tab's table.

        Args:
            tab_name: Name of the tab
            select: True to select all, False to deselect all
        """
        widgets = self.tab_widgets.get(tab_name)
        if not widgets:
            return

        table = widgets["table"]
        table.blockSignals(True)

        check_state = QtCore.Qt.Checked if select else QtCore.Qt.Unchecked

        for row in range(table.rowCount()):
            checkbox_item = table.item(row, 0)
            if checkbox_item:
                checkbox_item.setCheckState(check_state)
                self._update_row_style(table, row, select)

        table.blockSignals(False)

    def _on_table_item_changed(self, tab_name, item):
        """Handle table item changes (checkbox state changes).

        Args:
            tab_name: Name of the tab
            item: The changed item
        """
        if item.column() != 0:  # Only handle checkbox column
            return

        widgets = self.tab_widgets.get(tab_name)
        if not widgets:
            return

        table = widgets["table"]
        row = item.row()
        is_checked = item.checkState() == QtCore.Qt.Checked

        self._update_row_style(table, row, is_checked)

    def _update_row_style(self, table, row, is_enabled):
        """Update the visual style of a row based on its enabled state.

        Args:
            table: The table widget
            row: Row index
            is_enabled: True if row is enabled, False if disabled
        """
        # Set color and font for all cells in the row
        for col in range(table.columnCount()):
            item = table.item(row, col)
            if item:
                if is_enabled:
                    # Default styling
                    item.setForeground(QtGui.QColor("#e0e0e0"))
                    font = item.font()
                    font.setStrikeOut(False)
                    item.setFont(font)
                else:
                    # Disabled styling - gray and strikethrough
                    item.setForeground(QtGui.QColor("#606060"))
                    font = item.font()
                    font.setStrikeOut(True)
                    item.setFont(font)

    def _set_status(self, message, is_error=False):
        """Set status message."""
        color = "#ff8080" if is_error else "#a0a0a0"
        self.status_label.setStyleSheet(f"color: {color}; padding: 5px;")
        self.status_label.setText(message)

    def get_imported_data(self):
        """Get the imported data from all tabs, filtered by selected rows.

        Returns:
            dict: Dictionary mapping tab names to DataFrames (only selected rows)
        """
        import pandas as pd

        result = {}
        for tab_name, (_, data) in self.tab_config.items():
            if data is None:
                continue

            # Get the table for this tab
            widgets = self.tab_widgets.get(tab_name)
            if not widgets:
                continue

            table = widgets["table"]

            # Find which rows are checked
            selected_indices = []
            for row in range(table.rowCount()):
                checkbox_item = table.item(row, 0)
                if checkbox_item and checkbox_item.checkState() == QtCore.Qt.Checked:
                    selected_indices.append(row)

            # Filter the DataFrame to only include selected rows
            if selected_indices:
                filtered_df = data.iloc[selected_indices].reset_index(drop=True)
                result[tab_name] = filtered_df
                logger.info(f"Tab '{tab_name}': {len(selected_indices)} of {len(data)} rows selected for import")

        return result


class DragDropArea(QtWidgets.QLabel):
    """A widget that accepts drag and drop of files and can be clicked to open a file dialog."""

    fileDropped = QtCore.Signal(str)  # Emits file path

    def __init__(self, parent=None):
        """Initialize the drag drop area."""
        super().__init__(parent)

        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setText("Drag and drop an Excel file here\n\nor click to browse")
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #555555;
                border-radius: 8px;
                padding: 40px;
                background-color: #2b2b2b;
                color: #a0a0a0;
                font-size: 14px;
            }
            QLabel:hover {
                border-color: #777777;
                background-color: #333333;
                cursor: pointer;
            }
        """)

        # Enable drag and drop
        self.setAcceptDrops(True)
        self.setMinimumHeight(150)

        # Make it behave like a button
        self.setCursor(QtCore.Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        """Handle mouse click to open file dialog."""
        if event.button() == QtCore.Qt.LeftButton:
            file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self,
                "Select Excel File",
                "",
                "Excel Files (*.xlsx *.xls);;All Files (*)"
            )
            if file_path:
                self.fileDropped.emit(file_path)

    def dragEnterEvent(self, event):
        """Handle drag enter event."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("""
                QLabel {
                    border: 2px dashed #4a9eff;
                    border-radius: 8px;
                    padding: 40px;
                    background-color: #353535;
                    color: #4a9eff;
                    font-size: 14px;
                }
            """)

    def dragLeaveEvent(self, event):
        """Handle drag leave event."""
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #555555;
                border-radius: 8px;
                padding: 40px;
                background-color: #2b2b2b;
                color: #a0a0a0;
                font-size: 14px;
            }
        """)

    def dropEvent(self, event):
        """Handle drop event."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            urls = event.mimeData().urls()
            if urls:
                file_path = urls[0].toLocalFile()
                self.fileDropped.emit(file_path)

        # Reset style
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #555555;
                border-radius: 8px;
                padding: 40px;
                background-color: #2b2b2b;
                color: #a0a0a0;
                font-size: 14px;
            }
            QLabel:hover {
                border-color: #777777;
                background-color: #333333;
                cursor: pointer;
            }
        """)


class BidSelectorWidget(QtWidgets.QWidget):
    """
    Reusable widget for selecting and managing Bids.
    Displays a selector bar with dropdown and action buttons.
    """

    # Signals
    bidChanged = QtCore.Signal(object)  # Emits selected bid data (dict or None)
    statusMessageChanged = QtCore.Signal(str, bool)  # message, is_error

    def __init__(self, sg_session, parent=None):
        """Initialize the Bid selector widget.

        Args:
            sg_session: ShotGrid session for API access
            parent: Parent widget
        """
        super().__init__(parent)
        self.sg_session = sg_session
        self.parent_app = parent

        # Current state
        self.current_rfq = None
        self.current_project_id = None

        # UI widgets
        self.bid_combo = None
        self.set_current_btn = None
        self.add_btn = None
        self.remove_btn = None
        self.rename_btn = None
        self.refresh_btn = None
        self.import_btn = None
        self.status_label = None

        self._build_ui()

    def _build_ui(self):
        """Build the bid selector UI."""
        # Main collapsible group
        group = CollapsibleGroupBox("Bids")

        # Selector row
        selector_row = QtWidgets.QHBoxLayout()
        selector_label = QtWidgets.QLabel("Select Bid:")
        selector_row.addWidget(selector_label)

        self.bid_combo = QtWidgets.QComboBox()
        self.bid_combo.setMinimumWidth(250)
        self.bid_combo.currentIndexChanged.connect(self._on_bid_changed)
        selector_row.addWidget(self.bid_combo, stretch=1)

        self.set_current_btn = QtWidgets.QPushButton("Set as Current")
        self.set_current_btn.setEnabled(False)
        self.set_current_btn.clicked.connect(self._on_set_current_bid)
        self.set_current_btn.setToolTip("Set this Bid as the current one for the selected RFQ")
        selector_row.addWidget(self.set_current_btn)

        self.add_btn = QtWidgets.QPushButton("Add")
        self.add_btn.clicked.connect(self._on_add_bid)
        self.add_btn.setToolTip("Create a new Bid")
        selector_row.addWidget(self.add_btn)

        self.remove_btn = QtWidgets.QPushButton("Remove")
        self.remove_btn.clicked.connect(self._on_remove_bid)
        self.remove_btn.setToolTip("Delete the selected Bid")
        selector_row.addWidget(self.remove_btn)

        self.rename_btn = QtWidgets.QPushButton("Rename")
        self.rename_btn.clicked.connect(self._on_rename_bid)
        self.rename_btn.setToolTip("Rename the selected Bid")
        selector_row.addWidget(self.rename_btn)

        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._on_refresh_bids)
        self.refresh_btn.setToolTip("Refresh the Bid list")
        selector_row.addWidget(self.refresh_btn)

        self.import_btn = QtWidgets.QPushButton("Import")
        self.import_btn.clicked.connect(self._on_import_bid)
        self.import_btn.setToolTip("Import bid data from an Excel file")
        selector_row.addWidget(self.import_btn)

        group.addLayout(selector_row)

        # Status label
        self.status_label = QtWidgets.QLabel("Select an RFQ to view Bids.")
        self.status_label.setStyleSheet("color: #a0a0a0; padding: 2px 0;")
        group.addWidget(self.status_label)

        # Add group to main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(group)

    def populate_bids(self, rfq=None, project_id=None, auto_select=True):
        """Populate the Bid combo box.

        Args:
            rfq: RFQ data dict (optional, used to auto-select linked bid)
            project_id: Project ID to load bids from
            auto_select: Whether to auto-select a bid (default: True)
        """
        # Store current RFQ and project for button handlers
        self.current_rfq = rfq
        self.current_project_id = project_id

        self.bid_combo.blockSignals(True)
        self.bid_combo.clear()
        self.bid_combo.addItem("-- Select Bid --", None)

        # If no project, clear everything and return
        if not project_id:
            self.bid_combo.blockSignals(False)
            self.set_current_btn.setEnabled(False)
            self._set_status("Select an RFQ to view Bids.")
            return

        bids = []
        try:
            logger.info(f"Loading Bids for Project ID {project_id}")
            # Get all bids for the project
            bids = self.sg_session.get_bids(project_id, fields=["id", "code", "name", "sg_bid_type", "sg_vfx_breakdown"])
        except Exception as e:
            logger.error(f"Error loading Bids: {e}", exc_info=True)
            bids = []

        for bid in bids:
            # Format label: "Bid Name (Bid Type)"
            bid_name = bid.get("code") or f"Bid {bid.get('id', 'N/A')}"
            bid_type = bid.get("sg_bid_type", "Unknown")
            label = f"{bid_name} ({bid_type})"
            self.bid_combo.addItem(label, bid)

        self.bid_combo.blockSignals(False)

        # Enable Set button only if there are bids and an RFQ is selected
        self.set_current_btn.setEnabled(len(bids) > 0 and rfq is not None)

        # Status & selection
        if bids:
            self._set_status(f"Loaded {len(bids)} Bid(s) in project.")

            # Auto-select the bid linked to the RFQ if present
            if rfq and auto_select:
                # Check Early Bid first, then Turnover Bid
                linked_bid = rfq.get("sg_early_bid")
                if not linked_bid:
                    linked_bid = rfq.get("sg_turnover_bid")

                linked_bid_id = None
                if isinstance(linked_bid, dict):
                    linked_bid_id = linked_bid.get("id")
                elif isinstance(linked_bid, list) and linked_bid:
                    linked_bid_id = linked_bid[0].get("id") if linked_bid[0] else None

                if linked_bid_id:
                    # Try to select it
                    if not self._select_bid_by_id(linked_bid_id):
                        if self.bid_combo.count() > 1:
                            self.bid_combo.setCurrentIndex(1)
                else:
                    if self.bid_combo.count() > 1:
                        self.bid_combo.setCurrentIndex(1)
        else:
            self._set_status("No Bids found in this project.")

    def _select_bid_by_id(self, bid_id):
        """Select a bid by its ID.

        Args:
            bid_id: Bid ID to select

        Returns:
            bool: True if found and selected, False otherwise
        """
        if not bid_id:
            return False

        for index in range(self.bid_combo.count()):
            bid = self.bid_combo.itemData(index)
            if isinstance(bid, dict) and bid.get("id") == bid_id:
                self.bid_combo.setCurrentIndex(index)
                return True
        return False

    def get_current_bid(self):
        """Get the currently selected bid.

        Returns:
            dict: Current bid data or None
        """
        return self.bid_combo.currentData()

    def clear(self):
        """Clear the bid selector."""
        self.bid_combo.blockSignals(True)
        self.bid_combo.clear()
        self.bid_combo.addItem("-- Select Bid --", None)
        self.bid_combo.blockSignals(False)
        self.set_current_btn.setEnabled(False)
        self._set_status("Select an RFQ to view Bids.")

    def _on_bid_changed(self, index):
        """Handle bid selection change."""
        bid = self.bid_combo.itemData(index)

        if bid:
            bid_name = bid.get("code") or f"Bid {bid.get('id', 'N/A')}"
            bid_type = bid.get("sg_bid_type", "Unknown")
            self._set_status(f"Selected: {bid_name} ({bid_type})")
            logger.info(f"Bid selected: {bid_name} (ID: {bid.get('id')})")
        else:
            if index == 0:
                self._set_status("Select a Bid to view its details.")

        # Emit signal
        self.bidChanged.emit(bid)

    def _on_set_current_bid(self):
        """Handle Set as Current button click - link bid to RFQ."""
        bid = self.get_current_bid()
        if not bid:
            QtWidgets.QMessageBox.warning(self, "No Bid Selected", "Please select a Bid from the list.")
            return

        # Get current RFQ
        if not self.current_rfq:
            QtWidgets.QMessageBox.warning(self, "No RFQ Selected", "Please select an RFQ first.")
            return

        rfq = self.current_rfq

        bid_name = bid.get('code', f"Bid {bid.get('id')}")
        bid_type = bid.get('sg_bid_type', '')
        rfq_code = rfq.get('code', 'N/A')

        # Confirm with user
        reply = QtWidgets.QMessageBox.question(
            self,
            "Set Current Bid",
            f"Set '{bid_name}' ({bid_type}) as the current bid for RFQ '{rfq_code}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply != QtWidgets.QMessageBox.Yes:
            return

        try:
            # Determine which field to update based on bid type
            bid_type_value = bid.get('sg_bid_type', 'Early Bid')
            if bid_type_value == 'Turnover Bid':
                field_name = 'sg_turnover_bid'
            else:
                field_name = 'sg_early_bid'

            # Update RFQ to link this bid
            rfq_id = rfq['id']
            update_data = {field_name: {"type": "CustomEntity06", "id": bid['id']}}

            self.sg_session.sg.update("CustomEntity04", rfq_id, update_data)

            logger.info(f"DEBUG: Successfully updated ShotGrid - RFQ {rfq_id} {field_name} = Bid {bid['id']}")
            logger.info(f"DEBUG: self.parent_app = {self.parent_app}")
            logger.info(f"DEBUG: type(self.parent_app) = {type(self.parent_app)}")
            logger.info(f"DEBUG: hasattr(self.parent_app, 'parent_app') = {hasattr(self.parent_app, 'parent_app')}")
            logger.info(f"DEBUG: hasattr(self.parent_app, 'rfq_bid_label') = {hasattr(self.parent_app, 'rfq_bid_label')}")

            # Update the Current Bid label directly in main app
            # Need to go through parent_app.parent_app since:
            # BidSelectorWidget.parent_app = BiddingTab
            # BiddingTab.parent_app = MainApp (which has rfq_bid_label)
            main_app = None
            if hasattr(self.parent_app, 'parent_app'):
                main_app = self.parent_app.parent_app
                logger.info(f"DEBUG: main_app = {main_app}")
                logger.info(f"DEBUG: hasattr(main_app, 'rfq_bid_label') = {hasattr(main_app, 'rfq_bid_label')}")

            if main_app and hasattr(main_app, 'rfq_bid_label'):
                # Use the bid's name for display
                bid_display_name = bid.get('name') or bid.get('code') or bid_name
                label_text = f"{bid_display_name} ({bid_type})" if bid_type else bid_display_name
                main_app.rfq_bid_label.setText(label_text)
                logger.info(f"✓ Updated Current Bid label to: {label_text}")
            else:
                logger.warning("Could not update Current Bid label - main_app or rfq_bid_label not found")

            # Refresh RFQ data in parent to keep everything in sync
            if main_app and hasattr(main_app, '_load_rfqs') and hasattr(main_app, 'sg_project_combo'):
                proj = main_app.sg_project_combo.itemData(main_app.sg_project_combo.currentIndex())
                if proj:
                    current_rfq_index = main_app.rfq_combo.currentIndex()
                    main_app._load_rfqs(proj['id'])
                    # Restore RFQ selection - this will trigger _on_rfq_changed
                    if current_rfq_index > 0:  # Don't select the "-- Select RFQ --" item
                        main_app.rfq_combo.setCurrentIndex(current_rfq_index)

            self.statusMessageChanged.emit(f"✓ Set '{bid_name}' as current bid for RFQ", False)
            QtWidgets.QMessageBox.information(self, "Success", f"'{bid_name}' is now the current {bid_type} for this RFQ.")

        except Exception as e:
            logger.error(f"Failed to set current bid: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to set current bid:\n{str(e)}")

    def _on_add_bid(self):
        """Handle Add Bid button click."""
        # Get current project
        if not self.current_project_id:
            QtWidgets.QMessageBox.warning(self, "No Project Selected", "Please select a project first.")
            return

        # Show dialog to get bid name and type
        dialog = AddBidDialog(parent=self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            bid_name = dialog.get_bid_name()
            bid_type = dialog.get_bid_type()

            if not bid_name:
                QtWidgets.QMessageBox.warning(self, "Invalid Input", "Please enter a bid name.")
                return

            try:
                # Create the bid
                new_bid = self.sg_session.create_bid(self.current_project_id, bid_name, bid_type)

                logger.info(f"Created new bid: {bid_name} (ID: {new_bid['id']})")

                # Refresh the bid list
                self._refresh_bids()

                # Select the newly created bid
                self._select_bid_by_id(new_bid['id'])

                self.statusMessageChanged.emit(f"✓ Created bid '{bid_name}'", False)
                QtWidgets.QMessageBox.information(self, "Success", f"Bid '{bid_name}' created successfully.")

            except Exception as e:
                logger.error(f"Failed to create bid: {e}", exc_info=True)
                QtWidgets.QMessageBox.critical(self, "Error", f"Failed to create bid:\n{str(e)}")

    def _on_remove_bid(self):
        """Handle Remove Bid button click."""
        bid = self.get_current_bid()
        if not bid:
            QtWidgets.QMessageBox.warning(self, "No Bid Selected", "Please select a Bid from the list.")
            return

        bid_name = bid.get('code', f"Bid {bid.get('id')}")

        # Confirm deletion
        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete bid '{bid_name}'?\n\nThis cannot be undone.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply != QtWidgets.QMessageBox.Yes:
            return

        try:
            # Delete the bid
            self.sg_session.delete_bid(bid['id'])

            logger.info(f"Deleted bid: {bid_name} (ID: {bid['id']})")

            # Refresh the bid list
            self._refresh_bids()

            self.statusMessageChanged.emit(f"✓ Deleted bid '{bid_name}'", False)
            QtWidgets.QMessageBox.information(self, "Success", f"Bid '{bid_name}' deleted successfully.")

        except Exception as e:
            logger.error(f"Failed to delete bid: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to delete bid:\n{str(e)}")

    def _on_rename_bid(self):
        """Handle Rename Bid button click."""
        bid = self.get_current_bid()
        if not bid:
            QtWidgets.QMessageBox.warning(self, "No Bid Selected", "Please select a Bid from the list.")
            return

        current_name = bid.get('code', '')

        # Show dialog to get new name
        dialog = RenameBidDialog(current_name, parent=self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            new_name = dialog.get_new_name()

            if not new_name or new_name == current_name:
                return

            try:
                # Update the bid name
                self.sg_session.update_bid(bid['id'], {"code": new_name})

                logger.info(f"Renamed bid from '{current_name}' to '{new_name}' (ID: {bid['id']})")

                # Refresh the bid list
                self._refresh_bids()

                # Select the renamed bid
                self._select_bid_by_id(bid['id'])

                self.statusMessageChanged.emit(f"✓ Renamed bid to '{new_name}'", False)
                QtWidgets.QMessageBox.information(self, "Success", f"Bid renamed to '{new_name}'.")

            except Exception as e:
                logger.error(f"Failed to rename bid: {e}", exc_info=True)
                QtWidgets.QMessageBox.critical(self, "Error", f"Failed to rename bid:\n{str(e)}")

    def _on_import_bid(self):
        """Handle Import button click."""
        # Show the import dialog
        dialog = ImportBidDialog(parent=self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            # Get the imported data (dict of tab_name -> DataFrame)
            data = dialog.get_imported_data()

            if data:
                # Build summary message
                summary_lines = ["Successfully imported Excel data:\n"]
                total_rows = 0
                total_cols = 0

                for tab_name, df in data.items():
                    rows = len(df)
                    cols = len(df.columns)
                    total_rows += rows
                    total_cols = max(total_cols, cols)
                    summary_lines.append(f"• {tab_name}: {rows} rows, {cols} columns")

                summary_lines.append(f"\nTotal: {total_rows} rows imported across {len(data)} tabs")
                summary_lines.append("\nNote: Data processing and storage functionality can be implemented as needed.")

                QtWidgets.QMessageBox.information(
                    self,
                    "Import Successful",
                    "\n".join(summary_lines)
                )

                logger.info(f"Imported Excel data from {len(data)} tabs with total {total_rows} rows")
                self.statusMessageChanged.emit(f"✓ Imported data: {len(data)} tabs, {total_rows} rows total", False)

    def _on_refresh_bids(self):
        """Handle Refresh button click."""
        self._refresh_bids()

    def _refresh_bids(self):
        """Refresh the bid list from ShotGrid."""
        # Get current selections to restore after refresh
        current_bid_id = None
        current_bid = self.get_current_bid()
        if current_bid:
            current_bid_id = current_bid.get('id')

        # Repopulate bids using stored RFQ and project
        self.populate_bids(self.current_rfq, self.current_project_id, auto_select=False)

        # Restore selection if possible
        if current_bid_id:
            self._select_bid_by_id(current_bid_id)

        self.statusMessageChanged.emit("✓ Bid list refreshed", False)
        logger.info("Bid list refreshed")

    def _set_status(self, message, is_error=False):
        """Set the status message.

        Args:
            message: Status message to display
            is_error: Whether this is an error message (changes color)
        """
        color = "#ff8080" if is_error else "#a0a0a0"
        self.status_label.setStyleSheet(f"color: {color}; padding: 2px 0;")
        self.status_label.setText(message)
        self.statusMessageChanged.emit(message, is_error)
