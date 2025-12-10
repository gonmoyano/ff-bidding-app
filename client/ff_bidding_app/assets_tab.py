"""
Assets Tab
Contains UI and logic for managing Bid Assets (CustomEntity08) and Asset items (CustomEntity07).
"""

from PySide6 import QtWidgets, QtCore

try:
    from .logger import logger
    from .settings import AppSettings
    from .vfx_breakdown_model import VFXBreakdownModel, ValidatedComboBoxDelegate
    from .vfx_breakdown_widget import VFXBreakdownWidget
    from .bid_selector_widget import CollapsibleGroupBox
except ImportError:
    import logging
    logger = logging.getLogger("FFPackageManager")
    from settings import AppSettings
    from vfx_breakdown_model import VFXBreakdownModel, ValidatedComboBoxDelegate
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
        self.current_bid_data = None  # Store full bid data for accessing sg_bid_assets

        # Cached schema information for Assets
        self.asset_entity_type = "CustomEntity07"
        self.asset_field_names = []
        self.asset_field_labels = {}

        # Fields to display for Asset items, in order
        self.asset_field_allowlist = [
            "id",
            "code",
            "sg_bid_asset_type",
            "sg_bidding_notes",
        ]

        # Field schema information (data types and list values)
        self.field_schema = {}

        # UI widgets for assets selector
        self.bid_assets_combo = None
        self.bid_assets_set_btn = None
        self.bid_assets_refresh_btn = None
        self.bid_assets_status_label = None

        # Reusable assets widget (uses VFXBreakdownWidget for table display)
        self.assets_widget = None

        # Line Items validation
        self.line_item_names = []  # List of Line Item names from current Price List
        self.asset_type_delegate = None  # Delegate for sg_bid_asset_type column

        self._build_ui()

    def _build_ui(self):
        """Build the Assets tab UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        # Selector group (collapsible)
        self.bid_assets_selector_group = CollapsibleGroupBox("Bid Assets")
        selector_group = self.bid_assets_selector_group

        selector_row = QtWidgets.QHBoxLayout()
        selector_label = QtWidgets.QLabel("Bid Assets:")
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

        # Add info label for linked Bid Assets
        self.bid_assets_info_label = QtWidgets.QLabel("")
        self.bid_assets_info_label.setObjectName("bidAssetsInfoLabel")
        self.bid_assets_info_label.setStyleSheet("color: #6b9bd1; font-weight: bold; padding: 2px 0;")
        selector_group.addWidget(self.bid_assets_info_label)

        # Create reusable Assets widget (reusing VFXBreakdownWidget) before adding selector_group to layout
        self.assets_widget = VFXBreakdownWidget(self.sg_session, show_toolbar=True, settings_key="assets", parent=self)

        # Add search and sort toolbar to the selector group
        if self.assets_widget.toolbar_widget:
            selector_group.addWidget(self.assets_widget.toolbar_widget)

        layout.addWidget(selector_group)

        # Configure the model to use Asset-specific columns
        # Override the default VFX Breakdown columns with Asset columns
        if hasattr(self.assets_widget, 'model') and self.assets_widget.model:
            self.assets_widget.model.column_fields = self.asset_field_allowlist.copy()
            # Set entity type to CustomEntity07 (Asset items) instead of default CustomEntity02
            self.assets_widget.model.entity_type = "CustomEntity07"
            logger.info(f"Configured Assets widget model with fields: {self.asset_field_allowlist} and entity_type: CustomEntity07")

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

    def _update_bid_assets_info_label(self):
        """Update the info label to show linked Bid Assets from current Bid."""
        if not self.current_bid_data:
            self.bid_assets_info_label.setText("")
            self.bid_assets_selector_group.setAdditionalInfo("")
            return

        # Get linked Bid Assets from Bid
        linked_bid_assets = self.current_bid_data.get("sg_bid_assets")
        if not linked_bid_assets:
            self.bid_assets_info_label.setText("")
            self.bid_assets_selector_group.setAdditionalInfo("")
            return

        # Extract bid assets name
        if isinstance(linked_bid_assets, dict):
            bid_assets_name = linked_bid_assets.get("name") or linked_bid_assets.get("code") or f"ID {linked_bid_assets.get('id', 'N/A')}"
            self.bid_assets_info_label.setText(f"Linked to current Bid: {bid_assets_name}")
            self.bid_assets_selector_group.setAdditionalInfo(f"Linked to current Bid: {bid_assets_name}")
        else:
            self.bid_assets_info_label.setText("")
            self.bid_assets_selector_group.setAdditionalInfo("")

    def set_bid(self, bid_data, project_id):
        """Set the current bid and load associated bid assets.

        Args:
            bid_data: Dictionary containing Bid (CustomEntity06) data, or None
            project_id: ID of the project
        """
        self.current_bid_data = bid_data
        self.current_bid_id = bid_data.get('id') if bid_data else None
        self.current_project_id = project_id

        # Clear current selection and add placeholder
        self.bid_assets_combo.blockSignals(True)
        self.bid_assets_combo.clear()
        self.bid_assets_combo.addItem("-- Select Bid Assets --", None)
        self.bid_assets_combo.blockSignals(False)

        if not self.current_bid_id or not project_id:
            self._set_bid_assets_status("Select a Bid to view Bid Assets.")
            self.assets_widget.clear_data()
            self.bid_assets_set_btn.setEnabled(False)
            return

        # Fetch schema if not already loaded
        if not self.field_schema:
            self._fetch_asset_schema()

        # Refresh the bid assets list and auto-select the one linked to this bid
        self._refresh_bid_assets()

    def _fetch_asset_schema(self):
        """Fetch the schema for CustomEntity07 (Asset items) from ShotGrid."""
        try:
            # Get schema for CustomEntity07
            schema = self.sg_session.sg.schema_field_read("CustomEntity07")

            # Build field schema dictionary for allowlisted fields only
            for field_name in self.asset_field_allowlist:
                if field_name not in schema:
                    logger.warning(f"Field {field_name} not found in CustomEntity07 schema")
                    continue

                field_info = schema[field_name]
                self.field_schema[field_name] = {
                    "data_type": field_info.get("data_type", {}).get("value"),
                    "properties": field_info.get("properties", {}),
                    "editable": field_info.get("editable", {}).get("value", True),
                    "display_name": field_info.get("name", {}).get("value", field_name)
                }

                # Store list values for list fields
                if field_info.get("data_type", {}).get("value") == "list":
                    list_values = field_info.get("properties", {}).get("valid_values", {}).get("value", [])
                    self.field_schema[field_name]["list_values"] = list_values

            logger.info(f"Fetched schema for CustomEntity07 with {len(self.field_schema)} fields from allowlist")

            # Update the model's column headers with display names
            if hasattr(self.assets_widget, 'model') and self.assets_widget.model:
                display_names = {field: self.field_schema[field]["display_name"]
                                for field in self.asset_field_allowlist
                                if field in self.field_schema}
                # Override display name for 'id' field to show 'SG ID'
                if "id" in display_names:
                    display_names["id"] = "SG ID"
                self.assets_widget.model.set_column_headers(display_names)
                logger.info(f"Set column headers with display names: {display_names}")

        except Exception as e:
            logger.error(f"Failed to fetch schema for CustomEntity07: {e}", exc_info=True)
            self._set_bid_assets_status("Failed to fetch asset schema.", is_error=True)

    def _refresh_bid_assets(self):
        """Refresh the list of Bid Assets for the current bid."""
        if not self.current_project_id or not self.current_bid_id:
            return

        try:
            # Query CustomEntity08 (Bid Assets) filtered by parent bid
            filters = [
                ["project", "is", {"type": "Project", "id": self.current_project_id}],
                ["sg_parent_bid", "is", {"type": "CustomEntity06", "id": self.current_bid_id}]
            ]

            bid_assets_list = self.sg_session.sg.find(
                "CustomEntity08",
                filters,
                ["code", "id"]
            )

            # Update combo box
            self.bid_assets_combo.blockSignals(True)
            self.bid_assets_combo.clear()
            self.bid_assets_combo.addItem("-- Select Bid Assets --", None)

            for bid_assets in sorted(bid_assets_list, key=lambda x: x.get("code", "")):
                self.bid_assets_combo.addItem(bid_assets.get("code", "Unnamed"), bid_assets["id"])

            self.bid_assets_combo.blockSignals(False)

            if bid_assets_list:
                self._set_bid_assets_status(f"Found {len(bid_assets_list)} Bid Assets")
                self.bid_assets_set_btn.setEnabled(True)

                # Auto-select the Bid Assets linked to this Bid (if any)
                linked_bid_assets_id = None
                if self.current_bid_data:
                    linked_bid_assets = self.current_bid_data.get("sg_bid_assets")
                    if linked_bid_assets and isinstance(linked_bid_assets, dict):
                        linked_bid_assets_id = linked_bid_assets.get("id")

                # Try to find and select the linked Bid Assets
                if linked_bid_assets_id:
                    for i in range(self.bid_assets_combo.count()):
                        if self.bid_assets_combo.itemData(i) == linked_bid_assets_id:
                            self.bid_assets_combo.setCurrentIndex(i)
                            logger.info(f"Auto-selected Bid Assets {linked_bid_assets_id} linked to current Bid")
                            break
                    else:
                        # Linked Bid Assets not found
                        logger.warning(f"Linked Bid Assets {linked_bid_assets_id} not found in project")
                # If no linked Bid Assets, leave at placeholder (index 0)
                # Don't auto-select - user must explicitly choose

                # Update info label to show linked Bid Assets
                self._update_bid_assets_info_label()
            else:
                self._set_bid_assets_status("No Bid Assets found for this project.")
                self.bid_assets_set_btn.setEnabled(False)
                self.assets_widget.clear_data()
                self.bid_assets_info_label.setText("")

        except Exception as e:
            logger.error(f"Failed to refresh Bid Assets: {e}", exc_info=True)
            self._set_bid_assets_status("Failed to load Bid Assets.", is_error=True)

    def _on_bid_assets_changed(self, index):
        """Handle Bid Assets selection change."""
        if index < 0:
            self.assets_widget.clear_data()
            return

        bid_assets_id = self.bid_assets_combo.currentData()
        if not bid_assets_id:
            # Placeholder selected, clear the table
            self.assets_widget.clear_data()
            return

        # Load asset items for this Bid Assets
        self._load_asset_items(bid_assets_id)

    def _load_line_item_names(self):
        """Query Line Items from the current Bid's Price List for validation.

        Returns:
            List of Line Item code names
        """
        if not self.current_bid_id:
            return []

        try:
            # Query the Bid to get its Price List (sg_price_list)
            bid_data = self.sg_session.sg.find_one(
                "CustomEntity06",
                [["id", "is", self.current_bid_id]],
                ["sg_price_list"]
            )

            if not bid_data or not bid_data.get("sg_price_list"):
                logger.info("No Price List linked to current Bid")
                return []

            price_list_id = bid_data["sg_price_list"]["id"]

            # Query the Price List to get its linked Line Items
            # Line Items are linked via the Price List's sg_line_items field (multi-entity)
            price_list_data = self.sg_session.sg.find_one(
                "CustomEntity10",
                [["id", "is", price_list_id]],
                ["sg_line_items"]
            )

            if not price_list_data or not price_list_data.get("sg_line_items"):
                logger.info(f"No Line Items linked to Price List {price_list_id}")
                return []

            # Extract Line Item IDs from sg_line_items field
            line_item_refs = price_list_data["sg_line_items"]
            if not isinstance(line_item_refs, list):
                logger.warning(f"sg_line_items is not a list: {type(line_item_refs)}")
                return []

            line_item_ids = [item.get("id") for item in line_item_refs if isinstance(item, dict) and item.get("id")]

            if not line_item_ids:
                logger.info(f"No valid Line Item IDs found in Price List {price_list_id}")
                return []

            # Query Line Items by IDs to get their code names
            line_items = self.sg_session.sg.find(
                "CustomEntity03",
                [["id", "in", line_item_ids]],
                ["code"]
            )

            # Extract code names
            line_item_names = [item.get("code", "") for item in line_items if item.get("code")]
            return line_item_names

        except Exception as e:
            logger.error(f"Failed to query Line Items: {e}", exc_info=True)
            return []

    def _load_asset_items(self, bid_assets_id):
        """Load asset items (CustomEntity07) for the selected Bid Assets.

        Args:
            bid_assets_id: ID of the Bid Assets (CustomEntity08)
        """
        try:
            # Query Line Items for validation
            self.line_item_names = self._load_line_item_names()

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

            # Apply validated combobox delegate to sg_bid_asset_type column
            self._apply_asset_type_delegate()

            display_name = self.bid_assets_combo.currentText()
            if asset_items:
                self._set_bid_assets_status(f"Loaded {len(asset_items)} Asset item(s) for '{display_name}'.")
            else:
                self._set_bid_assets_status(f"No Asset items linked to '{display_name}'.")

        except Exception as e:
            logger.error(f"Failed to load asset items: {e}", exc_info=True)
            self._set_bid_assets_status("Failed to load asset items.", is_error=True)

    def _apply_asset_type_delegate(self):
        """Apply ValidatedComboBoxDelegate to the sg_bid_asset_type column."""
        if not self.assets_widget or not hasattr(self.assets_widget, 'table_view'):
            return

        try:
            # Find the column index for sg_bid_asset_type
            if hasattr(self.assets_widget, 'model') and self.assets_widget.model:
                try:
                    col_idx = self.assets_widget.model.column_fields.index("sg_bid_asset_type")
                except ValueError:
                    # Column not present
                    logger.warning("sg_bid_asset_type column not found in model")
                    return

                # Create or update the delegate
                if self.asset_type_delegate is None:
                    self.asset_type_delegate = ValidatedComboBoxDelegate(self.line_item_names, self.assets_widget.table_view)
                    self.assets_widget.table_view.setItemDelegateForColumn(col_idx, self.asset_type_delegate)
                    logger.info(f"Applied ValidatedComboBoxDelegate to sg_bid_asset_type column (index {col_idx}) with {len(self.line_item_names)} Line Items")
                else:
                    # Update existing delegate with new Line Item names
                    self.asset_type_delegate.update_valid_values(self.line_item_names)
                    # Trigger repaint
                    self.assets_widget.table_view.viewport().update()
                    logger.info(f"Updated ValidatedComboBoxDelegate with {len(self.line_item_names)} Line Items")

        except Exception as e:
            logger.error(f"Failed to apply asset type delegate: {e}", exc_info=True)

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

            # Link to current Bid if one is selected
            if self.current_bid_id:
                bid_assets_data["sg_parent_bid"] = {"type": "CustomEntity06", "id": self.current_bid_id}

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
