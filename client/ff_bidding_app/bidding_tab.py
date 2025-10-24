"""
Bidding Tab
Contains nested tabs for VFX Breakdown, Assets, Scene, Rates, and Summary.
"""

from PySide6 import QtWidgets, QtCore

try:
    from .vfx_breakdown_tab import VFXBreakdownTab
except ImportError:
    from vfx_breakdown_tab import VFXBreakdownTab


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

        # Initialize UI
        self._build_ui()

    def _build_ui(self):
        """Build the UI for the Bidding tab with nested tabs."""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

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
        # This method can be called by the parent app when RFQ changes
        # Store RFQ data for use in nested tabs
        self.current_rfq = rfq_data

        # Update VFX Breakdown tab with RFQ data
        if hasattr(self, 'vfx_breakdown_tab'):
            self.vfx_breakdown_tab.populate_vfx_breakdown_combo(rfq_data, auto_select=True)
