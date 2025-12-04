"""
Settings Dialog
Dialog for configuring application-wide settings.
"""

import shutil
from pathlib import Path
from PySide6 import QtWidgets, QtCore, QtGui


class ClientUserEditDialog(QtWidgets.QDialog):
    """Dialog for adding or editing a Client User."""

    def __init__(self, client_user=None, parent=None):
        """Initialize the client user edit dialog.

        Args:
            client_user: Existing ClientUser dict to edit, or None for new user
            parent: Parent widget
        """
        super().__init__(parent)
        self.client_user = client_user

        if client_user:
            self.setWindowTitle("Edit Client User")
        else:
            self.setWindowTitle("Add Client User")

        self.setModal(True)
        self.setMinimumWidth(400)
        self._build_ui()

    def _build_ui(self):
        """Build the dialog UI."""
        layout = QtWidgets.QVBoxLayout(self)

        form_layout = QtWidgets.QFormLayout()
        form_layout.setSpacing(10)

        # Name
        self.name_input = QtWidgets.QLineEdit()
        self.name_input.setPlaceholderText("Enter user's full name")
        if self.client_user:
            self.name_input.setText(self.client_user.get("name", ""))
        form_layout.addRow("Name:", self.name_input)

        # Email
        self.email_input = QtWidgets.QLineEdit()
        self.email_input.setPlaceholderText("Enter email address")
        if self.client_user:
            self.email_input.setText(self.client_user.get("email", "") or "")
        form_layout.addRow("Email:", self.email_input)

        # Status
        self.status_combo = QtWidgets.QComboBox()
        self.status_combo.addItem("Active", "act")
        self.status_combo.addItem("Inactive", "dis")
        if self.client_user:
            status = self.client_user.get("sg_status_list", "act")
            idx = self.status_combo.findData(status)
            if idx >= 0:
                self.status_combo.setCurrentIndex(idx)
        form_layout.addRow("Status:", self.status_combo)

        layout.addLayout(form_layout)

        # Button box
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _validate_and_accept(self):
        """Validate inputs and accept if valid."""
        name = self.name_input.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(
                self,
                "Validation Error",
                "Name is required."
            )
            self.name_input.setFocus()
            return

        email = self.email_input.text().strip()
        if not email:
            QtWidgets.QMessageBox.warning(
                self,
                "Validation Error",
                "Email is required."
            )
            self.email_input.setFocus()
            return

        self.accept()

    def get_client_user_data(self):
        """Get the client user data from the form.

        Returns:
            dict: ClientUser data with name, email, sg_status_list
        """
        return {
            "name": self.name_input.text().strip(),
            "email": self.email_input.text().strip(),
            "sg_status_list": self.status_combo.currentData(),
        }


class ManageClientUsersDialog(QtWidgets.QDialog):
    """Dialog for managing Client Users."""

    def __init__(self, sg_client, parent=None):
        """Initialize the manage client users dialog.

        Args:
            sg_client: ShotGrid client instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.sg_client = sg_client
        self.client_users = []

        self.setWindowTitle("Manage Client Users")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        self._build_ui()
        self._load_data()

    def _build_ui(self):
        """Build the dialog UI."""
        layout = QtWidgets.QVBoxLayout(self)

        # Description
        desc_label = QtWidgets.QLabel(
            "Manage Client Users. These users can be assigned as recipients to vendors."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(desc_label)

        # Client Users table
        self.users_table = QtWidgets.QTableWidget()
        self.users_table.setColumnCount(3)
        self.users_table.setHorizontalHeaderLabels(["Name", "Email", "Status"])
        self.users_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.users_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.users_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.users_table.horizontalHeader().setStretchLastSection(True)
        self.users_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.users_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.users_table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        self.users_table.verticalHeader().setVisible(False)
        self.users_table.doubleClicked.connect(self._edit_selected_user)
        layout.addWidget(self.users_table)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()

        self.add_btn = QtWidgets.QPushButton("Add")
        self.add_btn.clicked.connect(self._add_user)
        button_layout.addWidget(self.add_btn)

        self.edit_btn = QtWidgets.QPushButton("Edit")
        self.edit_btn.clicked.connect(self._edit_selected_user)
        self.edit_btn.setEnabled(False)
        button_layout.addWidget(self.edit_btn)

        self.delete_btn = QtWidgets.QPushButton("Delete")
        self.delete_btn.clicked.connect(self._delete_selected_user)
        self.delete_btn.setEnabled(False)
        button_layout.addWidget(self.delete_btn)

        button_layout.addStretch()

        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._load_data)
        button_layout.addWidget(self.refresh_btn)

        layout.addLayout(button_layout)

        # Close button
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        # Connect selection change
        self.users_table.selectionModel().selectionChanged.connect(self._on_selection_changed)

    def _load_data(self):
        """Load client users from ShotGrid."""
        if not self.sg_client:
            return

        try:
            self.client_users = self.sg_client.get_all_client_users(include_inactive=True)
            self._populate_table()
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to load client users:\n{str(e)}"
            )

    def _populate_table(self):
        """Populate the client users table."""
        self.users_table.setRowCount(len(self.client_users))

        for row, user in enumerate(self.client_users):
            # Name
            name_item = QtWidgets.QTableWidgetItem(user.get("name", ""))
            name_item.setData(QtCore.Qt.UserRole, user.get("id"))
            self.users_table.setItem(row, 0, name_item)

            # Email
            email_item = QtWidgets.QTableWidgetItem(user.get("email", "") or "")
            self.users_table.setItem(row, 1, email_item)

            # Status
            status = user.get("sg_status_list", "act")
            status_text = "Active" if status == "act" else "Inactive"
            status_item = QtWidgets.QTableWidgetItem(status_text)
            if status != "act":
                status_item.setForeground(QtGui.QColor("#999999"))
            self.users_table.setItem(row, 2, status_item)

    def _on_selection_changed(self):
        """Handle selection change in the table."""
        has_selection = len(self.users_table.selectedItems()) > 0
        self.edit_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)

    def _get_selected_user(self):
        """Get the currently selected user."""
        selected_rows = self.users_table.selectionModel().selectedRows()
        if not selected_rows:
            return None

        row = selected_rows[0].row()
        user_id = self.users_table.item(row, 0).data(QtCore.Qt.UserRole)

        for user in self.client_users:
            if user.get("id") == user_id:
                return user
        return None

    def _add_user(self):
        """Add a new client user."""
        dialog = ClientUserEditDialog(parent=self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            data = dialog.get_client_user_data()
            try:
                self.sg_client.create_client_user(
                    data["name"],
                    data["email"],
                    status=data["sg_status_list"]
                )
                self._load_data()
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to create client user:\n{str(e)}"
                )

    def _edit_selected_user(self):
        """Edit the selected client user."""
        user = self._get_selected_user()
        if not user:
            return

        dialog = ClientUserEditDialog(client_user=user, parent=self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            data = dialog.get_client_user_data()
            try:
                self.sg_client.update_client_user(user["id"], data)
                self._load_data()
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to update client user:\n{str(e)}"
                )

    def _delete_selected_user(self):
        """Delete the selected client user."""
        user = self._get_selected_user()
        if not user:
            return

        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete '{user.get('name')}'?\n\n"
            "This action cannot be undone.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            try:
                self.sg_client.delete_client_user(user["id"])
                self._load_data()
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to delete client user:\n{str(e)}"
                )


class VendorEditDialog(QtWidgets.QDialog):
    """Dialog for adding or editing a vendor."""

    def __init__(self, vendor=None, available_client_users=None, parent=None):
        """Initialize the vendor edit dialog.

        Args:
            vendor: Existing vendor dict to edit, or None for new vendor
            available_client_users: List of available ClientUser dicts for selection
            parent: Parent widget
        """
        super().__init__(parent)
        self.vendor = vendor
        self.available_client_users = available_client_users or []
        self.selected_recipients = []

        # Initialize selected recipients from vendor's sg_members
        if vendor:
            members = vendor.get("sg_members") or []
            for member in members:
                if isinstance(member, dict) and member.get("id"):
                    self.selected_recipients.append({
                        "type": "ClientUser",
                        "id": member["id"],
                        "name": member.get("name", f"User {member['id']}")
                    })

        if vendor:
            self.setWindowTitle("Edit Vendor")
        else:
            self.setWindowTitle("Add Vendor")

        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        self._build_ui()

    def _build_ui(self):
        """Build the dialog UI."""
        layout = QtWidgets.QVBoxLayout(self)

        form_layout = QtWidgets.QFormLayout()
        form_layout.setSpacing(10)

        # Vendor name/code
        self.name_input = QtWidgets.QLineEdit()
        self.name_input.setPlaceholderText("Enter vendor name")
        if self.vendor:
            self.name_input.setText(self.vendor.get("code", ""))
        form_layout.addRow("Name:", self.name_input)

        # Description
        self.description_input = QtWidgets.QTextEdit()
        self.description_input.setPlaceholderText("Enter vendor description (optional)")
        self.description_input.setMaximumHeight(80)
        if self.vendor:
            self.description_input.setText(self.vendor.get("description", "") or "")
        form_layout.addRow("Description:", self.description_input)

        layout.addLayout(form_layout)

        # Recipients section
        recipients_group = QtWidgets.QGroupBox("Recipients")
        recipients_layout = QtWidgets.QVBoxLayout(recipients_group)

        recipients_desc = QtWidgets.QLabel("Select Client Users who will receive deliveries for this vendor.")
        recipients_desc.setWordWrap(True)
        recipients_desc.setStyleSheet("color: #888888; font-size: 11px;")
        recipients_layout.addWidget(recipients_desc)

        # Horizontal layout for available and selected lists
        lists_layout = QtWidgets.QHBoxLayout()

        # Available users list
        available_layout = QtWidgets.QVBoxLayout()
        available_label = QtWidgets.QLabel("Available:")
        available_label.setStyleSheet("font-weight: bold;")
        available_layout.addWidget(available_label)

        self.available_list = QtWidgets.QListWidget()
        self.available_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self._populate_available_list()
        available_layout.addWidget(self.available_list)
        lists_layout.addLayout(available_layout)

        # Add/Remove buttons
        buttons_layout = QtWidgets.QVBoxLayout()
        buttons_layout.addStretch()

        self.add_recipient_btn = QtWidgets.QPushButton(">")
        self.add_recipient_btn.setFixedWidth(40)
        self.add_recipient_btn.setToolTip("Add selected users as recipients")
        self.add_recipient_btn.clicked.connect(self._add_recipients)
        buttons_layout.addWidget(self.add_recipient_btn)

        self.remove_recipient_btn = QtWidgets.QPushButton("<")
        self.remove_recipient_btn.setFixedWidth(40)
        self.remove_recipient_btn.setToolTip("Remove selected recipients")
        self.remove_recipient_btn.clicked.connect(self._remove_recipients)
        buttons_layout.addWidget(self.remove_recipient_btn)

        buttons_layout.addStretch()
        lists_layout.addLayout(buttons_layout)

        # Selected recipients list
        selected_layout = QtWidgets.QVBoxLayout()
        selected_label = QtWidgets.QLabel("Recipients:")
        selected_label.setStyleSheet("font-weight: bold;")
        selected_layout.addWidget(selected_label)

        self.selected_list = QtWidgets.QListWidget()
        self.selected_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self._populate_selected_list()
        selected_layout.addWidget(self.selected_list)
        lists_layout.addLayout(selected_layout)

        recipients_layout.addLayout(lists_layout)
        layout.addWidget(recipients_group)

        # Button box
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _populate_available_list(self):
        """Populate the available users list."""
        self.available_list.clear()
        selected_ids = {r["id"] for r in self.selected_recipients}

        for user in self.available_client_users:
            if user.get("id") not in selected_ids:
                display_text = user.get("name", "Unknown")
                email = user.get("email", "")
                if email:
                    display_text += f" ({email})"

                item = QtWidgets.QListWidgetItem(display_text)
                item.setData(QtCore.Qt.UserRole, user)
                self.available_list.addItem(item)

    def _populate_selected_list(self):
        """Populate the selected recipients list."""
        self.selected_list.clear()

        for recipient in self.selected_recipients:
            # Try to find the full user info from available users
            user_info = next(
                (u for u in self.available_client_users if u.get("id") == recipient["id"]),
                recipient
            )
            display_text = user_info.get("name", recipient.get("name", "Unknown"))
            email = user_info.get("email", "")
            if email:
                display_text += f" ({email})"

            item = QtWidgets.QListWidgetItem(display_text)
            item.setData(QtCore.Qt.UserRole, recipient)
            self.selected_list.addItem(item)

    def _add_recipients(self):
        """Add selected users to recipients list."""
        for item in self.available_list.selectedItems():
            user = item.data(QtCore.Qt.UserRole)
            if user and user.get("id") not in {r["id"] for r in self.selected_recipients}:
                self.selected_recipients.append({
                    "type": "ClientUser",
                    "id": user["id"],
                    "name": user.get("name", f"User {user['id']}")
                })

        self._populate_available_list()
        self._populate_selected_list()

    def _remove_recipients(self):
        """Remove selected recipients from the list."""
        ids_to_remove = set()
        for item in self.selected_list.selectedItems():
            recipient = item.data(QtCore.Qt.UserRole)
            if recipient:
                ids_to_remove.add(recipient["id"])

        self.selected_recipients = [r for r in self.selected_recipients if r["id"] not in ids_to_remove]

        self._populate_available_list()
        self._populate_selected_list()

    def _validate_and_accept(self):
        """Validate inputs and accept if valid."""
        name = self.name_input.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(
                self,
                "Validation Error",
                "Vendor name is required."
            )
            self.name_input.setFocus()
            return
        self.accept()

    def get_vendor_data(self):
        """Get the vendor data from the form.

        Returns:
            dict: Vendor data with code, description, sg_members
        """
        # Format sg_members as entity references
        sg_members = [{"type": "ClientUser", "id": r["id"]} for r in self.selected_recipients]

        return {
            "code": self.name_input.text().strip(),
            "description": self.description_input.toPlainText().strip() or None,
            "sg_members": sg_members if sg_members else None,
        }


class ManageVendorsDialog(QtWidgets.QDialog):
    """Dialog for managing Vendors."""

    def __init__(self, sg_client, project_id, parent=None):
        """Initialize the manage vendors dialog.

        Args:
            sg_client: ShotGrid client instance
            project_id: Current project ID
            parent: Parent widget
        """
        super().__init__(parent)
        self.sg_client = sg_client
        self.project_id = project_id
        self.vendors = []
        self.client_users = []

        self.setWindowTitle("Manage Vendors")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        self._build_ui()
        self._load_data()

    def _build_ui(self):
        """Build the dialog UI."""
        layout = QtWidgets.QVBoxLayout(self)

        # Description
        desc_label = QtWidgets.QLabel(
            "Manage vendors for this project. Vendors can be assigned to packages for delivery tracking."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(desc_label)

        # Vendors table
        self.vendors_table = QtWidgets.QTableWidget()
        self.vendors_table.setColumnCount(2)
        self.vendors_table.setHorizontalHeaderLabels(["Name", "Recipients"])
        self.vendors_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.vendors_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.vendors_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.vendors_table.horizontalHeader().setStretchLastSection(True)
        self.vendors_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.vendors_table.verticalHeader().setVisible(False)
        self.vendors_table.doubleClicked.connect(self._edit_selected_vendor)
        layout.addWidget(self.vendors_table)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()

        self.add_btn = QtWidgets.QPushButton("Add")
        self.add_btn.clicked.connect(self._add_vendor)
        button_layout.addWidget(self.add_btn)

        self.edit_btn = QtWidgets.QPushButton("Edit")
        self.edit_btn.clicked.connect(self._edit_selected_vendor)
        self.edit_btn.setEnabled(False)
        button_layout.addWidget(self.edit_btn)

        self.delete_btn = QtWidgets.QPushButton("Delete")
        self.delete_btn.clicked.connect(self._delete_selected_vendor)
        self.delete_btn.setEnabled(False)
        button_layout.addWidget(self.delete_btn)

        button_layout.addStretch()

        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._load_data)
        button_layout.addWidget(self.refresh_btn)

        layout.addLayout(button_layout)

        # Close button
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        # Connect selection change
        self.vendors_table.selectionModel().selectionChanged.connect(self._on_selection_changed)

    def _load_data(self):
        """Load vendors and client users from ShotGrid."""
        if not self.sg_client or not self.project_id:
            return

        try:
            self.vendors = self.sg_client.get_vendors(self.project_id)
            self.client_users = self.sg_client.get_all_client_users()
            self._populate_table()
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to load data:\n{str(e)}"
            )

    def _populate_table(self):
        """Populate the vendors table."""
        self.vendors_table.setRowCount(len(self.vendors))

        for row, vendor in enumerate(self.vendors):
            # Name
            name_item = QtWidgets.QTableWidgetItem(vendor.get("code", ""))
            name_item.setData(QtCore.Qt.UserRole, vendor.get("id"))
            self.vendors_table.setItem(row, 0, name_item)

            # Recipients
            members = vendor.get("sg_members") or []
            recipient_names = []
            for member in members:
                if isinstance(member, dict):
                    name = member.get("name", f"User {member.get('id', '?')}")
                    recipient_names.append(name)

            recipients_text = ", ".join(recipient_names) if recipient_names else "(none)"
            recipients_item = QtWidgets.QTableWidgetItem(recipients_text)
            self.vendors_table.setItem(row, 1, recipients_item)

    def _on_selection_changed(self):
        """Handle selection change in the table."""
        has_selection = len(self.vendors_table.selectedItems()) > 0
        self.edit_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)

    def _get_selected_vendor(self):
        """Get the currently selected vendor."""
        selected_rows = self.vendors_table.selectionModel().selectedRows()
        if not selected_rows:
            return None

        row = selected_rows[0].row()
        vendor_id = self.vendors_table.item(row, 0).data(QtCore.Qt.UserRole)

        for vendor in self.vendors:
            if vendor.get("id") == vendor_id:
                return vendor
        return None

    def _add_vendor(self):
        """Add a new vendor."""
        dialog = VendorEditDialog(available_client_users=self.client_users, parent=self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            data = dialog.get_vendor_data()
            try:
                # Create vendor first
                new_vendor = self.sg_client.create_vendor(
                    self.project_id,
                    data["code"],
                    description=data.get("description")
                )
                # Update with sg_members if provided
                if data.get("sg_members"):
                    self.sg_client.update_vendor(new_vendor["id"], {"sg_members": data["sg_members"]})
                self._load_data()
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to create vendor:\n{str(e)}"
                )

    def _edit_selected_vendor(self):
        """Edit the selected vendor."""
        vendor = self._get_selected_vendor()
        if not vendor:
            return

        dialog = VendorEditDialog(vendor=vendor, available_client_users=self.client_users, parent=self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            data = dialog.get_vendor_data()
            try:
                self.sg_client.update_vendor(vendor["id"], data)
                self._load_data()
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to update vendor:\n{str(e)}"
                )

    def _delete_selected_vendor(self):
        """Delete the selected vendor."""
        vendor = self._get_selected_vendor()
        if not vendor:
            return

        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete vendor '{vendor.get('code')}'?\n\n"
            "This action cannot be undone.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            try:
                self.sg_client.delete_vendor(vendor["id"])
                self._load_data()
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to delete vendor:\n{str(e)}"
                )


class VendorsTab(QtWidgets.QWidget):
    """Tab widget for managing vendors."""

    def __init__(self, sg_client, project_id, parent=None):
        """Initialize the vendors tab.

        Args:
            sg_client: ShotGrid client instance
            project_id: Current project ID
            parent: Parent widget
        """
        super().__init__(parent)
        self.sg_client = sg_client
        self.project_id = project_id
        self.vendors = []
        self.client_users = []

        self._build_ui()
        self._load_data()

    def _build_ui(self):
        """Build the tab UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Description label
        desc_label = QtWidgets.QLabel(
            "Manage vendors and client users for this project. Vendors can be assigned to packages for delivery tracking."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(desc_label)

        # Vendor table (read-only display)
        self.vendor_table = QtWidgets.QTableWidget()
        self.vendor_table.setColumnCount(2)
        self.vendor_table.setHorizontalHeaderLabels(["Name", "Recipients"])
        self.vendor_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.vendor_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.vendor_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.vendor_table.horizontalHeader().setStretchLastSection(True)
        self.vendor_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.vendor_table.verticalHeader().setVisible(False)
        layout.addWidget(self.vendor_table)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()

        self.manage_vendors_btn = QtWidgets.QPushButton("Manage Vendors")
        self.manage_vendors_btn.clicked.connect(self._open_manage_vendors)
        button_layout.addWidget(self.manage_vendors_btn)

        self.manage_users_btn = QtWidgets.QPushButton("Manage Client Users")
        self.manage_users_btn.clicked.connect(self._open_manage_client_users)
        button_layout.addWidget(self.manage_users_btn)

        button_layout.addStretch()

        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._load_data)
        button_layout.addWidget(self.refresh_btn)

        layout.addLayout(button_layout)

    def _load_data(self):
        """Load vendors and client users from ShotGrid."""
        if not self.sg_client or not self.project_id:
            return

        try:
            self.vendors = self.sg_client.get_vendors(self.project_id)
            self.client_users = self.sg_client.get_all_client_users()
            self._populate_table()
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to load data:\n{str(e)}"
            )

    def _populate_table(self):
        """Populate the vendor table."""
        self.vendor_table.setRowCount(len(self.vendors))

        for row, vendor in enumerate(self.vendors):
            # Store vendor ID in first column's data
            name_item = QtWidgets.QTableWidgetItem(vendor.get("code", ""))
            name_item.setData(QtCore.Qt.UserRole, vendor.get("id"))
            self.vendor_table.setItem(row, 0, name_item)

            # Build recipients display string
            members = vendor.get("sg_members") or []
            recipient_names = []
            for member in members:
                if isinstance(member, dict):
                    name = member.get("name", f"User {member.get('id', '?')}")
                    recipient_names.append(name)

            recipients_text = ", ".join(recipient_names) if recipient_names else "(none)"
            recipients_item = QtWidgets.QTableWidgetItem(recipients_text)
            self.vendor_table.setItem(row, 1, recipients_item)

    def _open_manage_vendors(self):
        """Open the Manage Vendors dialog."""
        dialog = ManageVendorsDialog(self.sg_client, self.project_id, parent=self)
        dialog.exec()
        # Refresh data after dialog closes
        self._load_data()

    def _open_manage_client_users(self):
        """Open the Manage Client Users dialog."""
        dialog = ManageClientUsersDialog(self.sg_client, parent=self)
        dialog.exec()
        # Refresh data after dialog closes (client users might have changed)
        self._load_data()


class GeneralTab(QtWidgets.QWidget):
    """Tab widget for general settings."""

    # Signal emitted when DPI slider changes
    dpiChanged = QtCore.Signal(int)

    def __init__(self, app_settings, parent=None):
        """Initialize the general settings tab.

        Args:
            app_settings: AppSettings instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.app_settings = app_settings
        self._build_ui()

    def _build_ui(self):
        """Build the tab UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # DPI Scale setting
        dpi_group = QtWidgets.QGroupBox("Display Scaling")
        dpi_layout = QtWidgets.QVBoxLayout(dpi_group)

        dpi_label = QtWidgets.QLabel(
            "Adjust the size of UI elements (50% - 200%). Changes apply in real-time."
        )
        dpi_label.setWordWrap(True)
        dpi_label.setStyleSheet("color: #888888; font-size: 11px;")
        dpi_layout.addWidget(dpi_label)

        # DPI scale slider with percentage display
        slider_layout = QtWidgets.QHBoxLayout()
        slider_label = QtWidgets.QLabel("Scale Factor:")

        self.dpi_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.dpi_slider.setMinimum(50)   # 50%
        self.dpi_slider.setMaximum(200)  # 200%
        self.dpi_slider.setSingleStep(5)
        self.dpi_slider.setPageStep(25)
        self.dpi_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.dpi_slider.setTickInterval(25)

        # Set current value
        current_dpi = self.app_settings.get_dpi_scale()
        self.dpi_slider.setValue(int(current_dpi * 100))

        # Percentage label that updates in real-time
        self.dpi_percentage_label = QtWidgets.QLabel(f"{int(current_dpi * 100)}%")
        self.dpi_percentage_label.setMinimumWidth(50)
        self.dpi_percentage_label.setStyleSheet("font-weight: bold; color: #0078d4;")

        # Connect slider to update label and emit signal
        self.dpi_slider.valueChanged.connect(self._on_dpi_slider_changed)

        slider_layout.addWidget(slider_label)
        slider_layout.addWidget(self.dpi_slider)
        slider_layout.addWidget(self.dpi_percentage_label)
        dpi_layout.addLayout(slider_layout)

        # Add min/max labels
        limits_layout = QtWidgets.QHBoxLayout()
        limits_layout.addWidget(QtWidgets.QLabel("50%"))
        limits_layout.addStretch()
        limits_layout.addWidget(QtWidgets.QLabel("100%"))
        limits_layout.addStretch()
        limits_layout.addWidget(QtWidgets.QLabel("200%"))
        limits_layout.setContentsMargins(45, 0, 50, 5)
        for i in range(limits_layout.count()):
            widget = limits_layout.itemAt(i).widget()
            if widget:
                widget.setStyleSheet("color: #666666; font-size: 10px;")
        dpi_layout.addLayout(limits_layout)

        layout.addWidget(dpi_group)

        # Currency setting
        currency_group = QtWidgets.QGroupBox("Currency")
        currency_layout = QtWidgets.QVBoxLayout(currency_group)

        currency_label = QtWidgets.QLabel(
            "Select the currency symbol to use throughout the application."
        )
        currency_label.setWordWrap(True)
        currency_label.setStyleSheet("color: #888888; font-size: 11px;")
        currency_layout.addWidget(currency_label)

        # Currency combo box
        currency_combo_layout = QtWidgets.QHBoxLayout()
        currency_combo_label = QtWidgets.QLabel("Currency Symbol:")
        self.currency_combo = QtWidgets.QComboBox()
        self.currency_combo.addItem("$ - US Dollar", "$")
        self.currency_combo.addItem("\u20ac - Euro", "\u20ac")
        self.currency_combo.addItem("\u00a3 - British Pound", "\u00a3")
        self.currency_combo.addItem("\u00a5 - Japanese Yen / Chinese Yuan", "\u00a5")
        self.currency_combo.addItem("\u20b9 - Indian Rupee", "\u20b9")
        self.currency_combo.addItem("\u20bd - Russian Ruble", "\u20bd")
        self.currency_combo.addItem("R$ - Brazilian Real", "R$")
        self.currency_combo.addItem("Custom...", "custom")

        # Set current value
        current_currency = self.app_settings.get_currency()
        found = False
        for i in range(self.currency_combo.count() - 1):  # Exclude "Custom..."
            if self.currency_combo.itemData(i) == current_currency:
                self.currency_combo.setCurrentIndex(i)
                found = True
                break

        if not found:
            # Set to Custom and show the custom value
            self.currency_combo.setCurrentIndex(self.currency_combo.count() - 1)

        currency_combo_layout.addWidget(currency_combo_label)
        currency_combo_layout.addWidget(self.currency_combo)
        currency_combo_layout.addStretch()
        currency_layout.addLayout(currency_combo_layout)

        # Custom currency input
        self.custom_currency_layout = QtWidgets.QHBoxLayout()
        custom_label = QtWidgets.QLabel("Custom Symbol:")
        self.custom_currency_input = QtWidgets.QLineEdit()
        self.custom_currency_input.setMaxLength(5)
        self.custom_currency_input.setPlaceholderText("Enter custom symbol")
        if not found:
            self.custom_currency_input.setText(current_currency)
        self.custom_currency_layout.addWidget(custom_label)
        self.custom_currency_layout.addWidget(self.custom_currency_input)
        self.custom_currency_layout.addStretch()
        currency_layout.addLayout(self.custom_currency_layout)

        # Show/hide custom input based on selection
        self._toggle_custom_currency()
        self.currency_combo.currentIndexChanged.connect(self._toggle_custom_currency)

        layout.addWidget(currency_group)

        # Thumbnail Cache setting
        cache_group = QtWidgets.QGroupBox("Thumbnail Cache")
        cache_layout = QtWidgets.QVBoxLayout(cache_group)

        cache_label = QtWidgets.QLabel(
            "Thumbnails are cached locally for faster loading. "
            "Clear the cache if images appear outdated or corrupted."
        )
        cache_label.setWordWrap(True)
        cache_label.setStyleSheet("color: #888888; font-size: 11px;")
        cache_layout.addWidget(cache_label)

        # Cache folder path
        cache_path_layout = QtWidgets.QHBoxLayout()
        cache_path_label = QtWidgets.QLabel("Cache Folder:")
        self.cache_path_input = QtWidgets.QLineEdit()
        self.cache_path_input.setReadOnly(True)
        current_cache_path = self.app_settings.get_thumbnail_cache_path()
        self.cache_path_input.setText(str(current_cache_path))

        browse_btn = QtWidgets.QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_cache_folder)

        cache_path_layout.addWidget(cache_path_label)
        cache_path_layout.addWidget(self.cache_path_input, 1)
        cache_path_layout.addWidget(browse_btn)
        cache_layout.addLayout(cache_path_layout)

        # Cache stats and actions
        cache_actions_layout = QtWidgets.QHBoxLayout()

        # Cache stats label
        self.cache_stats_label = QtWidgets.QLabel()
        self.cache_stats_label.setStyleSheet("color: #666666; font-size: 10px;")
        self._update_cache_stats()
        cache_actions_layout.addWidget(self.cache_stats_label)

        cache_actions_layout.addStretch()

        # Clear cache button
        clear_cache_btn = QtWidgets.QPushButton("Clear Cache")
        clear_cache_btn.setToolTip("Delete all cached thumbnails")
        clear_cache_btn.clicked.connect(self._clear_cache)
        cache_actions_layout.addWidget(clear_cache_btn)

        # Refresh cache button
        refresh_cache_btn = QtWidgets.QPushButton("Refresh All")
        refresh_cache_btn.setToolTip("Re-download all thumbnails from ShotGrid")
        refresh_cache_btn.clicked.connect(self._refresh_all_thumbnails)
        cache_actions_layout.addWidget(refresh_cache_btn)

        cache_layout.addLayout(cache_actions_layout)

        # Cache max age setting
        cache_age_layout = QtWidgets.QHBoxLayout()
        cache_age_label = QtWidgets.QLabel("Cache expires after:")
        self.cache_age_spinbox = QtWidgets.QSpinBox()
        self.cache_age_spinbox.setMinimum(1)
        self.cache_age_spinbox.setMaximum(365)
        self.cache_age_spinbox.setValue(self.app_settings.get_thumbnail_cache_max_age_days())
        self.cache_age_spinbox.setSuffix(" days")
        cache_age_layout.addWidget(cache_age_label)
        cache_age_layout.addWidget(self.cache_age_spinbox)
        cache_age_layout.addStretch()
        cache_layout.addLayout(cache_age_layout)

        layout.addWidget(cache_group)

        # Spacer
        layout.addStretch()

    def _on_dpi_slider_changed(self, value):
        """Handle DPI slider value change."""
        self.dpi_percentage_label.setText(f"{value}%")
        self.dpiChanged.emit(value)

    def _toggle_custom_currency(self):
        """Show/hide custom currency input based on selection."""
        is_custom = self.currency_combo.currentData() == "custom"
        custom_label = self.custom_currency_layout.itemAt(0).widget()
        custom_label.setVisible(is_custom)
        self.custom_currency_input.setVisible(is_custom)

    def get_dpi_scale(self):
        """Get the selected DPI scale factor.

        Returns:
            float: DPI scale factor
        """
        return self.dpi_slider.value() / 100.0

    def get_currency(self):
        """Get the selected currency symbol.

        Returns:
            str: Currency symbol
        """
        if self.currency_combo.currentData() == "custom":
            return self.custom_currency_input.text().strip() or "$"
        return self.currency_combo.currentData()

    def get_thumbnail_cache_path(self):
        """Get the thumbnail cache folder path.

        Returns:
            Path: Cache folder path
        """
        return Path(self.cache_path_input.text())

    def get_thumbnail_cache_max_age_days(self):
        """Get the cache max age in days.

        Returns:
            int: Max age in days
        """
        return self.cache_age_spinbox.value()

    def _browse_cache_folder(self):
        """Open a folder browser to select cache folder."""
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select Thumbnail Cache Folder",
            self.cache_path_input.text()
        )
        if folder:
            self.cache_path_input.setText(folder)
            self._update_cache_stats()

    def _update_cache_stats(self):
        """Update the cache statistics label."""
        cache_path = Path(self.cache_path_input.text())
        if cache_path.exists():
            # Count files and calculate size
            files = list(cache_path.glob("*.png")) + list(cache_path.glob("*.jpg"))
            total_size = sum(f.stat().st_size for f in files if f.exists())

            # Format size
            if total_size < 1024:
                size_str = f"{total_size} B"
            elif total_size < 1024 * 1024:
                size_str = f"{total_size / 1024:.1f} KB"
            else:
                size_str = f"{total_size / (1024 * 1024):.1f} MB"

            self.cache_stats_label.setText(f"{len(files)} cached images ({size_str})")
        else:
            self.cache_stats_label.setText("Cache folder does not exist")

    def _clear_cache(self):
        """Clear all cached thumbnails."""
        cache_path = Path(self.cache_path_input.text())

        if not cache_path.exists():
            QtWidgets.QMessageBox.information(
                self,
                "Cache Empty",
                "The cache folder does not exist or is already empty."
            )
            return

        # Confirm deletion
        reply = QtWidgets.QMessageBox.question(
            self,
            "Clear Cache",
            "Are you sure you want to delete all cached thumbnails?\n\n"
            "Thumbnails will be re-downloaded from ShotGrid when needed.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            try:
                # Delete all image files in the cache
                files = list(cache_path.glob("*.png")) + list(cache_path.glob("*.jpg"))
                for f in files:
                    f.unlink()

                self._update_cache_stats()
                QtWidgets.QMessageBox.information(
                    self,
                    "Cache Cleared",
                    f"Deleted {len(files)} cached thumbnails."
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to clear cache:\n{str(e)}"
                )

    def _refresh_all_thumbnails(self):
        """Signal the parent app to refresh all thumbnails."""
        # Clear cache first
        cache_path = Path(self.cache_path_input.text())
        if cache_path.exists():
            files = list(cache_path.glob("*.png")) + list(cache_path.glob("*.jpg"))
            for f in files:
                try:
                    f.unlink()
                except:
                    pass

        self._update_cache_stats()

        # Notify user
        QtWidgets.QMessageBox.information(
            self,
            "Cache Cleared",
            "Cache has been cleared. Thumbnails will be re-downloaded when you next load images.\n\n"
            "Close this dialog and refresh images to download fresh thumbnails."
        )


class SettingsDialog(QtWidgets.QDialog):
    """Dialog for configuring application settings."""

    def __init__(self, app_settings, sg_client=None, project_id=None, parent=None):
        """Initialize the settings dialog.

        Args:
            app_settings: AppSettings instance
            sg_client: ShotGrid client instance (optional, required for Vendors tab)
            project_id: Current project ID (optional, required for Vendors tab)
            parent: Parent widget (should be the main app window)
        """
        super().__init__(parent)
        self.app_settings = app_settings
        self.sg_client = sg_client
        self.project_id = project_id
        self.parent_app = parent  # Store reference to main app
        self.setWindowTitle("Application Settings")
        self.setModal(True)
        self.setMinimumWidth(550)
        self.setMinimumHeight(500)

        # Store original DPI scale to restore on cancel
        self.original_dpi_scale = app_settings.get_dpi_scale()

        self._build_ui()

    def _build_ui(self):
        """Build the dialog UI."""
        layout = QtWidgets.QVBoxLayout(self)

        # Title
        title_label = QtWidgets.QLabel("Application Settings")
        title_font = title_label.font()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Separator
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        layout.addWidget(separator)

        # Tab widget
        self.tab_widget = QtWidgets.QTabWidget()

        # General tab
        self.general_tab = GeneralTab(self.app_settings, parent=self)
        self.general_tab.dpiChanged.connect(self._on_dpi_slider_changed)
        self.tab_widget.addTab(self.general_tab, "General")

        # Vendors tab
        self.vendors_tab = VendorsTab(self.sg_client, self.project_id, parent=self)
        self.tab_widget.addTab(self.vendors_tab, "Vendors")

        layout.addWidget(self.tab_widget)

        # Button box
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _on_dpi_slider_changed(self, value):
        """Handle DPI slider value change - apply preview to main app."""
        # Apply real-time preview to the parent app (not this dialog)
        if self.parent_app and hasattr(self.parent_app, '_apply_app_font_scaling'):
            scale_factor = value / 100.0
            self.parent_app._apply_app_font_scaling(scale_factor)

    def reject(self):
        """Handle Cancel - restore original DPI scale."""
        # Restore original scaling to parent app
        if self.parent_app and hasattr(self.parent_app, '_apply_app_font_scaling'):
            self.parent_app._apply_app_font_scaling(self.original_dpi_scale)

        super().reject()

    def get_dpi_scale(self):
        """Get the selected DPI scale factor.

        Returns:
            float: DPI scale factor
        """
        return self.general_tab.get_dpi_scale()

    def get_currency(self):
        """Get the selected currency symbol.

        Returns:
            str: Currency symbol
        """
        return self.general_tab.get_currency()

    def get_thumbnail_cache_path(self):
        """Get the thumbnail cache folder path.

        Returns:
            Path: Cache folder path
        """
        return self.general_tab.get_thumbnail_cache_path()

    def get_thumbnail_cache_max_age_days(self):
        """Get the cache max age in days.

        Returns:
            int: Max age in days
        """
        return self.general_tab.get_thumbnail_cache_max_age_days()
