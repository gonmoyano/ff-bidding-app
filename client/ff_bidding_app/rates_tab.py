"""
Rates Tab
Contains UI and logic for managing Price Lists (CustomEntity10).
"""

from PySide6 import QtWidgets, QtCore

try:
    from .logger import logger
    from .bid_selector_widget import CollapsibleGroupBox
except ImportError:
    import logging
    logger = logging.getLogger("FFPackageManager")
    from bid_selector_widget import CollapsibleGroupBox


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

        # Current context
        self.current_project_id = None
        self.current_bid_id = None
        self.current_bid_data = None  # Store full bid data for accessing sg_price_list
        self.current_price_list_id = None  # Store currently selected price list

        # UI widgets for price lists selector
        self.price_lists_combo = None
        self.price_lists_set_btn = None
        self.price_lists_refresh_btn = None
        self.price_lists_status_label = None

        # Nested tabs
        self.nested_tab_widget = None

        self._build_ui()

    def _build_ui(self):
        """Build the Rates tab UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        # Selector group (collapsible)
        selector_group = CollapsibleGroupBox("Price Lists")

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
        """Create the Rate Card nested tab content."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)

        # Title
        title_label = QtWidgets.QLabel("Rate Card")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; padding: 20px;")
        layout.addWidget(title_label)

        # Placeholder content
        info_label = QtWidgets.QLabel("Rate Card content will be displayed here.\nThis section will contain rate card information for the selected Price List.")
        info_label.setStyleSheet("padding: 20px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        layout.addStretch()

        return widget

    def _create_line_items_tab(self):
        """Create the Line Items nested tab content."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)

        # Title
        title_label = QtWidgets.QLabel("Line Items")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; padding: 20px;")
        layout.addWidget(title_label)

        # Placeholder content
        info_label = QtWidgets.QLabel("Line Items content will be displayed here.\nThis section will contain line item information for the selected Price List.")
        info_label.setStyleSheet("padding: 20px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        layout.addStretch()

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
        """
        self.current_bid_data = bid_data
        self.current_bid_id = bid_data.get('id') if bid_data else None
        self.current_project_id = project_id

        # Clear current selection and add placeholder
        self.price_lists_combo.blockSignals(True)
        self.price_lists_combo.clear()
        self.price_lists_combo.addItem("-- Select Price List --", None)
        self.price_lists_combo.blockSignals(False)

        if not self.current_bid_id or not project_id:
            self._set_price_lists_status("Select a Bid to view Price Lists.")
            self.price_lists_set_btn.setEnabled(False)
            self.current_price_list_id = None
            return

        # Refresh the price lists and auto-select the one linked to this bid
        self._refresh_price_lists()

    def _refresh_price_lists(self):
        """Refresh the list of Price Lists for the current bid."""
        if not self.current_project_id or not self.current_bid_id:
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
                        # Linked Price List not found
                        logger.warning(f"Linked Price List {linked_price_list_id} not found in project")
                # If no linked Price List, leave at placeholder (index 0)
                # Don't auto-select - user must explicitly choose
            else:
                self._set_price_lists_status("No Price Lists found for this project.")
                self.price_lists_set_btn.setEnabled(False)

        except Exception as e:
            logger.error(f"Failed to refresh Price Lists: {e}", exc_info=True)
            self._set_price_lists_status("Failed to load Price Lists.", is_error=True)

    def _on_price_lists_changed(self, index):
        """Handle Price Lists selection change."""
        if index < 0:
            self.current_price_list_id = None
            return

        price_list_id = self.price_lists_combo.currentData()
        if not price_list_id:
            # Placeholder selected
            self.current_price_list_id = None
            self._set_price_lists_status("Select a Price List to view details.")
            return

        # Store the selected price list ID
        self.current_price_list_id = price_list_id
        display_name = self.price_lists_combo.currentText()
        self._set_price_lists_status(f"Selected Price List: '{display_name}'.")
        logger.info(f"Price List changed to: {display_name} (ID: {price_list_id})")

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
