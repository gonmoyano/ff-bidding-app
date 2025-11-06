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
        self.setFeatures(
            QtWidgets.QDockWidget.DockWidgetClosable |
            QtWidgets.QDockWidget.DockWidgetMovable |
            QtWidgets.QDockWidget.DockWidgetFloatable
        )


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
            # Fetch the VFX Breakdown entity with linked bidding scenes
            vfx_breakdown_data = self.sg_session.sg.find_one(
                "CustomEntity01",  # VFX Breakdown entity type
                [["id", "is", breakdown_id]],
                ["code", "sg_bidding_scenes"]
            )

            if not vfx_breakdown_data:
                logger.warning(f"  ❌ VFX Breakdown {breakdown_id} not found in ShotGrid")
                self.shots_cost_widget.load_bidding_scenes([])
                return

            # Get the linked bidding scenes
            bidding_scenes = vfx_breakdown_data.get("sg_bidding_scenes", [])

            if not bidding_scenes:
                logger.info("  ℹ No bidding scenes linked to this VFX Breakdown")
                self.shots_cost_widget.load_bidding_scenes([])
                return

            # Extract scene IDs
            scene_ids = []
            if isinstance(bidding_scenes, list):
                scene_ids = [scene.get("id") for scene in bidding_scenes if isinstance(scene, dict) and scene.get("id")]
            elif isinstance(bidding_scenes, dict) and bidding_scenes.get("id"):
                scene_ids = [bidding_scenes.get("id")]

            if not scene_ids:
                logger.warning("  ❌ No valid scene IDs found")
                self.shots_cost_widget.load_bidding_scenes([])
                return

            logger.info(f"  ✓ Found {len(scene_ids)} bidding scenes")

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

            # Fetch all bidding scenes
            fields_to_fetch = list(raw_schema.keys())
            bidding_scenes_data = self.sg_session.sg.find(
                "CustomEntity02",
                [["id", "in", scene_ids]],
                fields_to_fetch
            )

            logger.info(f"  ✓ Fetched {len(bidding_scenes_data)} bidding scenes from ShotGrid")

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
        for dock in (self.shots_cost_dock, self.asset_cost_dock, self.total_cost_dock):
            self.removeDockWidget(dock)

        # Re-add in default positions
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.shots_cost_dock)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.asset_cost_dock)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.total_cost_dock)

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
