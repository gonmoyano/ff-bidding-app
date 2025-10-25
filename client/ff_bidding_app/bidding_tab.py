"""
Bidding Tab
Contains nested tabs for VFX Breakdown, Assets, Scene, Rates, and Summary.
"""

from PySide6 import QtWidgets, QtCore

try:
    from .vfx_breakdown_tab import VFXBreakdownTab
    from .bid_selector_widget import BidSelectorWidget
    from .logger import logger
except ImportError:
    from vfx_breakdown_tab import VFXBreakdownTab
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
        self.bid_selector.statusMessageChanged.connect(self._on_bid_status_message)
        main_layout.addWidget(self.bid_selector)

        # Create nested tab widget
        self.nested_tab_widget = QtWidgets.QTabWidget()

        # Create and add nested tabs
        vfx_breakdown_tab = self._create_vfx_breakdown_tab()
        self.nested_tab_widget.addTab(vfx_breakdown_tab, "VFX Breakdown")

        assets_tab = self._create_assets_tab()
        self.nested_tab_widget.addTab(assets_tab, "Assets")

        scene_tab = self._create_scene_tab()
        self.nested_tab_widget.addTab(scene_tab, "Scene")

        rates_tab = self._create_rates_tab()
        self.nested_tab_widget.addTab(rates_tab, "Rates")

        summary_tab = self._create_summary_tab()
        self.nested_tab_widget.addTab(summary_tab, "Summary")

        main_layout.addWidget(self.nested_tab_widget)

    def _create_vfx_breakdown_tab(self):
        """Create the VFX Breakdown nested tab content with full functionality."""
        # Use the full VFXBreakdownTab (includes selector, Add/Remove/Rename buttons, etc.)
        tab = VFXBreakdownTab(self.sg_session, parent=self.parent_app)

        # Store reference to use in set_rfq if needed
        self.vfx_breakdown_tab = tab

        return tab

    def _create_assets_tab(self):
        """Create the Assets nested tab content."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)

        # Title
        title_label = QtWidgets.QLabel("Assets")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; padding: 20px;")
        layout.addWidget(title_label)

        # Placeholder content
        info_label = QtWidgets.QLabel("Assets content will be displayed here.\nThis tab will contain asset information and requirements for the bid.")
        info_label.setStyleSheet("padding: 20px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        layout.addStretch()

        return widget

    def _create_scene_tab(self):
        """Create the Scene nested tab content."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)

        # Title
        title_label = QtWidgets.QLabel("Scene")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; padding: 20px;")
        layout.addWidget(title_label)

        # Placeholder content
        info_label = QtWidgets.QLabel("Scene content will be displayed here.\nThis tab will contain scene-level information for bidding.")
        info_label.setStyleSheet("padding: 20px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        layout.addStretch()

        return widget

    def _create_rates_tab(self):
        """Create the Rates nested tab content."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)

        # Title
        title_label = QtWidgets.QLabel("Rates")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; padding: 20px;")
        layout.addWidget(title_label)

        # Placeholder content
        info_label = QtWidgets.QLabel("Rates content will be displayed here.\nThis tab will contain rate cards and pricing information for the bid.")
        info_label.setStyleSheet("padding: 20px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        layout.addStretch()

        return widget

    def _create_summary_tab(self):
        """Create the Summary nested tab content."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)

        # Title
        title_label = QtWidgets.QLabel("Summary")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; padding: 20px;")
        layout.addWidget(title_label)

        # Placeholder content
        info_label = QtWidgets.QLabel("Summary content will be displayed here.\nThis tab will contain a summary of the entire bid including totals and key information.")
        info_label.setStyleSheet("padding: 20px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        layout.addStretch()

        return widget

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
            # No bid selected, just populate breakdowns without auto-select
            if hasattr(self, 'vfx_breakdown_tab') and self.current_rfq:
                self.vfx_breakdown_tab.populate_vfx_breakdown_combo(self.current_rfq, auto_select=True)

    def _on_bid_status_message(self, message, is_error):
        """Handle status messages from bid selector.

        Args:
            message: Status message
            is_error: Whether this is an error message
        """
        logger.info(f"Bid selector status: {message}")
        # Could forward this to parent app status bar if needed
