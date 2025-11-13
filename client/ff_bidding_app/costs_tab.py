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
except ImportError:
    import logging
    logger = logging.getLogger("FFPackageManager")
    from settings import AppSettings
    from vfx_breakdown_widget import VFXBreakdownWidget, FormulaDelegate
    from vfx_breakdown_model import ValidatedComboBoxDelegate
    from formula_evaluator import FormulaEvaluator
    from table_with_totals_bar import TableWithTotalsBar


class CollapsibleDockTitleBar(QtWidgets.QWidget):
    """Custom title bar for collapsible dock widgets."""

    def __init__(self, dock_widget, parent=None):
        """Initialize the title bar.

        Args:
            dock_widget: The dock widget this title bar belongs to
            parent: Parent widget
        """
        super().__init__(parent)
        self.dock_widget = dock_widget

        # Create layout
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)

        # Collapse/expand button
        self.collapse_btn = QtWidgets.QToolButton()
        self.collapse_btn.setArrowType(QtCore.Qt.DownArrow)
        self.collapse_btn.setAutoRaise(True)
        self.collapse_btn.clicked.connect(self._on_collapse_clicked)
        self.collapse_btn.setToolTip("Collapse/Expand")
        layout.addWidget(self.collapse_btn)

        # Title label
        self.title_label = QtWidgets.QLabel(dock_widget.windowTitle())
        self.title_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.title_label)

        layout.addStretch()

        # Style
        self.setStyleSheet("""
            CollapsibleDockTitleBar {
                background-color: palette(window);
                border: 1px solid palette(mid);
                border-bottom: 1px solid palette(dark);
            }
            QToolButton:hover {
                background-color: palette(light);
            }
        """)

    def _on_collapse_clicked(self):
        """Handle collapse button click."""
        if hasattr(self.dock_widget, 'toggle_collapse'):
            self.dock_widget.toggle_collapse()

    def set_collapsed(self, collapsed):
        """Update the button arrow based on collapsed state.

        Args:
            collapsed: Whether the dock is collapsed
        """
        if collapsed:
            self.collapse_btn.setArrowType(QtCore.Qt.RightArrow)
        else:
            self.collapse_btn.setArrowType(QtCore.Qt.DownArrow)


class CostDock(QtWidgets.QDockWidget):
    """A collapsible dockable cost widget."""

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

        # Create custom title bar
        self.title_bar = CollapsibleDockTitleBar(self)
        self.setTitleBarWidget(self.title_bar)

        # Track collapsed state
        self._is_collapsed = False
        self._content_widget = widget
        self._expanded_size = None

    def toggle_collapse(self):
        """Toggle the collapsed state of the dock."""
        if self._is_collapsed:
            self.expand()
        else:
            self.collapse()

    def collapse(self):
        """Collapse the dock to show only the title bar (or totals bar if available)."""
        if self._is_collapsed:
            return

        # Save current size
        self._expanded_size = self.size()

        # Check if content widget contains a TableWithTotalsBar that we should partially collapse
        totals_wrapper = self._find_totals_wrapper()
        if totals_wrapper:
            # Collapse just the table, keep totals bar visible
            totals_wrapper.collapse_table()
            # Calculate height: title bar + totals bar
            title_height = self.title_bar.sizeHint().height()
            totals_height = totals_wrapper.totals_bar.sizeHint().height()
            collapsed_height = title_height + totals_height + 10  # Small padding
            self.setMinimumHeight(collapsed_height)
            self.setMaximumHeight(collapsed_height)
        else:
            # Traditional collapse: hide content widget entirely
            if self._content_widget:
                self._content_widget.hide()
            # Set minimum and maximum height to title bar height
            title_height = self.title_bar.sizeHint().height()
            self.setMinimumHeight(title_height)
            self.setMaximumHeight(title_height)

        self._is_collapsed = True
        self.title_bar.set_collapsed(True)

        logger.debug(f"Collapsed dock: {self.windowTitle()}")

    def expand(self):
        """Expand the dock to show the content widget."""
        if not self._is_collapsed:
            return

        # Check if content widget contains a TableWithTotalsBar
        totals_wrapper = self._find_totals_wrapper()
        if totals_wrapper:
            # Expand the table to show both table and totals bar
            totals_wrapper.expand_table()
        else:
            # Traditional expand: show content widget
            if self._content_widget:
                self._content_widget.show()

        # Reset size constraints
        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)  # Qt's QWIDGETSIZE_MAX

        # Restore size if we saved it
        if self._expanded_size:
            self.resize(self._expanded_size)

        self._is_collapsed = False
        self.title_bar.set_collapsed(False)

        logger.debug(f"Expanded dock: {self.windowTitle()}")

    def _find_totals_wrapper(self):
        """Find TableWithTotalsBar widget within the content widget.

        Returns:
            TableWithTotalsBar instance or None if not found
        """
        if not self._content_widget:
            return None

        # Check if the content widget itself is a TableWithTotalsBar
        if isinstance(self._content_widget, TableWithTotalsBar):
            return self._content_widget

        # Search through the widget's children recursively
        def find_in_children(widget):
            for child in widget.findChildren(TableWithTotalsBar):
                return child
            return None

        return find_in_children(self._content_widget)

    def is_collapsed(self):
        """Get the collapsed state.

        Returns:
            bool: True if collapsed, False otherwise
        """
        return self._is_collapsed

    def set_collapsed(self, collapsed):
        """Set the collapsed state.

        Args:
            collapsed: True to collapse, False to expand
        """
        if collapsed:
            self.collapse()
        else:
            self.expand()


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

        # Line Items data with prices for Price column calculation
        self.line_items_data = []  # Full Line Item data with calculated prices
        self.line_items_price_map = {}  # Map: Line Item code -> calculated price
        self.vfx_breakdown_formula_evaluator = None

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

        # Asset Cost
        self.asset_cost_dock = CostDock(
            "Asset Cost",
            self._create_asset_cost_widget(),
            self
        )

        # Total Cost
        self.total_cost_dock = CostDock(
            "Total Cost",
            self._create_total_cost_widget(),
            self
        )

        # Add docks vertically stacked - Order: Shots Cost -> Assets Cost -> Total Cost
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.shots_cost_dock)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.asset_cost_dock)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.total_cost_dock)

        # Force vertical stacking
        self.splitDockWidget(self.shots_cost_dock, self.asset_cost_dock, QtCore.Qt.Vertical)
        self.splitDockWidget(self.asset_cost_dock, self.total_cost_dock, QtCore.Qt.Vertical)

    def _create_shots_cost_widget(self):
        """Create the Shots Cost widget using VFXBreakdownWidget."""
        # Use VFXBreakdownWidget with toolbar enabled, but no VFX Breakdown selector
        # since the breakdown is preselected from the bid
        self.shots_cost_widget = VFXBreakdownWidget(
            self.sg_session,
            show_toolbar=True,  # Keep sorting and filtering bar
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
        """Create the Asset Cost widget."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QtWidgets.QLabel("Asset Cost")
        title.setStyleSheet("font-size: 16px; font-weight: bold; padding: 5px;")
        layout.addWidget(title)

        # Placeholder content
        content = QtWidgets.QTextEdit()
        content.setPlaceholderText("Asset cost breakdown will be displayed here...\n\n"
                                   "This will show:\n"
                                   "- Cost per asset\n"
                                   "- Asset categories\n"
                                   "- Total asset costs\n"
                                   "- Cost allocation")
        content.setReadOnly(True)
        layout.addWidget(content)

        return widget

    def _create_total_cost_widget(self):
        """Create the Total Cost widget."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QtWidgets.QLabel("Total Cost")
        title.setStyleSheet("font-size: 16px; font-weight: bold; padding: 5px;")
        layout.addWidget(title)

        # Placeholder content
        content = QtWidgets.QTextEdit()
        content.setPlaceholderText("Total cost summary will be displayed here...\n\n"
                                   "This will show:\n"
                                   "- Grand total for all shots and assets\n"
                                   "- Cost breakdown by category\n"
                                   "- Budget vs actual\n"
                                   "- Overall project cost summary")
        content.setReadOnly(True)
        layout.addWidget(content)

        return widget

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
        logger.info("="*80)

        self.current_bid_data = bid_data
        self.current_bid_id = bid_data.get('id') if bid_data else None
        self.current_project_id = project_id

        if bid_data and project_id:
            # Load VFX Breakdown linked to this bid into Shots Cost widget
            self._load_vfx_breakdown_for_bid(bid_data)

            # Refresh other cost views
            self._refresh_asset_cost()
            self._refresh_total_cost()
        else:
            # Clear all cost views
            if hasattr(self, 'shots_cost_widget'):
                self.shots_cost_widget.load_bidding_scenes([])

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

            # Load Line Items for VFX Shot Work validation
            self._load_line_item_names()

            # Load Line Items with prices for Price column calculation
            self._load_line_items_with_prices()

            # Populate virtual price columns for each bidding scene
            for scene in bidding_scenes_data:
                vfx_shot_work = scene.get("sg_vfx_shot_work")
                est_cuts = scene.get("sg_number_of_shots", 0) or 0

                # Look up Line Item price by code
                line_item_price = 0
                if vfx_shot_work and vfx_shot_work in self.line_items_price_map:
                    line_item_price = self.line_items_price_map[vfx_shot_work]
                    logger.debug(f"Scene '{scene.get('code')}': VFX Shot Work='{vfx_shot_work}', Price=${line_item_price:,.2f}")

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
                formula_delegate = FormulaDelegate(self.vfx_breakdown_formula_evaluator, app_settings=self.app_settings)
                self.shots_cost_widget.table_view.setItemDelegateForColumn(price_col_index, formula_delegate)
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
            logger.debug("No current bid for Line Items query")
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
            logger.info(f"Found {len(self.line_item_names)} Line Items for VFX Shot Work: {self.line_item_names}")

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
            logger.debug("No current bid for Line Items price query")
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
                    logger.debug(f"Calculated price for '{code}': ${calculated_price:,.2f}")
                else:
                    logger.debug(f"Using static price for '{code}': ${calculated_price:,.2f}")

                # Store in price map
                if code:
                    self.line_items_price_map[code] = calculated_price

                # Add to data list
                self.line_items_data.append(item)

            logger.info(f"Loaded {len(self.line_items_data)} Line Items with prices")
            logger.info(f"Price map: {self.line_items_price_map}")

        except Exception as e:
            logger.error(f"Failed to load Line Items with prices: {e}", exc_info=True)
            self.line_items_data = []
            self.line_items_price_map = {}

    def _apply_vfx_shot_work_delegate(self):
        """Apply ValidatedComboBoxDelegate to the sg_vfx_shot_work column."""
        logger.info("=== _apply_vfx_shot_work_delegate called ===")
        logger.info(f"Line Item names count: {len(self.line_item_names)}")
        logger.info(f"Line Item names: {self.line_item_names}")

        if not self.shots_cost_widget or not hasattr(self.shots_cost_widget, 'table_view'):
            logger.warning("shots_cost_widget or table_view not available")
            return

        try:
            # Find the column index for sg_vfx_shot_work
            if hasattr(self.shots_cost_widget, 'model') and self.shots_cost_widget.model:
                logger.info(f"Model columns: {self.shots_cost_widget.model.column_fields}")
                try:
                    col_idx = self.shots_cost_widget.model.column_fields.index("sg_vfx_shot_work")
                    logger.info(f"Found sg_vfx_shot_work at column index: {col_idx}")
                except ValueError:
                    # Column not present
                    logger.info("sg_vfx_shot_work column not found in model")
                    return

                # Ensure the column is visible
                is_hidden = self.shots_cost_widget.table_view.isColumnHidden(col_idx)
                logger.info(f"Column sg_vfx_shot_work (index {col_idx}) hidden: {is_hidden}")
                if is_hidden:
                    logger.warning(f"Column sg_vfx_shot_work is hidden - it may not be visible to user")

                # Create or update the delegate
                if self.vfx_shot_work_delegate is None:
                    logger.info(f"Creating new ValidatedComboBoxDelegate with {len(self.line_item_names)} Line Items")
                    self.vfx_shot_work_delegate = ValidatedComboBoxDelegate(
                        self.line_item_names,
                        self.shots_cost_widget.table_view
                    )
                    self.shots_cost_widget.table_view.setItemDelegateForColumn(col_idx, self.vfx_shot_work_delegate)
                    logger.info(f"✓ Applied ValidatedComboBoxDelegate to sg_vfx_shot_work column (index {col_idx})")

                    # Verify it was applied
                    current_delegate = self.shots_cost_widget.table_view.itemDelegateForColumn(col_idx)
                    logger.info(f"Verification - Current delegate for column {col_idx}: {type(current_delegate).__name__}")

                    # Protect delegate from being removed by _apply_column_dropdowns
                    # Store it in the widget's _dropdown_delegates dict
                    if hasattr(self.shots_cost_widget, '_dropdown_delegates'):
                        self.shots_cost_widget._dropdown_delegates['sg_vfx_shot_work'] = self.vfx_shot_work_delegate
                        logger.info(f"✓ Protected sg_vfx_shot_work delegate from removal")

                    # Force a complete repaint of the table
                    self.shots_cost_widget.table_view.viewport().update()
                    self.shots_cost_widget.table_view.update()
                    logger.info(f"✓ Triggered viewport repaint")
                else:
                    # Update existing delegate with new Line Item names
                    logger.info(f"Updating existing delegate with {len(self.line_item_names)} Line Items")
                    self.vfx_shot_work_delegate.update_valid_values(self.line_item_names)

                    # Ensure delegate is still protected
                    if hasattr(self.shots_cost_widget, '_dropdown_delegates'):
                        self.shots_cost_widget._dropdown_delegates['sg_vfx_shot_work'] = self.vfx_shot_work_delegate

                    # Force a complete repaint of the table
                    self.shots_cost_widget.table_view.viewport().update()
                    self.shots_cost_widget.table_view.update()
                    logger.info(f"✓ Updated ValidatedComboBoxDelegate and triggered repaint")

        except Exception as e:
            logger.error(f"Failed to apply VFX Shot Work delegate: {e}", exc_info=True)

    def _refresh_asset_cost(self):
        """Refresh the asset cost view."""
        logger.info("Refreshing asset cost view")
        # TODO: Implement actual asset cost calculation
        pass

    def _refresh_total_cost(self):
        """Refresh the total cost view."""
        logger.info("Refreshing total cost view")
        # TODO: Implement actual total cost calculation
        pass

    def save_layout(self):
        """Save the current dock layout to settings."""
        settings = QtCore.QSettings()
        settings.setValue(self.SETTINGS_KEY, self.saveState())

        # Save collapsed state for each dock
        settings.setValue(f"{self.SETTINGS_KEY}/shots_cost_collapsed", self.shots_cost_dock.is_collapsed())
        settings.setValue(f"{self.SETTINGS_KEY}/asset_cost_collapsed", self.asset_cost_dock.is_collapsed())
        settings.setValue(f"{self.SETTINGS_KEY}/total_cost_collapsed", self.total_cost_dock.is_collapsed())

        logger.info("Saved costs dock layout and collapsed states")

    def load_layout(self):
        """Load the saved dock layout from settings."""
        settings = QtCore.QSettings()
        state = settings.value(self.SETTINGS_KEY)
        if state is not None:
            self.restoreState(state)

            # Restore collapsed state for each dock
            shots_collapsed = settings.value(f"{self.SETTINGS_KEY}/shots_cost_collapsed", False, type=bool)
            asset_collapsed = settings.value(f"{self.SETTINGS_KEY}/asset_cost_collapsed", False, type=bool)
            total_collapsed = settings.value(f"{self.SETTINGS_KEY}/total_cost_collapsed", False, type=bool)

            self.shots_cost_dock.set_collapsed(shots_collapsed)
            self.asset_cost_dock.set_collapsed(asset_collapsed)
            self.total_cost_dock.set_collapsed(total_collapsed)

            logger.info("Loaded costs dock layout and collapsed states")
        else:
            logger.info("No saved layout found, using default")

    def reset_layout(self):
        """Reset dock layout to default."""
        settings = QtCore.QSettings()
        settings.remove(self.SETTINGS_KEY)

        # Remove all docks
        for dock in (self.shots_cost_dock, self.asset_cost_dock, self.total_cost_dock):
            self.removeDockWidget(dock)

        # Re-add in default positions (vertical stacking)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.shots_cost_dock)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.asset_cost_dock)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.total_cost_dock)

        # Force vertical stacking
        self.splitDockWidget(self.shots_cost_dock, self.asset_cost_dock, QtCore.Qt.Vertical)
        self.splitDockWidget(self.asset_cost_dock, self.total_cost_dock, QtCore.Qt.Vertical)

        # Reset collapsed states to expanded
        self.shots_cost_dock.set_collapsed(False)
        self.asset_cost_dock.set_collapsed(False)
        self.total_cost_dock.set_collapsed(False)

        logger.info("Reset costs dock layout to default")

    def get_view_menu_actions(self):
        """Get toggle view actions for all docks.

        Returns:
            Empty list (docks cannot be closed/hidden)
        """
        # Docks cannot be closed or hidden, so no menu actions needed
        return []

    def closeEvent(self, event: QtGui.QCloseEvent):
        """Handle close event - save layout."""
        self.save_layout()
        super().closeEvent(event)
