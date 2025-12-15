"""
Bidding Tab
Contains nested tabs for VFX Breakdown, Assets, Rates, and a sliding Costs panel.
"""

from PySide6 import QtWidgets, QtCore

try:
    from .vfx_breakdown_tab import VFXBreakdownTab
    from .assets_tab import AssetsTab
    from .rates_tab import RatesTab
    from .costs_tab import CostsTab
    from .bid_selector_widget import BidSelectorWidget
    from .sliding_overlay_panel import SlidingOverlayPanelWithBackground
    from .settings import AppSettings
    from .logger import logger
except ImportError:
    from vfx_breakdown_tab import VFXBreakdownTab
    from assets_tab import AssetsTab
    from rates_tab import RatesTab
    from costs_tab import CostsTab
    from bid_selector_widget import BidSelectorWidget
    from sliding_overlay_panel import SlidingOverlayPanelWithBackground
    from settings import AppSettings
    import logging
    logger = logging.getLogger("FFPackageManager")


class BiddingTab(QtWidgets.QWidget):
    """
    Main Bidding tab widget that contains nested tabs for different bidding aspects.
    """

    def __init__(self, sg_session, parent=None):
        """
        Initialize the Bidding tab.

        Args:
            sg_session: ShotGrid session for API access
            parent: Parent widget
        """
        super().__init__(parent)
        self.sg_session = sg_session
        self.parent_app = parent

        # Settings
        self.app_settings = AppSettings()

        # Store current selections
        self.current_rfq = None
        self.current_bid = None
        self.current_project_id = None

        # Costs panel state
        self._costs_panel_docked = self.app_settings.get("biddingTab/costsPanelDocked", False)

        # Initialize UI
        self._build_ui()

    def _build_ui(self):
        """Build the UI for the Bidding tab with nested tabs and sliding Costs panel."""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Add Bid selector widget at the top
        self.bid_selector = BidSelectorWidget(self.sg_session, parent=self)
        self.bid_selector.bidChanged.connect(self._on_bid_changed)
        self.bid_selector.loadLinkedRequested.connect(self._on_load_linked_requested)
        self.bid_selector.statusMessageChanged.connect(self._on_bid_status_message)
        self.bid_selector.currencySettingsChanged.connect(self._on_currency_settings_changed)
        main_layout.addWidget(self.bid_selector, 0)  # No stretch - keep preferred size

        # Create horizontal splitter for main content and docked costs panel
        self.main_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)

        # Create nested tab widget (now without Costs tab)
        self.nested_tab_widget = QtWidgets.QTabWidget()

        # Create and add nested tabs (excluding Costs - it will be in sliding panel)
        vfx_breakdown_tab = self._create_vfx_breakdown_tab()
        self.nested_tab_widget.addTab(vfx_breakdown_tab, "VFX Breakdown")

        assets_tab = self._create_assets_tab()
        self.nested_tab_widget.addTab(assets_tab, "Assets")

        rates_tab = self._create_rates_tab()
        self.nested_tab_widget.addTab(rates_tab, "Rates")

        # Add nested tabs to splitter
        self.main_splitter.addWidget(self.nested_tab_widget)

        # Create the Costs tab widget (will be used in sliding panel and docked mode)
        self.costs_tab = self._create_costs_tab()

        # Create docked costs container (initially hidden)
        self.docked_costs_container = QtWidgets.QWidget()
        docked_layout = QtWidgets.QVBoxLayout(self.docked_costs_container)
        docked_layout.setContentsMargins(0, 0, 0, 0)
        docked_layout.setSpacing(0)

        # Header for docked mode with undock button
        docked_header = QtWidgets.QWidget()
        docked_header.setObjectName("dockedCostsHeader")
        docked_header.setStyleSheet("""
            QWidget#dockedCostsHeader {
                background-color: #353535;
                border-bottom: 1px solid #555555;
            }
        """)
        docked_header_layout = QtWidgets.QHBoxLayout(docked_header)
        docked_header_layout.setContentsMargins(10, 5, 10, 5)

        docked_title = QtWidgets.QLabel("Costs")
        docked_title_font = docked_title.font()
        docked_title_font.setBold(True)
        docked_title.setFont(docked_title_font)
        docked_header_layout.addWidget(docked_title)
        docked_header_layout.addStretch()

        # Undock button
        self.undock_costs_btn = QtWidgets.QPushButton("Unpin")
        self.undock_costs_btn.setFixedSize(40, 24)
        self.undock_costs_btn.setToolTip("Undock panel")
        self.undock_costs_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #555555;
                border-radius: 4px;
                color: #e0e0e0;
                font-size: 11px;
                padding: 2px 4px;
            }
            QPushButton:hover {
                background-color: #4a9eff;
                border-color: #4a9eff;
            }
        """)
        self.undock_costs_btn.clicked.connect(self._undock_costs_panel)
        docked_header_layout.addWidget(self.undock_costs_btn)

        docked_layout.addWidget(docked_header)

        # Add docked container to splitter (costs_tab will be added based on docked state)
        self.main_splitter.addWidget(self.docked_costs_container)

        # Set up splitter sizes (70% tabs, 30% costs when docked)
        self.main_splitter.setSizes([700, 300])

        # Hide docked container initially (unless it was docked before)
        self.docked_costs_container.setVisible(self._costs_panel_docked)

        main_layout.addWidget(self.main_splitter, 1)  # Stretch to fill remaining space

        # Create the sliding overlay panel for Costs (when not docked)
        self.costs_overlay_panel = SlidingOverlayPanelWithBackground(
            parent=self,
            panel_width=600,
            animation_duration=300,
            background_opacity=0.3,
            close_on_background_click=True,
            show_dock_button=True
        )
        self.costs_overlay_panel.set_title("Costs")
        self.costs_overlay_panel.dock_requested.connect(self._dock_costs_panel)

        # Place costs_tab in the correct container based on docked state
        if self._costs_panel_docked:
            # Add costs tab to docked container
            docked_layout.addWidget(self.costs_tab)
        else:
            # Add costs tab to overlay panel
            self.costs_overlay_panel.set_content(self.costs_tab)

    def _create_vfx_breakdown_tab(self):
        """Create the VFX Breakdown nested tab content with full functionality."""
        # Use the full VFXBreakdownTab (includes selector, Add/Remove/Rename buttons, etc.)
        tab = VFXBreakdownTab(self.sg_session, parent=self.parent_app)

        # Connect signal to update Costs tab when VFX Breakdown changes
        tab.vfxBreakdownChanged.connect(self._on_vfx_breakdown_changed)

        # Connect signal to refresh Shots Cost when VFX Breakdown data changes
        tab.vfxBreakdownDataChanged.connect(self._on_vfx_breakdown_data_changed)

        # Store reference to use in set_rfq if needed
        self.vfx_breakdown_tab = tab

        return tab

    def _create_assets_tab(self):
        """Create the Assets nested tab content with full functionality."""
        # Use the full AssetsTab (includes selector, Add/Remove/Rename buttons, etc.)
        tab = AssetsTab(self.sg_session, parent=self.parent_app)

        # Connect signal to update VFX Breakdown pill colors when Bid Assets changes
        tab.bidAssetsChanged.connect(self._on_bid_assets_changed)

        # Connect signal to refresh Assets Cost when Bid Assets data changes
        tab.bidAssetsDataChanged.connect(self._on_bid_assets_data_changed)

        # Store reference to use in set_bid if needed
        self.assets_tab = tab

        return tab

    def _create_rates_tab(self):
        """Create the Rates nested tab content with full functionality."""
        # Use the full RatesTab (includes selector, Add/Remove/Rename buttons, etc.)
        tab = RatesTab(self.sg_session, parent=self.parent_app)

        # Store reference to use in set_bid if needed
        self.rates_tab = tab

        return tab

    def _create_costs_tab(self):
        """Create the Costs widget with dockable cost widgets."""
        # Use the full CostsTab (QMainWindow with dockable cost widgets)
        tab = CostsTab(self.sg_session, parent=self.parent_app)
        return tab

    def _toggle_costs_panel(self):
        """Toggle the Costs panel visibility."""
        if self._costs_panel_docked:
            # If docked, toggle the docked container visibility
            self.docked_costs_container.setVisible(not self.docked_costs_container.isVisible())
        else:
            # If not docked, toggle the overlay panel
            self.costs_overlay_panel.toggle()

    def _dock_costs_panel(self):
        """Dock the Costs panel (move from overlay to permanent split view)."""
        if self._costs_panel_docked:
            return  # Already docked

        # Hide the overlay panel
        self.costs_overlay_panel.hide_panel()

        # Move costs_tab from overlay panel to docked container
        # First, get the layout of docked container
        docked_layout = self.docked_costs_container.layout()

        # Set content to an empty widget to release costs_tab from overlay
        empty_widget = QtWidgets.QWidget()
        self.costs_overlay_panel.set_content(empty_widget)

        # Add costs_tab to docked container (after the header)
        docked_layout.addWidget(self.costs_tab)

        # Show the docked container
        self.docked_costs_container.setVisible(True)

        # Update state
        self._costs_panel_docked = True
        self.app_settings.set("biddingTab/costsPanelDocked", True)

        logger.info("Costs panel docked")

    def _undock_costs_panel(self):
        """Undock the Costs panel (move from permanent split view to overlay)."""
        if not self._costs_panel_docked:
            return  # Already undocked

        # Hide the docked container
        self.docked_costs_container.setVisible(False)

        # Remove costs_tab from docked container
        docked_layout = self.docked_costs_container.layout()
        docked_layout.removeWidget(self.costs_tab)

        # Add costs_tab to overlay panel
        self.costs_overlay_panel.set_content(self.costs_tab)

        # Update state
        self._costs_panel_docked = False
        self.app_settings.set("biddingTab/costsPanelDocked", False)

        # Show the overlay panel
        self.costs_overlay_panel.show_panel()

        logger.info("Costs panel undocked")

    def is_costs_panel_docked(self):
        """Check if the Costs panel is currently docked.

        Returns:
            bool: True if docked, False if in overlay mode
        """
        return self._costs_panel_docked

    def is_costs_panel_visible(self):
        """Check if the Costs panel is currently visible.

        Returns:
            bool: True if visible (either docked or overlay shown)
        """
        if self._costs_panel_docked:
            return self.docked_costs_container.isVisible()
        else:
            return self.costs_overlay_panel.is_panel_visible()

    def set_rfq(self, rfq_data):
        """
        Set the current RFQ data for this tab.

        Args:
            rfq_data: Dictionary containing RFQ information
        """
        # Store RFQ data for use in nested tabs
        self.current_rfq = rfq_data

        # Get project ID from parent app
        if self.parent_app and hasattr(self.parent_app, 'sg_project_combo'):
            proj = self.parent_app.sg_project_combo.itemData(self.parent_app.sg_project_combo.currentIndex())
            self.current_project_id = proj.get('id') if proj else None

        # Populate bid selector with bids for the project
        if hasattr(self, 'bid_selector') and self.current_project_id:
            self.bid_selector.populate_bids(rfq_data, self.current_project_id, auto_select=True)

    def _on_bid_changed(self, bid_data):
        """Handle bid selection change.

        Args:
            bid_data: Selected bid dictionary or None
        """
        self.current_bid = bid_data
        logger.info(f"Bid changed in Bidding tab: {bid_data.get('code') if bid_data else 'None'}")

        # Update breakdown widget with current bid for asset queries
        if hasattr(self, 'vfx_breakdown_tab') and hasattr(self.vfx_breakdown_tab, 'breakdown_widget'):
            self.vfx_breakdown_tab.breakdown_widget.set_current_bid(bid_data)

        # When a bid is selected, load its VFX breakdown
        if bid_data and hasattr(self, 'vfx_breakdown_tab'):
            # Get the VFX breakdown linked to this bid
            vfx_breakdown = bid_data.get("sg_vfx_breakdown")

            # Populate VFX breakdown combo with all breakdowns in project
            # (will auto-select the one linked to the bid if present)
            if self.current_rfq:
                self.vfx_breakdown_tab.populate_vfx_breakdown_combo(self.current_rfq, auto_select=False)

                # Auto-select the breakdown linked to this bid
                if vfx_breakdown and isinstance(vfx_breakdown, dict):
                    breakdown_id = vfx_breakdown.get('id')
                    if breakdown_id:
                        self.vfx_breakdown_tab._select_vfx_breakdown_by_id(breakdown_id)
        else:
            # No bid selected - cascade reset to downstream dropdowns
            if hasattr(self, 'vfx_breakdown_tab'):
                # Reset VFX Breakdown dropdown to placeholder
                self.vfx_breakdown_tab.vfx_breakdown_combo.blockSignals(True)
                self.vfx_breakdown_tab.vfx_breakdown_combo.clear()
                self.vfx_breakdown_tab.vfx_breakdown_combo.addItem("-- Select VFX Breakdown --", None)
                self.vfx_breakdown_tab.vfx_breakdown_combo.blockSignals(False)
                self.vfx_breakdown_tab._clear_vfx_breakdown_table()
                self.vfx_breakdown_tab._set_vfx_breakdown_status("Select a Bid to view VFX Breakdowns.")
                self.vfx_breakdown_tab.vfx_breakdown_set_btn.setEnabled(False)

        # Update Assets tab with the current bid
        if hasattr(self, 'assets_tab'):
            if bid_data and self.current_project_id:
                # Pass full bid_data so assets_tab can access sg_bid_assets field
                self.assets_tab.set_bid(bid_data, self.current_project_id)
            else:
                # Clear assets tab if no bid selected (cascading reset)
                self.assets_tab.set_bid(None, None)

        # Update Rates tab with the current bid
        if hasattr(self, 'rates_tab'):
            if bid_data and self.current_project_id:
                # Pass full bid_data so rates_tab can access sg_price_list field
                self.rates_tab.set_bid(bid_data, self.current_project_id)
            else:
                # Clear rates tab if no bid selected (cascading reset)
                self.rates_tab.set_bid(None, None)

        # Update Costs tab with the current bid
        if hasattr(self, 'costs_tab'):
            if bid_data and self.current_project_id:
                # Pass full bid_data for costs calculation
                logger.info(f"BIDDING TAB - Passing bid to costs_tab:")
                logger.info(f"  Bid ID: {bid_data.get('id')}")
                logger.info(f"  Bid Code: {bid_data.get('code')}")
                logger.info(f"  sg_bid_assets present: {'sg_bid_assets' in bid_data}")
                logger.info(f"  sg_bid_assets value: {bid_data.get('sg_bid_assets')}")
                self.costs_tab.set_bid(bid_data, self.current_project_id)
            else:
                # Clear costs tab if no bid selected (cascading reset)
                self.costs_tab.set_bid(None, None)

    def _on_bid_status_message(self, message, is_error):
        """Handle status messages from bid selector.

        Args:
            message: Status message
            is_error: Whether this is an error message
        """
        logger.info(f"Bid selector status: {message}")
        # Could forward this to parent app status bar if needed

    def _on_currency_settings_changed(self, bid_id, sg_currency_value):
        """Handle currency settings change from Configure Bid dialog.

        Args:
            bid_id: ID of the bid whose currency settings changed
            sg_currency_value: Combined currency value (e.g., "$+before", "€+after")
        """
        logger.info(f"Currency settings changed for bid ID: {bid_id}, currency: {sg_currency_value}")

        # Refresh currency formatting in Costs tab with the new currency value
        if hasattr(self, 'costs_tab'):
            self.costs_tab.refresh_currency_formatting(sg_currency_value)

        # Refresh currency formatting in Rates tab with the new currency value
        if hasattr(self, 'rates_tab'):
            self.rates_tab.refresh_currency_formatting(sg_currency_value)

    def _on_load_linked_requested(self, bid_data):
        """Handle Load Linked button click - load linked entities into their dropdown menus.

        Args:
            bid_data: Selected bid dictionary
        """
        if not bid_data:
            return

        bid_name = bid_data.get('code', f"Bid {bid_data.get('id')}")
        logger.info(f"Loading linked entities for Bid: {bid_name}")

        # Load VFX Breakdown linked to this bid
        if hasattr(self, 'vfx_breakdown_tab') and self.current_rfq:
            vfx_breakdown = bid_data.get("sg_vfx_breakdown")
            # Populate combo and select the linked breakdown
            self.vfx_breakdown_tab.populate_vfx_breakdown_combo(self.current_rfq, auto_select=False)
            if vfx_breakdown and isinstance(vfx_breakdown, dict):
                breakdown_id = vfx_breakdown.get('id')
                if breakdown_id:
                    self.vfx_breakdown_tab._select_vfx_breakdown_by_id(breakdown_id)
                    logger.info(f"  Selected VFX Breakdown ID: {breakdown_id}")

        # Load Bid Assets linked to this bid
        if hasattr(self, 'assets_tab') and self.current_project_id:
            self.assets_tab.set_bid(bid_data, self.current_project_id)
            bid_assets = bid_data.get("sg_bid_assets")
            if bid_assets and isinstance(bid_assets, dict):
                logger.info(f"  Selected Bid Assets ID: {bid_assets.get('id')}")

        # Load Price List linked to this bid
        if hasattr(self, 'rates_tab') and self.current_project_id:
            self.rates_tab.set_bid(bid_data, self.current_project_id)
            price_list = bid_data.get("sg_price_list")
            if price_list and isinstance(price_list, dict):
                logger.info(f"  Selected Price List ID: {price_list.get('id')}")

    def _on_vfx_breakdown_changed(self, updated_bid_data):
        """Handle VFX Breakdown change - update Costs tab Shots Cost table.

        Args:
            updated_bid_data: Updated bid data dictionary with new sg_vfx_breakdown
        """
        if not updated_bid_data:
            return

        logger.info(f"VFX Breakdown changed for Bid: {updated_bid_data.get('code')}")

        # Update current bid reference
        self.current_bid = updated_bid_data

        # Refresh Shots Cost table in Costs tab with new VFX Breakdown data
        if hasattr(self, 'costs_tab') and self.current_project_id:
            self.costs_tab.set_bid(updated_bid_data, self.current_project_id)
            logger.info("  Updated Costs tab with new VFX Breakdown")

    def _on_bid_assets_changed(self, updated_bid_data):
        """Handle Bid Assets change - update VFX Breakdown pill colors and Costs tab.

        Args:
            updated_bid_data: Updated bid data dictionary with new sg_bid_assets
        """
        if not updated_bid_data:
            return

        logger.info(f"Bid Assets changed for Bid: {updated_bid_data.get('code')}")

        # Update current bid reference
        self.current_bid = updated_bid_data

        # Update the VFX Breakdown widget with the new bid data so it can refresh pill colors
        if hasattr(self, 'vfx_breakdown_tab') and hasattr(self.vfx_breakdown_tab, 'breakdown_widget'):
            breakdown_widget = self.vfx_breakdown_tab.breakdown_widget
            # Update the current bid reference in the breakdown widget
            breakdown_widget.set_current_bid(updated_bid_data)
            # Refresh asset widgets to update pill colors based on new Bid Assets
            breakdown_widget._refresh_asset_widgets_validation()
            logger.info("  Updated VFX Breakdown pill colors based on new Bid Assets")

        # Refresh Assets Cost table in Costs tab with new Bid Assets data
        if hasattr(self, 'costs_tab') and self.current_project_id:
            self.costs_tab.set_bid(updated_bid_data, self.current_project_id)
            logger.info("  Updated Costs tab with new Bid Assets")

    def _on_vfx_breakdown_data_changed(self):
        """Handle VFX Breakdown data change - refresh Shots Cost table in Costs tab.

        This is called when a field is updated in the VFX Breakdown table
        and the loaded VFX Breakdown is the one assigned to the current bid.
        """
        logger.info("VFX Breakdown data changed - refreshing Shots Cost table")

        # Refresh Shots Cost table in Costs tab
        if hasattr(self, 'costs_tab') and self.current_bid and self.current_project_id:
            self.costs_tab.set_bid(self.current_bid, self.current_project_id)
            logger.info("  Refreshed Shots Cost table in Costs tab")

    def _on_bid_assets_data_changed(self):
        """Handle Bid Assets data change - refresh Assets Cost table in Costs tab.

        This is called when a field is updated in the Bid Assets table
        and the loaded Bid Assets is the one assigned to the current bid.
        """
        logger.info("Bid Assets data changed - refreshing Assets Cost table")

        # Refresh Assets Cost table in Costs tab
        if hasattr(self, 'costs_tab') and self.current_bid and self.current_project_id:
            self.costs_tab.set_bid(self.current_bid, self.current_project_id)
            logger.info("  Refreshed Assets Cost table in Costs tab")
