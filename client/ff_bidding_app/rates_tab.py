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
        self.price_lists_group_box = None  # CollapsibleGroupBox for Price Lists

        # Nested tabs
        self.nested_tab_widget = None

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
        selector_group = CollapsibleGroupBox("Price Lists")
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

        layout.addWidget(selector_group)

        # Create nested tab widget for Rate Card, Line Items, and Prices
        self.nested_tab_widget = QtWidgets.QTabWidget()

        # Create and add nested tabs
        rate_card_tab = self._create_rate_card_tab()
        self.nested_tab_widget.addTab(rate_card_tab, "Rate Card")

        line_items_tab = self._create_line_items_tab()
        self.nested_tab_widget.addTab(line_items_tab, "Line Items")

        prices_tab = self._create_prices_tab()
        self.nested_tab_widget.addTab(prices_tab, "Prices")

        layout.addWidget(self.nested_tab_widget)

    def _create_rate_card_tab(self):
        """Create the Rate Card nested tab content with full functionality."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)

        # Selector group (collapsible)
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

        self.rate_card_status_label = QtWidgets.QLabel("Select a Price List to view Rate Cards.")
        self.rate_card_status_label.setObjectName("rateCardStatusLabel")
        self.rate_card_status_label.setStyleSheet("color: #a0a0a0; padding: 2px 0;")
        selector_group.addWidget(self.rate_card_status_label)

        layout.addWidget(selector_group)

        # Create reusable Rate Card widget (reusing VFXBreakdownWidget)
        self.rate_card_widget = VFXBreakdownWidget(self.sg_session, show_toolbar=True, parent=self)

        # Configure the model to use Rate Card-specific columns
        if hasattr(self.rate_card_widget, 'model') and self.rate_card_widget.model:
            self.rate_card_widget.model.column_fields = self.rate_card_field_allowlist.copy()
            self.rate_card_widget.model.entity_type = "CustomEntity09"
            logger.info(f"Configured Rate Card widget model with fields: {self.rate_card_field_allowlist}")

        # Connect widget signals
        self.rate_card_widget.statusMessageChanged.connect(lambda msg, err: self._set_rate_card_status(msg, err))

        layout.addWidget(self.rate_card_widget)

        return widget

    def _create_line_items_tab(self):
        """Create the Line Items nested tab content with auto-loading from Price List."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)

        # Create Line Items widget (reusing VFXBreakdownWidget) with toolbar for search/sort
        self.line_items_widget = VFXBreakdownWidget(self.sg_session, show_toolbar=True, entity_name="Line Item", parent=self)

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

    def _create_prices_tab(self):
        """Create the Prices nested tab content."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)

        # Title
        title_label = QtWidgets.QLabel("Prices")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; padding: 20px;")
        layout.addWidget(title_label)

        # Placeholder content
        info_label = QtWidgets.QLabel("Prices content will be displayed here.\nThis section will contain pricing information for the selected Price List.")
        info_label.setStyleSheet("padding: 20px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        layout.addStretch()

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
        - If Price List == placeholder → ALWAYS clear Rate Card & Line Items
        - If Price List is valid → ALWAYS refresh Rate Card & Line Items
        """
        if index < 0:
            self.current_price_list_id = None
            self.current_price_list_data = None
            self._update_price_list_info_label(None)
            # Ensure cascade happens even for invalid index
            if hasattr(self, 'rate_card_combo'):
                self._clear_rate_card_tab()
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
            # ALWAYS Clear Rate Card and Line Items tabs when placeholder selected
            if hasattr(self, 'rate_card_combo'):
                self._clear_rate_card_tab()
            if hasattr(self, 'line_items_widget'):
                self._clear_line_items_tab()
            logger.info("Price List set to placeholder - cascaded to clear Rate Card and Line Items")
            return

        # Store the selected price list ID
        self.current_price_list_id = price_list_id
        display_name = self.price_lists_combo.currentText()
        self._set_price_lists_status(f"Selected Price List: '{display_name}'.")
        logger.info(f"Price List changed to: {display_name} (ID: {price_list_id})")

        # Fetch full price list data with linked entities
        self._fetch_price_list_data(price_list_id)

        # ALWAYS Refresh Rate Card and Line Items tabs when valid Price List selected
        if hasattr(self, 'rate_card_combo'):
            self._refresh_rate_cards()
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
            # Clear label and group box title if no price list selected
            self.price_lists_status_label.setText("Select a Bid to view Price Lists.")
            self.price_lists_group_box.setAdditionalInfo("")
            return

        info_parts = []

        # Get price list name for title bar
        price_list_name = price_list_data.get("code") or f"Price List {price_list_data.get('id', 'N/A')}"
        # Start with "Current Price List: (name)"
        title_text = f"Current Price List: {price_list_name}"

        # Add Rate Card info
        rate_card = price_list_data.get("sg_rate_card")
        if rate_card:
            # Extract rate card name/code
            if isinstance(rate_card, dict):
                rate_card_name = rate_card.get("name") or rate_card.get("code") or f"ID {rate_card.get('id', 'N/A')}"
            elif isinstance(rate_card, list) and rate_card:
                rate_card_name = rate_card[0].get("name") or rate_card[0].get("code") or f"ID {rate_card[0].get('id', 'N/A')}"
            else:
                rate_card_name = str(rate_card)
            info_parts.append(f"Rate Card: {rate_card_name}")
            title_text += f" | Rate Card: {rate_card_name}"

        # Update the label with the info (for display under dropdown)
        if info_parts:
            self.price_lists_status_label.setText("  ".join(info_parts))
        else:
            self.price_lists_status_label.setText(f"Selected Price List: '{price_list_name}'.")

        # Update the group box title with price list name and info (for collapsed state)
        self.price_lists_group_box.setAdditionalInfo(title_text)

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

    # ===========================
    # Rate Card Methods
    # ===========================

    def _set_rate_card_status(self, message, is_error=False):
        """Set the status message for rate card."""
        if is_error:
            self.rate_card_status_label.setStyleSheet("color: #ff6b6b; padding: 2px 0;")
        else:
            self.rate_card_status_label.setStyleSheet("color: #a0a0a0; padding: 2px 0;")
        self.rate_card_status_label.setText(message)

    def _clear_rate_card_tab(self):
        """Clear the Rate Card tab and trigger cascade.

        CASCADE LOGIC:
        - ALWAYS resets Rate Card dropdown to placeholder
        - ALWAYS triggers _on_rate_card_changed(0) to clear Rate Card table
        """
        self.rate_card_combo.blockSignals(True)
        self.rate_card_combo.clear()
        self.rate_card_combo.addItem("-- Select Rate Card --", None)
        self.rate_card_combo.setCurrentIndex(0)
        self.rate_card_combo.blockSignals(False)
        self.rate_card_set_btn.setEnabled(False)
        self._set_rate_card_status("Select a Price List to view Rate Cards.")
        # ALWAYS trigger cascade to clear Rate Card table
        self._on_rate_card_changed(0)
        logger.info("Rate Card tab cleared - triggered cascade to clear Rate Card table")

    def _refresh_rate_cards(self):
        """Refresh the list of Rate Cards for the current price list."""
        if not self.current_project_id or not self.current_price_list_id:
            self._clear_rate_card_tab()
            return

        try:
            # Query CustomEntity09 (Rate Cards) filtered by project
            filters = [
                ["project", "is", {"type": "Project", "id": self.current_project_id}]
            ]

            rate_cards_list = self.sg_session.sg.find(
                "CustomEntity09",
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
                            # Explicitly load rate card details to ensure table is updated
                            self._load_rate_card_details(linked_rate_card_id)
                            break
                    else:
                        # Linked Rate Card not found - trigger cascade
                        logger.warning(f"Linked Rate Card {linked_rate_card_id} not found in project")
                        self._on_rate_card_changed(0)
                else:
                    # No linked Rate Card - trigger cascade
                    self._on_rate_card_changed(0)
            else:
                self._set_rate_card_status("No Rate Cards found for this project.")
                self.rate_card_set_btn.setEnabled(False)
                # Trigger cascade to clear table
                self._on_rate_card_changed(0)

        except Exception as e:
            logger.error(f"Failed to refresh Rate Cards: {e}", exc_info=True)
            self._set_rate_card_status("Failed to load Rate Cards.", is_error=True)

    def _on_rate_card_changed(self, index):
        """Handle Rate Card selection change.

        CASCADE LOGIC:
        - If Rate Card == placeholder → ALWAYS clear Rate Card table
        - If Rate Card is valid → ALWAYS load Rate Card details
        """
        if index < 0:
            self.rate_card_widget.clear_data()
            logger.info("Rate Card index invalid - cleared Rate Card table")
            return

        rate_card_id = self.rate_card_combo.currentData()
        if not rate_card_id:
            # Placeholder selected - ALWAYS clear Rate Card table
            self.rate_card_widget.clear_data()
            logger.info("Rate Card set to placeholder - cleared Rate Card table")
            return

        # Load the selected rate card details
        self._load_rate_card_details(rate_card_id)

    def _load_rate_card_details(self, rate_card_id):
        """Load details for the selected Rate Card."""
        try:
            filters = [["id", "is", rate_card_id]]
            fields = self.rate_card_field_allowlist.copy()

            rate_card_data = self.sg_session.sg.find_one(
                "CustomEntity09",
                filters,
                fields
            )

            if rate_card_data:
                # Fetch schema if not already loaded
                if not self.rate_card_field_schema:
                    self._fetch_rate_card_schema()

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
        """Fetch the schema for CustomEntity09 (Rate Cards) and build field allowlist."""
        try:
            schema = self.sg_session.sg.schema_field_read("CustomEntity09")

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
                    logger.warning(f"Field {field_name} not found in CustomEntity09 schema")
                    continue

                field_info = schema[field_name]
                self.rate_card_field_schema[field_name] = {
                    "data_type": field_info.get("data_type", {}).get("value"),
                    "properties": field_info.get("properties", {}),
                    "editable": field_info.get("editable", {}).get("value", True),
                    "display_name": field_info.get("name", {}).get("value", field_name)
                }

            logger.info(f"Fetched schema for CustomEntity09 with {len(self.rate_card_field_schema)} fields")

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
            logger.error(f"Failed to fetch schema for CustomEntity09: {e}", exc_info=True)

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
                {"sg_rate_card": {"type": "CustomEntity09", "id": rate_card_id}}
            )

            rate_card_name = self.rate_card_combo.currentText()
            self._set_rate_card_status(f"Set '{rate_card_name}' as current Rate Card.")
            QtWidgets.QMessageBox.information(
                self,
                "Success",
                f"'{rate_card_name}' is now the current Rate Card for this Price List."
            )

            logger.info(f"Set Rate Card {rate_card_id} as current for Price List {self.current_price_list_id}")

        except Exception as e:
            logger.error(f"Failed to set current Rate Card: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to set current Rate Card:\n{str(e)}"
            )

    def _on_add_rate_card(self):
        """Add a new Rate Card."""
        if not self.current_project_id:
            QtWidgets.QMessageBox.warning(self, "No Project Selected", "Please select a project first.")
            return

        name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Add Rate Card",
            "Enter name for new Rate Card:"
        )

        if not ok or not name:
            return

        try:
            rate_card_data = {
                "code": name,
                "project": {"type": "Project", "id": self.current_project_id}
            }

            new_rate_card = self.sg_session.sg.create("CustomEntity09", rate_card_data)

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
            self.sg_session.sg.delete("CustomEntity09", rate_card_id)

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
            self.sg_session.sg.update("CustomEntity09", rate_card_id, {"code": new_name})

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
                self.line_items_widget.model.set_column_headers(display_names)

                # Set up formula delegate for the Price column
                if hasattr(self, 'line_items_formula_evaluator'):
                    price_col_index = self.line_items_field_allowlist.index("_calc_price") if "_calc_price" in self.line_items_field_allowlist else -1
                    if price_col_index >= 0:
                        formula_delegate = FormulaDelegate(self.line_items_formula_evaluator)
                        self.line_items_widget.table_view.setItemDelegateForColumn(price_col_index, formula_delegate)
                        logger.info(f"Set formula delegate for Price column (index {price_col_index})")

        except Exception as e:
            logger.error(f"Failed to fetch schema for CustomEntity03: {e}", exc_info=True)
