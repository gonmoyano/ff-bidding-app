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

        # Debounce timer for saving spreadsheet data to ShotGrid
        self._misc_save_timer = QtCore.QTimer()
        self._misc_save_timer.setSingleShot(True)
        self._misc_save_timer.setInterval(1000)  # 1 second debounce
        self._misc_save_timer.timeout.connect(self._save_misc_spreadsheet_to_shotgrid)

        self._total_cost_save_timer = QtCore.QTimer()
        self._total_cost_save_timer.setSingleShot(True)
        self._total_cost_save_timer.setInterval(1000)  # 1 second debounce
        self._total_cost_save_timer.timeout.connect(self._save_total_cost_spreadsheet_to_shotgrid)

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

        # Create cost docks
        self._create_cost_docks()

        # Set up cross-tab formula evaluator after all widgets are created
        self._setup_cross_tab_formulas()

        # Load saved layout
        QtCore.QTimer.singleShot(0, self.load_layout)

        logger.info("CostsTab initialized")

    def _create_cost_docks(self):
        """Create the individual cost dock widgets."""
        # Shots Cost (uses VFXBreakdownWidget)
        self.shots_cost_dock = CostDock(
            "Shots Cost",
            self._create_shots_cost_widget(),
            self
        )

        # Assets Cost
        self.asset_cost_dock = CostDock(
            "Assets Cost",
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
        """Create the Shots Cost widget using VFXBreakdownWidget."""
        # Use VFXBreakdownWidget with toolbar for search and sort functionality
        self.shots_cost_widget = VFXBreakdownWidget(
            self.sg_session,
            show_toolbar=True,  # Show search and sort toolbar in collapsible group
            entity_name="Shot",
            settings_key="shots_cost",  # Unique settings key for Shots Cost table
            parent=self
        )

        # Now intercept the layout and replace table_view with wrapped version
        layout = self.shots_cost_widget.layout()

        # Remove table_view from layout
        layout.removeWidget(self.shots_cost_widget.table_view)

        # Create wrapper with totals bar, passing app_settings for currency formatting
        self.shots_cost_totals_wrapper = TableWithTotalsBar(
            self.shots_cost_widget.table_view,
            app_settings=self.app_settings
        )

        # Add wrapper back to layout
        layout.addWidget(self.shots_cost_totals_wrapper)

        return self.shots_cost_widget

    def _create_asset_cost_widget(self):
        """Create the Asset Cost widget using VFXBreakdownWidget."""
        # Use VFXBreakdownWidget with toolbar for search and sort functionality
        self.asset_cost_widget = VFXBreakdownWidget(
            self.sg_session,
            show_toolbar=True,  # Show search and sort toolbar in collapsible group
            entity_name="Asset",
            settings_key="asset_cost",  # Unique settings key for Asset Cost table
            parent=self
        )

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

    def _on_misc_data_changed(self):
        """Handle data changes in the Misc Cost spreadsheet - update summary and save."""
        # Update Total Cost summary
        self._update_total_cost_summary()

        # Schedule debounced save to ShotGrid
        if self.current_bid_id and self.current_project_id:
            self._misc_save_timer.start()  # Restart timer on each change

    def _on_total_cost_data_changed(self):
        """Handle data changes in the Total Cost spreadsheet - save to ShotGrid."""
        # Schedule debounced save to ShotGrid
        if self.current_bid_id and self.current_project_id:
            self._total_cost_save_timer.start()  # Restart timer on each change

    def _setup_cross_tab_formulas(self):
        """Set up cross-tab formula references between cost sheets."""
        # Create a dictionary of sheet models for cross-tab references
        # Use names with spaces for user-friendly formula references like 'Shots Cost'!A1
        sheet_models = {}

        # Add Shot Costs model (accessible via 'Shots Cost'!ref)
        if hasattr(self, 'shots_cost_widget') and hasattr(self.shots_cost_widget, 'model'):
            sheet_models['Shots Cost'] = self.shots_cost_widget.model

        # Add Asset Costs model (accessible via 'Assets Cost'!ref)
        if hasattr(self, 'asset_cost_widget') and hasattr(self.asset_cost_widget, 'model'):
            sheet_models['Assets Cost'] = self.asset_cost_widget.model

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

            # Update Total Cost summary with initial totals
            QtCore.QTimer.singleShot(100, self._update_total_cost_summary)
        else:
            # Clear all cost views
            if hasattr(self, 'shots_cost_widget'):
                self.shots_cost_widget.load_bidding_scenes([])
            if hasattr(self, 'asset_cost_widget'):
                self.asset_cost_widget.load_bidding_scenes([])
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
                        logger.debug(f"  Updated row {row_idx}: {vfx_shot_work} -> price {self.line_items_price_map[vfx_shot_work]}")
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

                # Create or update the delegate
                if self.vfx_shot_work_delegate is None:
                    self.vfx_shot_work_delegate = ValidatedComboBoxDelegate(
                        self.line_item_names,
                        self.shots_cost_widget.table_view
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

                # Create or update the delegate
                if not hasattr(self, 'asset_type_delegate') or self.asset_type_delegate is None:
                    self.asset_type_delegate = ValidatedComboBoxDelegate(
                        self.line_item_names,
                        self.asset_cost_widget.table_view
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
        """Save Misc Cost spreadsheet data to ShotGrid."""
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

            # Save to ShotGrid
            self.sg_session.save_spreadsheet_data(
                project_id=self.current_project_id,
                bid_id=self.current_bid_id,
                spreadsheet_type="misc",
                data_dict=data_dict
            )
            logger.info(f"Saved Misc spreadsheet data to ShotGrid ({len(data_dict)} cells)")

        except Exception as e:
            logger.error(f"Failed to save Misc spreadsheet to ShotGrid: {e}", exc_info=True)

    def _load_misc_spreadsheet_from_shotgrid(self):
        """Load Misc Cost spreadsheet data from ShotGrid, or initialize with defaults."""
        if not hasattr(self, 'misc_cost_spreadsheet'):
            return

        # Always clear and initialize first
        self._initialize_misc_spreadsheet_defaults()

        if not self.current_bid_id:
            return

        try:
            # Load from ShotGrid
            data_dict = self.sg_session.load_spreadsheet_data(
                bid_id=self.current_bid_id,
                spreadsheet_type="misc"
            )

            if data_dict:
                self.misc_cost_spreadsheet.load_data_from_dict(data_dict)
                logger.info(f"Loaded Misc spreadsheet data from ShotGrid ({len(data_dict)} cells)")
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
        """Save Total Cost spreadsheet data to ShotGrid."""
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

            # Save to ShotGrid
            self.sg_session.save_spreadsheet_data(
                project_id=self.current_project_id,
                bid_id=self.current_bid_id,
                spreadsheet_type="total_cost",
                data_dict=data_dict
            )
            logger.info(f"Saved Total Cost spreadsheet data to ShotGrid ({len(data_dict)} cells)")

        except Exception as e:
            logger.error(f"Failed to save Total Cost spreadsheet to ShotGrid: {e}", exc_info=True)

    def _load_total_cost_spreadsheet_from_shotgrid(self):
        """Load Total Cost spreadsheet data from ShotGrid, or initialize with defaults."""
        if not hasattr(self, 'total_cost_spreadsheet'):
            return

        # Always clear and initialize with defaults first
        self._initialize_total_cost_spreadsheet_defaults()

        if not self.current_bid_id:
            return

        try:
            # Load from ShotGrid
            data_dict = self.sg_session.load_spreadsheet_data(
                bid_id=self.current_bid_id,
                spreadsheet_type="total_cost"
            )

            if data_dict:
                self.total_cost_spreadsheet.load_data_from_dict(data_dict)
                logger.info(f"Loaded Total Cost spreadsheet data from ShotGrid ({len(data_dict)} cells)")
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
        """Handle close event - save layout and pending spreadsheet data."""
        # Stop the debounce timers and save any pending data immediately
        if hasattr(self, '_misc_save_timer') and self._misc_save_timer.isActive():
            self._misc_save_timer.stop()
            self._save_misc_spreadsheet_to_shotgrid()

        if hasattr(self, '_total_cost_save_timer') and self._total_cost_save_timer.isActive():
            self._total_cost_save_timer.stop()
            self._save_total_cost_spreadsheet_to_shotgrid()

        self.save_layout()
        super().closeEvent(event)
