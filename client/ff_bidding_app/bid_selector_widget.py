"""
Bid Selector Widget
Reusable widget component for selecting and managing Bids (CustomEntity06).
"""

from PySide6 import QtWidgets, QtCore

try:
    from .logger import logger
except ImportError:
    import logging
    logger = logging.getLogger("FFPackageManager")


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

        # UI widgets
        self.bid_combo = None
        self.set_current_btn = None
        self.add_btn = None
        self.remove_btn = None
        self.rename_btn = None
        self.refresh_btn = None
        self.status_label = None

        self._build_ui()

    def _build_ui(self):
        """Build the bid selector UI."""
        # Main group box
        group = QtWidgets.QGroupBox("Bids")
        layout = QtWidgets.QVBoxLayout(group)

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

        layout.addLayout(selector_row)

        # Status label
        self.status_label = QtWidgets.QLabel("Select an RFQ to view Bids.")
        self.status_label.setStyleSheet("color: #a0a0a0; padding: 2px 0;")
        layout.addWidget(self.status_label)

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
            bids = self.sg_session.get_bids(project_id, fields=["id", "code", "sg_bid_type", "sg_vfx_breakdown"])
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
                linked_bid = rfq.get("sg_bid")
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
        """Handle Set as Current button click."""
        # This will be implemented to update RFQ.sg_bid
        bid = self.get_current_bid()
        if not bid:
            QtWidgets.QMessageBox.warning(self, "No Bid Selected", "Please select a Bid from the list.")
            return

        # Signal to parent or handle directly
        # For now, emit a message
        self.statusMessageChanged.emit("Set as Current functionality needs parent implementation", False)
        logger.info(f"Set as Current clicked for Bid ID: {bid.get('id')}")

    def _on_add_bid(self):
        """Handle Add Bid button click."""
        # TODO: Show dialog to create new bid
        self.statusMessageChanged.emit("Add Bid functionality not yet implemented", False)
        logger.info("Add Bid clicked")

    def _on_remove_bid(self):
        """Handle Remove Bid button click."""
        # TODO: Show dialog to confirm and delete bid
        self.statusMessageChanged.emit("Remove Bid functionality not yet implemented", False)
        logger.info("Remove Bid clicked")

    def _on_rename_bid(self):
        """Handle Rename Bid button click."""
        # TODO: Show dialog to rename bid
        self.statusMessageChanged.emit("Rename Bid functionality not yet implemented", False)
        logger.info("Rename Bid clicked")

    def _on_refresh_bids(self):
        """Handle Refresh button click."""
        # Need parent context to know current project/RFQ
        self.statusMessageChanged.emit("Refresh functionality needs parent implementation", False)
        logger.info("Refresh Bids clicked")

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
