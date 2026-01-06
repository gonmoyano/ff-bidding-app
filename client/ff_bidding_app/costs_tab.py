"""
Costs Tab
Contains dockable cost analysis widgets using QDockWidget pattern.
"""

from PySide6 import QtCore, QtGui, QtWidgets

try:
    from .logger import logger
    from .settings import AppSettings
    from .vfx_breakdown_widget import VFXBreakdownWidget, FormulaDelegate
    from .vfx_breakdown_model import ValidatedComboBoxDelegate
    from .formula_evaluator import FormulaEvaluator
    from .table_with_totals_bar import TableWithTotalsBar
    from .spreadsheet_widget import SpreadsheetWidget
    from .bid_selector_widget import parse_sg_currency
    from .spreadsheet_cache import get_spreadsheet_cache
except ImportError:
    import logging
    logger = logging.getLogger("FFPackageManager")
    from settings import AppSettings
    from vfx_breakdown_widget import VFXBreakdownWidget, FormulaDelegate
    from vfx_breakdown_model import ValidatedComboBoxDelegate
    from formula_evaluator import FormulaEvaluator
    from table_with_totals_bar import TableWithTotalsBar
    from spreadsheet_widget import SpreadsheetWidget
    from bid_selector_widget import parse_sg_currency
    from spreadsheet_cache import get_spreadsheet_cache


class CostDock(QtWidgets.QDockWidget):
    """A dockable cost widget."""

    def __init__(self, title, widget, parent=None):
        """Initialize the cost dock.

        Args:
            title: Title of the dock
            widget: Widget to display in the dock
            parent: Parent widget
        """
        super().__init__(title, parent)
        self.setObjectName(title)
        self.setWidget(widget)
        # No features - docks cannot be closed, moved, or floated
        self.setFeatures(QtWidgets.QDockWidget.NoDockWidgetFeatures)


class CostsTab(QtWidgets.QMainWindow):
    """Costs tab with dockable cost analysis widgets."""

    SETTINGS_KEY = "costsTab/dockState"

    def __init__(self, sg_session, parent=None):
        """Initialize the Costs tab.

        Args:
            sg_session: ShotgridClient instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.sg_session = sg_session
        self.parent_app = parent

        # Settings
        self.app_settings = AppSettings()

        # Current context
        self.current_project_id = None
        self.current_bid_id = None
        self.current_bid_data = None

        # Line Items for VFX Shot Work validation
        self.line_item_names = []
        self.vfx_shot_work_delegate = None

        # Asset Type delegate for Asset Cost
        self.asset_type_delegate = None

        # Line Items data with prices for Price column calculation
        self.line_items_data = []  # Full Line Item data with calculated prices
        self.line_items_price_map = {}  # Map: Line Item code -> calculated price
        self.vfx_breakdown_formula_evaluator = None
        self.asset_cost_formula_evaluator = None

        # Formula delegates for currency formatting updates
        self.shots_cost_formula_delegate = None
        self.asset_cost_formula_delegate = None

        # Spreadsheet cache for deferred ShotGrid saves
        self._spreadsheet_cache = get_spreadsheet_cache()
        self._spreadsheet_cache.set_sg_session(sg_session)

        # Track custom spreadsheets added by user
        self._custom_spreadsheet_docks = []
        self._custom_spreadsheet_counter = 0

        # No central widget - docks can take full space
        self.setCentralWidget(None)

        # Enable tabbing/nesting
        self.setDockOptions(
            QtWidgets.QMainWindow.AllowTabbedDocks |
            QtWidgets.QMainWindow.AllowNestedDocks |
            QtWidgets.QMainWindow.AnimatedDocks
        )

        # Force tabs on TOP for every dock area
        self.setTabPosition(
            QtCore.Qt.AllDockWidgetAreas,
            QtWidgets.QTabWidget.North
        )

        # Apply purple/violet theme to the Costs panel
        self._apply_costs_panel_style()

        # Create toolbar with add spreadsheet button
        self._create_toolbar()

        # Create cost docks
        self._create_cost_docks()

        # Set up cross-tab formula evaluator after all widgets are created
        self._setup_cross_tab_formulas()

        # Set up tab bar event handling for rename and position tracking
        QtCore.QTimer.singleShot(100, self._setup_tab_bar_handling)

        # Load saved layout
        QtCore.QTimer.singleShot(0, self.load_layout)

        logger.info("CostsTab initialized")

    def _setup_tab_bar_handling(self):
        """Set up tab bar event handling for double-click rename and position tracking."""
        # Find the tab bar widget for the dock area
        tab_bars = self.findChildren(QtWidgets.QTabBar)
        for tab_bar in tab_bars:
            # Enable double-click to rename
            tab_bar.setTabsClosable(False)
            tab_bar.tabBarDoubleClicked.connect(self._on_tab_double_clicked)
            # Track tab moves for position saving
            tab_bar.tabMoved.connect(self._on_tab_moved)
            logger.debug(f"Connected tab bar signals: {tab_bar}")

    def _on_tab_double_clicked(self, index):
        """Handle double-click on a tab to rename it."""
        tab_bar = self.sender()
        if not tab_bar:
            return

        tab_text = tab_bar.tabText(index)

        # Only allow renaming custom spreadsheets (not built-in tabs)
        dock = self._find_dock_by_title(tab_text)
        if not dock or dock not in self._custom_spreadsheet_docks:
            return

        # Show rename dialog
        new_name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Rename Sheet",
            "Enter new name:",
            QtWidgets.QLineEdit.Normal,
            tab_text
        )

        if ok and new_name and new_name != tab_text:
            self._rename_custom_spreadsheet(dock, new_name)

    def _rename_custom_spreadsheet(self, dock, new_name):
        """Rename a custom spreadsheet.

        Args:
            dock: The CostDock to rename
            new_name: New name for the spreadsheet
        """
        old_name = dock.sheet_name

        # Update dock title
        dock.setWindowTitle(new_name)
        dock.setObjectName(new_name)
        dock.sheet_name = new_name

        # Update in ShotGrid
        if hasattr(dock, 'sg_spreadsheet_id') and dock.sg_spreadsheet_id:
            try:
                self.sg_session.update_spreadsheet(
                    dock.sg_spreadsheet_id,
                    code=new_name
                )
                logger.info(f"Renamed spreadsheet from '{old_name}' to '{new_name}' in ShotGrid")
            except Exception as e:
                logger.error(f"Failed to rename spreadsheet in ShotGrid: {e}", exc_info=True)

    def _on_tab_moved(self, from_index, to_index):
        """Handle tab position changes - save new positions to ShotGrid."""
        logger.debug(f"Tab moved from {from_index} to {to_index}")
        # Delay position save to allow UI to settle
        QtCore.QTimer.singleShot(100, self._save_custom_spreadsheet_positions)

    def _save_custom_spreadsheet_positions(self):
        """Save current tab positions of custom spreadsheets to ShotGrid."""
        if not self._custom_spreadsheet_docks:
            return

        # Get the tab bar to determine current order
        tab_bars = self.findChildren(QtWidgets.QTabBar)
        if not tab_bars:
            return

        # Find positions of custom spreadsheets in the tab bar
        for tab_bar in tab_bars:
            for i in range(tab_bar.count()):
                tab_text = tab_bar.tabText(i)
                dock = self._find_dock_by_title(tab_text)
                if dock and dock in self._custom_spreadsheet_docks:
                    # Save position to ShotGrid
                    if hasattr(dock, 'sg_spreadsheet_id') and dock.sg_spreadsheet_id:
                        try:
                            # Get existing metadata and update position
                            sheet_meta = {}
                            if hasattr(dock, 'spreadsheet') and hasattr(dock.spreadsheet, 'model'):
                                sheet_meta = dock.spreadsheet.model.get_sheet_meta() or {}
                            sheet_meta['tab_position'] = i

                            self.sg_session.update_spreadsheet(
                                dock.sg_spreadsheet_id,
                                sheet_meta=sheet_meta
                            )
                            logger.debug(f"Saved position {i} for spreadsheet '{tab_text}'")
                        except Exception as e:
                            logger.error(f"Failed to save position for '{tab_text}': {e}")

    def _find_dock_by_title(self, title):
        """Find a dock widget by its title.

        Args:
            title: Window title to search for

        Returns:
            QDockWidget or None
        """
        # Check custom spreadsheets first
        for dock in self._custom_spreadsheet_docks:
            if dock.windowTitle() == title:
                return dock

        # Check built-in docks
        if hasattr(self, 'shots_cost_dock') and self.shots_cost_dock.windowTitle() == title:
            return self.shots_cost_dock
        if hasattr(self, 'asset_cost_dock') and self.asset_cost_dock.windowTitle() == title:
            return self.asset_cost_dock
        if hasattr(self, 'misc_cost_dock') and self.misc_cost_dock.windowTitle() == title:
            return self.misc_cost_dock
        if hasattr(self, 'total_cost_dock') and self.total_cost_dock.windowTitle() == title:
            return self.total_cost_dock

        return None

    def _create_toolbar(self):
        """Create the toolbar with add spreadsheet button."""
        self.toolbar = QtWidgets.QToolBar("Costs Toolbar")
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setIconSize(QtCore.QSize(16, 16))

        # Style the toolbar
        self.toolbar.setStyleSheet("""
            QToolBar {
                background-color: #2d2d30;
                border: none;
                spacing: 5px;
                padding: 2px 5px;
            }
            QToolButton {
                background-color: transparent;
                border: 1px solid #555555;
                border-radius: 4px;
                color: #e0e0e0;
                padding: 4px 8px;
                font-size: 12px;
            }
            QToolButton:hover {
                background-color: #6b5b95;
                border-color: #6b5b95;
            }
            QToolButton:pressed {
                background-color: #5b4b85;
            }
        """)

        # Add spacer to push button to the right
        spacer = QtWidgets.QWidget()
        spacer.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        self.toolbar.addWidget(spacer)

        # Add spreadsheet button
        self.add_spreadsheet_btn = QtWidgets.QToolButton()
        self.add_spreadsheet_btn.setText("+ Add Spreadsheet")
        self.add_spreadsheet_btn.setToolTip("Add a new spreadsheet tab")
        self.add_spreadsheet_btn.clicked.connect(lambda: self._add_custom_spreadsheet())
        self.toolbar.addWidget(self.add_spreadsheet_btn)

        # Add toolbar to the top
        self.addToolBar(QtCore.Qt.TopToolBarArea, self.toolbar)

    def _add_custom_spreadsheet(self, sheet_name=None, load_from_sg=False):
        """Add a new custom spreadsheet dock after Asset Costs.

        Args:
            sheet_name: Optional name for the sheet. If None, auto-generates "Sheet1", "Sheet2", etc.
            load_from_sg: If True, load existing data from ShotGrid for this sheet name
        """
        if sheet_name is None:
            self._custom_spreadsheet_counter += 1
            sheet_name = f"Sheet{self._custom_spreadsheet_counter}"

        # Create the spreadsheet widget
        spreadsheet = SpreadsheetWidget(
            cols=10,
            app_settings=self.app_settings,
            parent=self
        )

        # Apply currency settings if we have bid data
        if self.current_bid_data:
            default_symbol = self.app_settings.get_currency() if self.app_settings else "$"
            sg_currency_value = self.current_bid_data.get("sg_currency")
            currency_symbol, currency_position = parse_sg_currency(sg_currency_value, default_symbol or "$")
            spreadsheet.set_currency_settings(currency_symbol, currency_position)

        # Set up formula evaluator for this spreadsheet (same as Misc)
        formula_evaluator = FormulaEvaluator(
            table_model=spreadsheet.model,
            sheet_models={sheet_name: spreadsheet.model}
        )
        spreadsheet.set_formula_evaluator(formula_evaluator)

        # Create the dock widget
        dock = CostDock(sheet_name, spreadsheet, self)

        # Store reference to the spreadsheet, name, and evaluator for later access
        dock.spreadsheet = spreadsheet
        dock.sheet_name = sheet_name
        dock.formula_evaluator = formula_evaluator

        # Add dock to the left area
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dock)

        # Tabify with Asset Costs dock (so it appears after it)
        self.tabifyDockWidget(self.asset_cost_dock, dock)

        # Raise the new tab to show it
        dock.raise_()

        # Track this custom spreadsheet
        self._custom_spreadsheet_docks.append(dock)

        # Create the spreadsheet in ShotGrid immediately (if not loading existing)
        if not load_from_sg and self.current_bid_id and self.current_project_id:
            try:
                # Check if spreadsheet already exists
                existing = self.sg_session.get_spreadsheet_by_name(self.current_bid_id, sheet_name)
                if not existing:
                    # Create new spreadsheet in ShotGrid (no sg_type, just code)
                    sg_spreadsheet = self.sg_session.create_spreadsheet(
                        self.current_project_id,
                        self.current_bid_id,
                        code=sheet_name
                    )
                    dock.sg_spreadsheet_id = sg_spreadsheet.get("id")
                    logger.info(f"Created CustomEntity15 '{sheet_name}' (ID: {dock.sg_spreadsheet_id}) in ShotGrid")
                else:
                    dock.sg_spreadsheet_id = existing.get("id")
                    logger.info(f"Found existing CustomEntity15 '{sheet_name}' (ID: {dock.sg_spreadsheet_id})")
            except Exception as e:
                logger.error(f"Failed to create spreadsheet in ShotGrid: {e}", exc_info=True)
                dock.sg_spreadsheet_id = None
        else:
            dock.sg_spreadsheet_id = None

        # Connect dataChanged signal to save directly to ShotGrid
        # Use default argument to capture dock by value, not by reference
        def on_data_changed(d=dock):
            self._on_custom_spreadsheet_data_changed(d)

        spreadsheet.model.dataChanged.connect(on_data_changed)

        # Load existing data from ShotGrid if requested
        if load_from_sg and self.current_bid_id:
            self._load_custom_spreadsheet_from_shotgrid(dock)

        logger.info(f"Added custom spreadsheet: {sheet_name}")

    def _on_custom_spreadsheet_data_changed(self, dock):
        """Handle data changes in a custom spreadsheet - save directly to ShotGrid.

        Args:
            dock: The CostDock containing the spreadsheet
        """
        if not self.current_bid_id or not self.current_project_id:
            return

        if not hasattr(dock, 'spreadsheet') or not hasattr(dock, 'sheet_name'):
            return

        try:
            data_dict = dock.spreadsheet.get_data_as_dict()
            cell_meta_dict = dock.spreadsheet.model.get_all_cell_meta()
            sheet_meta = dock.spreadsheet.model.get_sheet_meta()

            # Save directly to ShotGrid
            self.sg_session.save_spreadsheet_by_name(
                project_id=self.current_project_id,
                bid_id=self.current_bid_id,
                spreadsheet_name=dock.sheet_name,
                data_dict=data_dict,
                cell_meta_dict=cell_meta_dict,
                sheet_meta=sheet_meta
            )
            logger.debug(f"Saved custom spreadsheet '{dock.sheet_name}' to ShotGrid ({len(data_dict)} cells)")
        except Exception as e:
            logger.error(f"Failed to save custom spreadsheet {dock.sheet_name}: {e}", exc_info=True)

    def _load_custom_spreadsheet_from_shotgrid(self, dock):
        """Load custom spreadsheet data from ShotGrid.

        Args:
            dock: The CostDock containing the spreadsheet
        """
        if not self.current_bid_id or not hasattr(dock, 'sheet_name'):
            return

        try:
            # Get the spreadsheet entity to store its ID
            sg_spreadsheet = self.sg_session.get_spreadsheet_by_name(self.current_bid_id, dock.sheet_name)
            if sg_spreadsheet:
                dock.sg_spreadsheet_id = sg_spreadsheet.get("id")

            data_dict, cell_meta_dict, sheet_meta = self.sg_session.load_spreadsheet_by_name(
                self.current_bid_id,
                dock.sheet_name
            )

            if data_dict:
                dock.spreadsheet.load_data_from_dict(data_dict)

                if cell_meta_dict:
                    dock.spreadsheet.model.load_cell_meta(cell_meta_dict)

                if sheet_meta:
                    dock.spreadsheet.model.load_sheet_meta(sheet_meta)
                    dock.spreadsheet.apply_saved_sizes()

                logger.info(f"Loaded custom spreadsheet '{dock.sheet_name}' from ShotGrid ({len(data_dict)} cells)")
        except Exception as e:
            logger.error(f"Failed to load custom spreadsheet {dock.sheet_name}: {e}", exc_info=True)

    def _load_custom_spreadsheets_for_bid(self):
        """Load all custom spreadsheets for the current bid from ShotGrid."""
        import json

        if not self.current_bid_id:
            return

        try:
            # Get all spreadsheets for this bid
            all_spreadsheets = self.sg_session.get_all_spreadsheets_for_bid(self.current_bid_id)

            # Filter to only custom spreadsheets (those without sg_type or not 'misc'/'total_cost')
            custom_sheets = [
                s for s in all_spreadsheets
                if s.get("sg_type") not in ('misc', 'total_cost')
            ]

            # Parse sheet_meta to get tab positions for sorting
            def get_tab_position(sheet_data):
                """Extract tab position from sheet metadata, default to a high number."""
                meta_str = sheet_data.get("sg_sheet_meta", "")
                if meta_str:
                    try:
                        meta = json.loads(meta_str)
                        return meta.get("tab_position", 9999)
                    except (json.JSONDecodeError, TypeError):
                        pass
                return 9999

            # Sort by tab position (saved order), then by code as fallback
            custom_sheets.sort(key=lambda s: (get_tab_position(s), s.get("code", "")))

            # Create docks for each custom spreadsheet
            for sheet_data in custom_sheets:
                sheet_name = sheet_data.get("code", "")
                if sheet_name:
                    # Update counter if this is a numbered sheet
                    if sheet_name.startswith("Sheet"):
                        try:
                            num = int(sheet_name.replace("Sheet", ""))
                            if num > self._custom_spreadsheet_counter:
                                self._custom_spreadsheet_counter = num
                        except ValueError:
                            pass

                    self._add_custom_spreadsheet(sheet_name=sheet_name, load_from_sg=True)

            logger.info(f"Loaded {len(custom_sheets)} custom spreadsheets for bid {self.current_bid_id}")

        except Exception as e:
            logger.error(f"Failed to load custom spreadsheets: {e}", exc_info=True)

    def _clear_custom_spreadsheets(self):
        """Remove all custom spreadsheet docks."""
        for dock in self._custom_spreadsheet_docks:
            self.removeDockWidget(dock)
            dock.deleteLater()
        self._custom_spreadsheet_docks.clear()
        self._custom_spreadsheet_counter = 0

    def _apply_costs_panel_style(self):
        """Apply a purple/violet theme to specific elements in the Costs panel."""
        # Only style specific elements: selected tabs, scrollbars
        self.setStyleSheet("""
            /* Dock widget tabs - only selected tab is purple */
            QTabBar::tab:selected {
                background-color: #6b5b95;
                color: white;
                border: 1px solid #8b7bb5;
                border-bottom: none;
            }

            /* Scrollbars - purple theme */
            QScrollBar:vertical {
                background-color: #2d2d30;
                width: 12px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background-color: #6b5b95;
                min-height: 20px;
                border-radius: 4px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #7b6ba5;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }

            QScrollBar:horizontal {
                background-color: #2d2d30;
                height: 12px;
                border: none;
            }
            QScrollBar::handle:horizontal {
                background-color: #6b5b95;
                min-width: 20px;
                border-radius: 4px;
                margin: 2px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #7b6ba5;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
        """)

    def _create_cost_docks(self):
        """Create the individual cost dock widgets."""
        # Shot Costs (uses VFXBreakdownWidget)
        self.shots_cost_dock = CostDock(
            "Shot Costs",
            self._create_shots_cost_widget(),
            self
        )

        # Asset Costs
        self.asset_cost_dock = CostDock(
            "Asset Costs",
            self._create_asset_cost_widget(),
            self
        )

        # Miscellaneous Costs
        self.misc_cost_dock = CostDock(
            "Misc",
            self._create_misc_cost_widget(),
            self
        )

        # Total Cost
        self.total_cost_dock = CostDock(
            "Total Cost",
            self._create_total_cost_widget(),
            self
        )

        # Add docks as tabs - Order: Shots Cost -> Assets Cost -> Misc Cost -> Total Cost
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.shots_cost_dock)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.asset_cost_dock)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.misc_cost_dock)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.total_cost_dock)

        # Create tabs instead of vertical stacking
        self.tabifyDockWidget(self.shots_cost_dock, self.asset_cost_dock)
        self.tabifyDockWidget(self.asset_cost_dock, self.misc_cost_dock)
        self.tabifyDockWidget(self.misc_cost_dock, self.total_cost_dock)

        # Show the first tab by default
        self.shots_cost_dock.raise_()

    def _create_shots_cost_widget(self):
        """Create the Shot Costs widget using VFXBreakdownWidget."""
        # Use VFXBreakdownWidget with toolbar for search and sort functionality
        self.shots_cost_widget = VFXBreakdownWidget(
            self.sg_session,
            show_toolbar=True,  # Show search and sort toolbar in collapsible group
            entity_name="Shot",
            settings_key="shots_cost",  # Unique settings key for Shot Costs table
            parent=self
        )

        # Enable read-only mode - edits should be made in the VFX Breakdown tab
        self.shots_cost_widget.set_readonly_mode(True, entity_type="VFX Breakdown")

        # Apply purple pill colors for the Costs panel
        self.shots_cost_widget.set_pill_colors({
            'valid_bg': '#6b5b95',
            'valid_border': '#5b4b85',
            'invalid_bg': '#e74c3c',
            'invalid_border': '#c0392b'
        })

        # Apply purple checkbox color for the Costs panel
        self.shots_cost_widget.set_checkbox_color('#6b5b95')

        # Apply purple price column color for the Costs panel
        self.shots_cost_widget.set_price_column_color('#6b5b95')

        # Now intercept the layout and replace table_view with wrapped version
        layout = self.shots_cost_widget.layout()

        # Remove table_view from layout
        layout.removeWidget(self.shots_cost_widget.table_view)

        # Create wrapper with totals bar, passing app_settings for currency formatting
        self.shots_cost_totals_wrapper = TableWithTotalsBar(
            self.shots_cost_widget.table_view,
            app_settings=self.app_settings
        )
        # Apply purple highlight color for the totals bar
        self.shots_cost_totals_wrapper.set_highlight_color('#6b5b95')

        # Add wrapper back to layout
        layout.addWidget(self.shots_cost_totals_wrapper)

        return self.shots_cost_widget

    def _create_asset_cost_widget(self):
        """Create the Asset Costs widget using VFXBreakdownWidget."""
        # Use VFXBreakdownWidget with toolbar for search and sort functionality
        self.asset_cost_widget = VFXBreakdownWidget(
            self.sg_session,
            show_toolbar=True,  # Show search and sort toolbar in collapsible group
            entity_name="Asset",
            settings_key="asset_cost",  # Unique settings key for Asset Costs table
            parent=self
        )

        # Enable read-only mode - edits should be made in the Assets tab
        self.asset_cost_widget.set_readonly_mode(True, entity_type="Bid Asset")

        # Apply purple pill colors for the Costs panel
        self.asset_cost_widget.set_pill_colors({
            'valid_bg': '#6b5b95',
            'valid_border': '#5b4b85',
            'invalid_bg': '#e74c3c',
            'invalid_border': '#c0392b'
        })

        # Apply purple checkbox color for the Costs panel
        self.asset_cost_widget.set_checkbox_color('#6b5b95')

        # Apply purple price column color for the Costs panel
        self.asset_cost_widget.set_price_column_color('#6b5b95')

        # Configure the model to use Asset-specific columns and entity type
        if hasattr(self.asset_cost_widget, 'model') and self.asset_cost_widget.model:
            # Define Asset item column fields (including virtual price columns)
            asset_field_list = [
                "id", "code", "sg_bid_asset_type", "sg_bidding_notes", "_line_item_price", "_calc_price"
            ]
            self.asset_cost_widget.model.column_fields = asset_field_list.copy()
            # Set entity type to CustomEntity07 (Asset items) instead of default CustomEntity02
            self.asset_cost_widget.model.entity_type = "CustomEntity07"
            logger.info(f"Configured Assets Cost widget model with fields: {asset_field_list} and entity_type: CustomEntity07")

        # Now intercept the layout and replace table_view with wrapped version
        layout = self.asset_cost_widget.layout()

        # Remove table_view from layout
        layout.removeWidget(self.asset_cost_widget.table_view)

        # Create wrapper with totals bar, passing app_settings for currency formatting
        self.asset_cost_totals_wrapper = TableWithTotalsBar(
            self.asset_cost_widget.table_view,
            app_settings=self.app_settings
        )
        # Apply purple highlight color for the totals bar
        self.asset_cost_totals_wrapper.set_highlight_color('#6b5b95')

        # Add wrapper back to layout
        layout.addWidget(self.asset_cost_totals_wrapper)

        return self.asset_cost_widget

    def _create_misc_cost_widget(self):
        """Create the Misc widget with full Google Sheets-style spreadsheet."""
        # Create the spreadsheet widget (defaults to 10 rows)
        self.misc_cost_spreadsheet = SpreadsheetWidget(
            cols=10,
            app_settings=self.app_settings,
            parent=self
        )

        logger.info("Created Misc spreadsheet")

        return self.misc_cost_spreadsheet

    def _create_total_cost_widget(self):
        """Create the Total Cost widget with summary table."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QtWidgets.QLabel("Total Cost Summary")
        title.setStyleSheet("font-size: 16px; font-weight: bold; padding: 5px;")
        layout.addWidget(title)

        # Create summary table using SpreadsheetWidget for formula support
        self.total_cost_spreadsheet = SpreadsheetWidget(
            rows=5,  # Header + 4 data rows
            cols=2,
            app_settings=self.app_settings,
            parent=self
        )

        # Initialize column headers
        self.total_cost_spreadsheet.set_cell_value(0, 0, "Category")
        self.total_cost_spreadsheet.set_cell_value(0, 1, "Amount")

        # Initialize row labels (Category column)
        row_labels = ["Shot Costs", "Asset Costs", "Misc", "Total Cost"]
        for row, label in enumerate(row_labels, start=1):
            self.total_cost_spreadsheet.set_cell_value(row, 0, label)

        # Initialize Amount column with default values
        # Values are updated via _update_total_cost_summary()
        self.total_cost_spreadsheet.set_cell_value(1, 1, 0)  # Shot Costs
        self.total_cost_spreadsheet.set_cell_value(2, 1, 0)  # Asset Costs
        self.total_cost_spreadsheet.set_cell_value(3, 1, 0)  # Misc
        # Total Cost formula: sum of B2:B4
        self.total_cost_spreadsheet.set_cell_value(4, 1, "=B2+B3+B4")

        # Set column widths
        self.total_cost_spreadsheet.table_view.setColumnWidth(0, 200)
        self.total_cost_spreadsheet.table_view.setColumnWidth(1, 150)

        # Adjust table height to fit content
        self.total_cost_spreadsheet.setMaximumHeight(250)

        layout.addWidget(self.total_cost_spreadsheet)
        layout.addStretch()

        logger.info("Created Total Cost Summary spreadsheet")

        return widget

    def _update_total_cost_summary(self):
        """Update the Total Cost summary table with live totals from each dock.

        Only updates cells that don't contain user-entered formulas.
        This preserves cross-tab references like =Misc!A1 that the user may have set.
        """
        try:
            # Get Shot Costs total
            shot_total = 0.0
            if hasattr(self, 'shots_cost_totals_wrapper') and hasattr(self, 'shots_cost_widget'):
                if hasattr(self.shots_cost_widget, 'model') and self.shots_cost_widget.model:
                    # Find the Price column index (_calc_price)
                    try:
                        price_col_idx = self.shots_cost_widget.model.column_fields.index("_calc_price")
                        total_str = self.shots_cost_totals_wrapper.get_total(price_col_idx)
                        # Parse the total string (format: "$1,234.56")
                        shot_total = self._parse_currency_value(total_str)
                    except (ValueError, AttributeError):
                        pass

            # Get Asset Costs total
            asset_total = 0.0
            if hasattr(self, 'asset_cost_totals_wrapper') and hasattr(self, 'asset_cost_widget'):
                if hasattr(self.asset_cost_widget, 'model') and self.asset_cost_widget.model:
                    # Find the Price column index (_calc_price)
                    try:
                        price_col_idx = self.asset_cost_widget.model.column_fields.index("_calc_price")
                        total_str = self.asset_cost_totals_wrapper.get_total(price_col_idx)
                        # Parse the total string (format: "$1,234.56")
                        asset_total = self._parse_currency_value(total_str)
                    except (ValueError, AttributeError):
                        pass

            # Get Misc total from spreadsheet
            misc_total = 0.0
            if hasattr(self, 'misc_cost_spreadsheet') and hasattr(self.misc_cost_spreadsheet, 'model'):
                # Sum all values in column C (index 2) which contains formulas
                # Starting from row 2 (index 1) to skip header
                try:
                    for row in range(1, self.misc_cost_spreadsheet.model.rowCount()):
                        value = self.misc_cost_spreadsheet.get_cell_value(row, 2)  # Column C
                        if value:
                            parsed_value = self._parse_currency_value(str(value))
                            misc_total += parsed_value
                except (ValueError, AttributeError):
                    pass

            # Update the summary spreadsheet (rows 1-3, column 1)
            # Only update cells that don't have user-entered formulas
            # This preserves cross-tab references like =Misc!A1
            model = self.total_cost_spreadsheet.model

            # Shot Costs (B2 = row 1, col 1) - only update if no formula
            if not model.get_cell_formula(1, 1):
                self.total_cost_spreadsheet.set_cell_value(1, 1, shot_total)
            else:
                # Clear cache to force formula re-evaluation
                model._evaluated_cache.pop((1, 1), None)

            # Asset Costs (B3 = row 2, col 1) - only update if no formula
            if not model.get_cell_formula(2, 1):
                self.total_cost_spreadsheet.set_cell_value(2, 1, asset_total)
            else:
                # Clear cache to force formula re-evaluation
                model._evaluated_cache.pop((2, 1), None)

            # Misc (B4 = row 3, col 1) - only update if no formula
            if not model.get_cell_formula(3, 1):
                self.total_cost_spreadsheet.set_cell_value(3, 1, misc_total)
            else:
                # Clear cache to force formula re-evaluation
                model._evaluated_cache.pop((3, 1), None)

            # Total Cost (B5 = row 4, col 1) - always has formula, just clear cache
            model._evaluated_cache.pop((4, 1), None)

            # Refresh the view to show updated values
            model.layoutChanged.emit()

        except Exception as e:
            logger.error(f"Error updating Total Cost summary: {e}", exc_info=True)

    def _parse_currency_value(self, value_str):
        """Parse a currency string and return the numeric value.

        Args:
            value_str: String like "$1,234.56" or "1234.56"

        Returns:
            float: Parsed numeric value, or 0.0 if parsing fails
        """
        if not value_str:
            return 0.0

        try:
            # Remove currency symbols, commas, and whitespace
            cleaned = value_str.replace('$', '').replace('€', '').replace('£', '').replace('¥', '').replace('₹', '').replace('₽', '').replace(',', '').strip()
            return float(cleaned)
        except (ValueError, AttributeError):
            return 0.0

    def _format_currency(self, value):
        """Format a numeric value with currency symbol based on bid settings.

        Args:
            value: Numeric value to format

        Returns:
            str: Formatted currency string
        """
        # Get currency symbol and position from bid data (ShotGrid sg_currency field)
        # Format is "symbol+before" or "symbol+after"
        default_symbol = self.app_settings.get_currency() if self.app_settings else "$"
        sg_currency_value = self.current_bid_data.get("sg_currency") if self.current_bid_data else None
        currency_symbol, currency_position = parse_sg_currency(sg_currency_value, default_symbol or "$")

        # Format based on position
        if currency_position == "append":
            return f"{value:,.2f}{currency_symbol}"
        else:
            return f"{currency_symbol}{value:,.2f}"

    def _on_shots_data_changed(self):
        """Handle data changes in the Shots Cost model - recalculate totals and update summary."""
        # Clear cross-tab formula caches so references to ShotCosts update
        self._clear_cross_tab_caches()

        if hasattr(self, 'shots_cost_totals_wrapper') and hasattr(self, 'shots_cost_widget'):
            if hasattr(self.shots_cost_widget, 'model') and self.shots_cost_widget.model:
                try:
                    # Find the Price column index
                    price_col_idx = self.shots_cost_widget.model.column_fields.index("_calc_price")
                    # Recalculate totals
                    self.shots_cost_totals_wrapper.calculate_totals(columns=[price_col_idx], skip_first_col=True)
                    # Update Total Cost summary
                    self._update_total_cost_summary()
                except (ValueError, AttributeError):
                    pass

    def _on_assets_data_changed(self):
        """Handle data changes in the Assets Cost model - recalculate totals and update summary."""
        # Clear cross-tab formula caches so references to AssetCosts update
        self._clear_cross_tab_caches()

        if hasattr(self, 'asset_cost_totals_wrapper') and hasattr(self, 'asset_cost_widget'):
            if hasattr(self.asset_cost_widget, 'model') and self.asset_cost_widget.model:
                try:
                    # Find the Price column index
                    price_col_idx = self.asset_cost_widget.model.column_fields.index("_calc_price")
                    # Recalculate totals
                    self.asset_cost_totals_wrapper.calculate_totals(columns=[price_col_idx], skip_first_col=True)
                    # Update Total Cost summary
                    self._update_total_cost_summary()
                except (ValueError, AttributeError):
                    pass

    def _clear_cross_tab_caches(self, source=None):
        """Clear formula caches on all spreadsheets to ensure cross-tab references update.

        Args:
            source: The source model that triggered the change (to avoid clearing its own cache again)
        """
        from PySide6.QtCore import Qt

        # Prevent recursive calls
        if getattr(self, '_clearing_caches', False):
            logger.info("_clear_cross_tab_caches: Skipping (already clearing)")
            return
        self._clearing_caches = True

        logger.info(f"_clear_cross_tab_caches: Starting (source={type(source).__name__ if source else None})")

        try:
            # Clear Misc spreadsheet cache (only if not the source)
            if hasattr(self, 'misc_cost_spreadsheet') and hasattr(self.misc_cost_spreadsheet, 'model'):
                model = self.misc_cost_spreadsheet.model
                if model != source and hasattr(model, '_evaluated_cache'):
                    logger.info(f"_clear_cross_tab_caches: Clearing Misc cache (had {len(model._evaluated_cache)} entries)")
                    model._evaluated_cache.clear()
                    # Emit dataChanged for all cells to force repaint
                    top_left = model.index(0, 0)
                    bottom_right = model.index(model.rowCount() - 1, model.columnCount() - 1)
                    model.dataChanged.emit(top_left, bottom_right, [Qt.DisplayRole])

            # Clear TotalCost spreadsheet cache (only if not the source)
            if hasattr(self, 'total_cost_spreadsheet') and hasattr(self.total_cost_spreadsheet, 'model'):
                model = self.total_cost_spreadsheet.model
                if model != source and hasattr(model, '_evaluated_cache'):
                    logger.info(f"_clear_cross_tab_caches: Clearing TotalCost cache (had {len(model._evaluated_cache)} entries)")
                    model._evaluated_cache.clear()
                    # Emit dataChanged for all cells to force repaint
                    top_left = model.index(0, 0)
                    bottom_right = model.index(model.rowCount() - 1, model.columnCount() - 1)
                    model.dataChanged.emit(top_left, bottom_right, [Qt.DisplayRole])
        finally:
            self._clearing_caches = False
            logger.info("_clear_cross_tab_caches: Done")

    def _on_misc_data_changed(self):
        """Handle data changes in the Misc Cost spreadsheet - update summary and cache."""
        # Update Total Cost summary
        self._update_total_cost_summary()

        # Mark spreadsheet as dirty in cache (will be saved on bid change or app close)
        if self.current_bid_id and self.current_project_id:
            self._cache_misc_spreadsheet()

    def _on_total_cost_data_changed(self):
        """Handle data changes in the Total Cost spreadsheet - cache for later save."""
        # Mark spreadsheet as dirty in cache (will be saved on bid change or app close)
        if self.current_bid_id and self.current_project_id:
            self._cache_total_cost_spreadsheet()

    def _cache_misc_spreadsheet(self):
        """Cache Misc Cost spreadsheet data for deferred ShotGrid save."""
        if not self.current_bid_id or not self.current_project_id:
            return

        if not hasattr(self, 'misc_cost_spreadsheet'):
            return

        try:
            data_dict = self.misc_cost_spreadsheet.get_data_as_dict()
            if not data_dict:
                return

            cell_meta_dict = self.misc_cost_spreadsheet.model.get_all_cell_meta()
            sheet_meta = self.misc_cost_spreadsheet.model.get_sheet_meta()

            self._spreadsheet_cache.mark_dirty(
                project_id=self.current_project_id,
                bid_id=self.current_bid_id,
                spreadsheet_type="misc",
                data_dict=data_dict,
                cell_meta_dict=cell_meta_dict,
                sheet_meta=sheet_meta
            )
        except Exception as e:
            logger.error(f"Failed to cache Misc spreadsheet: {e}", exc_info=True)

    def _cache_total_cost_spreadsheet(self):
        """Cache Total Cost spreadsheet data for deferred ShotGrid save."""
        if not self.current_bid_id or not self.current_project_id:
            return

        if not hasattr(self, 'total_cost_spreadsheet'):
            return

        try:
            data_dict = self.total_cost_spreadsheet.get_data_as_dict()
            if not data_dict:
                return

            cell_meta_dict = self.total_cost_spreadsheet.model.get_all_cell_meta()
            sheet_meta = self.total_cost_spreadsheet.model.get_sheet_meta()

            self._spreadsheet_cache.mark_dirty(
                project_id=self.current_project_id,
                bid_id=self.current_bid_id,
                spreadsheet_type="total_cost",
                data_dict=data_dict,
                cell_meta_dict=cell_meta_dict,
                sheet_meta=sheet_meta
            )
        except Exception as e:
            logger.error(f"Failed to cache Total Cost spreadsheet: {e}", exc_info=True)

    def _setup_cross_tab_formulas(self):
        """Set up cross-tab formula references between cost sheets."""
        # Create a dictionary of sheet models for cross-tab references
        # Use names with spaces for user-friendly formula references like 'Shot Costs'!A1
        sheet_models = {}

        # Add Shot Costs model (accessible via 'Shot Costs'!ref)
        if hasattr(self, 'shots_cost_widget') and hasattr(self.shots_cost_widget, 'model'):
            sheet_models['Shot Costs'] = self.shots_cost_widget.model

        # Add Asset Costs model (accessible via 'Asset Costs'!ref)
        if hasattr(self, 'asset_cost_widget') and hasattr(self.asset_cost_widget, 'model'):
            sheet_models['Asset Costs'] = self.asset_cost_widget.model

        # Add Misc Costs spreadsheet model
        if hasattr(self, 'misc_cost_spreadsheet') and hasattr(self.misc_cost_spreadsheet, 'model'):
            sheet_models['Misc'] = self.misc_cost_spreadsheet.model

        # Create formula evaluator with cross-tab support
        self.misc_cost_formula_evaluator = FormulaEvaluator(
            table_model=self.misc_cost_spreadsheet.model,
            sheet_models=sheet_models
        )

        # Set the formula evaluator on the spreadsheet
        self.misc_cost_spreadsheet.set_formula_evaluator(self.misc_cost_formula_evaluator)

        # Connect dataChanged signal
        self.misc_cost_spreadsheet.model.dataChanged.connect(self._on_misc_data_changed)

        # Set up formula evaluator for Total Cost Summary spreadsheet
        if hasattr(self, 'total_cost_spreadsheet') and hasattr(self.total_cost_spreadsheet, 'model'):
            # Add Total Cost Summary model to sheet_models
            sheet_models['TotalCost'] = self.total_cost_spreadsheet.model

            # Create formula evaluator with cross-tab support for Total Cost Summary
            self.total_cost_formula_evaluator = FormulaEvaluator(
                table_model=self.total_cost_spreadsheet.model,
                sheet_models=sheet_models
            )

            # Set the formula evaluator on the spreadsheet
            self.total_cost_spreadsheet.set_formula_evaluator(self.total_cost_formula_evaluator)

            # Connect dataChanged signal for Total Cost persistence
            self.total_cost_spreadsheet.model.dataChanged.connect(self._on_total_cost_data_changed)

            logger.info("Set up cross-tab formula references for Total Cost Summary")

        logger.info("Set up cross-tab formula references for all cost sheets")

    def set_bid(self, bid_data, project_id):
        """Set the current bid and update all cost views.

        Args:
            bid_data: Dictionary containing Bid (CustomEntity06) data, or None
            project_id: ID of the project
        """
        logger.info("="*80)
        logger.info(f"COSTS TAB - set_bid() called")
        logger.info(f"  Bid: {bid_data.get('code') if bid_data else 'None'} (ID: {bid_data.get('id') if bid_data else 'None'})")
        logger.info(f"  Project ID: {project_id}")
        if bid_data:
            logger.info(f"  sg_vfx_breakdown in bid_data: {bid_data.get('sg_vfx_breakdown')}")
            logger.info(f"  sg_bid_assets in bid_data: {bid_data.get('sg_bid_assets')}")
        logger.info("="*80)

        # Commit cached spreadsheet changes for the previous bid before switching
        if self.current_bid_id and self._spreadsheet_cache.has_dirty_spreadsheets():
            logger.info(f"Committing cached spreadsheet changes for bid {self.current_bid_id} before switching...")
            self._spreadsheet_cache.commit_for_bid(self.current_bid_id, parent_widget=self)

        # Clear custom spreadsheets from previous bid
        self._clear_custom_spreadsheets()

        self.current_bid_data = bid_data
        self.current_bid_id = bid_data.get('id') if bid_data else None
        self.current_project_id = project_id

        # Get currency symbol and position from bid data (ShotGrid sg_currency field)
        # Format is "symbol+before" or "symbol+after"
        default_symbol = self.app_settings.get_currency() if self.app_settings else "$"
        sg_currency_value = bid_data.get("sg_currency") if bid_data else None
        currency_symbol, currency_position = parse_sg_currency(sg_currency_value, default_symbol or "$")

        # Update bid_id and currency symbol on totals wrappers
        if hasattr(self, 'shots_cost_totals_wrapper'):
            self.shots_cost_totals_wrapper.set_bid_id(self.current_bid_id)
            self.shots_cost_totals_wrapper.set_currency_symbol(currency_symbol)
        if hasattr(self, 'asset_cost_totals_wrapper'):
            self.asset_cost_totals_wrapper.set_bid_id(self.current_bid_id)
            self.asset_cost_totals_wrapper.set_currency_symbol(currency_symbol)

        # Update currency settings on spreadsheet widgets
        if hasattr(self, 'misc_cost_spreadsheet'):
            self.misc_cost_spreadsheet.set_currency_settings(currency_symbol, currency_position)
        if hasattr(self, 'total_cost_spreadsheet'):
            self.total_cost_spreadsheet.set_currency_settings(currency_symbol, currency_position)

        # Update read-only linked entity references for cost widgets
        # Need to fetch full entity data since link fields only contain type/id
        if hasattr(self, 'shots_cost_widget'):
            vfx_breakdown = bid_data.get("sg_vfx_breakdown") if bid_data else None
            if vfx_breakdown and isinstance(vfx_breakdown, dict) and vfx_breakdown.get("id"):
                # Fetch the VFX Breakdown entity to get its code/name
                try:
                    breakdown_data = self.sg_session.sg.find_one(
                        vfx_breakdown.get("type", "CustomEntity01"),
                        [["id", "is", vfx_breakdown["id"]]],
                        ["code", "id"]
                    )
                    self.shots_cost_widget.set_readonly_linked_entity(breakdown_data)
                except Exception as e:
                    logger.warning(f"Failed to fetch VFX Breakdown details: {e}")
                    self.shots_cost_widget.set_readonly_linked_entity(vfx_breakdown)
            else:
                self.shots_cost_widget.set_readonly_linked_entity(None)

        if hasattr(self, 'asset_cost_widget'):
            bid_assets = bid_data.get("sg_bid_assets") if bid_data else None
            if bid_assets and isinstance(bid_assets, dict) and bid_assets.get("id"):
                # Fetch the Bid Assets entity to get its code/name
                try:
                    assets_data = self.sg_session.sg.find_one(
                        bid_assets.get("type", "CustomEntity08"),
                        [["id", "is", bid_assets["id"]]],
                        ["code", "id"]
                    )
                    self.asset_cost_widget.set_readonly_linked_entity(assets_data)
                except Exception as e:
                    logger.warning(f"Failed to fetch Bid Assets details: {e}")
                    self.asset_cost_widget.set_readonly_linked_entity(bid_assets)
            else:
                self.asset_cost_widget.set_readonly_linked_entity(None)

        if bid_data and project_id:
            # Load Line Items first - needed for both VFX breakdown and asset cost pricing
            logger.info("Loading Line Items for pricing...")
            self._load_line_item_names()
            self._load_line_items_with_prices()
            logger.info(f"Loaded {len(self.line_item_names)} line item names")
            logger.info(f"Loaded {len(self.line_items_price_map)} line item prices")

            # Load VFX Breakdown linked to this bid into Shots Cost widget
            self._load_vfx_breakdown_for_bid(bid_data)

            # Refresh other cost views
            logger.info("About to refresh Asset Cost...")
            self._refresh_asset_cost()
            logger.info("Finished refreshing Asset Cost")
            self._refresh_total_cost()

            # Load Misc spreadsheet data from ShotGrid
            logger.info("Loading Misc spreadsheet data...")
            self._load_misc_spreadsheet_from_shotgrid()

            # Load Total Cost spreadsheet data from ShotGrid
            logger.info("Loading Total Cost spreadsheet data...")
            self._load_total_cost_spreadsheet_from_shotgrid()

            # Load custom spreadsheets for this bid
            logger.info("Loading custom spreadsheets...")
            self._load_custom_spreadsheets_for_bid()

            # Update Total Cost summary with initial totals
            QtCore.QTimer.singleShot(100, self._update_total_cost_summary)
        else:
            # Clear all cost views
            if hasattr(self, 'shots_cost_widget'):
                self.shots_cost_widget.load_bidding_scenes([])
                self.shots_cost_widget.set_readonly_linked_entity(None)
            if hasattr(self, 'asset_cost_widget'):
                self.asset_cost_widget.load_bidding_scenes([])
                self.asset_cost_widget.set_readonly_linked_entity(None)
            # Initialize Misc spreadsheet with defaults (empty)
            self._initialize_misc_spreadsheet_defaults()
            # Initialize Total Cost spreadsheet with defaults
            self._initialize_total_cost_spreadsheet_defaults()

    def refresh_for_rate_card_change(self):
        """Refresh all cost tables when the rate card changes.

        This is an optimized refresh that only reloads the line item prices
        (which are calculated from the rate card) and updates the displays,
        without reloading all entity data from ShotGrid.
        """
        if not self.current_bid_data or not self.current_project_id:
            logger.warning("Cannot refresh for rate card change - no bid data")
            return

        logger.info("=" * 80)
        logger.info("COSTS TAB - Refreshing for Rate Card change")
        logger.info("=" * 80)

        # Step 1: Reload line item prices (these use the rate card for calculations)
        logger.info("Step 1: Reloading line item prices...")
        self._load_line_items_with_prices()
        logger.info(f"  Reloaded {len(self.line_items_price_map)} line item prices")

        # Step 2: Update the line item price column in Shots Cost widget
        # This updates the virtual _line_item_price column used in _calc_price formula
        if hasattr(self, 'shots_cost_widget') and self.shots_cost_widget.model:
            logger.info("Step 2: Updating Shots Cost prices...")
            model = self.shots_cost_widget.model
            # Update line item prices in existing data without reloading
            # Uses all_bidding_scenes_data (the model's data storage)
            for row_idx, row_data in enumerate(model.all_bidding_scenes_data):
                if row_data:
                    # sg_vfx_shot_work is the line item code (text), used to look up price
                    vfx_shot_work = row_data.get("sg_vfx_shot_work")
                    if vfx_shot_work and vfx_shot_work in self.line_items_price_map:
                        row_data["_line_item_price"] = self.line_items_price_map[vfx_shot_work]
                        logger.info(f"  Updated row {row_idx}: {vfx_shot_work} -> price {self.line_items_price_map[vfx_shot_work]}")
            # Notify view to refresh
            model.layoutChanged.emit()
            logger.info(f"  Updated {len(model.all_bidding_scenes_data)} rows in Shots Cost model")

        # Step 3: Refresh Asset Cost (recalculates prices based on new line item prices)
        logger.info("Step 3: Refreshing Asset Cost...")
        self._refresh_asset_cost()

        # Step 4: Recalculate totals in both wrappers
        logger.info("Step 4: Recalculating totals...")
        if hasattr(self, 'shots_cost_totals_wrapper') and hasattr(self, 'shots_cost_widget'):
            if hasattr(self.shots_cost_widget, 'model') and self.shots_cost_widget.model:
                try:
                    price_col_idx = self.shots_cost_widget.model.column_fields.index("_calc_price")
                    self.shots_cost_totals_wrapper.calculate_totals(columns=[price_col_idx], skip_first_col=True)
                except (ValueError, AttributeError):
                    pass

        if hasattr(self, 'asset_cost_totals_wrapper') and hasattr(self, 'asset_cost_widget'):
            if hasattr(self.asset_cost_widget, 'model') and self.asset_cost_widget.model:
                try:
                    price_col_idx = self.asset_cost_widget.model.column_fields.index("_calc_price")
                    self.asset_cost_totals_wrapper.calculate_totals(columns=[price_col_idx], skip_first_col=True)
                except (ValueError, AttributeError):
                    pass

        # Step 5: Update Total Cost summary
        logger.info("Step 5: Updating Total Cost summary...")
        self._update_total_cost_summary()

        logger.info("Rate Card refresh complete")
        logger.info("=" * 80)

    def refresh_currency_formatting(self, sg_currency_value=None):
        """Refresh currency formatting in all cost tables.

        Call this method when currency settings have changed to update
        all displayed values with the new currency symbol and position.

        Args:
            sg_currency_value: Combined currency value (e.g., "$+before"). If None, uses current bid data.
        """
        logger.info("Refreshing currency formatting in Costs tab")

        # Get sg_currency value from parameter or current bid data
        if sg_currency_value is None:
            if self.current_bid_data:
                sg_currency_value = self.current_bid_data.get("sg_currency")

        # Parse the combined format (symbol+position)
        default_symbol = self.app_settings.get_currency() if self.app_settings else "$"
        currency_symbol, currency_position = parse_sg_currency(sg_currency_value, default_symbol or "$")

        # Update sg_currency in current_bid_data for _format_currency
        if self.current_bid_data and sg_currency_value:
            self.current_bid_data["sg_currency"] = sg_currency_value

        # Update currency symbol on formula delegates (for Price columns)
        if self.shots_cost_formula_delegate:
            self.shots_cost_formula_delegate.set_currency_symbol(currency_symbol, currency_position)
        if self.asset_cost_formula_delegate:
            self.asset_cost_formula_delegate.set_currency_symbol(currency_symbol, currency_position)

        # Update currency symbol on wrappers (for totals bar)
        if hasattr(self, 'shots_cost_totals_wrapper'):
            self.shots_cost_totals_wrapper.set_currency_symbol(currency_symbol)
        if hasattr(self, 'asset_cost_totals_wrapper'):
            self.asset_cost_totals_wrapper.set_currency_symbol(currency_symbol)

        # Update currency settings on spreadsheet widgets
        if hasattr(self, 'misc_cost_spreadsheet'):
            self.misc_cost_spreadsheet.set_currency_settings(currency_symbol, currency_position)
        if hasattr(self, 'total_cost_spreadsheet'):
            self.total_cost_spreadsheet.set_currency_settings(currency_symbol, currency_position)

        # Recalculate totals in Shots Cost wrapper (will use updated currency)
        if hasattr(self, 'shots_cost_totals_wrapper') and hasattr(self, 'shots_cost_widget'):
            if hasattr(self.shots_cost_widget, 'model') and self.shots_cost_widget.model:
                try:
                    price_col_idx = self.shots_cost_widget.model.column_fields.index("_calc_price")
                    self.shots_cost_totals_wrapper.calculate_totals(columns=[price_col_idx], skip_first_col=True)
                    # Force repaint of the Price column
                    self.shots_cost_widget.table_view.viewport().update()
                except (ValueError, AttributeError):
                    pass

        # Recalculate totals in Asset Cost wrapper (will use updated currency)
        if hasattr(self, 'asset_cost_totals_wrapper') and hasattr(self, 'asset_cost_widget'):
            if hasattr(self.asset_cost_widget, 'model') and self.asset_cost_widget.model:
                try:
                    price_col_idx = self.asset_cost_widget.model.column_fields.index("_calc_price")
                    self.asset_cost_totals_wrapper.calculate_totals(columns=[price_col_idx], skip_first_col=True)
                    # Force repaint of the Price column
                    self.asset_cost_widget.table_view.viewport().update()
                except (ValueError, AttributeError):
                    pass

        # Update Total Cost summary with new currency formatting
        self._update_total_cost_summary()

        logger.info("Currency formatting refreshed")

    def _load_vfx_breakdown_for_bid(self, bid_data):
        """Load VFX Breakdown scenes linked to the bid.

        Args:
            bid_data: Dictionary containing Bid data
        """
        logger.info(f"COSTS TAB - Loading VFX Breakdown...")

        # Get the linked VFX Breakdown from the bid
        vfx_breakdown = bid_data.get("sg_vfx_breakdown")
        logger.info(f"  Raw sg_vfx_breakdown value: {vfx_breakdown}")
        logger.info(f"  Type: {type(vfx_breakdown)}")

        if not vfx_breakdown:
            logger.warning("  ❌ No VFX Breakdown linked to this bid")
            logger.warning("  Please link a VFX Breakdown to this Bid in ShotGrid")
            self.shots_cost_widget.load_bidding_scenes([])
            return

        # Extract breakdown ID
        breakdown_id = None
        if isinstance(vfx_breakdown, dict):
            breakdown_id = vfx_breakdown.get('id')
            logger.info(f"  VFX Breakdown is dict, extracted ID: {breakdown_id}")
        elif isinstance(vfx_breakdown, list) and vfx_breakdown:
            breakdown_id = vfx_breakdown[0].get('id') if isinstance(vfx_breakdown[0], dict) else None
            logger.info(f"  VFX Breakdown is list, extracted ID: {breakdown_id}")
        else:
            logger.warning(f"  Unexpected VFX Breakdown type: {type(vfx_breakdown)}")

        if not breakdown_id:
            logger.warning("  ❌ Invalid VFX Breakdown data - could not extract ID")
            self.shots_cost_widget.load_bidding_scenes([])
            return

        logger.info(f"  ✓ Found VFX Breakdown ID: {breakdown_id}")

        try:
            # Bidding Scenes (CustomEntity02) link TO the VFX Breakdown via sg_parent field
            # Use the ShotGrid session method to query bidding scenes by parent
            logger.info(f"  Fetching bidding scenes where sg_parent = VFX Breakdown {breakdown_id}...")

            # Get field schema for CustomEntity02 (Bidding Scenes)
            raw_schema = self.sg_session.sg.schema_field_read("CustomEntity02")

            # Build field_schema dict and display_names dict (like VFXBreakdownTab does)
            field_schema = {}
            display_names = {}

            for field_name, field_info in raw_schema.items():
                data_type = field_info.get("data_type", {})
                properties = field_info.get("properties", {})

                field_schema[field_name] = {
                    "data_type": data_type.get("value") if isinstance(data_type, dict) else data_type,
                    "properties": properties
                }

                # Extract display name
                name_info = field_info.get("name", {})
                if isinstance(name_info, dict):
                    display_name = name_info.get("value", field_name)
                else:
                    display_name = name_info or field_name
                display_names[field_name] = display_name

                # Extract list values if it's a list field
                if field_schema[field_name]["data_type"] == "list":
                    valid_values = properties.get("valid_values", {})
                    if isinstance(valid_values, dict):
                        list_values = list(valid_values.get("value", []))
                    else:
                        list_values = []
                    field_schema[field_name]["list_values"] = list_values

            # Override display name for 'id' field to show 'SG ID'
            if "id" in display_names:
                display_names["id"] = "SG ID"

            # Add virtual columns for price calculation
            field_schema["_line_item_price"] = {
                "data_type": "number",
                "properties": {}
            }
            display_names["_line_item_price"] = "Line Item Price"

            field_schema["_calc_price"] = {
                "data_type": "text",
                "properties": {}
            }
            display_names["_calc_price"] = "Price"

            # Define fields to fetch (matches VFXBreakdownModel.column_fields)
            fields_to_fetch = [
                "id", "code", "sg_bid_assets", "sg_sequence_code", "sg_vfx_breakdown_scene",
                "sg_interior_exterior", "sg_number_of_shots", "sg_on_set_vfx_needs",
                "sg_page_eights", "sg_previs", "sg_script_excerpt", "sg_set", "sg_sim",
                "sg_sorting_priority", "sg_team_notes", "sg_time_of_day", "sg_unit",
                "sg_vfx_assumptions", "sg_vfx_description", "sg_vfx_questions",
                "sg_vfx_supervisor_notes", "sg_vfx_type", "sg_vfx_shot_work",
            ]

            # Use the ShotGrid session helper method to get bidding scenes for this VFX Breakdown
            # This queries bidding scenes WHERE sg_parent = VFX Breakdown
            bidding_scenes_data = self.sg_session.get_bidding_scenes_for_vfx_breakdown(
                breakdown_id,
                fields=fields_to_fetch
            )

            logger.info(f"  ✓ Fetched {len(bidding_scenes_data)} bidding scenes from ShotGrid")

            if not bidding_scenes_data:
                logger.info("  ℹ No bidding scenes found for this VFX Breakdown")
                self.shots_cost_widget.load_bidding_scenes([])
                return

            # Line Items are loaded in set_bid() before this method is called
            # Populate virtual price columns for each bidding scene
            for scene in bidding_scenes_data:
                vfx_shot_work = scene.get("sg_vfx_shot_work")
                est_cuts = scene.get("sg_number_of_shots", 0) or 0

                # Look up Line Item price by code
                line_item_price = 0
                if vfx_shot_work and vfx_shot_work in self.line_items_price_map:
                    line_item_price = self.line_items_price_map[vfx_shot_work]

                # Store Line Item price in hidden column
                scene["_line_item_price"] = line_item_price

                # Create formula for Price column: =sg_number_of_shots * _line_item_price
                scene["_calc_price"] = f"=sg_number_of_shots * _line_item_price"

            logger.info(f"  ✓ Populated price columns for {len(bidding_scenes_data)} scenes")

            # Ensure sg_vfx_shot_work is not in column_dropdowns to prevent delegate conflicts
            if hasattr(self.shots_cost_widget, 'column_dropdowns'):
                if 'sg_vfx_shot_work' in self.shots_cost_widget.column_dropdowns:
                    self.shots_cost_widget.column_dropdowns['sg_vfx_shot_work'] = False
                    logger.info("  ✓ Disabled dropdown for sg_vfx_shot_work to prevent delegate conflicts")

            # Load into the VFXBreakdownWidget
            self.shots_cost_widget.load_bidding_scenes(bidding_scenes_data, field_schema=field_schema)
            logger.info(f"  ✓ Loaded bidding scenes into Shots Cost table")

            # Set the display names on the model AFTER loading data
            if hasattr(self.shots_cost_widget, 'model'):
                # Add virtual columns to the model's column_fields
                columns_added = []
                if "_line_item_price" not in self.shots_cost_widget.model.column_fields:
                    self.shots_cost_widget.model.column_fields.append("_line_item_price")
                    columns_added.append("_line_item_price")
                if "_calc_price" not in self.shots_cost_widget.model.column_fields:
                    self.shots_cost_widget.model.column_fields.append("_calc_price")
                    columns_added.append("_calc_price")
                logger.info(f"  ✓ Added virtual price columns to model")

                # Notify the view that the model structure changed
                if columns_added:
                    self.shots_cost_widget.model.layoutChanged.emit()
                    logger.info(f"  ✓ Emitted layoutChanged signal for {len(columns_added)} new columns")

                # Set default widths for the new columns before updating totals bar
                if columns_added:
                    for col_name in columns_added:
                        col_idx = self.shots_cost_widget.model.column_fields.index(col_name)
                        # Set a reasonable default width (100 pixels)
                        self.shots_cost_widget.table_view.setColumnWidth(col_idx, 100)
                        logger.info(f"  ✓ Set width for column {col_name} (index {col_idx})")

                # Hide the _line_item_price column (needed for calculations but not visible)
                if "_line_item_price" in self.shots_cost_widget.model.column_fields:
                    line_item_col_idx = self.shots_cost_widget.model.column_fields.index("_line_item_price")
                    self.shots_cost_widget.table_view.setColumnHidden(line_item_col_idx, True)
                    logger.info(f"  ✓ Hidden _line_item_price column (index {line_item_col_idx})")

                # Update totals bar to reflect new column count
                if hasattr(self, 'shots_cost_totals_wrapper'):
                    self.shots_cost_totals_wrapper.update_column_count()
                    logger.info(f"  ✓ Updated totals bar column count")

                # Force viewport update to ensure new columns are immediately visible
                if columns_added:
                    self.shots_cost_widget.table_view.viewport().update()
                    self.shots_cost_widget.table_view.horizontalHeader().viewport().update()
                    logger.info(f"  ✓ Forced viewport update for new columns")

                # Make Price column read-only
                if "_calc_price" not in self.shots_cost_widget.model.readonly_columns:
                    self.shots_cost_widget.model.readonly_columns.append("_calc_price")
                    logger.info("  ✓ Set _calc_price column as read-only")

                self.shots_cost_widget.model.set_column_headers(display_names)
                logger.info(f"  ✓ Set {len(display_names)} column headers with display names")
                # Log a few examples
                examples = list(display_names.items())[:5]
                logger.info(f"     Examples: {examples}")

                # Create FormulaEvaluator for the VFX Breakdown model
                self.vfx_breakdown_formula_evaluator = FormulaEvaluator(
                    self.shots_cost_widget.model
                )
                # Set the formula evaluator on the model for dependency tracking
                self.shots_cost_widget.model.set_formula_evaluator(self.vfx_breakdown_formula_evaluator)
                logger.info("  ✓ Created FormulaEvaluator for VFX Breakdown")

                # Apply FormulaDelegate to the Price column
                price_col_index = self.shots_cost_widget.model.column_fields.index("_calc_price")
                self.shots_cost_formula_delegate = FormulaDelegate(self.vfx_breakdown_formula_evaluator, app_settings=self.app_settings)
                # Set currency symbol and position from bid data (sg_currency field)
                if self.current_bid_data:
                    default_symbol = self.app_settings.get_currency() or "$"
                    sg_currency_value = self.current_bid_data.get("sg_currency")
                    currency_symbol, currency_position = parse_sg_currency(sg_currency_value, default_symbol)
                    self.shots_cost_formula_delegate.set_currency_symbol(currency_symbol, currency_position)
                self.shots_cost_widget.table_view.setItemDelegateForColumn(price_col_index, self.shots_cost_formula_delegate)
                logger.info(f"  ✓ Applied FormulaDelegate to Price column (index {price_col_index})")

                # Configure totals bar for Price column
                if hasattr(self, 'shots_cost_totals_wrapper'):
                    # Set formula evaluator on totals wrapper for formula evaluation
                    self.shots_cost_totals_wrapper.set_formula_evaluator(self.vfx_breakdown_formula_evaluator)
                    logger.info(f"  ✓ Set formula evaluator on totals wrapper")

                    # Mark Price column as blue
                    self.shots_cost_totals_wrapper.set_blue_columns([price_col_index])

                    # Calculate totals only for Price column (formulas will be evaluated)
                    self.shots_cost_totals_wrapper.calculate_totals(columns=[price_col_index], skip_first_col=True)
                    logger.info(f"  ✓ Configured totals bar for Price column (index {price_col_index})")

                # Connect model dataChanged signal to update Total Cost summary
                self.shots_cost_widget.model.dataChanged.connect(self._on_shots_data_changed)
                logger.info(f"  ✓ Connected shots model dataChanged signal to Total Cost summary update")

                # Force the header view to update
                if hasattr(self.shots_cost_widget, 'table_view'):
                    self.shots_cost_widget.table_view.horizontalHeader().viewport().update()
                    logger.info(f"  ✓ Forced header view update")

            logger.info("="*80)

            # Apply VFX Shot Work delegate
            self._apply_vfx_shot_work_delegate()

        except Exception as e:
            logger.error(f"Failed to load VFX Breakdown scenes: {e}", exc_info=True)
            self.shots_cost_widget.load_bidding_scenes([])

    def _load_line_item_names(self):
        """Load Line Item names from the current Bid's Price List for VFX Shot Work validation."""
        if not self.current_bid_data or not self.current_bid_data.get('id'):
            self.line_item_names = []
            return

        try:
            bid_id = self.current_bid_data['id']

            # Query the Bid to get its Price List (sg_price_list)
            bid_data = self.sg_session.sg.find_one(
                "CustomEntity06",
                [["id", "is", bid_id]],
                ["sg_price_list"]
            )

            if not bid_data or not bid_data.get("sg_price_list"):
                logger.info("No Price List linked to current Bid")
                self.line_item_names = []
                return

            price_list_id = bid_data["sg_price_list"]["id"]

            # Query the Price List to get its linked Line Items
            price_list_data = self.sg_session.sg.find_one(
                "CustomEntity10",
                [["id", "is", price_list_id]],
                ["sg_line_items"]
            )

            if not price_list_data or not price_list_data.get("sg_line_items"):
                logger.info(f"No Line Items linked to Price List {price_list_id}")
                self.line_item_names = []
                return

            # Extract Line Item IDs from sg_line_items field
            line_item_refs = price_list_data["sg_line_items"]
            if not isinstance(line_item_refs, list):
                logger.warning(f"sg_line_items is not a list: {type(line_item_refs)}")
                self.line_item_names = []
                return

            line_item_ids = [item.get("id") for item in line_item_refs if isinstance(item, dict) and item.get("id")]

            if not line_item_ids:
                logger.info(f"No valid Line Item IDs found in Price List {price_list_id}")
                self.line_item_names = []
                return

            # Query Line Items by IDs to get their code names
            line_items = self.sg_session.sg.find(
                "CustomEntity03",
                [["id", "in", line_item_ids]],
                ["code"]
            )

            # Extract code names
            self.line_item_names = [item.get("code", "") for item in line_items if item.get("code")]

        except Exception as e:
            logger.error(f"Failed to load Line Items for VFX Shot Work: {e}", exc_info=True)
            self.line_item_names = []

    def _load_line_items_with_prices(self):
        """Load Line Items with their calculated prices for the current Bid's Price List.

        Price resolution order:
        1. sg_price_static (snapshot/static price) - preferred
        2. sg_price (calculated price)
        3. Calculate from mandays × rates (fallback)

        This populates:
        - self.line_items_data: Full Line Item records
        - self.line_items_price_map: Dict mapping Line Item code to calculated price
        """
        self.line_items_data = []
        self.line_items_price_map = {}

        if not self.current_bid_data or not self.current_bid_data.get('id'):
            return

        try:
            bid_id = self.current_bid_data['id']

            # Query the Bid to get its Price List (sg_price_list)
            bid_data = self.sg_session.sg.find_one(
                "CustomEntity06",
                [["id", "is", bid_id]],
                ["sg_price_list"]
            )

            if not bid_data or not bid_data.get("sg_price_list"):
                logger.info("No Price List linked to current Bid")
                return

            price_list_id = bid_data["sg_price_list"]["id"]

            # Query the Price List to get its linked Line Items and Rate Card
            price_list_data = self.sg_session.sg.find_one(
                "CustomEntity10",
                [["id", "is", price_list_id]],
                ["sg_line_items", "sg_rate_card"]
            )

            if not price_list_data or not price_list_data.get("sg_line_items"):
                logger.info(f"No Line Items linked to Price List {price_list_id}")
                return

            # Extract Line Item IDs from sg_line_items field
            line_item_refs = price_list_data["sg_line_items"]
            if not isinstance(line_item_refs, list):
                logger.warning(f"sg_line_items is not a list: {type(line_item_refs)}")
                return

            line_item_ids = [item.get("id") for item in line_item_refs if isinstance(item, dict) and item.get("id")]

            if not line_item_ids:
                logger.info(f"No valid Line Item IDs found in Price List {price_list_id}")
                return

            # Get all mandays fields from schema
            schema = self.sg_session.sg.schema_field_read("CustomEntity03")
            mandays_fields = [field for field in schema.keys() if field.endswith("_mandays")]

            # Query Line Items with all mandays fields
            fields_to_fetch = ["id", "code"] + mandays_fields

            # Fetch sg_price_static for the static/snapshot price value
            if "sg_price_static" in schema:
                fields_to_fetch.append("sg_price_static")

            # Also fetch sg_price if it exists (for calculated prices)
            if "sg_price" in schema:
                fields_to_fetch.append("sg_price")

            line_items = self.sg_session.sg.find(
                "CustomEntity03",
                [["id", "in", line_item_ids]],
                fields_to_fetch
            )

            if not line_items:
                logger.info(f"No Line Items found for IDs: {line_item_ids}")
                return

            # Load Rate Card data if available
            rate_card_data = None
            if price_list_data.get("sg_rate_card"):
                rate_card_id = price_list_data["sg_rate_card"]["id"]
                rate_fields = [field for field in schema.keys() if field.endswith("_rate")]

                rate_card_schema = self.sg_session.sg.schema_field_read("CustomEntity04")
                rate_fields = [field for field in rate_card_schema.keys() if field.endswith("_rate")]

                if rate_fields:
                    rate_card_data = self.sg_session.sg.find_one(
                        "CustomEntity04",
                        [["id", "is", rate_card_id]],
                        rate_fields
                    )
                    logger.info(f"Loaded Rate Card {rate_card_id} with {len(rate_fields)} rate fields")

            # Calculate prices for each Line Item
            for item in line_items:
                code = item.get("code", "")

                # First priority: Use sg_price_static (snapshot price)
                calculated_price = item.get("sg_price_static", 0) or 0

                # Second priority: Use sg_price if sg_price_static is not available
                if calculated_price == 0:
                    calculated_price = item.get("sg_price", 0) or 0

                # Third priority: Calculate from mandays × rates
                if calculated_price == 0 and rate_card_data:
                    total_price = 0
                    for mandays_field in mandays_fields:
                        # Extract discipline name (e.g., "sg_model_mandays" -> "model")
                        discipline = mandays_field.replace("sg_", "").replace("_mandays", "")
                        rate_field = f"sg_{discipline}_rate"

                        mandays = item.get(mandays_field, 0) or 0
                        rate = rate_card_data.get(rate_field, 0) or 0

                        total_price += mandays * rate

                    calculated_price = total_price

                # Store in price map
                if code:
                    self.line_items_price_map[code] = calculated_price

                # Add to data list
                self.line_items_data.append(item)

        except Exception as e:
            logger.error(f"Failed to load Line Items with prices: {e}", exc_info=True)
            self.line_items_data = []
            self.line_items_price_map = {}

    def _apply_vfx_shot_work_delegate(self):
        """Apply ValidatedComboBoxDelegate to the sg_vfx_shot_work column."""
        if not self.shots_cost_widget or not hasattr(self.shots_cost_widget, 'table_view'):
            logger.warning("shots_cost_widget or table_view not available")
            return

        try:
            # Find the column index for sg_vfx_shot_work
            if hasattr(self.shots_cost_widget, 'model') and self.shots_cost_widget.model:
                try:
                    col_idx = self.shots_cost_widget.model.column_fields.index("sg_vfx_shot_work")
                except ValueError:
                    # Column not present
                    return

                # Create or update the delegate with purple color for Costs panel
                if self.vfx_shot_work_delegate is None:
                    self.vfx_shot_work_delegate = ValidatedComboBoxDelegate(
                        self.line_item_names,
                        self.shots_cost_widget.table_view,
                        valid_color="#6b5b95"  # Purple for Costs panel
                    )
                    self.shots_cost_widget.table_view.setItemDelegateForColumn(col_idx, self.vfx_shot_work_delegate)

                    # Protect delegate from being removed by _apply_column_dropdowns
                    # Store it in the widget's _dropdown_delegates dict
                    if hasattr(self.shots_cost_widget, '_dropdown_delegates'):
                        self.shots_cost_widget._dropdown_delegates['sg_vfx_shot_work'] = self.vfx_shot_work_delegate

                    # Force a complete repaint of the table
                    self.shots_cost_widget.table_view.viewport().update()
                else:
                    # Update existing delegate with new Line Item names
                    self.vfx_shot_work_delegate.update_valid_values(self.line_item_names)

                    # Ensure delegate is still protected
                    if hasattr(self.shots_cost_widget, '_dropdown_delegates'):
                        self.shots_cost_widget._dropdown_delegates['sg_vfx_shot_work'] = self.vfx_shot_work_delegate

                    # Force a complete repaint of the table
                    self.shots_cost_widget.table_view.viewport().update()

        except Exception as e:
            logger.error(f"Failed to apply VFX Shot Work delegate: {e}", exc_info=True)

    def _load_asset_items_for_bid(self, bid_data):
        """Load Asset items (CustomEntity07) linked to the Bid Assets.

        Args:
            bid_data: Dictionary containing Bid data
        """
        logger.info("="*80)
        logger.info(f"COSTS TAB - Loading Asset items...")
        logger.info(f"  Bid data keys: {list(bid_data.keys())}")

        # Get the linked Bid Assets from the bid
        bid_assets = bid_data.get("sg_bid_assets")
        logger.info(f"  Raw sg_bid_assets value: {bid_assets}")
        logger.info(f"  Type: {type(bid_assets)}")

        if not bid_assets:
            logger.warning("  ❌ No Bid Assets linked to this bid")
            logger.warning("  Please link Bid Assets to this Bid in ShotGrid")
            logger.warning("  Clearing Asset Cost table")
            if hasattr(self, 'asset_cost_widget'):
                self.asset_cost_widget.load_bidding_scenes([])
            return

        # Extract Bid Assets ID
        bid_assets_id = None
        if isinstance(bid_assets, dict):
            bid_assets_id = bid_assets.get('id')
            logger.info(f"  Bid Assets is dict, extracted ID: {bid_assets_id}")
        elif isinstance(bid_assets, list) and bid_assets:
            bid_assets_id = bid_assets[0].get('id') if isinstance(bid_assets[0], dict) else None
            logger.info(f"  Bid Assets is list, extracted ID: {bid_assets_id}")
        else:
            logger.warning(f"  Unexpected Bid Assets type: {type(bid_assets)}")

        if not bid_assets_id:
            logger.warning("  ❌ Invalid Bid Assets data - could not extract ID")
            self.asset_cost_widget.load_bidding_scenes([])
            return

        logger.info(f"  ✓ Found Bid Assets ID: {bid_assets_id}")

        try:
            # Get field schema for CustomEntity07 (Asset items)
            raw_schema = self.sg_session.sg.schema_field_read("CustomEntity07")

            # Build field_schema dict and display_names dict
            field_schema = {}
            display_names = {}

            for field_name, field_info in raw_schema.items():
                data_type = field_info.get("data_type", {})
                properties = field_info.get("properties", {})

                field_schema[field_name] = {
                    "data_type": data_type.get("value") if isinstance(data_type, dict) else data_type,
                    "properties": properties
                }

                # Extract display name
                name_info = field_info.get("name", {})
                if isinstance(name_info, dict):
                    display_name = name_info.get("value", field_name)
                else:
                    display_name = name_info or field_name
                display_names[field_name] = display_name

                # Extract list values if it's a list field
                if field_schema[field_name]["data_type"] == "list":
                    valid_values = properties.get("valid_values", {})
                    if isinstance(valid_values, dict):
                        list_values = list(valid_values.get("value", []))
                    else:
                        list_values = []
                    field_schema[field_name]["list_values"] = list_values

            # Override display name for 'id' field to show 'SG ID'
            if "id" in display_names:
                display_names["id"] = "SG ID"

            # Add virtual columns for price calculation
            field_schema["_line_item_price"] = {
                "data_type": "number",
                "properties": {}
            }
            display_names["_line_item_price"] = "Line Item Price"

            field_schema["_calc_price"] = {
                "data_type": "text",
                "properties": {}
            }
            display_names["_calc_price"] = "Price"

            # Define fields to fetch for Asset items
            fields_to_fetch = [
                "id", "code", "sg_bid_asset_type", "sg_bidding_notes"
            ]

            # Query CustomEntity07 (Asset items) linked to this Bid Assets
            logger.info(f"  Fetching asset items where sg_bid_assets = {bid_assets_id}...")
            asset_items_data = self.sg_session.sg.find(
                "CustomEntity07",
                [["sg_bid_assets", "is", {"type": "CustomEntity08", "id": bid_assets_id}]],
                fields_to_fetch
            )

            logger.info(f"  ✓ Fetched {len(asset_items_data)} asset items from ShotGrid")

            if not asset_items_data:
                logger.info("  ℹ No asset items found for this Bid Assets")
                self.asset_cost_widget.load_bidding_scenes([])
                return

            # Populate virtual price columns for each asset item
            for asset in asset_items_data:
                asset_type = asset.get("sg_bid_asset_type")

                # Look up Line Item price by code
                line_item_price = 0
                if asset_type and asset_type in self.line_items_price_map:
                    line_item_price = self.line_items_price_map[asset_type]

                # Store Line Item price in hidden column
                asset["_line_item_price"] = line_item_price

                # Create formula for Price column: =_line_item_price (for assets, it's just the line item price)
                asset["_calc_price"] = f"=_line_item_price"

            logger.info(f"  ✓ Populated price columns for {len(asset_items_data)} assets")

            # Ensure sg_bid_asset_type is not in column_dropdowns to prevent delegate conflicts
            if hasattr(self.asset_cost_widget, 'column_dropdowns'):
                if 'sg_bid_asset_type' in self.asset_cost_widget.column_dropdowns:
                    self.asset_cost_widget.column_dropdowns['sg_bid_asset_type'] = False
                    logger.info("  ✓ Disabled dropdown for sg_bid_asset_type to prevent delegate conflicts")

            # Load into the VFXBreakdownWidget
            self.asset_cost_widget.load_bidding_scenes(asset_items_data, field_schema=field_schema)
            logger.info(f"  ✓ Loaded asset items into Asset Cost table")

            # Set the display names on the model AFTER loading data
            if hasattr(self.asset_cost_widget, 'model'):
                # Update totals bar to reflect column count
                if hasattr(self, 'asset_cost_totals_wrapper'):
                    self.asset_cost_totals_wrapper.update_column_count()
                    logger.info(f"  ✓ Updated totals bar column count")

                # Make Price column read-only
                if "_calc_price" not in self.asset_cost_widget.model.readonly_columns:
                    self.asset_cost_widget.model.readonly_columns.append("_calc_price")
                    logger.info("  ✓ Set _calc_price column as read-only")

                self.asset_cost_widget.model.set_column_headers(display_names)
                logger.info(f"  ✓ Set {len(display_names)} column headers with display names")

                # Hide the _line_item_price column (needed for calculations but not visible)
                if "_line_item_price" in self.asset_cost_widget.model.column_fields:
                    line_item_col_idx = self.asset_cost_widget.model.column_fields.index("_line_item_price")
                    self.asset_cost_widget.table_view.setColumnHidden(line_item_col_idx, True)
                    logger.info(f"  ✓ Hidden _line_item_price column (index {line_item_col_idx})")

                # Create FormulaEvaluator for the Asset Cost model
                # FormulaEvaluator is already imported at the top of the file
                self.asset_cost_formula_evaluator = FormulaEvaluator(
                    self.asset_cost_widget.model
                )
                # Set the formula evaluator on the model for dependency tracking
                self.asset_cost_widget.model.set_formula_evaluator(self.asset_cost_formula_evaluator)
                logger.info("  ✓ Created FormulaEvaluator for Asset Cost")

                # Apply FormulaDelegate to the Price column
                price_col_index = self.asset_cost_widget.model.column_fields.index("_calc_price")
                self.asset_cost_formula_delegate = FormulaDelegate(self.asset_cost_formula_evaluator, app_settings=self.app_settings)
                # Set currency symbol and position from bid data (sg_currency field)
                if self.current_bid_data:
                    default_symbol = self.app_settings.get_currency() or "$"
                    sg_currency_value = self.current_bid_data.get("sg_currency")
                    currency_symbol, currency_position = parse_sg_currency(sg_currency_value, default_symbol)
                    self.asset_cost_formula_delegate.set_currency_symbol(currency_symbol, currency_position)
                self.asset_cost_widget.table_view.setItemDelegateForColumn(price_col_index, self.asset_cost_formula_delegate)
                logger.info(f"  ✓ Applied FormulaDelegate to Price column (index {price_col_index})")

                # Configure totals bar for Price column
                if hasattr(self, 'asset_cost_totals_wrapper'):
                    # Set formula evaluator on totals wrapper for formula evaluation
                    self.asset_cost_totals_wrapper.set_formula_evaluator(self.asset_cost_formula_evaluator)
                    logger.info(f"  ✓ Set formula evaluator on totals wrapper")

                    # Mark Price column as blue
                    self.asset_cost_totals_wrapper.set_blue_columns([price_col_index])

                    # Calculate totals only for Price column (formulas will be evaluated)
                    self.asset_cost_totals_wrapper.calculate_totals(columns=[price_col_index], skip_first_col=True)
                    logger.info(f"  ✓ Configured totals bar for Price column (index {price_col_index})")

                # Connect model dataChanged signal to update Total Cost summary
                self.asset_cost_widget.model.dataChanged.connect(self._on_assets_data_changed)
                logger.info(f"  ✓ Connected assets model dataChanged signal to Total Cost summary update")

                # Force the header view to update
                if hasattr(self.asset_cost_widget, 'table_view'):
                    self.asset_cost_widget.table_view.horizontalHeader().viewport().update()
                    logger.info(f"  ✓ Forced header view update")

            logger.info(f"  ✅ SUCCESSFULLY LOADED {len(asset_items_data)} ASSET ITEMS")
            logger.info("="*80)

            # Apply Asset Type delegate
            self._apply_asset_type_delegate()

        except Exception as e:
            logger.error(f"❌ Failed to load Asset items: {e}", exc_info=True)
            if hasattr(self, 'asset_cost_widget'):
                self.asset_cost_widget.load_bidding_scenes([])

    def _apply_asset_type_delegate(self):
        """Apply ValidatedComboBoxDelegate to the sg_bid_asset_type column."""
        if not self.asset_cost_widget or not hasattr(self.asset_cost_widget, 'table_view'):
            logger.warning("asset_cost_widget or table_view not available")
            return

        try:
            # Find the column index for sg_bid_asset_type
            if hasattr(self.asset_cost_widget, 'model') and self.asset_cost_widget.model:
                try:
                    col_idx = self.asset_cost_widget.model.column_fields.index("sg_bid_asset_type")
                except ValueError:
                    # Column not present
                    return

                # Create or update the delegate with purple color for Costs panel
                if not hasattr(self, 'asset_type_delegate') or self.asset_type_delegate is None:
                    self.asset_type_delegate = ValidatedComboBoxDelegate(
                        self.line_item_names,
                        self.asset_cost_widget.table_view,
                        valid_color="#6b5b95"  # Purple for Costs panel
                    )
                    self.asset_cost_widget.table_view.setItemDelegateForColumn(col_idx, self.asset_type_delegate)

                    # Protect delegate from being removed by _apply_column_dropdowns
                    if hasattr(self.asset_cost_widget, '_dropdown_delegates'):
                        self.asset_cost_widget._dropdown_delegates['sg_bid_asset_type'] = self.asset_type_delegate

                    # Force a complete repaint of the table
                    self.asset_cost_widget.table_view.viewport().update()
                else:
                    # Update existing delegate with new Line Item names
                    self.asset_type_delegate.update_valid_values(self.line_item_names)

                    # Ensure delegate is still protected
                    if hasattr(self.asset_cost_widget, '_dropdown_delegates'):
                        self.asset_cost_widget._dropdown_delegates['sg_bid_asset_type'] = self.asset_type_delegate

                    # Force a complete repaint of the table
                    self.asset_cost_widget.table_view.viewport().update()

        except Exception as e:
            logger.error(f"Failed to apply Asset Type delegate: {e}", exc_info=True)

    def _refresh_asset_cost(self):
        """Refresh the asset cost view."""
        logger.info("Refreshing asset cost view")
        if not hasattr(self, 'asset_cost_widget'):
            logger.warning("  ❌ asset_cost_widget not initialized yet")
            return

        if self.current_bid_data and self.current_bid_id:
            self._load_asset_items_for_bid(self.current_bid_data)
        else:
            self.asset_cost_widget.load_bidding_scenes([])

    def _refresh_total_cost(self):
        """Refresh the total cost view."""
        logger.info("Refreshing total cost view")
        # TODO: Implement actual total cost calculation
        pass

    def save_layout(self):
        """Save the current dock layout to settings."""
        settings = QtCore.QSettings()
        settings.setValue(self.SETTINGS_KEY, self.saveState())

        logger.info("Saved costs dock layout")

    def load_layout(self):
        """Load the saved dock layout from settings."""
        settings = QtCore.QSettings()
        state = settings.value(self.SETTINGS_KEY)
        if state is not None:
            self.restoreState(state)
            logger.info("Loaded costs dock layout")
        else:
            logger.info("No saved layout found, using default")

    def reset_layout(self):
        """Reset dock layout to default."""
        settings = QtCore.QSettings()
        settings.remove(self.SETTINGS_KEY)

        # Remove all docks
        for dock in (self.shots_cost_dock, self.asset_cost_dock, self.misc_cost_dock, self.total_cost_dock):
            self.removeDockWidget(dock)

        # Re-add in default positions (as tabs)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.shots_cost_dock)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.asset_cost_dock)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.misc_cost_dock)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.total_cost_dock)

        # Create tabs
        self.tabifyDockWidget(self.shots_cost_dock, self.asset_cost_dock)
        self.tabifyDockWidget(self.asset_cost_dock, self.misc_cost_dock)
        self.tabifyDockWidget(self.misc_cost_dock, self.total_cost_dock)

        # Show the first tab by default
        self.shots_cost_dock.raise_()

        logger.info("Reset costs dock layout to default")

    # ------------------------------------------------------------------
    # Spreadsheet ShotGrid Persistence
    # ------------------------------------------------------------------

    def _save_misc_spreadsheet_to_shotgrid(self):
        """Save Misc Cost spreadsheet data to ShotGrid including formatting."""
        if not self.current_bid_id or not self.current_project_id:
            logger.warning("Cannot save Misc spreadsheet - no bid selected")
            return

        if not hasattr(self, 'misc_cost_spreadsheet'):
            return

        try:
            # Get the spreadsheet data
            data_dict = self.misc_cost_spreadsheet.get_data_as_dict()

            if not data_dict:
                logger.debug("No data to save for Misc spreadsheet")
                return

            # Get cell metadata and sheet metadata for formatting persistence
            cell_meta_dict = self.misc_cost_spreadsheet.model.get_all_cell_meta()
            sheet_meta = self.misc_cost_spreadsheet.model.get_sheet_meta()

            # Save to ShotGrid with metadata
            self.sg_session.save_spreadsheet_data(
                project_id=self.current_project_id,
                bid_id=self.current_bid_id,
                spreadsheet_type="misc",
                data_dict=data_dict,
                cell_meta_dict=cell_meta_dict,
                sheet_meta=sheet_meta
            )
            logger.info(f"Saved Misc spreadsheet data to ShotGrid ({len(data_dict)} cells, {len(cell_meta_dict)} formatted)")

        except Exception as e:
            logger.error(f"Failed to save Misc spreadsheet to ShotGrid: {e}", exc_info=True)

    def _load_misc_spreadsheet_from_shotgrid(self):
        """Load Misc Cost spreadsheet data from ShotGrid including formatting, or initialize with defaults."""
        if not hasattr(self, 'misc_cost_spreadsheet'):
            return

        # Always clear and initialize first
        self._initialize_misc_spreadsheet_defaults()

        if not self.current_bid_id:
            return

        try:
            # Load from ShotGrid (now returns tuple with metadata)
            result = self.sg_session.load_spreadsheet_data(
                bid_id=self.current_bid_id,
                spreadsheet_type="misc"
            )

            # Handle both old (dict only) and new (tuple) return formats
            if isinstance(result, tuple):
                data_dict, cell_meta_dict, sheet_meta = result
            else:
                data_dict = result
                cell_meta_dict = {}
                sheet_meta = {}

            if data_dict:
                self.misc_cost_spreadsheet.load_data_from_dict(data_dict)

                # Load cell metadata if present
                if cell_meta_dict:
                    self.misc_cost_spreadsheet.model.load_cell_meta(cell_meta_dict)

                # Load sheet metadata if present (column widths, row heights, merged cells)
                if sheet_meta:
                    self.misc_cost_spreadsheet.model.load_sheet_meta(sheet_meta)
                    # Apply saved column/row sizes to view
                    self.misc_cost_spreadsheet.apply_saved_sizes()

                logger.info(f"Loaded Misc spreadsheet data from ShotGrid ({len(data_dict)} cells, {len(cell_meta_dict)} formatted)")
            else:
                logger.info("No Misc spreadsheet data found in ShotGrid - using defaults")

        except Exception as e:
            logger.error(f"Failed to load Misc spreadsheet from ShotGrid: {e}", exc_info=True)

    def _initialize_misc_spreadsheet_defaults(self):
        """Initialize Misc spreadsheet with empty defaults."""
        if not hasattr(self, 'misc_cost_spreadsheet'):
            return

        # Clear all data
        self.misc_cost_spreadsheet.load_data_from_dict({})
        logger.debug("Initialized Misc spreadsheet with empty defaults")

    def _save_total_cost_spreadsheet_to_shotgrid(self):
        """Save Total Cost spreadsheet data to ShotGrid including formatting."""
        if not self.current_bid_id or not self.current_project_id:
            logger.warning("Cannot save Total Cost spreadsheet - no bid selected")
            return

        if not hasattr(self, 'total_cost_spreadsheet'):
            return

        try:
            # Get the spreadsheet data
            data_dict = self.total_cost_spreadsheet.get_data_as_dict()

            if not data_dict:
                logger.debug("No data to save for Total Cost spreadsheet")
                return

            # Get cell metadata and sheet metadata for formatting persistence
            cell_meta_dict = self.total_cost_spreadsheet.model.get_all_cell_meta()
            sheet_meta = self.total_cost_spreadsheet.model.get_sheet_meta()

            # Save to ShotGrid with metadata
            self.sg_session.save_spreadsheet_data(
                project_id=self.current_project_id,
                bid_id=self.current_bid_id,
                spreadsheet_type="total_cost",
                data_dict=data_dict,
                cell_meta_dict=cell_meta_dict,
                sheet_meta=sheet_meta
            )
            logger.info(f"Saved Total Cost spreadsheet data to ShotGrid ({len(data_dict)} cells, {len(cell_meta_dict)} formatted)")

        except Exception as e:
            logger.error(f"Failed to save Total Cost spreadsheet to ShotGrid: {e}", exc_info=True)

    def _load_total_cost_spreadsheet_from_shotgrid(self):
        """Load Total Cost spreadsheet data from ShotGrid including formatting, or initialize with defaults."""
        if not hasattr(self, 'total_cost_spreadsheet'):
            return

        # Always clear and initialize with defaults first
        self._initialize_total_cost_spreadsheet_defaults()

        if not self.current_bid_id:
            return

        try:
            # Load from ShotGrid (now returns tuple with metadata)
            result = self.sg_session.load_spreadsheet_data(
                bid_id=self.current_bid_id,
                spreadsheet_type="total_cost"
            )

            # Handle both old (dict only) and new (tuple) return formats
            if isinstance(result, tuple):
                data_dict, cell_meta_dict, sheet_meta = result
            else:
                data_dict = result
                cell_meta_dict = {}
                sheet_meta = {}

            if data_dict:
                self.total_cost_spreadsheet.load_data_from_dict(data_dict)

                # Load cell metadata if present
                if cell_meta_dict:
                    self.total_cost_spreadsheet.model.load_cell_meta(cell_meta_dict)

                # Load sheet metadata if present (column widths, row heights, merged cells)
                if sheet_meta:
                    self.total_cost_spreadsheet.model.load_sheet_meta(sheet_meta)
                    # Apply saved column/row sizes to view
                    self.total_cost_spreadsheet.apply_saved_sizes()

                logger.info(f"Loaded Total Cost spreadsheet data from ShotGrid ({len(data_dict)} cells, {len(cell_meta_dict)} formatted)")
            else:
                logger.info("No Total Cost spreadsheet data found in ShotGrid - using defaults")

        except Exception as e:
            logger.error(f"Failed to load Total Cost spreadsheet from ShotGrid: {e}", exc_info=True)

    def _initialize_total_cost_spreadsheet_defaults(self):
        """Initialize Total Cost spreadsheet with default structure."""
        if not hasattr(self, 'total_cost_spreadsheet'):
            return

        # Clear all existing data
        self.total_cost_spreadsheet.load_data_from_dict({})

        # Set up the default structure:
        # Row 0: Headers (Category, Amount)
        # Row 1: Shot Costs
        # Row 2: Asset Costs
        # Row 3: Misc
        # Row 4: Total Cost (formula)

        # Column headers
        self.total_cost_spreadsheet.set_cell_value(0, 0, "Category")
        self.total_cost_spreadsheet.set_cell_value(0, 1, "Amount")

        # Row labels
        self.total_cost_spreadsheet.set_cell_value(1, 0, "Shot Costs")
        self.total_cost_spreadsheet.set_cell_value(2, 0, "Asset Costs")
        self.total_cost_spreadsheet.set_cell_value(3, 0, "Misc")
        self.total_cost_spreadsheet.set_cell_value(4, 0, "Total Cost")

        # Amount values (will be updated by _update_total_cost_summary)
        self.total_cost_spreadsheet.set_cell_value(1, 1, 0)  # Shot Costs
        self.total_cost_spreadsheet.set_cell_value(2, 1, 0)  # Asset Costs
        self.total_cost_spreadsheet.set_cell_value(3, 1, 0)  # Misc
        # Total Cost formula: sum of B2:B4
        self.total_cost_spreadsheet.set_cell_value(4, 1, "=B2+B3+B4")

        logger.debug("Initialized Total Cost spreadsheet with defaults")

    def get_view_menu_actions(self):
        """Get toggle view actions for all docks.

        Returns:
            Empty list (docks cannot be closed/hidden)
        """
        # Docks cannot be closed or hidden, so no menu actions needed
        return []

    def closeEvent(self, event: QtGui.QCloseEvent):
        """Handle close event - save layout and commit any cached spreadsheet data."""
        # Commit any cached spreadsheet changes to ShotGrid
        if self._spreadsheet_cache.has_dirty_spreadsheets():
            logger.info("Committing cached spreadsheet changes before closing...")
            self._spreadsheet_cache.commit_all(parent_widget=self)

        self.save_layout()
        super().closeEvent(event)
