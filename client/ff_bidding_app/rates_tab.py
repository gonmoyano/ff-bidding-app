"""
Rates Tab
Contains UI and logic for managing Price Lists (CustomEntity10).
"""

import re
from PySide6 import QtWidgets, QtCore, QtGui

try:
    from .logger import logger
    from .settings import AppSettings
    from .bid_selector_widget import CollapsibleGroupBox, parse_sg_currency
    from .vfx_breakdown_widget import VFXBreakdownWidget, FormulaDelegate
    from .formula_evaluator import FormulaEvaluator
except ImportError:
    import logging
    logger = logging.getLogger("FireframeProdigy")
    from settings import AppSettings
    from bid_selector_widget import CollapsibleGroupBox, parse_sg_currency
    from vfx_breakdown_widget import VFXBreakdownWidget, FormulaDelegate
    from formula_evaluator import FormulaEvaluator


class CreatePriceListDialog(QtWidgets.QDialog):
    """Dialog for creating a new Price List with options to copy from existing or create new."""

    def __init__(self, sg_session, project_id, current_bid=None, parent=None):
        """Initialize the dialog.

        Args:
            sg_session: ShotgridClient instance
            project_id: ID of the current project
            current_bid: Currently selected Bid dict for name prefill
            parent: Parent widget
        """
        super().__init__(parent)
        self.sg_session = sg_session
        self.project_id = project_id
        self.current_bid = current_bid
        self.existing_price_lists = []

        self.setWindowTitle("Add Price List")
        self.setModal(True)
        self.setMinimumWidth(400)

        self._load_existing_price_lists()
        self._build_ui()
        self._prefill_name_from_bid()

    def _load_existing_price_lists(self):
        """Load existing Price Lists for the copy option."""
        try:
            if self.project_id:
                filters = [["project", "is", {"type": "Project", "id": self.project_id}]]
                self.existing_price_lists = self.sg_session.sg.find(
                    "CustomEntity10",
                    filters,
                    ["id", "code", "sg_line_items"]
                )
                # Sort by name
                self.existing_price_lists.sort(key=lambda x: x.get("code", "").lower())
        except Exception as e:
            logger.error(f"Failed to load existing Price Lists: {e}")
            self.existing_price_lists = []

    def _build_ui(self):
        """Build the dialog UI."""
        layout = QtWidgets.QVBoxLayout(self)

        # Creation mode
        mode_layout = QtWidgets.QHBoxLayout()
        mode_label = QtWidgets.QLabel("Mode:")
        mode_layout.addWidget(mode_label)

        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItem("Create empty")
        self.mode_combo.addItem("Copy from existing")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self.mode_combo, stretch=1)

        layout.addLayout(mode_layout)

        # Name field
        name_layout = QtWidgets.QHBoxLayout()
        name_label = QtWidgets.QLabel("Name:")
        name_layout.addWidget(name_label)

        self.name_field = QtWidgets.QLineEdit()
        self.name_field.setPlaceholderText("Enter Price List name...")
        name_layout.addWidget(self.name_field, stretch=1)

        layout.addLayout(name_layout)

        # Copy from dropdown
        copy_layout = QtWidgets.QHBoxLayout()
        copy_label = QtWidgets.QLabel("Copy from:")
        copy_layout.addWidget(copy_label)

        self.copy_combo = QtWidgets.QComboBox()
        self.copy_combo.addItem("-- Select Price List --", None)
        for price_list in self.existing_price_lists:
            line_items_count = 0
            sg_line_items = price_list.get("sg_line_items")
            if sg_line_items:
                if isinstance(sg_line_items, list):
                    line_items_count = len(sg_line_items)
                elif isinstance(sg_line_items, dict):
                    line_items_count = 1
            display_text = f"{price_list.get('code', 'Unnamed')} ({line_items_count} items)"
            self.copy_combo.addItem(display_text, price_list)
        self.copy_combo.currentIndexChanged.connect(self._on_copy_selection_changed)
        copy_layout.addWidget(self.copy_combo, stretch=1)

        layout.addLayout(copy_layout)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()

        self.ok_button = QtWidgets.QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_button)

        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

        # Initial state
        self._on_mode_changed(0)

    def _on_mode_changed(self, index):
        """Handle mode change."""
        is_copy_mode = (index == 1)
        self.copy_combo.setEnabled(is_copy_mode)
        # Apply visual styling to make disabled state more obvious
        if is_copy_mode:
            self.copy_combo.setStyleSheet("")
        else:
            self.copy_combo.setStyleSheet("QComboBox:disabled { color: #666666; background-color: #2d2d2d; }")
        # If switching to copy mode and a price list is already selected, update name
        if is_copy_mode and self.copy_combo.currentIndex() > 0:
            self._on_copy_selection_changed(self.copy_combo.currentIndex())

    def _prefill_name_from_bid(self):
        """Prefill the Name field with BidName-Price List-v### format."""
        if not self.current_bid:
            return

        bid_name = self.current_bid.get("code") or self.current_bid.get("name") or ""
        if bid_name:
            # Build base name as "BidName-Price List"
            base_name = f"{bid_name}-Price List"
            next_name = self._get_next_price_list_version(base_name)
            logger.info(f"Prefilling name field from bid '{bid_name}' -> '{next_name}'")
            self.name_field.setText(next_name)

    def _on_copy_selection_changed(self, index):
        """Handle copy source selection change - prefill name with next version."""
        # Only process in copy mode
        if self.mode_combo.currentIndex() != 1:
            return

        # Skip if no valid selection (first item is placeholder)
        if index <= 0:
            return

        price_list = self.copy_combo.currentData()
        if not price_list:
            logger.warning("No price list data found for selected index")
            return

        source_name = price_list.get("code") or price_list.get("name") or ""
        logger.info(f"Copy selection changed: source_name='{source_name}'")
        if source_name:
            next_name = self._get_next_version_name(source_name)
            logger.info(f"Prefilling name field with: '{next_name}'")
            self.name_field.setText(next_name)

    def _get_next_version_name(self, base_name):
        """Calculate the next version name based on existing price lists.

        Handles formats like:
        - "Name v1" -> "Name v2"
        - "Name-v001" -> "Name-v002"
        - "Puzzle Box - v002-Price List-v001" -> "Puzzle Box - v002-Price List-v002"

        Args:
            base_name: The source name to version

        Returns:
            str: The next version name
        """
        logger.debug(f"_get_next_version_name called with base_name='{base_name}'")

        # Try to match version pattern at the end: -v### or v### or -v## or v##
        # Pattern matches: optional separator, 'v' or 'V', and digits
        version_pattern = re.compile(r'^(.+?)[-\s]?[vV](\d+)$')
        match = version_pattern.match(base_name)
        logger.debug(f"Version pattern match: {match}")

        if match:
            name_without_version = match.group(1)
            current_version = int(match.group(2))
            version_digits = len(match.group(2))  # Preserve digit count (e.g., 001 vs 1)

            # Determine the separator used (-, space, or none)
            # Check original name for the separator before 'v'
            sep_match = re.search(r'([-\s])?[vV]\d+$', base_name)
            separator = sep_match.group(1) if sep_match and sep_match.group(1) else ''
        else:
            # No version found, treat whole name as base and start at v0
            name_without_version = base_name
            current_version = 0
            version_digits = 3  # Default to 3 digits like v001
            separator = '-'

        # Find the highest version number for this base name pattern
        highest_version = current_version

        if self.sg_session and self.project_id:
            try:
                existing = self.sg_session.sg.find(
                    "CustomEntity10",
                    [
                        ["project", "is", {"type": "Project", "id": self.project_id}],
                        ["code", "starts_with", name_without_version]
                    ],
                    ["code"]
                )

                for item in existing:
                    code = item.get("code", "")
                    # Try to extract version number
                    item_match = version_pattern.match(code)
                    if item_match and item_match.group(1) == name_without_version:
                        version_num = int(item_match.group(2))
                        highest_version = max(highest_version, version_num)

            except Exception as e:
                logger.error(f"Failed to query existing price lists for version: {e}")

        # Create next version name
        next_version = highest_version + 1
        next_name = f"{name_without_version}{separator}v{next_version:0{version_digits}d}"
        logger.debug(f"Generated next name: '{next_name}'")

        return next_name

    def _get_next_price_list_version(self, base_name):
        """Get the next version for a Price List name.

        Args:
            base_name: Base name without version (e.g., "BidName-Price List")

        Returns:
            str: Name with next version (e.g., "BidName-Price List-v001")
        """
        highest_version = 0

        if self.sg_session and self.project_id:
            try:
                # Query existing Price Lists with this base name
                existing = self.sg_session.sg.find(
                    "CustomEntity10",
                    [
                        ["project", "is", {"type": "Project", "id": self.project_id}],
                        ["code", "starts_with", f"{base_name}-v"]
                    ],
                    ["code"]
                )

                for item in existing:
                    code = item.get("code", "")
                    # Extract version number
                    if code.startswith(f"{base_name}-v"):
                        try:
                            version_str = code[len(f"{base_name}-v"):]
                            version_num = int(version_str)
                            highest_version = max(highest_version, version_num)
                        except ValueError:
                            pass

            except Exception as e:
                logger.error(f"Failed to query existing price lists: {e}")

        next_version = highest_version + 1
        return f"{base_name}-v{next_version:03d}"

    def get_price_list_name(self):
        """Get the entered Price List name."""
        return self.name_field.text().strip()

    def is_copy_mode(self):
        """Check if copy mode is selected."""
        return self.mode_combo.currentIndex() == 1

    def get_source_price_list_id(self):
        """Get the selected source Price List ID for copying."""
        if self.is_copy_mode():
            price_list = self.copy_combo.currentData()
            if price_list:
                return price_list.get("id")
        return None

    def get_source_price_list_data(self):
        """Get the full data for the selected source Price List."""
        if self.is_copy_mode():
            return self.copy_combo.currentData()
        return None

    def get_result(self):
        """Get the dialog result.

        Returns:
            dict: Result with 'name', 'mode', 'source' keys
        """
        return {
            "name": self.name_field.text().strip(),
            "mode": "empty" if self.mode_combo.currentIndex() == 0 else "copy",
            "source": self.copy_combo.currentData() if self.mode_combo.currentIndex() == 1 else None
        }


class RatesTab(QtWidgets.QWidget):
    """Rates tab widget for managing Price Lists."""

    # Signal emitted when the current rate card is changed
    rateCardChanged = QtCore.Signal()

    # Signal emitted when line item prices change (sg_price_static updated)
    lineItemPricesChanged = QtCore.Signal()

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
        self.line_items_formula_delegate = None  # For currency formatting updates

        # Track signal connection state to avoid RuntimeWarning on disconnect
        self._line_items_data_changed_connected = False

        self._build_ui()

        # Fetch schema early to populate column headers with user-friendly names
        self._fetch_line_items_schema()

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

        self.price_lists_add_btn = QtWidgets.QPushButton("Create")
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

            # Create formula evaluator for this table with cross-sheet references
            # Build sheet_models dictionary for cross-sheet references
            sheet_models = {}
            if hasattr(self, 'rate_card_widget') and hasattr(self.rate_card_widget, 'model') and self.rate_card_widget.model:
                sheet_models['Rate Card'] = self.rate_card_widget.model

            self.line_items_formula_evaluator = FormulaEvaluator(
                self.line_items_widget.model,
                sheet_models=sheet_models
            )
            # Set the formula evaluator on the model for dependency tracking
            self.line_items_widget.model.set_formula_evaluator(self.line_items_formula_evaluator)

        layout.addWidget(self.line_items_widget)

        return widget

    def _set_price_lists_status(self, message, is_error=False):
        """Log the status message for price lists.

        Args:
            message: Status message to log
            is_error: Whether this is an error message
        """
        if is_error:
            logger.warning(f"Price Lists status: {message}")
        else:
            logger.info(f"Price Lists status: {message}")

    def set_bid(self, bid_data, project_id):
        """Set the current bid and load associated price lists.

        Args:
            bid_data: Dictionary containing Bid (CustomEntity06) data, or None
            project_id: ID of the project

        CASCADE LOGIC:
        - If Bid == placeholder OR no linked Price List → Price List set to placeholder → cascade continues
        """
        self.current_bid_data = bid_data
        self.current_bid_id = bid_data.get('id') if bid_data else None
        self.current_project_id = project_id

        # ALWAYS reset Price List to placeholder first - do this BEFORE any checks
        self.price_lists_combo.blockSignals(True)
        self.price_lists_combo.clear()
        self.price_lists_combo.addItem("-- Select Price List --", None)
        self.price_lists_combo.setCurrentIndex(0)
        self.price_lists_combo.blockSignals(False)

        if not self.current_bid_id or not project_id:
            # No bid selected - ALWAYS trigger cascade to clear downstream
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
            self._set_price_lists_status("Select a Bid to view Price Lists.")
            self._on_price_lists_changed(0)
            return

        # Refresh the price lists and auto-select the one linked to this bid
        self._refresh_price_lists()

        # Update currency formatting for the price column
        self.refresh_currency_formatting()

    def refresh_currency_formatting(self, sg_currency_value=None):
        """Refresh currency formatting in the Line Items price column.

        Call this method when currency settings have changed to update
        the Price column with the new currency symbol and position.

        Args:
            sg_currency_value: Combined currency value (e.g., "$+before"). If None, uses current bid data.
        """
        # Get sg_currency value from parameter or current bid data
        if sg_currency_value is None:
            if self.current_bid_data:
                sg_currency_value = self.current_bid_data.get("sg_currency")

        # Parse the combined format (symbol+position)
        default_symbol = self.app_settings.get_currency() if self.app_settings else "$"
        currency_symbol, currency_position = parse_sg_currency(sg_currency_value, default_symbol or "$")

        # Update currency symbol on the formula delegate
        if self.line_items_formula_delegate:
            self.line_items_formula_delegate.set_currency_symbol(currency_symbol, currency_position)
            # Force repaint of the table
            if hasattr(self, 'line_items_widget') and self.line_items_widget:
                if hasattr(self.line_items_widget, 'table_view'):
                    self.line_items_widget.table_view.viewport().update()

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
            # Query CustomEntity10 (Price Lists) filtered by parent bid
            filters = [
                ["project", "is", {"type": "Project", "id": self.current_project_id}],
                ["sg_parent_bid", "is", {"type": "CustomEntity06", "id": self.current_bid_id}]
            ]

            logger.info(f"Querying Price Lists with filters: {filters}")

            price_lists_list = self.sg_session.sg.find(
                "CustomEntity10",
                filters,
                ["code", "id", "description"]
            )

            logger.info(f"Found {len(price_lists_list)} Price List(s) for Bid {self.current_bid_id}")

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
                            break
                    else:
                        # Linked Price List not found - trigger cascade
                        self._on_price_lists_changed(0)  # Manually trigger cascade
                else:
                    # No linked Price List - trigger cascade
                    self._on_price_lists_changed(0)  # Manually trigger cascade

                # Update info label to show linked Price List
                self._update_price_list_group_info()
            else:
                self._set_price_lists_status("No Price Lists found for this Bid.")
                self.price_lists_set_btn.setEnabled(False)
                # Trigger cascade to clear downstream
                self._on_price_lists_changed(0)
                # Clear group info
                self.price_lists_selector_group.setAdditionalInfo("")

        except Exception as e:
            logger.error(f"Failed to refresh Price Lists: {e}", exc_info=True)
            self._set_price_lists_status("Failed to load Price Lists.", is_error=True)
            # Clear group info on error
            self.price_lists_selector_group.setAdditionalInfo("")

    def _on_price_lists_changed(self, index):
        """Handle Price Lists selection change.

        CASCADE LOGIC:
        - If Price List == placeholder → ALWAYS clear Line Items
        - If Price List is valid → ALWAYS refresh Line Items
        """
        if index < 0:
            self.current_price_list_id = None
            self.current_price_list_data = None
            self._update_price_list_group_info()
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
            self._update_price_list_info_label()
            # ALWAYS Clear Line Items tab when placeholder selected
            if hasattr(self, 'line_items_widget'):
                self._clear_line_items_tab()
            return

        # Store the selected price list ID
        self.current_price_list_id = price_list_id
        display_name = self.price_lists_combo.currentText()
        self._set_price_lists_status(f"Selected Price List: '{display_name}'.")

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
            # Load Rate Card data for formula evaluator
            self._load_rate_card_for_formula_evaluator()
        except Exception as e:
            logger.error(f"Failed to fetch Price List data: {e}", exc_info=True)
            self.current_price_list_data = None

    def _update_price_list_group_info(self):
        """Update the group box additional info to show linked Price List from current Bid."""
        if not self.current_bid_data:
            self.price_lists_selector_group.setAdditionalInfo("")
            return

        # Get linked Price List from Bid
        linked_price_list = self.current_bid_data.get("sg_price_list")
        if not linked_price_list:
            self.price_lists_selector_group.setAdditionalInfo("")
            return

        # Extract price list name
        if isinstance(linked_price_list, dict):
            price_list_name = linked_price_list.get("code") or linked_price_list.get("name") or f"ID {linked_price_list.get('id', 'N/A')}"
            self.price_lists_selector_group.setAdditionalInfo(f"Linked to current Bid: {price_list_name}")
        else:
            self.price_lists_selector_group.setAdditionalInfo("")

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

            # Refresh the bid data and update the bid info label
            self._refresh_bid_info_label()

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

    def _refresh_bid_info_label(self):
        """Refresh the bid data from ShotGrid and update the bid info label in the Bids group."""
        if not self.current_bid_id or not self.parent_app:
            return

        try:
            # Fetch updated bid data from ShotGrid
            updated_bid = self.sg_session.sg.find_one(
                "CustomEntity06",
                [["id", "is", self.current_bid_id]],
                ["id", "code", "sg_bid_type", "sg_vfx_breakdown", "sg_bid_assets", "sg_price_list", "description"]
            )
            if not updated_bid:
                return

            # Update our local copy of the bid data
            self.current_bid_data = updated_bid

            # Update current bid in bidding tab
            if hasattr(self.parent_app, 'bidding_tab'):
                self.parent_app.bidding_tab.current_bid = updated_bid
                # Update bid selector's combo box data and info label
                if hasattr(self.parent_app.bidding_tab, 'bid_selector'):
                    bid_selector = self.parent_app.bidding_tab.bid_selector
                    # Find and update the item in the combo
                    combo = bid_selector.bid_combo
                    for i in range(combo.count()):
                        item_bid = combo.itemData(i)
                        if isinstance(item_bid, dict) and item_bid.get('id') == self.current_bid_id:
                            combo.setItemData(i, updated_bid)
                            break
                    # Update the bid info label
                    bid_selector._update_bid_info_label(updated_bid)

            logger.info(f"Bid {self.current_bid_id} refreshed with latest data.")
        except Exception as e:
            logger.warning(f"Failed to refresh Bid info label: {e}")

    def _on_add_price_list(self):
        """Add a new Price List using dialog with copy/new options."""
        if not self.current_project_id:
            QtWidgets.QMessageBox.warning(self, "No Project Selected", "Please select a project first.")
            return

        if not self.current_bid_id:
            QtWidgets.QMessageBox.warning(self, "No Bid Selected", "Please select a Bid first.")
            return

        # Show creation dialog with current bid for name prefill
        dialog = CreatePriceListDialog(
            self.sg_session,
            self.current_project_id,
            current_bid=self.current_bid_data,
            parent=self
        )
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return

        # Get dialog result
        result = dialog.get_result()
        name = result["name"]
        mode = result["mode"]
        source = result["source"]

        # Validate name
        if not name:
            QtWidgets.QMessageBox.warning(self, "Invalid Name", "Please enter a name for the Price List.")
            return

        # Validate source for copy mode
        if mode == "copy" and not source:
            QtWidgets.QMessageBox.warning(self, "No Source Selected", "Please select a Price List to copy from.")
            return

        try:
            # Create CustomEntity10 (Price List)
            price_list_data = {
                "code": name,
                "project": {"type": "Project", "id": self.current_project_id}
            }

            # Link to current Bid if one is selected
            if self.current_bid_id:
                price_list_data["sg_parent_bid"] = {"type": "CustomEntity06", "id": self.current_bid_id}

            # Link to currently selected Rate Card (if any)
            if self.rate_card_combo and self.rate_card_combo.currentData():
                rate_card_id = self.rate_card_combo.currentData()
                price_list_data["sg_rate_card"] = {"type": "CustomNonProjectEntity01", "id": rate_card_id}
                logger.info(f"Linking new Price List to Rate Card ID: {rate_card_id}")

            new_price_list = self.sg_session.sg.create("CustomEntity10", price_list_data)
            new_price_list_id = new_price_list['id']

            logger.info(f"Created Price List: {name} (ID: {new_price_list_id})")

            if mode == "copy":
                # Copy Line Items from source Price List
                source_id = source.get("id") if source else None
                if source_id:
                    self._copy_line_items_from_price_list(source_id, new_price_list_id)
                    self._set_price_lists_status(f"Created Price List '{name}' (copied from existing).")
                else:
                    self._set_price_lists_status(f"Created Price List '{name}'.")
            else:
                # Create new with initial empty Line Item
                self._create_initial_line_item(new_price_list_id)
                self._set_price_lists_status(f"Created Price List '{name}' with initial Line Item.")

            # Refresh list and select new one
            self._refresh_price_lists()

            # Find and select the new price list
            for i in range(self.price_lists_combo.count()):
                if self.price_lists_combo.itemData(i) == new_price_list_id:
                    self.price_lists_combo.setCurrentIndex(i)
                    break

        except Exception as e:
            logger.error(f"Failed to create Price List: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to create Price List:\n{str(e)}"
            )

    def _create_initial_line_item(self, price_list_id):
        """Create an initial empty Line Item for a new Price List.

        Args:
            price_list_id: ID of the Price List to add the Line Item to
        """
        # Create initial Line Item with link to Price List
        line_item_data = {
            "code": "New Line Item",
            "project": {"type": "Project", "id": self.current_project_id},
            "sg_parent_pricelist": {"type": "CustomEntity10", "id": price_list_id}
        }

        new_line_item = self.sg_session.sg.create("CustomEntity03", line_item_data)

        # Also link the Line Item to the Price List via sg_line_items
        self.sg_session.sg.update(
            "CustomEntity10",
            price_list_id,
            {"sg_line_items": [{"type": "CustomEntity03", "id": new_line_item["id"]}]}
        )

        logger.info(f"Created initial Line Item (ID: {new_line_item['id']}) for Price List {price_list_id}")

        # Notify other tabs that Line Items have changed
        self._notify_line_items_changed()

    def _copy_line_items_from_price_list(self, source_price_list_id, target_price_list_id):
        """Copy Line Items from a source Price List to a target Price List.

        Args:
            source_price_list_id: ID of the source Price List to copy from
            target_price_list_id: ID of the target Price List to copy to
        """
        try:
            # Get source Price List's Line Items
            source_data = self.sg_session.sg.find_one(
                "CustomEntity10",
                [["id", "is", source_price_list_id]],
                ["sg_line_items"]
            )

            if not source_data or not source_data.get("sg_line_items"):
                logger.info(f"No Line Items to copy from Price List {source_price_list_id}")
                return

            # Get source Line Item IDs
            source_line_items = source_data["sg_line_items"]
            if not isinstance(source_line_items, list):
                source_line_items = [source_line_items] if source_line_items else []

            source_ids = [item["id"] for item in source_line_items if isinstance(item, dict) and item.get("id")]

            if not source_ids:
                logger.info(f"No valid Line Item IDs to copy from Price List {source_price_list_id}")
                return

            # Query the source Line Items to get their data
            # Get all fields to copy
            if not self.line_items_field_schema:
                self._fetch_line_items_schema()

            # Fields to skip when copying (read-only, calculated, or special fields)
            skip_fields = [
                "id", "_calc_price", "sg_parent_pricelist", "project",
                "sg_total_mandays",  # Calculated field
                "created_at", "created_by", "updated_at", "updated_by",
            ]
            fields_to_query = [f for f in self.line_items_field_allowlist if f not in skip_fields]

            source_line_item_data = self.sg_session.sg.find(
                "CustomEntity03",
                [["id", "in", source_ids]],
                fields_to_query
            )

            # Create new Line Items as copies
            new_line_item_refs = []
            for item in source_line_item_data:
                # Build data for the new Line Item (copy all fields except id)
                new_item_data = {
                    "project": {"type": "Project", "id": self.current_project_id},
                    "sg_parent_pricelist": {"type": "CustomEntity10", "id": target_price_list_id}
                }

                for field in fields_to_query:
                    # Skip sg_parent_pricelist since we set it above
                    if field == "sg_parent_pricelist":
                        continue
                    if field in item and item[field] is not None:
                        value = item[field]
                        # Handle entity references
                        if isinstance(value, dict) and "type" in value and "id" in value:
                            new_item_data[field] = {"type": value["type"], "id": value["id"]}
                        elif isinstance(value, list):
                            # Multi-entity reference
                            new_item_data[field] = [
                                {"type": v["type"], "id": v["id"]}
                                for v in value
                                if isinstance(v, dict) and "type" in v and "id" in v
                            ]
                        else:
                            new_item_data[field] = value

                # Create the new Line Item
                new_line_item = self.sg_session.sg.create("CustomEntity03", new_item_data)
                new_line_item_refs.append({"type": "CustomEntity03", "id": new_line_item["id"]})

            # Link all new Line Items to the target Price List
            if new_line_item_refs:
                self.sg_session.sg.update(
                    "CustomEntity10",
                    target_price_list_id,
                    {"sg_line_items": new_line_item_refs}
                )

            logger.info(f"Copied {len(new_line_item_refs)} Line Items from Price List {source_price_list_id} to {target_price_list_id}")

            # Notify other tabs that Line Items have changed
            self._notify_line_items_changed()

        except Exception as e:
            logger.error(f"Failed to copy Line Items: {e}", exc_info=True)
            raise

    def _notify_line_items_changed(self):
        """Notify other tabs that Line Items have changed so they can update their dropdowns."""
        try:
            # Get the main app reference
            main_app = self.parent_app
            if not main_app:
                return

            # Update Assets tab's Bid Asset Type dropdown
            if hasattr(main_app, 'assets_tab') and main_app.assets_tab:
                assets_tab = main_app.assets_tab
                # Reload Line Item names and update delegate
                assets_tab.line_item_names = assets_tab._load_line_item_names()
                if assets_tab.asset_type_delegate:
                    assets_tab.asset_type_delegate.update_valid_values(assets_tab.line_item_names)
                    if hasattr(assets_tab, 'assets_widget') and assets_tab.assets_widget:
                        assets_tab.assets_widget.table_view.viewport().update()
                logger.info(f"Updated Assets tab Bid Asset Type dropdown with {len(assets_tab.line_item_names)} Line Items")

            # Update VFX Breakdown tab's VFX Shot Work dropdown
            if hasattr(main_app, 'vfx_breakdown_tab') and main_app.vfx_breakdown_tab:
                vfx_tab = main_app.vfx_breakdown_tab
                # Reload Line Item names and update delegate
                vfx_tab.line_item_names = vfx_tab._load_line_item_names()
                if vfx_tab.vfx_shot_work_delegate:
                    vfx_tab.vfx_shot_work_delegate.update_valid_values(vfx_tab.line_item_names)
                    if hasattr(vfx_tab, 'breakdown_widget') and vfx_tab.breakdown_widget:
                        vfx_tab.breakdown_widget.table_view.viewport().update()
                logger.info(f"Updated VFX Breakdown tab VFX Shot Work dropdown with {len(vfx_tab.line_item_names)} Line Items")

        except Exception as e:
            logger.error(f"Failed to notify Line Items changed: {e}", exc_info=True)

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
            # Check if this price list is assigned to the current bid and clear the reference
            should_refresh_info_label = False
            if self.current_bid_id and self.current_bid_data:
                price_list_ref = self.current_bid_data.get("sg_price_list")
                price_list_ref_id = None
                if isinstance(price_list_ref, dict):
                    price_list_ref_id = price_list_ref.get("id")
                elif isinstance(price_list_ref, list) and price_list_ref:
                    price_list_ref_id = price_list_ref[0].get("id") if price_list_ref[0] else None

                if price_list_ref_id == price_list_id:
                    # Clear the reference in the Bid
                    self.sg_session.sg.update("CustomEntity06", self.current_bid_id, {"sg_price_list": None})
                    logger.info(f"Cleared sg_price_list reference from Bid {self.current_bid_id}")
                    should_refresh_info_label = True

            # Delete the Price List (CustomEntity10)
            self.sg_session.sg.delete("CustomEntity10", price_list_id)

            logger.info(f"Deleted Price List: {price_list_name} (ID: {price_list_id})")
            self._set_price_lists_status(f"Deleted Price List '{price_list_name}'.")

            # Refresh list
            self._refresh_price_lists()

            # Update the bid info label if the price list was assigned to current bid
            if should_refresh_info_label:
                self._refresh_bid_info_label()

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

        # Check for name clash with existing Price Lists
        try:
            filters = [
                ["project", "is", {"type": "Project", "id": self.current_project_id}],
                ["sg_parent_bid", "is", {"type": "CustomEntity06", "id": self.current_bid_id}],
                ["code", "is", new_name],
                ["id", "is_not", price_list_id]
            ]
            existing = self.sg_session.sg.find("CustomEntity10", filters, ["id", "code"])

            if existing:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Name Already Exists",
                    f"A Price List with the name '{new_name}' already exists.\n\nPlease choose a different name."
                )
                return
        except Exception as e:
            logger.error(f"Failed to check for name clash: {e}", exc_info=True)
            # Continue with rename attempt - let ShotGrid handle any conflict

        try:
            # Update the Price List name
            self.sg_session.sg.update("CustomEntity10", price_list_id, {"code": new_name})

            logger.info(f"Renamed Price List from '{current_name}' to '{new_name}' (ID: {price_list_id})")
            self._set_price_lists_status(f"Renamed to '{new_name}'.")

            # Check if this price list is assigned to the current bid
            should_refresh_info_label = False
            if self.current_bid_data:
                price_list_ref = self.current_bid_data.get("sg_price_list")
                price_list_ref_id = None
                if isinstance(price_list_ref, dict):
                    price_list_ref_id = price_list_ref.get("id")
                elif isinstance(price_list_ref, list) and price_list_ref:
                    price_list_ref_id = price_list_ref[0].get("id") if price_list_ref[0] else None

                if price_list_ref_id == price_list_id:
                    should_refresh_info_label = True

            # Refresh list and maintain selection
            current_index = self.price_lists_combo.currentIndex()
            self._refresh_price_lists()
            if current_index < self.price_lists_combo.count():
                self.price_lists_combo.setCurrentIndex(current_index)

            # Update the bid info label if the renamed price list is assigned to current bid
            if should_refresh_info_label:
                self._refresh_bid_info_label()

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
        """Load Line Items linked to the current Price List via sg_parent_pricelist."""
        if not self.current_price_list_id or not self.current_price_list_data:
            self._clear_line_items_tab()
            return

        try:
            logger.info(f"Loading Line Items for Price List ID: {self.current_price_list_id}")

            # Fetch schema if not already loaded
            if not self.line_items_field_schema:
                logger.info("Fetching Line Items schema...")
                self._fetch_line_items_schema()

            # Query Line Items where sg_parent_pricelist equals this Price List
            filters = [
                ["sg_parent_pricelist", "is", {"type": "CustomEntity10", "id": self.current_price_list_id}]
            ]

            fields = self.line_items_field_allowlist.copy()

            # Ensure we have at least basic fields
            if not fields:
                logger.warning("Field allowlist is empty, using default fields")
                fields = ["id", "code"]

            # Remove virtual fields from query (they don't exist in ShotGrid)
            virtual_fields = ["_calc_price"]
            query_fields = [f for f in fields if f not in virtual_fields]

            line_items_list = self.sg_session.sg.find(
                "CustomEntity03",
                filters,
                query_fields
            )

            logger.info(f"Query returned {len(line_items_list) if line_items_list else 0} Line Item(s)")

            # If no Line Items exist, create an initial empty one
            if not line_items_list and self.current_project_id:
                logger.info("No Line Items found - creating initial empty Line Item")
                self._create_initial_line_item(self.current_price_list_id)
                # Re-query to get the newly created Line Item
                line_items_list = self.sg_session.sg.find(
                    "CustomEntity03",
                    filters,
                    query_fields
                )
                logger.info(f"After creating initial Line Item, query returned {len(line_items_list) if line_items_list else 0} Line Item(s)")

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
                            else:
                                item[virtual_field] = ""  # Initialize with empty string

            if line_items_list:
                self.line_items_widget.load_bidding_scenes(line_items_list, field_schema=self.line_items_field_schema)
                logger.info(f"Successfully loaded {len(line_items_list)} Line Item(s) into table")

                # Connect signal for Price Static auto-update (do this every time after loading)
                if "_calc_price" in self.line_items_field_allowlist and "sg_price_static" in self.line_items_field_allowlist:
                    if hasattr(self.line_items_widget, 'model') and self.line_items_widget.model:
                        # Disconnect any existing connection first
                        if self._line_items_data_changed_connected:
                            self.line_items_widget.model.dataChanged.disconnect(self._on_line_items_data_changed)
                            self._line_items_data_changed_connected = False

                        # Reconnect the signal
                        self.line_items_widget.model.dataChanged.connect(self._on_line_items_data_changed)
                        self._line_items_data_changed_connected = True
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

                # Hide the sg_price_static column (it's needed for calculations but not visible)
                if "sg_price_static" in self.line_items_field_allowlist:
                    price_static_col_index = self.line_items_field_allowlist.index("sg_price_static")
                    self.line_items_widget.table_view.setColumnHidden(price_static_col_index, True)
                    logger.info(f"Hidden sg_price_static column (index {price_static_col_index})")

                # Set up formula delegate for the Price column
                if hasattr(self, 'line_items_formula_evaluator'):
                    price_col_index = self.line_items_field_allowlist.index("_calc_price") if "_calc_price" in self.line_items_field_allowlist else -1
                    if price_col_index >= 0:
                        self.line_items_formula_delegate = FormulaDelegate(self.line_items_formula_evaluator, app_settings=self.app_settings)
                        # Set currency symbol and position from bid data (sg_currency field)
                        if self.current_bid_data:
                            default_symbol = self.app_settings.get_currency() or "$"
                            sg_currency_value = self.current_bid_data.get("sg_currency")
                            currency_symbol, currency_position = parse_sg_currency(sg_currency_value, default_symbol)
                            self.line_items_formula_delegate.set_currency_symbol(currency_symbol, currency_position)
                        self.line_items_widget.table_view.setItemDelegateForColumn(price_col_index, self.line_items_formula_delegate)

                # Connect to dataChanged signal to auto-update sg_price_static when _calc_price changes
                if "_calc_price" in self.line_items_field_allowlist and "sg_price_static" in self.line_items_field_allowlist:
                    # Disconnect any existing connection first (in case of reload)
                    if self._line_items_data_changed_connected:
                        self.line_items_widget.model.dataChanged.disconnect(self._on_line_items_data_changed)
                        self._line_items_data_changed_connected = False

                    self.line_items_widget.model.dataChanged.connect(self._on_line_items_data_changed)
                    self._line_items_data_changed_connected = True

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

            # Emit signal to notify Costs tab that prices changed (debounced)
            self._schedule_line_item_price_signal()

        except Exception as e:
            # Ensure flag is reset even if error occurs
            if hasattr(self, 'line_items_widget') and hasattr(self.line_items_widget, 'model'):
                if hasattr(self.line_items_widget.model, '_skip_undo_command'):
                    self.line_items_widget.model._skip_undo_command = False
            logger.error(f"Error in _update_price_static_deferred: {e}", exc_info=True)

    def _schedule_line_item_price_signal(self):
        """Schedule emission of lineItemPricesChanged signal with debouncing."""
        # Use a timer to debounce multiple rapid updates
        if not hasattr(self, '_price_signal_timer'):
            self._price_signal_timer = QtCore.QTimer(self)
            self._price_signal_timer.setSingleShot(True)
            self._price_signal_timer.timeout.connect(self._emit_line_item_price_signal)

        # Reset the timer (debounce)
        self._price_signal_timer.start(500)  # 500ms debounce

    def _emit_line_item_price_signal(self):
        """Emit the lineItemPricesChanged signal."""
        logger.info("Emitting lineItemPricesChanged signal")
        self.lineItemPricesChanged.emit()


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

        # Create Rate Card widget (no toolbar/search bar needed)
        self.rate_card_widget = VFXBreakdownWidget(self.sg_session, show_toolbar=False, settings_key="rate_card_dialog", parent=self)

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
                # Recalculate prices based on new Rate Card
                parent._initialize_price_static_values()
                # Update bid info label to reflect Rate Card change
                parent._refresh_bid_info_label()
                # Emit signal to notify other tabs (e.g., Costs) about rate card change
                logger.info("Emitting rateCardChanged signal")
                parent.rateCardChanged.emit()

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
