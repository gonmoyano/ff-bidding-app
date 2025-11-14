"""
Rates Tab
Contains UI and logic for managing Price Lists (CustomEntity10).
"""

from PySide6 import QtWidgets, QtCore

try:
    from .logger import logger
    from .settings import AppSettings
    from .bid_selector_widget import CollapsibleGroupBox
    from .vfx_breakdown_widget import VFXBreakdownWidget, FormulaDelegate
    from .formula_evaluator import FormulaEvaluator
except ImportError:
    import logging
    logger = logging.getLogger("FFPackageManager")
    from settings import AppSettings
    from bid_selector_widget import CollapsibleGroupBox
    from vfx_breakdown_widget import VFXBreakdownWidget, FormulaDelegate
    from formula_evaluator import FormulaEvaluator


class RatesTab(QtWidgets.QWidget):
    """Rates tab widget for managing Price Lists."""

    def __init__(self, sg_session, parent=None):
        """Initialize the Rates tab.

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
        self.current_bid_data = None  # Store full bid data for accessing sg_price_list
        self.current_price_list_id = None  # Store currently selected price list
        self.current_price_list_data = None  # Store full price list data

        # UI widgets for price lists selector
        self.price_lists_combo = None
        self.price_lists_set_btn = None
        self.price_lists_refresh_btn = None
        self.price_lists_status_label = None
        self.price_lists_info_label = None  # Info label for Rate Card
        self.price_lists_group_box = None  # CollapsibleGroupBox for Price Lists

        # Rate Card widgets and data
        self.rate_card_combo = None
        self.rate_card_set_btn = None
        self.rate_card_status_label = None
        self.rate_card_widget = None
        self.rate_card_field_schema = {}
        self.rate_card_field_allowlist = []  # Will be populated dynamically with _rate fields

        # Line Items widgets and data
        self.line_items_widget = None
        self.line_items_field_schema = {}
        self.line_items_field_allowlist = []  # Will be populated dynamically with _mandays fields

        self._build_ui()

    def _build_ui(self):
        """Build the Rates tab UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        # Selector group (collapsible)
        self.price_lists_selector_group = CollapsibleGroupBox("Price Lists")
        selector_group = self.price_lists_selector_group
        self.price_lists_group_box = selector_group

        selector_row = QtWidgets.QHBoxLayout()
        selector_label = QtWidgets.QLabel("Price Lists:")
        selector_row.addWidget(selector_label)

        self.price_lists_combo = QtWidgets.QComboBox()
        self.price_lists_combo.setMinimumWidth(250)
        self.price_lists_combo.currentIndexChanged.connect(self._on_price_lists_changed)
        selector_row.addWidget(self.price_lists_combo, stretch=1)

        self.price_lists_set_btn = QtWidgets.QPushButton("Set as Current")
        self.price_lists_set_btn.setEnabled(False)
        self.price_lists_set_btn.clicked.connect(self._on_set_current_price_list)
        selector_row.addWidget(self.price_lists_set_btn)

        self.price_lists_rate_cards_btn = QtWidgets.QPushButton("Rate Cards")
        self.price_lists_rate_cards_btn.clicked.connect(self._on_open_rate_cards_dialog)
        selector_row.addWidget(self.price_lists_rate_cards_btn)

        self.price_lists_add_btn = QtWidgets.QPushButton("Add")
        self.price_lists_add_btn.clicked.connect(self._on_add_price_list)
        selector_row.addWidget(self.price_lists_add_btn)

        self.price_lists_remove_btn = QtWidgets.QPushButton("Remove")
        self.price_lists_remove_btn.clicked.connect(self._on_remove_price_list)
        selector_row.addWidget(self.price_lists_remove_btn)

        self.price_lists_rename_btn = QtWidgets.QPushButton("Rename")
        self.price_lists_rename_btn.clicked.connect(self._on_rename_price_list)
        selector_row.addWidget(self.price_lists_rename_btn)

        self.price_lists_refresh_btn = QtWidgets.QPushButton("Refresh")
        self.price_lists_refresh_btn.clicked.connect(self._refresh_price_lists)
        selector_row.addWidget(self.price_lists_refresh_btn)

        selector_group.addLayout(selector_row)

        self.price_lists_status_label = QtWidgets.QLabel("Select a Bid to view Price Lists.")
        self.price_lists_status_label.setObjectName("priceListsStatusLabel")
        self.price_lists_status_label.setStyleSheet("color: #a0a0a0; padding: 2px 0;")
        selector_group.addWidget(self.price_lists_status_label)

        # Add info label for Rate Card
        self.price_lists_info_label = QtWidgets.QLabel("")
        self.price_lists_info_label.setObjectName("priceListsInfoLabel")
        self.price_lists_info_label.setStyleSheet("color: #6b9bd1; font-weight: bold; padding: 2px 0;")
        selector_group.addWidget(self.price_lists_info_label)

        # Create Line Items widget before adding selector_group to layout
        line_items_content = self._create_line_items_tab()

        # Add search and sort toolbar to the selector group
        if self.line_items_widget.toolbar_widget:
            selector_group.addWidget(self.line_items_widget.toolbar_widget)

        layout.addWidget(selector_group)

        # Add Line Items widget content
        layout.addWidget(line_items_content)

    def _create_line_items_tab(self):
        """Create the Line Items nested tab content with auto-loading from Price List."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)

        # Create Line Items widget (reusing VFXBreakdownWidget) with toolbar for search/sort
        self.line_items_widget = VFXBreakdownWidget(self.sg_session, show_toolbar=True, entity_name="Line Item", settings_key="line_items", parent=self)

        # Set context provider so the widget can access current_price_list_id, current_project_id, etc.
        self.line_items_widget.context_provider = self

        # Set entity type - columns will be configured when schema is fetched
        if hasattr(self.line_items_widget, 'model') and self.line_items_widget.model:
            self.line_items_widget.model.entity_type = "CustomEntity03"
            logger.info(f"Configured Line Items widget model for CustomEntity03")

            # Create formula evaluator for this table with cross-sheet references
            # Build sheet_models dictionary for cross-sheet references
            sheet_models = {}
            if hasattr(self, 'rate_card_widget') and hasattr(self.rate_card_widget, 'model') and self.rate_card_widget.model:
                sheet_models['Rate Card'] = self.rate_card_widget.model
                logger.info("Added 'Rate Card' sheet to Line Items formula evaluator")

            self.line_items_formula_evaluator = FormulaEvaluator(
                self.line_items_widget.model,
                sheet_models=sheet_models
            )
            # Set the formula evaluator on the model for dependency tracking
            self.line_items_widget.model.set_formula_evaluator(self.line_items_formula_evaluator)

        # Connect widget signals
        self.line_items_widget.statusMessageChanged.connect(lambda msg, err: logger.info(f"Line Items status: {msg}"))

        layout.addWidget(self.line_items_widget)

        return widget

    def _set_price_lists_status(self, message, is_error=False):
        """Set the status message for price lists.

        Args:
            message: Status message
            is_error: Whether this is an error message
        """
        if is_error:
            self.price_lists_status_label.setStyleSheet("color: #ff6b6b; padding: 2px 0;")
        else:
            self.price_lists_status_label.setStyleSheet("color: #a0a0a0; padding: 2px 0;")
        self.price_lists_status_label.setText(message)

    def set_bid(self, bid_data, project_id):
        """Set the current bid and load associated price lists.

        Args:
            bid_data: Dictionary containing Bid (CustomEntity06) data, or None
            project_id: ID of the project

        CASCADE LOGIC:
        - If Bid == placeholder OR no linked Price List → Price List set to placeholder → cascade continues
        """
        logger.info(f"set_bid() called with bid_data={bid_data}, project_id={project_id}")

        self.current_bid_data = bid_data
        self.current_bid_id = bid_data.get('id') if bid_data else None
        self.current_project_id = project_id

        # ALWAYS reset Price List to placeholder first - do this BEFORE any checks
        logger.info("Resetting Price List dropdown to placeholder")
        self.price_lists_combo.blockSignals(True)
        self.price_lists_combo.clear()
        self.price_lists_combo.addItem("-- Select Price List --", None)
        self.price_lists_combo.setCurrentIndex(0)
        self.price_lists_combo.blockSignals(False)

        # Verify the dropdown is actually at placeholder
        current_text = self.price_lists_combo.currentText()
        current_data = self.price_lists_combo.currentData()
        logger.info(f"Price List dropdown after reset: text='{current_text}', data={current_data}, index={self.price_lists_combo.currentIndex()}")

        if not self.current_bid_id or not project_id:
            # No bid selected - ALWAYS trigger cascade to clear downstream
            logger.info("No Bid selected - triggering cascade to clear Price List, Rate Card, and Line Items")
            self._set_price_lists_status("Select a Bid to view Price Lists.")
            self._on_price_lists_changed(0)
            return

        # Check if Bid has a valid linked Price List
        linked_price_list = bid_data.get("sg_price_list") if bid_data else None
        has_valid_price_list = False

        if linked_price_list:
            if isinstance(linked_price_list, dict):
                # Single entity reference - check if it has an ID
                has_valid_price_list = bool(linked_price_list.get("id"))
            elif isinstance(linked_price_list, list) and linked_price_list:
                # Multi-entity reference - check if first item has an ID
                has_valid_price_list = bool(linked_price_list[0].get("id") if linked_price_list[0] else None)

        if not has_valid_price_list:
            # Bid has no valid linked Price List - ALWAYS trigger cascade
            logger.info(f"Bid has no valid linked Price List (sg_price_list={linked_price_list}) - triggering cascade")
            self._set_price_lists_status("Select a Bid to view Price Lists.")
            self._on_price_lists_changed(0)
            return

        # Refresh the price lists and auto-select the one linked to this bid
        logger.info(f"Bid has valid linked Price List - refreshing Price Lists")
        self._refresh_price_lists()

    def _refresh_price_lists(self):
        """Refresh the list of Price Lists for the current bid.

        IMPORTANT: This should only be called when a valid Bid is selected.
        If called with no Bid, it will reset to placeholder and cascade.
        """
        if not self.current_project_id or not self.current_bid_id:
            logger.warning("_refresh_price_lists() called with no Bid/Project - resetting to placeholder")
            # Ensure dropdown is at placeholder
            self.price_lists_combo.blockSignals(True)
            self.price_lists_combo.clear()
            self.price_lists_combo.addItem("-- Select Price List --", None)
            self.price_lists_combo.setCurrentIndex(0)
            self.price_lists_combo.blockSignals(False)
            # Trigger cascade
            self._on_price_lists_changed(0)
            return

        try:
            # Query CustomEntity10 (Price Lists) filtered by project
            filters = [
                ["project", "is", {"type": "Project", "id": self.current_project_id}]
            ]

            price_lists_list = self.sg_session.sg.find(
                "CustomEntity10",
                filters,
                ["code", "id", "description"]
            )

            # Update combo box
            self.price_lists_combo.blockSignals(True)
            self.price_lists_combo.clear()
            self.price_lists_combo.addItem("-- Select Price List --", None)

            for price_list in sorted(price_lists_list, key=lambda x: x.get("code", "")):
                self.price_lists_combo.addItem(price_list.get("code", "Unnamed"), price_list["id"])

            self.price_lists_combo.blockSignals(False)

            if price_lists_list:
                self._set_price_lists_status(f"Found {len(price_lists_list)} Price List(s)")
                self.price_lists_set_btn.setEnabled(True)

                # Auto-select the Price List linked to this Bid (if any)
                linked_price_list_id = None
                if self.current_bid_data:
                    linked_price_list = self.current_bid_data.get("sg_price_list")
                    if linked_price_list and isinstance(linked_price_list, dict):
                        linked_price_list_id = linked_price_list.get("id")

                # Try to find and select the linked Price List
                if linked_price_list_id:
                    for i in range(self.price_lists_combo.count()):
                        if self.price_lists_combo.itemData(i) == linked_price_list_id:
                            self.price_lists_combo.setCurrentIndex(i)
                            logger.info(f"Auto-selected Price List {linked_price_list_id} linked to current Bid")
                            break
                    else:
                        # Linked Price List not found - trigger cascade
                        logger.warning(f"Linked Price List {linked_price_list_id} not found in project")
                        self._on_price_lists_changed(0)  # Manually trigger cascade
                else:
                    # No linked Price List - trigger cascade
                    logger.info("No Price List linked to Bid - selecting placeholder")
                    self._on_price_lists_changed(0)  # Manually trigger cascade
            else:
                self._set_price_lists_status("No Price Lists found for this project.")
                self.price_lists_set_btn.setEnabled(False)
                # Trigger cascade to clear downstream
                self._on_price_lists_changed(0)

        except Exception as e:
            logger.error(f"Failed to refresh Price Lists: {e}", exc_info=True)
            self._set_price_lists_status("Failed to load Price Lists.", is_error=True)

    def _on_price_lists_changed(self, index):
        """Handle Price Lists selection change.

        CASCADE LOGIC:
        - If Price List == placeholder → ALWAYS clear Line Items
        - If Price List is valid → ALWAYS refresh Line Items
        """
        if index < 0:
            self.current_price_list_id = None
            self.current_price_list_data = None
            self._update_price_list_info_label(None)
            # Ensure cascade happens even for invalid index
            if hasattr(self, 'line_items_widget'):
                self._clear_line_items_tab()
            return

        price_list_id = self.price_lists_combo.currentData()
        if not price_list_id:
            # Placeholder selected - ALWAYS cascade to clear downstream
            self.current_price_list_id = None
            self.current_price_list_data = None
            self._set_price_lists_status("Select a Price List to view details.")
            self._update_price_list_info_label(None)
            # ALWAYS Clear Line Items tab when placeholder selected
            if hasattr(self, 'line_items_widget'):
                self._clear_line_items_tab()
            logger.info("Price List set to placeholder - cascaded to clear Line Items")
            return

        # Store the selected price list ID
        self.current_price_list_id = price_list_id
        display_name = self.price_lists_combo.currentText()
        self._set_price_lists_status(f"Selected Price List: '{display_name}'.")
        logger.info(f"Price List changed to: {display_name} (ID: {price_list_id})")

        # Fetch full price list data with linked entities
        self._fetch_price_list_data(price_list_id)

        # ALWAYS Refresh Line Items tab when valid Price List selected
        if hasattr(self, 'line_items_widget'):
            self._load_line_items()

    def _fetch_price_list_data(self, price_list_id):
        """Fetch full price list data including linked entities."""
        try:
            price_list_data = self.sg_session.sg.find_one(
                "CustomEntity10",
                [["id", "is", price_list_id]],
                ["code", "sg_rate_card", "sg_line_items"]
            )
            self.current_price_list_data = price_list_data
            logger.info(f"Fetched Price List data: {price_list_data}")
            # Update the info label with Rate Card and Line Item details
            self._update_price_list_info_label(price_list_data)
            # Load Rate Card data for formula evaluator
            self._load_rate_card_for_formula_evaluator()
        except Exception as e:
            logger.error(f"Failed to fetch Price List data: {e}", exc_info=True)
            self.current_price_list_data = None
            self._update_price_list_info_label(None)

    def _update_price_list_info_label(self, price_list_data):
        """Update the price list info label and group box title with Rate Card info.

        Args:
            price_list_data: Price List data dict or None
        """
        if not price_list_data:
            # Clear labels and group box title if no price list selected
            self.price_lists_status_label.setText("Select a Bid to view Price Lists.")
            self.price_lists_info_label.setText("")
            self.price_lists_selector_group.setAdditionalInfo("")
            return

        # Get price list name for title bar
        price_list_name = price_list_data.get("code") or f"Price List {price_list_data.get('id', 'N/A')}"
        # Start with "Linked to Current Bid: (name)"
        title_text = f"Linked to Current Bid: {price_list_name}"

        # Show the Price List linked to current Bid
        self.price_lists_info_label.setText(f"Linked to current Bid: {price_list_name}")
        self.price_lists_selector_group.setAdditionalInfo(f"Linked to current Bid: {price_list_name}")

        # Add Rate Card info to title text
        rate_card = price_list_data.get("sg_rate_card")
        if rate_card:
            # Extract rate card name/code
            if isinstance(rate_card, dict):
                rate_card_name = rate_card.get("name") or rate_card.get("code") or f"ID {rate_card.get('id', 'N/A')}"
            elif isinstance(rate_card, list) and rate_card:
                rate_card_name = rate_card[0].get("name") or rate_card[0].get("code") or f"ID {rate_card[0].get('id', 'N/A')}"
            else:
                rate_card_name = str(rate_card)
            title_text += f" | Rate Card: {rate_card_name}"

        # Update the status label to just show the price list name
        self.price_lists_status_label.setText(f"Selected Price List: '{price_list_name}'.")

        # Update the group box title with price list name and info (for collapsed state)
        self.price_lists_group_box.setAdditionalInfo(title_text)

    def _load_rate_card_for_formula_evaluator(self):
        """Load the Rate Card data for the current Price List into the formula evaluator.

        This method creates/updates a Rate Card widget to provide data for cross-sheet
        references in Line Items formulas (e.g., 'Rate Card'!model.1).
        """
        # Clear existing Rate Card widget if any
        if self.rate_card_widget:
            self.rate_card_widget.clear_data()
            self.rate_card_widget = None

        # Clear the sheet_models for the formula evaluator
        if hasattr(self, 'line_items_formula_evaluator'):
            self.line_items_formula_evaluator.sheet_models.clear()
            logger.info("Cleared Rate Card from formula evaluator")

        # Check if we have a valid Price List with a Rate Card
        if not self.current_price_list_data:
            logger.info("No Price List data - cannot load Rate Card for formula evaluator")
            return

        rate_card = self.current_price_list_data.get("sg_rate_card")
        if not rate_card:
            logger.info("No Rate Card assigned to current Price List")
            return

        # Extract Rate Card ID
        rate_card_id = None
        if isinstance(rate_card, dict):
            rate_card_id = rate_card.get("id")
        elif isinstance(rate_card, list) and rate_card:
            rate_card_id = rate_card[0].get("id") if rate_card[0] else None

        if not rate_card_id:
            logger.warning(f"Could not extract Rate Card ID from: {rate_card}")
            return

        try:
            # Fetch Rate Card schema if not already loaded
            if not self.rate_card_field_schema:
                self._fetch_rate_card_schema()

            # Query the Rate Card data
            fields = self.rate_card_field_allowlist.copy()
            rate_card_data = self.sg_session.sg.find_one(
                "CustomNonProjectEntity01",
                [["id", "is", rate_card_id]],
                fields
            )

            if not rate_card_data:
                logger.warning(f"Rate Card {rate_card_id} not found")
                return

            # Create a hidden Rate Card widget to hold the data
            self.rate_card_widget = VFXBreakdownWidget(
                self.sg_session,
                show_toolbar=False,
                entity_name="Rate Card",
                settings_key="rate_card_hidden",
                parent=self
            )
            self.rate_card_widget.hide()  # Hide it since it's only for data

            # Configure the model
            if hasattr(self.rate_card_widget, 'model') and self.rate_card_widget.model:
                self.rate_card_widget.model.entity_type = "CustomNonProjectEntity01"
                self.rate_card_widget.model.column_fields = self.rate_card_field_allowlist.copy()

                # Load the Rate Card data
                self.rate_card_widget.load_bidding_scenes([rate_card_data], field_schema=self.rate_card_field_schema)

                # Add to formula evaluator's sheet_models
                if hasattr(self, 'line_items_formula_evaluator'):
                    self.line_items_formula_evaluator.sheet_models['Rate Card'] = self.rate_card_widget.model
                    logger.info(f"Loaded Rate Card {rate_card_id} into formula evaluator")

                    # Trigger refresh of all cells in Line Items to recalculate formulas
                    if hasattr(self.line_items_widget, 'model') and self.line_items_widget.model:
                        # Emit layoutChanged to trigger view refresh
                        self.line_items_widget.model.layoutChanged.emit()
                        logger.info("Triggered view refresh to recalculate formulas in Line Items")

        except Exception as e:
            logger.error(f"Failed to load Rate Card for formula evaluator: {e}", exc_info=True)

    def _fetch_rate_card_schema(self):
        """Fetch the schema for CustomNonProjectEntity01 (Rate Cards) and build field allowlist."""
        try:
            schema = self.sg_session.sg.schema_field_read("CustomNonProjectEntity01")

            # Build field allowlist: start with basic fields, then add all fields ending with "_rate"
            self.rate_card_field_allowlist = ["id", "code"]

            # Find all fields ending with "_rate"
            rate_fields = []
            for field_name in schema.keys():
                if field_name.endswith("_rate"):
                    rate_fields.append(field_name)

            # Sort rate fields alphabetically for consistent display
            rate_fields.sort()
            self.rate_card_field_allowlist.extend(rate_fields)

            logger.info(f"Built Rate Card field allowlist with {len(self.rate_card_field_allowlist)} fields: {self.rate_card_field_allowlist}")

            # Build field schema dictionary for allowlisted fields
            for field_name in self.rate_card_field_allowlist:
                if field_name not in schema:
                    logger.warning(f"Field {field_name} not found in CustomNonProjectEntity01 schema")
                    continue

                field_info = schema[field_name]
                self.rate_card_field_schema[field_name] = {
                    "data_type": field_info.get("data_type", {}).get("value"),
                    "properties": field_info.get("properties", {}),
                    "editable": field_info.get("editable", {}).get("value", True),
                    "display_name": field_info.get("name", {}).get("value", field_name)
                }

            logger.info(f"Fetched schema for CustomNonProjectEntity01 with {len(self.rate_card_field_schema)} fields")

        except Exception as e:
            logger.error(f"Failed to fetch schema for CustomNonProjectEntity01: {e}", exc_info=True)

    def _on_set_current_price_list(self):
        """Set the selected Price List as current for the Bid."""
        if not self.current_bid_id:
            QtWidgets.QMessageBox.warning(self, "No Bid Selected", "Please select a Bid first.")
            return

        price_list_id = self.price_lists_combo.currentData()
        if not price_list_id:
            QtWidgets.QMessageBox.warning(self, "No Price List Selected", "Please select a Price List.")
            return

        try:
            # Update the Bid's sg_price_list field
            self.sg_session.sg.update(
                "CustomEntity06",
                self.current_bid_id,
                {"sg_price_list": {"type": "CustomEntity10", "id": price_list_id}}
            )

            price_list_name = self.price_lists_combo.currentText()
            self._set_price_lists_status(f"Set '{price_list_name}' as current Price List.")
            QtWidgets.QMessageBox.information(
                self,
                "Success",
                f"'{price_list_name}' is now the current Price List for this Bid."
            )

            logger.info(f"Set Price List {price_list_id} as current for Bid {self.current_bid_id}")

        except Exception as e:
            logger.error(f"Failed to set current Price List: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to set current Price List:\n{str(e)}"
            )

    def _on_add_price_list(self):
        """Add a new Price List."""
        if not self.current_project_id:
            QtWidgets.QMessageBox.warning(self, "No Project Selected", "Please select a project first.")
            return

        # Prompt for name
        name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Add Price List",
            "Enter name for new Price List:"
        )

        if not ok or not name:
            return

        try:
            # Create CustomEntity10 (Price List)
            price_list_data = {
                "code": name,
                "project": {"type": "Project", "id": self.current_project_id}
            }

            new_price_list = self.sg_session.sg.create("CustomEntity10", price_list_data)

            logger.info(f"Created Price List: {name} (ID: {new_price_list['id']})")
            self._set_price_lists_status(f"Created Price List '{name}'.")

            # Refresh list and select new one
            self._refresh_price_lists()

            # Find and select the new price list
            for i in range(self.price_lists_combo.count()):
                if self.price_lists_combo.itemData(i) == new_price_list['id']:
                    self.price_lists_combo.setCurrentIndex(i)
                    break

        except Exception as e:
            logger.error(f"Failed to create Price List: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to create Price List:\n{str(e)}"
            )

    def _on_remove_price_list(self):
        """Remove the selected Price List."""
        price_list_id = self.price_lists_combo.currentData()
        if not price_list_id:
            QtWidgets.QMessageBox.warning(self, "No Price List Selected", "Please select a Price List to remove.")
            return

        price_list_name = self.price_lists_combo.currentText()

        # Confirm deletion
        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete Price List '{price_list_name}'?\n\n"
            f"This action cannot be undone.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply != QtWidgets.QMessageBox.Yes:
            return

        try:
            # Delete the Price List (CustomEntity10)
            self.sg_session.sg.delete("CustomEntity10", price_list_id)

            logger.info(f"Deleted Price List: {price_list_name} (ID: {price_list_id})")
            self._set_price_lists_status(f"Deleted Price List '{price_list_name}'.")

            # Refresh list
            self._refresh_price_lists()

        except Exception as e:
            logger.error(f"Failed to delete Price List: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to delete Price List:\n{str(e)}"
            )

    def _on_rename_price_list(self):
        """Rename the selected Price List."""
        price_list_id = self.price_lists_combo.currentData()
        if not price_list_id:
            QtWidgets.QMessageBox.warning(self, "No Price List Selected", "Please select a Price List to rename.")
            return

        current_name = self.price_lists_combo.currentText()

        # Prompt for new name
        new_name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Rename Price List",
            "Enter new name:",
            text=current_name
        )

        if not ok or not new_name or new_name == current_name:
            return

        try:
            # Update the Price List name
            self.sg_session.sg.update("CustomEntity10", price_list_id, {"code": new_name})

            logger.info(f"Renamed Price List from '{current_name}' to '{new_name}' (ID: {price_list_id})")
            self._set_price_lists_status(f"Renamed to '{new_name}'.")

            # Refresh list and maintain selection
            current_index = self.price_lists_combo.currentIndex()
            self._refresh_price_lists()
            if current_index < self.price_lists_combo.count():
                self.price_lists_combo.setCurrentIndex(current_index)

        except Exception as e:
            logger.error(f"Failed to rename Price List: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to rename Price List:\n{str(e)}"
            )

    def _on_open_rate_cards_dialog(self):
        """Open the Rate Cards dialog."""
        if not self.current_price_list_id:
            QtWidgets.QMessageBox.warning(self, "No Price List Selected", "Please select a Price List first.")
            return

        dialog = RateCardDialog(self.sg_session, self.current_price_list_id, self.current_project_id, self)
        dialog.exec()

        # Refresh Price List data to update the info label with any changes from the dialog
        if self.current_price_list_id:
            self._fetch_price_list_data(self.current_price_list_id)

    # ===========================
    # Line Items Methods
    # ===========================

    def _clear_line_items_tab(self):
        """Clear the Line Items tab.

        CASCADE LOGIC:
        - ALWAYS clears Line Items table when called
        """
        if self.line_items_widget:
            self.line_items_widget.clear_data()
        logger.info("Line Items tab cleared - cleared Line Items table")

    def _load_line_items(self):
        """Load Line Items linked to the current Price List."""
        if not self.current_price_list_id or not self.current_price_list_data:
            self._clear_line_items_tab()
            return

        try:
            logger.info(f"Loading Line Items for Price List ID: {self.current_price_list_id}")

            # Fetch schema if not already loaded
            if not self.line_items_field_schema:
                logger.info("Fetching Line Items schema...")
                self._fetch_line_items_schema()

            # Get Line Items from the Price List's sg_line_items field
            sg_line_items = self.current_price_list_data.get("sg_line_items")
            logger.info(f"Price List sg_line_items field: {sg_line_items}")

            # Build filters for querying Line Items
            filters = []
            line_item_ids = []

            if sg_line_items:
                # sg_line_items could be a list of entity references or a single entity reference
                if isinstance(sg_line_items, list):
                    # Multi-entity reference
                    line_item_ids = [item.get("id") for item in sg_line_items if isinstance(item, dict) and item.get("id")]
                elif isinstance(sg_line_items, dict):
                    # Single entity reference
                    if sg_line_items.get("id"):
                        line_item_ids = [sg_line_items.get("id")]

                if line_item_ids:
                    # Query specific Line Items by IDs
                    filters = [["id", "in", line_item_ids]]
                    logger.info(f"Line Item IDs to fetch: {line_item_ids}")
                else:
                    logger.info("sg_line_items present but no valid IDs found")

            # Fallback: if no Line Items linked via sg_line_items, query all Line Items in project
            if not filters:
                logger.info("No Line Items linked to Price List - querying all Line Items in project as fallback")
                filters = [["project", "is", {"type": "Project", "id": self.current_project_id}]]

            fields = self.line_items_field_allowlist.copy()

            # Ensure we have at least basic fields
            if not fields:
                logger.warning("Field allowlist is empty, using default fields")
                fields = ["id", "code"]

            # Remove virtual fields from query (they don't exist in ShotGrid)
            virtual_fields = ["_calc_price"]
            query_fields = [f for f in fields if f not in virtual_fields]

            logger.info(f"Querying CustomEntity03 with filters: {filters}")
            logger.info(f"Requesting fields: {query_fields}")

            line_items_list = self.sg_session.sg.find(
                "CustomEntity03",
                filters,
                query_fields
            )

            # Add virtual fields to the returned data with default values
            if line_items_list:
                # Get default formula for Price column from settings
                default_price_formula = self.app_settings.get_default_line_items_price_formula()

                for item in line_items_list:
                    for virtual_field in virtual_fields:
                        if virtual_field not in item:
                            # Set default formula for Price column
                            if virtual_field == "_calc_price":
                                item[virtual_field] = default_price_formula
                                logger.debug(f"Set default Price formula for Line Item: {default_price_formula}")
                            else:
                                item[virtual_field] = ""  # Initialize with empty string

            logger.info(f"Query returned {len(line_items_list) if line_items_list else 0} Line Item(s)")

            if line_items_list:
                logger.info(f"Line Items data: {line_items_list}")
                self.line_items_widget.load_bidding_scenes(line_items_list, field_schema=self.line_items_field_schema)
                logger.info(f"Successfully loaded {len(line_items_list)} Line Item(s) into table")

                # Connect signal for Price Static auto-update (do this every time after loading)
                if "_calc_price" in self.line_items_field_allowlist and "sg_price_static" in self.line_items_field_allowlist:
                    if hasattr(self.line_items_widget, 'model') and self.line_items_widget.model:
                        # Disconnect any existing connection first
                        try:
                            self.line_items_widget.model.dataChanged.disconnect(self._on_line_items_data_changed)
                        except:
                            pass

                        # Reconnect the signal
                        self.line_items_widget.model.dataChanged.connect(self._on_line_items_data_changed)
                        logger.info(f"[Price Static] ✓ Connected dataChanged signal for auto-update (after loading)")

                # Initialize sg_price_static with calculated prices
                self._initialize_price_static_values()
            else:
                self.line_items_widget.clear_data()
                logger.info(f"No Line Items found for the given IDs")

        except Exception as e:
            logger.error(f"Failed to load Line Items: {e}", exc_info=True)
            self.line_items_widget.clear_data()

    def _fetch_line_items_schema(self):
        """Fetch the schema for CustomEntity03 (Line Items) and build field allowlist."""
        try:
            schema = self.sg_session.sg.schema_field_read("CustomEntity03")

            # Build field allowlist: start with basic fields, then add all fields ending with "_mandays"
            self.line_items_field_allowlist = ["id", "code"]

            # Find all fields ending with "_mandays"
            mandays_fields = []
            for field_name in schema.keys():
                if field_name.endswith("_mandays"):
                    mandays_fields.append(field_name)

            # Sort mandays fields alphabetically for consistent display
            mandays_fields.sort()
            self.line_items_field_allowlist.extend(mandays_fields)

            # Always add the Price calculated field (may or may not exist in ShotGrid)
            # This is a client-side calculated column
            self.line_items_field_allowlist.append("_calc_price")
            logger.info("Added _calc_price as calculated Price field")

            # Add sg_price_static for storing calculated price values
            if "sg_price_static" in schema:
                self.line_items_field_allowlist.append("sg_price_static")
                logger.info("Added sg_price_static field for storing calculated prices")

            # If sg_price_formula exists, also include it for storing formulas
            if "sg_price_formula" in schema:
                self.line_items_field_allowlist.append("sg_price_formula")
                logger.info("Added sg_price_formula field for formula storage")

            logger.info(f"Built Line Items field allowlist with {len(self.line_items_field_allowlist)} fields: {self.line_items_field_allowlist}")

            # Build field schema dictionary for allowlisted fields
            for field_name in self.line_items_field_allowlist:
                if field_name == "_calc_price":
                    # Virtual calculated field
                    self.line_items_field_schema[field_name] = {
                        "data_type": "text",
                        "properties": {},
                        "editable": True,
                        "display_name": "Price (Calculated)"
                    }
                    continue

                if field_name not in schema:
                    logger.warning(f"Field {field_name} not found in CustomEntity03 schema")
                    continue

                field_info = schema[field_name]
                self.line_items_field_schema[field_name] = {
                    "data_type": field_info.get("data_type", {}).get("value"),
                    "properties": field_info.get("properties", {}),
                    "editable": field_info.get("editable", {}).get("value", True),
                    "display_name": field_info.get("name", {}).get("value", field_name)
                }

            logger.info(f"Fetched schema for CustomEntity03 with {len(self.line_items_field_schema)} fields")

            # Update model's column fields and headers
            if hasattr(self.line_items_widget, 'model') and self.line_items_widget.model:
                self.line_items_widget.model.column_fields = self.line_items_field_allowlist.copy()

                # Make the Price column read-only
                if "_calc_price" in self.line_items_field_allowlist:
                    if "_calc_price" not in self.line_items_widget.model.readonly_columns:
                        self.line_items_widget.model.readonly_columns.append("_calc_price")
                        logger.info("Set _calc_price column as read-only")

                display_names = {field: self.line_items_field_schema[field]["display_name"]
                                for field in self.line_items_field_allowlist
                                if field in self.line_items_field_schema}
                if "id" in display_names:
                    display_names["id"] = "SG ID"
                # Rename calculated field to "Price"
                if "_calc_price" in display_names:
                    display_names["_calc_price"] = "Price"
                # Rename sg_price_static to "Price Static"
                if "sg_price_static" in display_names:
                    display_names["sg_price_static"] = "Price Static"
                self.line_items_widget.model.set_column_headers(display_names)

                # Set up formula delegate for the Price column
                if hasattr(self, 'line_items_formula_evaluator'):
                    price_col_index = self.line_items_field_allowlist.index("_calc_price") if "_calc_price" in self.line_items_field_allowlist else -1
                    if price_col_index >= 0:
                        formula_delegate = FormulaDelegate(self.line_items_formula_evaluator, app_settings=self.app_settings)
                        self.line_items_widget.table_view.setItemDelegateForColumn(price_col_index, formula_delegate)
                        logger.info(f"Set formula delegate for Price column (index {price_col_index}) with app_settings for dynamic currency")

                # Connect to dataChanged signal to auto-update sg_price_static when _calc_price changes
                if "_calc_price" in self.line_items_field_allowlist and "sg_price_static" in self.line_items_field_allowlist:
                    # Disconnect any existing connection first (in case of reload)
                    try:
                        self.line_items_widget.model.dataChanged.disconnect(self._on_line_items_data_changed)
                    except:
                        pass

                    self.line_items_widget.model.dataChanged.connect(self._on_line_items_data_changed)
                    logger.info(f"[Price Static] ✓ Connected dataChanged signal for Price Static auto-update")
                    logger.info(f"[Price Static] Model type: {type(self.line_items_widget.model)}")
                    logger.info(f"[Price Static] Columns: {self.line_items_widget.model.column_fields}")

        except Exception as e:
            logger.error(f"Failed to fetch schema for CustomEntity03: {e}", exc_info=True)

    def _initialize_price_static_values(self):
        """Initialize sg_price_static values from calculated _calc_price formulas."""
        try:
            if not hasattr(self, 'line_items_widget') or not self.line_items_widget:
                return
            if not hasattr(self.line_items_widget, 'model') or not self.line_items_widget.model:
                return
            if not hasattr(self, 'line_items_formula_evaluator') or not self.line_items_formula_evaluator:
                return

            model = self.line_items_widget.model

            # Check if we have both columns
            if "_calc_price" not in model.column_fields or "sg_price_static" not in model.column_fields:
                return

            price_col_idx = model.column_fields.index("_calc_price")
            price_static_col_idx = model.column_fields.index("sg_price_static")

            logger.info(f"Initializing sg_price_static for {model.rowCount()} Line Items...")

            # Process each row
            for row in range(model.rowCount()):
                # Get the _calc_price formula
                price_index = model.index(row, price_col_idx)
                formula = model.data(price_index, QtCore.Qt.EditRole)

                if isinstance(formula, str) and formula.startswith('='):
                    # Evaluate the formula to get the calculated price
                    calculated_price = self.line_items_formula_evaluator.evaluate(formula, row, price_col_idx)

                    # Convert to numeric value
                    if isinstance(calculated_price, (int, float)):
                        # Get current sg_price_static value
                        price_static_index = model.index(row, price_static_col_idx)
                        current_static_price = model.data(price_static_index, QtCore.Qt.EditRole)

                        # Convert current value to numeric for comparison
                        if current_static_price is None:
                            current_static_price = 0
                        elif isinstance(current_static_price, str):
                            try:
                                current_static_price = float(current_static_price)
                            except ValueError:
                                current_static_price = 0

                        # Update if different (with tolerance for floating point comparison)
                        if abs(calculated_price - current_static_price) > 0.01:
                            logger.info(f"  Row {row}: Setting initial sg_price_static = ${calculated_price:,.2f}")
                            model.setData(price_static_index, calculated_price, QtCore.Qt.EditRole)

            logger.info("Finished initializing sg_price_static values")

        except Exception as e:
            logger.error(f"Error in _initialize_price_static_values: {e}", exc_info=True)

    def _on_line_items_data_changed(self, top_left, bottom_right, roles):
        """Handle Line Items data changes to auto-update sg_price_static when _calc_price changes.

        Args:
            top_left: Top-left index of changed region
            bottom_right: Bottom_right index of changed region
            roles: List of changed roles
        """
        try:
            # Check if we have the necessary components
            if not hasattr(self, 'line_items_widget') or not self.line_items_widget:
                return
            if not hasattr(self.line_items_widget, 'model') or not self.line_items_widget.model:
                return
            if not hasattr(self, 'line_items_formula_evaluator') or not self.line_items_formula_evaluator:
                return

            model = self.line_items_widget.model

            # Get column indices
            if "_calc_price" not in model.column_fields or "sg_price_static" not in model.column_fields:
                return

            price_col_idx = model.column_fields.index("_calc_price")
            price_static_col_idx = model.column_fields.index("sg_price_static")

            # Process each changed row
            for row in range(top_left.row(), bottom_right.row() + 1):
                # Get the _calc_price formula
                price_index = model.index(row, price_col_idx)
                formula = model.data(price_index, QtCore.Qt.EditRole)

                if isinstance(formula, str) and formula.startswith('='):
                    # Evaluate the formula to get the calculated price
                    calculated_price = self.line_items_formula_evaluator.evaluate(formula, row, price_col_idx)

                    # Convert to numeric value
                    if isinstance(calculated_price, (int, float)):
                        # Get current sg_price_static value
                        price_static_index = model.index(row, price_static_col_idx)
                        current_static_price = model.data(price_static_index, QtCore.Qt.EditRole)

                        # Convert current value to numeric for comparison
                        if current_static_price is None:
                            current_static_price = 0
                        elif isinstance(current_static_price, str):
                            try:
                                current_static_price = float(current_static_price)
                            except ValueError:
                                current_static_price = 0

                        # Check if the value changed (with small tolerance for floating point comparison)
                        if abs(calculated_price - current_static_price) > 0.01:
                            # Defer the update using a timer to avoid re-entrancy issues
                            QtCore.QTimer.singleShot(0, lambda idx=price_static_index, val=calculated_price: self._update_price_static_deferred(idx, val))

        except Exception as e:
            logger.error(f"Error in _on_line_items_data_changed: {e}", exc_info=True)

    def _update_price_static_deferred(self, index, value):
        """Deferred update for Price Static field to avoid re-entrancy.

        Args:
            index: QModelIndex for sg_price_static field
            value: New price value to set
        """
        try:
            if not hasattr(self, 'line_items_widget') or not self.line_items_widget:
                return
            if not hasattr(self.line_items_widget, 'model') or not self.line_items_widget.model:
                return

            model = self.line_items_widget.model

            # Set flag to prevent creating undo command for automatic Price Static updates
            model._skip_undo_command = True
            model.setData(index, value, QtCore.Qt.EditRole)
            model._skip_undo_command = False

        except Exception as e:
            # Ensure flag is reset even if error occurs
            if hasattr(self, 'line_items_widget') and hasattr(self.line_items_widget, 'model'):
                if hasattr(self.line_items_widget.model, '_skip_undo_command'):
                    self.line_items_widget.model._skip_undo_command = False
            logger.error(f"Error in _update_price_static_deferred: {e}", exc_info=True)


class RateCardDialog(QtWidgets.QDialog):
    """Dialog for managing Rate Cards."""

    def __init__(self, sg_session, price_list_id, project_id, parent=None):
        """Initialize the Rate Card dialog.

        Args:
            sg_session: ShotgridClient instance
            price_list_id: ID of the current Price List
            project_id: ID of the project
            parent: Parent widget
        """
        super().__init__(parent)
        self.sg_session = sg_session
        self.current_price_list_id = price_list_id
        self.current_project_id = project_id
        self.current_price_list_data = None

        # Rate Card widgets and data
        self.rate_card_combo = None
        self.rate_card_set_btn = None
        self.rate_card_status_label = None
        self.rate_card_widget = None
        self.rate_card_field_schema = {}
        self.rate_card_field_allowlist = []

        self.setWindowTitle("Rate Cards")
        self.resize(1000, 600)

        self._build_ui()
        self._fetch_price_list_data()
        self._refresh_rate_cards()

    def _build_ui(self):
        """Build the dialog UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Selector group
        selector_group = CollapsibleGroupBox("Rate Card")

        selector_row = QtWidgets.QHBoxLayout()
        selector_label = QtWidgets.QLabel("Rate Card:")
        selector_row.addWidget(selector_label)

        self.rate_card_combo = QtWidgets.QComboBox()
        self.rate_card_combo.setMinimumWidth(250)
        self.rate_card_combo.currentIndexChanged.connect(self._on_rate_card_changed)
        selector_row.addWidget(self.rate_card_combo, stretch=1)

        self.rate_card_set_btn = QtWidgets.QPushButton("Set as Current")
        self.rate_card_set_btn.setEnabled(False)
        self.rate_card_set_btn.clicked.connect(self._on_set_current_rate_card)
        selector_row.addWidget(self.rate_card_set_btn)

        self.rate_card_add_btn = QtWidgets.QPushButton("Add")
        self.rate_card_add_btn.clicked.connect(self._on_add_rate_card)
        selector_row.addWidget(self.rate_card_add_btn)

        self.rate_card_remove_btn = QtWidgets.QPushButton("Remove")
        self.rate_card_remove_btn.clicked.connect(self._on_remove_rate_card)
        selector_row.addWidget(self.rate_card_remove_btn)

        self.rate_card_rename_btn = QtWidgets.QPushButton("Rename")
        self.rate_card_rename_btn.clicked.connect(self._on_rename_rate_card)
        selector_row.addWidget(self.rate_card_rename_btn)

        self.rate_card_refresh_btn = QtWidgets.QPushButton("Refresh")
        self.rate_card_refresh_btn.clicked.connect(self._refresh_rate_cards)
        selector_row.addWidget(self.rate_card_refresh_btn)

        selector_group.addLayout(selector_row)

        self.rate_card_status_label = QtWidgets.QLabel("Loading Rate Cards...")
        self.rate_card_status_label.setObjectName("rateCardStatusLabel")
        self.rate_card_status_label.setStyleSheet("color: #a0a0a0; padding: 2px 0;")
        selector_group.addWidget(self.rate_card_status_label)

        layout.addWidget(selector_group)

        # Create Rate Card widget
        self.rate_card_widget = VFXBreakdownWidget(self.sg_session, show_toolbar=True, settings_key="rate_card_dialog", parent=self)

        # Set context provider
        self.rate_card_widget.context_provider = self

        # Configure the model to use Rate Card-specific columns
        if hasattr(self.rate_card_widget, 'model') and self.rate_card_widget.model:
            self.rate_card_widget.model.column_fields = self.rate_card_field_allowlist.copy()
            self.rate_card_widget.model.entity_type = "CustomNonProjectEntity01"
            logger.info(f"Configured Rate Card dialog widget model with fields: {self.rate_card_field_allowlist}")

        # Connect widget signals
        self.rate_card_widget.statusMessageChanged.connect(lambda msg, err: self._set_rate_card_status(msg, err))

        layout.addWidget(self.rate_card_widget)

        # Add Close button at the bottom
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

    def _fetch_price_list_data(self):
        """Fetch full price list data including linked entities."""
        try:
            price_list_data = self.sg_session.sg.find_one(
                "CustomEntity10",
                [["id", "is", self.current_price_list_id]],
                ["code", "sg_rate_card"]
            )
            self.current_price_list_data = price_list_data
            logger.info(f"Fetched Price List data: {price_list_data}")
        except Exception as e:
            logger.error(f"Failed to fetch Price List data: {e}", exc_info=True)
            self.current_price_list_data = None

    def _set_rate_card_status(self, message, is_error=False):
        """Set the status message for rate card."""
        if is_error:
            self.rate_card_status_label.setStyleSheet("color: #ff6b6b; padding: 2px 0;")
        else:
            self.rate_card_status_label.setStyleSheet("color: #a0a0a0; padding: 2px 0;")
        self.rate_card_status_label.setText(message)

    def _refresh_rate_cards(self):
        """Refresh the list of Rate Cards."""
        try:
            # Query CustomNonProjectEntity01 (Rate Cards)
            filters = []

            rate_cards_list = self.sg_session.sg.find(
                "CustomNonProjectEntity01",
                filters,
                ["code", "id", "description"]
            )

            # Update combo box
            self.rate_card_combo.blockSignals(True)
            self.rate_card_combo.clear()
            self.rate_card_combo.addItem("-- Select Rate Card --", None)

            for rate_card in sorted(rate_cards_list, key=lambda x: x.get("code", "")):
                self.rate_card_combo.addItem(rate_card.get("code", "Unnamed"), rate_card["id"])

            self.rate_card_combo.blockSignals(False)

            if rate_cards_list:
                self._set_rate_card_status(f"Found {len(rate_cards_list)} Rate Card(s)")
                self.rate_card_set_btn.setEnabled(True)

                # Auto-select the Rate Card linked to this Price List (if any)
                linked_rate_card_id = None
                if self.current_price_list_data:
                    linked_rate_card = self.current_price_list_data.get("sg_rate_card")
                    if linked_rate_card and isinstance(linked_rate_card, dict):
                        linked_rate_card_id = linked_rate_card.get("id")

                # Try to find and select the linked Rate Card
                if linked_rate_card_id:
                    for i in range(self.rate_card_combo.count()):
                        if self.rate_card_combo.itemData(i) == linked_rate_card_id:
                            self.rate_card_combo.setCurrentIndex(i)
                            logger.info(f"Auto-selected Rate Card {linked_rate_card_id} linked to current Price List")
                            self._load_rate_card_details(linked_rate_card_id)
                            break
                    else:
                        logger.warning(f"Linked Rate Card {linked_rate_card_id} not found")
                        self._on_rate_card_changed(0)
                else:
                    self._on_rate_card_changed(0)
            else:
                self._set_rate_card_status("No Rate Cards found.")
                self.rate_card_set_btn.setEnabled(False)
                self._on_rate_card_changed(0)

        except Exception as e:
            logger.error(f"Failed to refresh Rate Cards: {e}", exc_info=True)
            self._set_rate_card_status("Failed to load Rate Cards.", is_error=True)

    def _on_rate_card_changed(self, index):
        """Handle Rate Card selection change."""
        if index < 0:
            self.rate_card_widget.clear_data()
            logger.info("Rate Card index invalid - cleared Rate Card table")
            return

        rate_card_id = self.rate_card_combo.currentData()
        if not rate_card_id:
            self.rate_card_widget.clear_data()
            logger.info("Rate Card set to placeholder - cleared Rate Card table")
            return

        # Load the selected rate card details
        self._load_rate_card_details(rate_card_id)

    def _load_rate_card_details(self, rate_card_id):
        """Load details for the selected Rate Card."""
        try:
            # Fetch schema if not already loaded - MUST be done before querying
            if not self.rate_card_field_schema:
                self._fetch_rate_card_schema()

            filters = [["id", "is", rate_card_id]]
            fields = self.rate_card_field_allowlist.copy()

            rate_card_data = self.sg_session.sg.find_one(
                "CustomNonProjectEntity01",
                filters,
                fields
            )

            if rate_card_data:
                self.rate_card_widget.load_bidding_scenes([rate_card_data], field_schema=self.rate_card_field_schema)
                display_name = self.rate_card_combo.currentText()
                self._set_rate_card_status(f"Loaded Rate Card '{display_name}'.")
            else:
                self._set_rate_card_status("Rate Card not found.")
                self.rate_card_widget.clear_data()

        except Exception as e:
            logger.error(f"Failed to load rate card details: {e}", exc_info=True)
            self._set_rate_card_status("Failed to load rate card details.", is_error=True)

    def _fetch_rate_card_schema(self):
        """Fetch the schema for CustomNonProjectEntity01 (Rate Cards) and build field allowlist."""
        try:
            schema = self.sg_session.sg.schema_field_read("CustomNonProjectEntity01")

            # Build field allowlist: start with basic fields, then add all fields ending with "_rate"
            self.rate_card_field_allowlist = ["id", "code"]

            # Find all fields ending with "_rate"
            rate_fields = []
            for field_name in schema.keys():
                if field_name.endswith("_rate"):
                    rate_fields.append(field_name)

            # Sort rate fields alphabetically for consistent display
            rate_fields.sort()
            self.rate_card_field_allowlist.extend(rate_fields)

            logger.info(f"Built Rate Card field allowlist with {len(self.rate_card_field_allowlist)} fields: {self.rate_card_field_allowlist}")

            # Build field schema dictionary for allowlisted fields
            for field_name in self.rate_card_field_allowlist:
                if field_name not in schema:
                    logger.warning(f"Field {field_name} not found in CustomNonProjectEntity01 schema")
                    continue

                field_info = schema[field_name]
                self.rate_card_field_schema[field_name] = {
                    "data_type": field_info.get("data_type", {}).get("value"),
                    "properties": field_info.get("properties", {}),
                    "editable": field_info.get("editable", {}).get("value", True),
                    "display_name": field_info.get("name", {}).get("value", field_name)
                }

            logger.info(f"Fetched schema for CustomNonProjectEntity01 with {len(self.rate_card_field_schema)} fields")

            # Update model's column fields and headers
            if hasattr(self.rate_card_widget, 'model') and self.rate_card_widget.model:
                self.rate_card_widget.model.column_fields = self.rate_card_field_allowlist.copy()

                display_names = {field: self.rate_card_field_schema[field]["display_name"]
                                for field in self.rate_card_field_allowlist
                                if field in self.rate_card_field_schema}
                if "id" in display_names:
                    display_names["id"] = "SG ID"
                self.rate_card_widget.model.set_column_headers(display_names)

        except Exception as e:
            logger.error(f"Failed to fetch schema for CustomNonProjectEntity01: {e}", exc_info=True)

    def _on_set_current_rate_card(self):
        """Set the selected Rate Card as current for the Price List."""
        if not self.current_price_list_id:
            QtWidgets.QMessageBox.warning(self, "No Price List Selected", "Please select a Price List first.")
            return

        rate_card_id = self.rate_card_combo.currentData()
        if not rate_card_id:
            QtWidgets.QMessageBox.warning(self, "No Rate Card Selected", "Please select a Rate Card.")
            return

        try:
            self.sg_session.sg.update(
                "CustomEntity10",
                self.current_price_list_id,
                {"sg_rate_card": {"type": "CustomNonProjectEntity01", "id": rate_card_id}}
            )

            rate_card_name = self.rate_card_combo.currentText()
            self._set_rate_card_status(f"Set '{rate_card_name}' as current Rate Card.")
            QtWidgets.QMessageBox.information(
                self,
                "Success",
                f"'{rate_card_name}' is now the current Rate Card for this Price List."
            )

            logger.info(f"Set Rate Card {rate_card_id} as current for Price List {self.current_price_list_id}")

            # Refresh price list data to reflect the change (for dialog's internal state)
            self._fetch_price_list_data()

            # Update parent's Price List data and info label immediately
            parent = self.parent()
            if parent and isinstance(parent, RatesTab):
                logger.info("Updating parent RatesTab info label immediately")
                parent._fetch_price_list_data(self.current_price_list_id)

        except Exception as e:
            logger.error(f"Failed to set current Rate Card: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to set current Rate Card:\n{str(e)}"
            )

    def _on_add_rate_card(self):
        """Add a new Rate Card."""
        name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Add Rate Card",
            "Enter name for new Rate Card:"
        )

        if not ok or not name:
            return

        try:
            rate_card_data = {
                "code": name
            }

            new_rate_card = self.sg_session.sg.create("CustomNonProjectEntity01", rate_card_data)

            logger.info(f"Created Rate Card: {name} (ID: {new_rate_card['id']})")
            self._set_rate_card_status(f"Created Rate Card '{name}'.")

            self._refresh_rate_cards()

            for i in range(self.rate_card_combo.count()):
                if self.rate_card_combo.itemData(i) == new_rate_card['id']:
                    self.rate_card_combo.setCurrentIndex(i)
                    break

        except Exception as e:
            logger.error(f"Failed to create Rate Card: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to create Rate Card:\n{str(e)}"
            )

    def _on_remove_rate_card(self):
        """Remove the selected Rate Card."""
        rate_card_id = self.rate_card_combo.currentData()
        if not rate_card_id:
            QtWidgets.QMessageBox.warning(self, "No Rate Card Selected", "Please select a Rate Card to remove.")
            return

        rate_card_name = self.rate_card_combo.currentText()

        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete Rate Card '{rate_card_name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply != QtWidgets.QMessageBox.Yes:
            return

        try:
            self.sg_session.sg.delete("CustomNonProjectEntity01", rate_card_id)

            logger.info(f"Deleted Rate Card: {rate_card_name} (ID: {rate_card_id})")
            self._set_rate_card_status(f"Deleted Rate Card '{rate_card_name}'.")

            self._refresh_rate_cards()

        except Exception as e:
            logger.error(f"Failed to delete Rate Card: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to delete Rate Card:\n{str(e)}"
            )

    def _on_rename_rate_card(self):
        """Rename the selected Rate Card."""
        rate_card_id = self.rate_card_combo.currentData()
        if not rate_card_id:
            QtWidgets.QMessageBox.warning(self, "No Rate Card Selected", "Please select a Rate Card to rename.")
            return

        current_name = self.rate_card_combo.currentText()

        new_name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Rename Rate Card",
            "Enter new name:",
            text=current_name
        )

        if not ok or not new_name or new_name == current_name:
            return

        try:
            self.sg_session.sg.update("CustomNonProjectEntity01", rate_card_id, {"code": new_name})

            logger.info(f"Renamed Rate Card from '{current_name}' to '{new_name}' (ID: {rate_card_id})")
            self._set_rate_card_status(f"Renamed to '{new_name}'.")

            current_index = self.rate_card_combo.currentIndex()
            self._refresh_rate_cards()
            if current_index < self.rate_card_combo.count():
                self.rate_card_combo.setCurrentIndex(current_index)

        except Exception as e:
            logger.error(f"Failed to rename Rate Card: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to rename Rate Card:\n{str(e)}"
            )
