"""
Bidding Tab
Contains nested tabs for VFX Breakdown, Assets, Rates, and Costs.
"""

from PySide6 import QtWidgets, QtCore

try:
    from .vfx_breakdown_tab import VFXBreakdownTab
    from .assets_tab import AssetsTab
    from .rates_tab import RatesTab
    from .costs_tab import CostsTab
    from .bid_selector_widget import BidSelectorWidget
    from .logger import logger
except ImportError:
    from vfx_breakdown_tab import VFXBreakdownTab
    from assets_tab import AssetsTab
    from rates_tab import RatesTab
    from costs_tab import CostsTab
    from bid_selector_widget import BidSelectorWidget
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

        # Store current selections
        self.current_rfq = None
        self.current_bid = None
        self.current_project_id = None

        # Initialize UI
        self._build_ui()

    def _build_ui(self):
        """Build the UI for the Bidding tab with nested tabs."""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Add Bid selector widget at the top
        self.bid_selector = BidSelectorWidget(self.sg_session, parent=self)
        self.bid_selector.bidChanged.connect(self._on_bid_changed)
        self.bid_selector.loadLinkedRequested.connect(self._on_load_linked_requested)
        self.bid_selector.statusMessageChanged.connect(self._on_bid_status_message)
        self.bid_selector.currencySettingsChanged.connect(self._on_currency_settings_changed)
        main_layout.addWidget(self.bid_selector)

        # Create nested tab widget
        self.nested_tab_widget = QtWidgets.QTabWidget()

        # Create and add nested tabs
        vfx_breakdown_tab = self._create_vfx_breakdown_tab()
        self.nested_tab_widget.addTab(vfx_breakdown_tab, "VFX Breakdown")

        assets_tab = self._create_assets_tab()
        self.nested_tab_widget.addTab(assets_tab, "Assets")

        rates_tab = self._create_rates_tab()
        self.nested_tab_widget.addTab(rates_tab, "Rates")

        costs_tab = self._create_costs_tab()
        self.nested_tab_widget.addTab(costs_tab, "Costs")

        main_layout.addWidget(self.nested_tab_widget)

    def _create_vfx_breakdown_tab(self):
        """Create the VFX Breakdown nested tab content with full functionality."""
        # Use the full VFXBreakdownTab (includes selector, Add/Remove/Rename buttons, etc.)
        tab = VFXBreakdownTab(self.sg_session, parent=self.parent_app)

        # Store reference to use in set_rfq if needed
        self.vfx_breakdown_tab = tab

        return tab

    def _create_assets_tab(self):
        """Create the Assets nested tab content with full functionality."""
        # Use the full AssetsTab (includes selector, Add/Remove/Rename buttons, etc.)
        tab = AssetsTab(self.sg_session, parent=self.parent_app)

        # Connect signal to update VFX Breakdown pill colors when Bid Assets changes
        tab.bidAssetsChanged.connect(self._on_bid_assets_changed)

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
        """Create the Costs nested tab content with dockable cost widgets."""
        # Use the full CostsTab (QMainWindow with dockable cost widgets)
        tab = CostsTab(self.sg_session, parent=self.parent_app)

        # Store reference to use in set_bid
        self.costs_tab = tab

        return tab

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

    def _on_currency_settings_changed(self, bid_id):
        """Handle currency settings change from Configure Bid dialog.

        Args:
            bid_id: ID of the bid whose currency settings changed
        """
        logger.info(f"Currency settings changed for bid ID: {bid_id}")

        # Refresh currency formatting in Costs tab
        if hasattr(self, 'costs_tab'):
            self.costs_tab.refresh_currency_formatting()

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

    def _on_bid_assets_changed(self, updated_bid_data):
        """Handle Bid Assets change - update VFX Breakdown pill colors.

        Args:
            updated_bid_data: Updated bid data dictionary with new sg_bid_assets
        """
        if not updated_bid_data:
            return

        logger.info(f"Bid Assets changed for Bid: {updated_bid_data.get('code')}")

        # Update the VFX Breakdown widget with the new bid data so it can refresh pill colors
        if hasattr(self, 'vfx_breakdown_tab') and hasattr(self.vfx_breakdown_tab, 'breakdown_widget'):
            breakdown_widget = self.vfx_breakdown_tab.breakdown_widget
            # Update the current bid reference in the breakdown widget
            breakdown_widget.set_current_bid(updated_bid_data)
            # Refresh asset widgets to update pill colors based on new Bid Assets
            breakdown_widget._refresh_asset_widgets_validation()
            logger.info("  Updated VFX Breakdown pill colors based on new Bid Assets")
