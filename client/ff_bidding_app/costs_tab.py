"""
Costs Tab
Contains dockable cost analysis widgets using QDockWidget pattern.
"""

from PySide6 import QtCore, QtGui, QtWidgets

try:
    from .logger import logger
    from .settings import AppSettings
    from .vfx_breakdown_widget import VFXBreakdownWidget
except ImportError:
    import logging
    logger = logging.getLogger("FFPackageManager")
    from settings import AppSettings
    from vfx_breakdown_widget import VFXBreakdownWidget


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

        # Float button
        float_btn = QtWidgets.QToolButton()
        float_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_TitleBarNormalButton))
        float_btn.setAutoRaise(True)
        float_btn.setToolTip("Float")
        float_btn.clicked.connect(lambda: dock_widget.setFloating(not dock_widget.isFloating()))
        layout.addWidget(float_btn)

        # Close button
        close_btn = QtWidgets.QToolButton()
        close_btn.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_TitleBarCloseButton))
        close_btn.setAutoRaise(True)
        close_btn.setToolTip("Close")
        close_btn.clicked.connect(dock_widget.close)
        layout.addWidget(close_btn)

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
        self.setFeatures(
            QtWidgets.QDockWidget.DockWidgetClosable |
            QtWidgets.QDockWidget.DockWidgetMovable |
            QtWidgets.QDockWidget.DockWidgetFloatable
        )

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
        """Collapse the dock to show only the title bar."""
        if self._is_collapsed:
            return

        # Save current size
        self._expanded_size = self.size()

        # Hide content widget
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

        # Show content widget
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

        # Set up corner ownership for dock areas
        self.setCorner(QtCore.Qt.TopLeftCorner, QtCore.Qt.LeftDockWidgetArea)
        self.setCorner(QtCore.Qt.BottomLeftCorner, QtCore.Qt.LeftDockWidgetArea)
        self.setCorner(QtCore.Qt.TopRightCorner, QtCore.Qt.RightDockWidgetArea)
        self.setCorner(QtCore.Qt.BottomRightCorner, QtCore.Qt.RightDockWidgetArea)

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

        # Add docks to areas
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.shots_cost_dock)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.asset_cost_dock)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.total_cost_dock)

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

            # Load into the VFXBreakdownWidget FIRST
            self.shots_cost_widget.load_bidding_scenes(bidding_scenes_data, field_schema=field_schema)
            logger.info(f"  ✓ Loaded bidding scenes into Shots Cost table")

            # Set the display names on the model AFTER loading data
            if hasattr(self.shots_cost_widget, 'model'):
                self.shots_cost_widget.model.set_column_headers(display_names)
                logger.info(f"  ✓ Set {len(display_names)} column headers with display names")
                # Log a few examples
                examples = list(display_names.items())[:5]
                logger.info(f"     Examples: {examples}")

                # Force the header view to update
                if hasattr(self.shots_cost_widget, 'table_view'):
                    self.shots_cost_widget.table_view.horizontalHeader().viewport().update()
                    logger.info(f"  ✓ Forced header view update")

            logger.info("="*80)

        except Exception as e:
            logger.error(f"Failed to load VFX Breakdown scenes: {e}", exc_info=True)
            self.shots_cost_widget.load_bidding_scenes([])

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

        # Re-add in default positions
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.shots_cost_dock)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.asset_cost_dock)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.total_cost_dock)

        # Reset collapsed states to expanded
        self.shots_cost_dock.set_collapsed(False)
        self.asset_cost_dock.set_collapsed(False)
        self.total_cost_dock.set_collapsed(False)

        logger.info("Reset costs dock layout to default")

    def get_view_menu_actions(self):
        """Get toggle view actions for all docks.

        Returns:
            List of QActions for toggling dock visibility
        """
        return [
            self.shots_cost_dock.toggleViewAction(),
            self.asset_cost_dock.toggleViewAction(),
            self.total_cost_dock.toggleViewAction(),
        ]

    def closeEvent(self, event: QtGui.QCloseEvent):
        """Handle close event - save layout."""
        self.save_layout()
        super().closeEvent(event)
