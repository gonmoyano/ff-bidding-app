"""
Assets Tab
Contains UI and logic for managing Bid Assets (CustomEntity08) and Asset items (CustomEntity07).
"""

from PySide6 import QtWidgets, QtCore

try:
    from .logger import logger
    from .settings import AppSettings
    from .vfx_breakdown_model import VFXBreakdownModel
    from .vfx_breakdown_widget import VFXBreakdownWidget
    from .bid_selector_widget import CollapsibleGroupBox
except ImportError:
    import logging
    logger = logging.getLogger("FFPackageManager")
    from settings import AppSettings
    from vfx_breakdown_model import VFXBreakdownModel
    from vfx_breakdown_widget import VFXBreakdownWidget
    from bid_selector_widget import CollapsibleGroupBox


class AssetsTab(QtWidgets.QWidget):
    """Assets tab widget for managing Bid Assets and Asset items."""

    def __init__(self, sg_session, parent=None):
        """Initialize the Assets tab.

        Args:
            sg_session: ShotgridClient instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.sg_session = sg_session
        self.parent_app = parent

        # Current context
        self.current_project_id = None
        self.current_bid_id = None

        # Cached schema information for Assets
        self.asset_entity_type = "CustomEntity07"
        self.asset_field_names = []
        self.asset_field_labels = {}

        # Field schema information (data types and list values)
        self.field_schema = {}

        # UI widgets for assets selector
        self.bid_assets_combo = None
        self.bid_assets_set_btn = None
        self.bid_assets_refresh_btn = None
        self.bid_assets_status_label = None

        # Reusable assets widget (uses VFXBreakdownWidget for table display)
        self.assets_widget = None

        self._build_ui()

    def _build_ui(self):
        """Build the Assets tab UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        # Selector group (collapsible)
        selector_group = CollapsibleGroupBox("Bid Assets")

        selector_row = QtWidgets.QHBoxLayout()
        selector_label = QtWidgets.QLabel("Select Bid Assets:")
        selector_row.addWidget(selector_label)

        self.bid_assets_combo = QtWidgets.QComboBox()
        self.bid_assets_combo.setMinimumWidth(250)
        self.bid_assets_combo.currentIndexChanged.connect(self._on_bid_assets_changed)
        selector_row.addWidget(self.bid_assets_combo, stretch=1)

        self.bid_assets_set_btn = QtWidgets.QPushButton("Set as Current")
        self.bid_assets_set_btn.setEnabled(False)
        self.bid_assets_set_btn.clicked.connect(self._on_set_current_bid_assets)
        selector_row.addWidget(self.bid_assets_set_btn)

        self.bid_assets_add_btn = QtWidgets.QPushButton("Add")
        self.bid_assets_add_btn.clicked.connect(self._on_add_bid_assets)
        selector_row.addWidget(self.bid_assets_add_btn)

        self.bid_assets_remove_btn = QtWidgets.QPushButton("Remove")
        self.bid_assets_remove_btn.clicked.connect(self._on_remove_bid_assets)
        selector_row.addWidget(self.bid_assets_remove_btn)

        self.bid_assets_rename_btn = QtWidgets.QPushButton("Rename")
        self.bid_assets_rename_btn.clicked.connect(self._on_rename_bid_assets)
        selector_row.addWidget(self.bid_assets_rename_btn)

        self.bid_assets_refresh_btn = QtWidgets.QPushButton("Refresh")
        self.bid_assets_refresh_btn.clicked.connect(self._refresh_bid_assets)
        selector_row.addWidget(self.bid_assets_refresh_btn)

        selector_group.addLayout(selector_row)

        self.bid_assets_status_label = QtWidgets.QLabel("Select a Bid to view Bid Assets.")
        self.bid_assets_status_label.setObjectName("bidAssetsStatusLabel")
        self.bid_assets_status_label.setStyleSheet("color: #a0a0a0; padding: 2px 0;")
        selector_group.addWidget(self.bid_assets_status_label)

        layout.addWidget(selector_group)

        # Create reusable Assets widget (reusing VFXBreakdownWidget)
        self.assets_widget = VFXBreakdownWidget(self.sg_session, show_toolbar=True, parent=self)

        # Connect widget signals
        self.assets_widget.statusMessageChanged.connect(self._on_widget_status_changed)

        layout.addWidget(self.assets_widget)

    def _on_widget_status_changed(self, message, is_error):
        """Handle status message from assets widget."""
        self._set_bid_assets_status(message, is_error)

    def _set_bid_assets_status(self, message, is_error=False):
        """Set the status message for bid assets.

        Args:
            message: Status message
            is_error: Whether this is an error message
        """
        if is_error:
            self.bid_assets_status_label.setStyleSheet("color: #ff6b6b; padding: 2px 0;")
        else:
            self.bid_assets_status_label.setStyleSheet("color: #a0a0a0; padding: 2px 0;")
        self.bid_assets_status_label.setText(message)

    def set_bid(self, bid_id, project_id):
        """Set the current bid and load associated bid assets.

        Args:
            bid_id: ID of the Bid (CustomEntity06)
            project_id: ID of the project
        """
        self.current_bid_id = bid_id
        self.current_project_id = project_id

        # Clear current selection
        self.bid_assets_combo.blockSignals(True)
        self.bid_assets_combo.clear()
        self.bid_assets_combo.blockSignals(False)

        if not bid_id or not project_id:
            self._set_bid_assets_status("Select a Bid to view Bid Assets.")
            self.assets_widget.clear_table()
            return

        # Fetch schema if not already loaded
        if not self.field_schema:
            self._fetch_asset_schema()

        # Refresh the bid assets list
        self._refresh_bid_assets()

    def _fetch_asset_schema(self):
        """Fetch the schema for CustomEntity07 (Asset items) from ShotGrid."""
        try:
            # Get schema for CustomEntity07
            schema = self.sg_session.sg.schema_field_read("CustomEntity07")

            # Build field schema dictionary
            for field_name, field_info in schema.items():
                self.field_schema[field_name] = {
                    "data_type": field_info.get("data_type", {}).get("value"),
                    "properties": field_info.get("properties", {}),
                    "editable": field_info.get("editable", {}).get("value", True)
                }

                # Store list values for list fields
                if field_info.get("data_type", {}).get("value") == "list":
                    list_values = field_info.get("properties", {}).get("valid_values", {}).get("value", [])
                    self.field_schema[field_name]["list_values"] = list_values

            logger.info(f"Fetched schema for CustomEntity07 with {len(self.field_schema)} fields")

        except Exception as e:
            logger.error(f"Failed to fetch schema for CustomEntity07: {e}", exc_info=True)
            self._set_bid_assets_status("Failed to fetch asset schema.", is_error=True)

    def _refresh_bid_assets(self):
        """Refresh the list of Bid Assets for the current bid."""
        if not self.current_project_id or not self.current_bid_id:
            return

        try:
            # Query CustomEntity08 (Bid Assets) filtered by project
            filters = [
                ["project", "is", {"type": "Project", "id": self.current_project_id}]
            ]

            bid_assets_list = self.sg_session.sg.find(
                "CustomEntity08",
                filters,
                ["code", "id"]
            )

            # Update combo box
            self.bid_assets_combo.blockSignals(True)
            self.bid_assets_combo.clear()

            for bid_assets in sorted(bid_assets_list, key=lambda x: x.get("code", "")):
                self.bid_assets_combo.addItem(bid_assets.get("code", "Unnamed"), bid_assets["id"])

            self.bid_assets_combo.blockSignals(False)

            if bid_assets_list:
                self._set_bid_assets_status(f"Found {len(bid_assets_list)} Bid Assets")
                self.bid_assets_set_btn.setEnabled(True)
                # Load the first one
                self._on_bid_assets_changed(0)
            else:
                self._set_bid_assets_status("No Bid Assets found for this project.")
                self.bid_assets_set_btn.setEnabled(False)
                self.assets_widget.clear_table()

        except Exception as e:
            logger.error(f"Failed to refresh Bid Assets: {e}", exc_info=True)
            self._set_bid_assets_status("Failed to load Bid Assets.", is_error=True)

    def _on_bid_assets_changed(self, index):
        """Handle Bid Assets selection change."""
        if index < 0:
            self.assets_widget.clear_table()
            return

        bid_assets_id = self.bid_assets_combo.currentData()
        if not bid_assets_id:
            return

        # Load asset items for this Bid Assets
        self._load_asset_items(bid_assets_id)

    def _load_asset_items(self, bid_assets_id):
        """Load asset items (CustomEntity07) for the selected Bid Assets.

        Args:
            bid_assets_id: ID of the Bid Assets (CustomEntity08)
        """
        try:
            # Query CustomEntity07 (Asset items) linked to this Bid Assets
            filters = [
                ["sg_bid_assets", "is", {"type": "CustomEntity08", "id": bid_assets_id}]
            ]

            # Get all fields from schema
            fields = list(self.field_schema.keys()) if self.field_schema else ["code"]

            asset_items = self.sg_session.sg.find(
                "CustomEntity07",
                filters,
                fields
            )

            # Use the assets widget to display the items
            self.assets_widget.load_bidding_scenes(asset_items, field_schema=self.field_schema)

            display_name = self.bid_assets_combo.currentText()
            if asset_items:
                self._set_bid_assets_status(f"Loaded {len(asset_items)} Asset item(s) for '{display_name}'.")
            else:
                self._set_bid_assets_status(f"No Asset items linked to '{display_name}'.")

        except Exception as e:
            logger.error(f"Failed to load asset items: {e}", exc_info=True)
            self._set_bid_assets_status("Failed to load asset items.", is_error=True)

    def _on_set_current_bid_assets(self):
        """Set the selected Bid Assets as current for the Bid."""
        if not self.current_bid_id:
            QtWidgets.QMessageBox.warning(self, "No Bid Selected", "Please select a Bid first.")
            return

        bid_assets_id = self.bid_assets_combo.currentData()
        if not bid_assets_id:
            QtWidgets.QMessageBox.warning(self, "No Bid Assets Selected", "Please select a Bid Assets.")
            return

        try:
            # Update the Bid's sg_bid_assets field
            self.sg_session.sg.update(
                "CustomEntity06",
                self.current_bid_id,
                {"sg_bid_assets": {"type": "CustomEntity08", "id": bid_assets_id}}
            )

            bid_assets_name = self.bid_assets_combo.currentText()
            self._set_bid_assets_status(f"Set '{bid_assets_name}' as current Bid Assets.")
            QtWidgets.QMessageBox.information(
                self,
                "Success",
                f"'{bid_assets_name}' is now the current Bid Assets for this Bid."
            )

            logger.info(f"Set Bid Assets {bid_assets_id} as current for Bid {self.current_bid_id}")

        except Exception as e:
            logger.error(f"Failed to set current Bid Assets: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to set current Bid Assets:\n{str(e)}"
            )

    def _on_add_bid_assets(self):
        """Add a new Bid Assets."""
        if not self.current_project_id:
            QtWidgets.QMessageBox.warning(self, "No Project Selected", "Please select a project first.")
            return

        # Prompt for name
        name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Add Bid Assets",
            "Enter name for new Bid Assets:"
        )

        if not ok or not name:
            return

        try:
            # Create CustomEntity08 (Bid Assets)
            bid_assets_data = {
                "code": name,
                "project": {"type": "Project", "id": self.current_project_id}
            }

            new_bid_assets = self.sg_session.sg.create("CustomEntity08", bid_assets_data)

            logger.info(f"Created Bid Assets: {name} (ID: {new_bid_assets['id']})")
            self._set_bid_assets_status(f"Created Bid Assets '{name}'.")

            # Refresh list and select new one
            self._refresh_bid_assets()

            # Find and select the new bid assets
            for i in range(self.bid_assets_combo.count()):
                if self.bid_assets_combo.itemData(i) == new_bid_assets['id']:
                    self.bid_assets_combo.setCurrentIndex(i)
                    break

        except Exception as e:
            logger.error(f"Failed to create Bid Assets: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to create Bid Assets:\n{str(e)}"
            )

    def _on_remove_bid_assets(self):
        """Remove the selected Bid Assets."""
        bid_assets_id = self.bid_assets_combo.currentData()
        if not bid_assets_id:
            QtWidgets.QMessageBox.warning(self, "No Bid Assets Selected", "Please select a Bid Assets to remove.")
            return

        bid_assets_name = self.bid_assets_combo.currentText()

        # Confirm deletion
        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete Bid Assets '{bid_assets_name}'?\n\n"
            f"This will also delete all linked Asset items.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply != QtWidgets.QMessageBox.Yes:
            return

        try:
            # Delete the Bid Assets (CustomEntity08)
            self.sg_session.sg.delete("CustomEntity08", bid_assets_id)

            logger.info(f"Deleted Bid Assets: {bid_assets_name} (ID: {bid_assets_id})")
            self._set_bid_assets_status(f"Deleted Bid Assets '{bid_assets_name}'.")

            # Refresh list
            self._refresh_bid_assets()

        except Exception as e:
            logger.error(f"Failed to delete Bid Assets: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to delete Bid Assets:\n{str(e)}"
            )

    def _on_rename_bid_assets(self):
        """Rename the selected Bid Assets."""
        bid_assets_id = self.bid_assets_combo.currentData()
        if not bid_assets_id:
            QtWidgets.QMessageBox.warning(self, "No Bid Assets Selected", "Please select a Bid Assets to rename.")
            return

        current_name = self.bid_assets_combo.currentText()

        # Prompt for new name
        new_name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Rename Bid Assets",
            "Enter new name:",
            text=current_name
        )

        if not ok or not new_name or new_name == current_name:
            return

        try:
            # Update the Bid Assets name
            self.sg_session.sg.update("CustomEntity08", bid_assets_id, {"code": new_name})

            logger.info(f"Renamed Bid Assets from '{current_name}' to '{new_name}' (ID: {bid_assets_id})")
            self._set_bid_assets_status(f"Renamed to '{new_name}'.")

            # Refresh list and maintain selection
            current_index = self.bid_assets_combo.currentIndex()
            self._refresh_bid_assets()
            if current_index < self.bid_assets_combo.count():
                self.bid_assets_combo.setCurrentIndex(current_index)

        except Exception as e:
            logger.error(f"Failed to rename Bid Assets: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to rename Bid Assets:\n{str(e)}"
            )
