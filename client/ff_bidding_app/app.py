from PySide6 import QtWidgets, QtCore, QtGui
import json
import logging
from datetime import datetime, date
from pathlib import Path
import sys
import random
import string

# Try relative imports first, fall back to absolute
try:
    from .shotgrid import ShotgridClient
    from .package_data_treeview import PackageTreeView, CustomCheckBox
    from .packages_tab import PackagesTab
    from .bidding_tab import BiddingTab
    from .delivery_tab import DeliveryTab
    from .bid_selector_widget import CollapsibleGroupBox
    from .settings import AppSettings
    from .settings_dialog import SettingsDialog
    from .logger import logger
    from .gdrive_service import get_gdrive_service, GOOGLE_API_AVAILABLE
except ImportError:
    # Standalone mode - add to path and import
    import os

    current_dir = Path(__file__).parent
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))

    from shotgrid import ShotgridClient
    from package_data_treeview import PackageTreeView, CustomCheckBox
    from packages_tab import PackagesTab
    from bidding_tab import BiddingTab
    from delivery_tab import DeliveryTab
    from bid_selector_widget import CollapsibleGroupBox
    from settings import AppSettings
    from settings_dialog import SettingsDialog
    from gdrive_service import get_gdrive_service, GOOGLE_API_AVAILABLE

    # Setup basic logger for standalone mode
    try:
        log_dir = Path(__file__).parent.parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"ff_package_manager_{timestamp}.log"

        logging.basicConfig(
            level=logging.WARNING,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        logger = logging.getLogger("FFPackageManager")
        logger.setLevel(logging.WARNING)
    except Exception as e:
        print(f"Could not setup file logging: {e}")
        logging.basicConfig(level=logging.WARNING)
        logger = logging.getLogger("FFPackageManager")
        logger.setLevel(logging.WARNING)


# SVG path data for icons (from Material Design Icons - https://pictogrammers.com)
COG_OUTLINE_SVG_PATH = "M12,8A4,4 0 0,1 16,12A4,4 0 0,1 12,16A4,4 0 0,1 8,12A4,4 0 0,1 12,8M12,10A2,2 0 0,0 10,12A2,2 0 0,0 12,14A2,2 0 0,0 14,12A2,2 0 0,0 12,10M10,22C9.75,22 9.54,21.82 9.5,21.58L9.13,18.93C8.5,18.68 7.96,18.34 7.44,17.94L4.95,18.95C4.73,19.03 4.46,18.95 4.34,18.73L2.34,15.27C2.21,15.05 2.27,14.78 2.46,14.63L4.57,12.97L4.5,12L4.57,11L2.46,9.37C2.27,9.22 2.21,8.95 2.34,8.73L4.34,5.27C4.46,5.05 4.73,4.96 4.95,5.05L7.44,6.05C7.96,5.66 8.5,5.32 9.13,5.07L9.5,2.42C9.54,2.18 9.75,2 10,2H14C14.25,2 14.46,2.18 14.5,2.42L14.87,5.07C15.5,5.32 16.04,5.66 16.56,6.05L19.05,5.05C19.27,4.96 19.54,5.05 19.66,5.27L21.66,8.73C21.79,8.95 21.73,9.22 21.54,9.37L19.43,11L19.5,12L19.43,13L21.54,14.63C21.73,14.78 21.79,15.05 21.66,15.27L19.66,18.73C19.54,18.95 19.27,19.04 19.05,18.95L16.56,17.95C16.04,18.34 15.5,18.68 14.87,18.93L14.5,21.58C14.46,21.82 14.25,22 14,22H10M11.25,4L10.88,6.61C9.68,6.86 8.62,7.5 7.85,8.39L5.44,7.35L4.69,8.65L6.8,10.2C6.4,11.37 6.4,12.64 6.8,13.8L4.68,15.36L5.43,16.66L7.86,15.62C8.63,16.5 9.68,17.14 10.87,17.38L11.24,20H12.76L13.13,17.39C14.32,17.14 15.37,16.5 16.14,15.62L18.57,16.66L19.32,15.36L17.2,13.81C17.6,12.64 17.6,11.37 17.2,10.2L19.31,8.65L18.56,7.35L16.15,8.39C15.38,7.5 14.32,6.86 13.12,6.62L12.75,4H11.25Z"

# Cloud download icon (from Material Design Icons - https://pictogrammers.com/library/mdi/icon/cloud-download/)
CLOUD_DOWNLOAD_SVG_PATH = "M17,13L12,18L7,13H10V9H14V13M19.35,10.03C18.67,6.59 15.64,4 12,4C9.11,4 6.6,5.64 5.35,8.03C2.34,8.36 0,10.9 0,14A6,6 0 0,0 6,20H19A5,5 0 0,0 24,15C24,12.36 21.95,10.22 19.35,10.03Z"

# File cog icon (from Material Design Icons - https://pictogrammers.com/library/mdi/icon/file-cog/)
FILE_COG_SVG_PATH = "M6 2C4.89 2 4 2.9 4 4V20C4 21.11 4.89 22 6 22H12.68A7 7 0 0 1 12 19A7 7 0 0 1 19 12A7 7 0 0 1 22 12.68V8L15 2H6M13 3.5L19.5 10H13V3.5M18 14C17.87 14 17.76 14.09 17.74 14.21L17.55 15.53C17.25 15.66 16.96 15.82 16.7 16L15.46 15.5C15.35 15.5 15.22 15.5 15.15 15.63L14.15 17.36C14.09 17.47 14.11 17.6 14.21 17.68L15.27 18.5C15.25 18.67 15.24 18.83 15.24 19C15.24 19.17 15.25 19.33 15.27 19.5L14.21 20.32C14.12 20.4 14.09 20.53 14.15 20.64L15.15 22.37C15.21 22.5 15.34 22.5 15.46 22.5L16.7 22C16.96 22.18 17.24 22.35 17.55 22.47L17.74 23.79C17.76 23.91 17.86 24 18 24H20C20.11 24 20.22 23.91 20.24 23.79L20.43 22.47C20.73 22.34 21 22.18 21.27 22L22.5 22.5C22.63 22.5 22.76 22.5 22.83 22.37L23.83 20.64C23.89 20.53 23.86 20.4 23.77 20.32L22.7 19.5C22.72 19.33 22.74 19.17 22.74 19C22.74 18.83 22.73 18.67 22.7 18.5L23.76 17.68C23.85 17.6 23.88 17.47 23.82 17.36L22.82 15.63C22.76 15.5 22.63 15.5 22.5 15.5L21.27 16C21 15.82 20.73 15.65 20.42 15.53L20.23 14.21C20.22 14.09 20.11 14 20 14H18M19 17.5C19.83 17.5 20.5 18.17 20.5 19C20.5 19.83 19.83 20.5 19 20.5C18.16 20.5 17.5 19.83 17.5 19C17.5 18.17 18.17 17.5 19 17.5Z"

# File chart outline icon (from Material Design Icons - https://pictogrammers.com/library/mdi/icon/file-chart-outline/)
FILE_CHART_OUTLINE_SVG_PATH = "M14 2H6C4.89 2 4 2.9 4 4V20C4 21.11 4.89 22 6 22H18C19.11 22 20 21.11 20 20V8L14 2M18 20H6V4H13V9H18V20M9 13V19H7V13H9M15 15V19H17V15H15M11 11V19H13V11H11Z"


def create_icon_from_svg_path(svg_path, size=24, color="#e0e0e0"):
    """Create a QIcon from an SVG path string.

    Args:
        svg_path: SVG path data string (the 'd' attribute of a path element)
        size: Icon size in pixels
        color: Icon fill color

    Returns:
        QIcon: The created icon
    """
    svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="{size}" height="{size}">
        <path fill="{color}" d="{svg_path}"/>
    </svg>'''

    # Create pixmap from SVG
    from PySide6.QtSvg import QSvgRenderer
    renderer = QSvgRenderer(svg_content.encode('utf-8'))
    pixmap = QtGui.QPixmap(size, size)
    pixmap.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    return QtGui.QIcon(pixmap)


class ProjectDetailsDialog(QtWidgets.QDialog):
    """Dialog showing project and RFQ details."""

    def __init__(self, project, rfq, parent=None):
        """Initialize the dialog.

        Args:
            project: Project data dict or None
            rfq: RFQ data dict or None
            parent: Parent widget
        """
        super().__init__(parent)
        self.project = project
        self.rfq = rfq

        self.setWindowTitle("Project Details")
        self.setModal(True)
        self.setMinimumWidth(400)

        self._build_ui()

    def _build_ui(self):
        """Build the dialog UI."""
        layout = QtWidgets.QVBoxLayout(self)

        # Create form layout for details
        form_layout = QtWidgets.QFormLayout()

        # Project details
        if self.project:
            project_id = QtWidgets.QLabel(str(self.project.get('id', '-')))
            form_layout.addRow("Project ID:", project_id)

            project_name = QtWidgets.QLabel(self.project.get('name', '-'))
            form_layout.addRow("Project Name:", project_name)

            project_status = QtWidgets.QLabel(self.project.get('sg_status', '-'))
            form_layout.addRow("Project Status:", project_status)
        else:
            no_project = QtWidgets.QLabel("No project selected")
            form_layout.addRow("", no_project)

        # Separator
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        form_layout.addRow(separator)

        # RFQ details
        if self.rfq:
            rfq_id = QtWidgets.QLabel(str(self.rfq.get('id', '-')))
            form_layout.addRow("RFQ ID:", rfq_id)

            rfq_code = QtWidgets.QLabel(self.rfq.get('code', '-'))
            form_layout.addRow("RFQ Code:", rfq_code)

            rfq_status = QtWidgets.QLabel(self.rfq.get('sg_status_list', '-'))
            form_layout.addRow("RFQ Status:", rfq_status)
        else:
            no_rfq = QtWidgets.QLabel("No RFQ selected")
            form_layout.addRow("", no_rfq)

        layout.addLayout(form_layout)

        # Close button
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()

        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setDefault(True)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)


class CreateRFQDialog(QtWidgets.QDialog):
    """Dialog for creating a new RFQ."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New RFQ")
        self.setModal(True)
        self.setMinimumWidth(400)

        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Name field
        name_layout = QtWidgets.QHBoxLayout()
        name_label = QtWidgets.QLabel("RFQ Name:")
        name_layout.addWidget(name_label)

        self.name_field = QtWidgets.QLineEdit()
        self.name_field.setPlaceholderText("Enter RFQ name...")
        name_layout.addWidget(self.name_field, stretch=1)

        layout.addLayout(name_layout)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()

        self.ok_button = QtWidgets.QPushButton("Create")
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setDefault(True)
        button_layout.addWidget(self.ok_button)

        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def get_rfq_name(self):
        """Get the entered RFQ name."""
        return self.name_field.text().strip()


class RenameRFQDialog(QtWidgets.QDialog):
    """Dialog for renaming an existing RFQ."""

    def __init__(self, existing_rfqs, parent=None):
        super().__init__(parent)
        self.existing_rfqs = existing_rfqs
        self.setWindowTitle("Rename RFQ")
        self.setModal(True)
        self.setMinimumWidth(400)

        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Select RFQ
        select_layout = QtWidgets.QHBoxLayout()
        select_label = QtWidgets.QLabel("Select RFQ:")
        select_layout.addWidget(select_label)

        self.rfq_combo = QtWidgets.QComboBox()
        self.rfq_combo.addItem("-- Select RFQ --", None)
        for rfq in self.existing_rfqs:
            label = rfq.get("code") or f"RFQ {rfq.get('id', 'N/A')}"
            self.rfq_combo.addItem(label, rfq)
        self.rfq_combo.currentIndexChanged.connect(self._on_rfq_selected)
        select_layout.addWidget(self.rfq_combo, stretch=1)

        layout.addLayout(select_layout)

        # New name field
        name_layout = QtWidgets.QHBoxLayout()
        name_label = QtWidgets.QLabel("New Name:")
        name_layout.addWidget(name_label)

        self.name_field = QtWidgets.QLineEdit()
        self.name_field.setPlaceholderText("Enter new RFQ name...")
        self.name_field.setEnabled(False)
        name_layout.addWidget(self.name_field, stretch=1)

        layout.addLayout(name_layout)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()

        self.ok_button = QtWidgets.QPushButton("Rename")
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setEnabled(False)
        self.ok_button.setDefault(True)
        button_layout.addWidget(self.ok_button)

        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def _on_rfq_selected(self, index):
        """Handle RFQ selection."""
        rfq = self.rfq_combo.currentData()
        if rfq:
            current_name = rfq.get("code", "")
            self.name_field.setText(current_name)
            self.name_field.selectAll()
            self.name_field.setEnabled(True)
            self.ok_button.setEnabled(True)
        else:
            self.name_field.clear()
            self.name_field.setEnabled(False)
            self.ok_button.setEnabled(False)

    def get_selected_rfq(self):
        """Get the selected RFQ."""
        return self.rfq_combo.currentData()

    def get_new_name(self):
        """Get the new RFQ name."""
        return self.name_field.text().strip()


class RemoveRFQDialog(QtWidgets.QDialog):
    """Dialog for removing an RFQ with confirmation."""

    def __init__(self, existing_rfqs, parent=None):
        super().__init__(parent)
        self.existing_rfqs = existing_rfqs
        self.setWindowTitle("Remove RFQ")
        self.setModal(True)
        self.setMinimumWidth(450)

        # Generate random confirmation string
        self.confirmation_string = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Warning message
        warning_label = QtWidgets.QLabel(
            "⚠️ WARNING: This action cannot be undone!\n"
            "Deleting an RFQ will remove it permanently from the project."
        )
        warning_label.setStyleSheet("color: #ff6666; font-weight: bold; padding: 10px;")
        warning_label.setWordWrap(True)
        layout.addWidget(warning_label)

        # Select RFQ to delete
        select_layout = QtWidgets.QHBoxLayout()
        select_label = QtWidgets.QLabel("Select RFQ:")
        select_layout.addWidget(select_label)

        self.rfq_combo = QtWidgets.QComboBox()
        self.rfq_combo.addItem("-- Select RFQ --", None)
        for rfq in self.existing_rfqs:
            label = rfq.get("code") or f"RFQ {rfq.get('id', 'N/A')}"
            self.rfq_combo.addItem(label, rfq)
        select_layout.addWidget(self.rfq_combo, stretch=1)

        layout.addLayout(select_layout)

        # Delete related elements checkbox
        layout.addSpacing(10)
        self.delete_related_checkbox = QtWidgets.QCheckBox(
            "Also delete all related elements (Bids, VFX Breakdowns, Bidding Scenes, Bid Assets)"
        )
        self.delete_related_checkbox.setChecked(False)
        self.delete_related_checkbox.setStyleSheet("padding: 10px;")
        layout.addWidget(self.delete_related_checkbox)

        # Confirmation section
        layout.addSpacing(20)

        confirm_label = QtWidgets.QLabel(
            f"To confirm deletion, type the following string:\n\n{self.confirmation_string}"
        )
        confirm_label.setStyleSheet("font-weight: bold; padding: 10px;")
        confirm_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(confirm_label)

        # Confirmation input
        confirm_layout = QtWidgets.QHBoxLayout()
        confirm_input_label = QtWidgets.QLabel("Confirmation:")
        confirm_layout.addWidget(confirm_input_label)

        self.confirmation_field = QtWidgets.QLineEdit()
        self.confirmation_field.setPlaceholderText("Type confirmation string here...")
        self.confirmation_field.textChanged.connect(self._on_confirmation_changed)
        confirm_layout.addWidget(self.confirmation_field, stretch=1)

        layout.addLayout(confirm_layout)

        # Buttons
        layout.addSpacing(20)
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()

        self.delete_button = QtWidgets.QPushButton("Delete")
        self.delete_button.setEnabled(False)
        self.delete_button.setStyleSheet("background-color: #ff6666; color: white; font-weight: bold;")
        self.delete_button.clicked.connect(self.accept)
        button_layout.addWidget(self.delete_button)

        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def _on_confirmation_changed(self, text):
        """Handle confirmation text change."""
        is_valid = (text == self.confirmation_string)
        self.delete_button.setEnabled(is_valid)

    def get_selected_rfq(self):
        """Get the selected RFQ to delete."""
        return self.rfq_combo.currentData()

    def should_delete_related(self):
        """Get whether related elements should also be deleted."""
        return self.delete_related_checkbox.isChecked()


class ManageRFQVendorsDialog(QtWidgets.QDialog):
    """Dialog for managing vendors assigned to an RFQ."""

    def __init__(self, rfq, all_vendors, sg_session, parent=None):
        """Initialize the dialog.

        Args:
            rfq: RFQ entity dict with sg_vendors field
            all_vendors: List of all available vendor entities
            sg_session: ShotGrid client instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.rfq = rfq
        self.all_vendors = all_vendors
        self.sg_session = sg_session
        self.assigned_vendors = []

        # Initialize assigned vendors from RFQ's sg_vendors
        sg_vendors = rfq.get("sg_vendors") or []
        for vendor in sg_vendors:
            if isinstance(vendor, dict) and vendor.get("id"):
                self.assigned_vendors.append({
                    "type": "CustomEntity05",
                    "id": vendor["id"],
                    "name": vendor.get("name", f"Vendor {vendor['id']}")
                })

        self.setWindowTitle(f"Manage Vendors for RFQ: {rfq.get('code', 'Unknown')}")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        self._build_ui()

    def _build_ui(self):
        """Build the dialog UI."""
        layout = QtWidgets.QVBoxLayout(self)

        # Description
        desc_label = QtWidgets.QLabel(
            "Select vendors to assign to this RFQ. Only assigned vendors will appear in the Delivery tab."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(desc_label)

        # Horizontal layout for available and assigned lists
        lists_layout = QtWidgets.QHBoxLayout()

        # Available vendors list
        available_layout = QtWidgets.QVBoxLayout()
        available_label = QtWidgets.QLabel("Available Vendors:")
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

        self.add_btn = QtWidgets.QPushButton(">")
        self.add_btn.setFixedWidth(40)
        self.add_btn.setToolTip("Add selected vendors to RFQ")
        self.add_btn.clicked.connect(self._add_vendors)
        buttons_layout.addWidget(self.add_btn)

        self.remove_btn = QtWidgets.QPushButton("<")
        self.remove_btn.setFixedWidth(40)
        self.remove_btn.setToolTip("Remove selected vendors from RFQ")
        self.remove_btn.clicked.connect(self._remove_vendors)
        buttons_layout.addWidget(self.remove_btn)

        buttons_layout.addStretch()
        lists_layout.addLayout(buttons_layout)

        # Assigned vendors list
        assigned_layout = QtWidgets.QVBoxLayout()
        assigned_label = QtWidgets.QLabel("Assigned to RFQ:")
        assigned_label.setStyleSheet("font-weight: bold;")
        assigned_layout.addWidget(assigned_label)

        self.assigned_list = QtWidgets.QListWidget()
        self.assigned_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self._populate_assigned_list()
        assigned_layout.addWidget(self.assigned_list)
        lists_layout.addLayout(assigned_layout)

        layout.addLayout(lists_layout)

        # Button box
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self._save_and_close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _populate_available_list(self):
        """Populate the available vendors list."""
        self.available_list.clear()
        assigned_ids = {v["id"] for v in self.assigned_vendors}

        for vendor in self.all_vendors:
            if vendor.get("id") not in assigned_ids:
                item = QtWidgets.QListWidgetItem(vendor.get("code", f"Vendor {vendor.get('id')}"))
                item.setData(QtCore.Qt.UserRole, vendor)
                self.available_list.addItem(item)

    def _populate_assigned_list(self):
        """Populate the assigned vendors list."""
        self.assigned_list.clear()

        for vendor in self.assigned_vendors:
            # Find full vendor info
            full_vendor = next(
                (v for v in self.all_vendors if v.get("id") == vendor["id"]),
                vendor
            )
            item = QtWidgets.QListWidgetItem(full_vendor.get("code", vendor.get("name", "Unknown")))
            item.setData(QtCore.Qt.UserRole, vendor)
            self.assigned_list.addItem(item)

    def _add_vendors(self):
        """Add selected vendors to assigned list."""
        for item in self.available_list.selectedItems():
            vendor = item.data(QtCore.Qt.UserRole)
            if vendor and vendor.get("id") not in {v["id"] for v in self.assigned_vendors}:
                self.assigned_vendors.append({
                    "type": "CustomEntity05",
                    "id": vendor["id"],
                    "name": vendor.get("code", f"Vendor {vendor['id']}")
                })

        self._populate_available_list()
        self._populate_assigned_list()

    def _remove_vendors(self):
        """Remove selected vendors from assigned list."""
        ids_to_remove = set()
        for item in self.assigned_list.selectedItems():
            vendor = item.data(QtCore.Qt.UserRole)
            if vendor:
                ids_to_remove.add(vendor["id"])

        self.assigned_vendors = [v for v in self.assigned_vendors if v["id"] not in ids_to_remove]

        self._populate_available_list()
        self._populate_assigned_list()

    def _save_and_close(self):
        """Save the vendor assignments to ShotGrid and close."""
        try:
            # Format vendors as entity references
            sg_vendors = [{"type": "CustomEntity05", "id": v["id"]} for v in self.assigned_vendors]

            # Update RFQ with new vendor assignments
            self.sg_session.update_rfq(self.rfq["id"], {"sg_vendors": sg_vendors})

            QtWidgets.QMessageBox.information(
                self,
                "Success",
                f"Vendors updated for RFQ '{self.rfq.get('code', 'Unknown')}'."
            )
            self.accept()
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to update vendors:\n{str(e)}"
            )


class ConfigRFQsDialog(QtWidgets.QDialog):
    """Main dialog for configuring RFQs with create/rename/remove options."""

    def __init__(self, existing_rfqs, parent=None):
        super().__init__(parent)
        self.existing_rfqs = existing_rfqs
        self.setWindowTitle("Configure RFQs")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.result_action = None

        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Title
        title_label = QtWidgets.QLabel("RFQ Configuration")
        title_font = title_label.font()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(title_label)

        layout.addSpacing(20)

        # Instruction
        instruction_label = QtWidgets.QLabel("Choose an action:")
        layout.addWidget(instruction_label)

        layout.addSpacing(10)

        # Action buttons
        create_btn = QtWidgets.QPushButton("Create New RFQ")
        create_btn.clicked.connect(self._on_create_clicked)
        layout.addWidget(create_btn)

        rename_btn = QtWidgets.QPushButton("Rename Existing RFQ")
        rename_btn.clicked.connect(self._on_rename_clicked)
        rename_btn.setEnabled(len(self.existing_rfqs) > 0)
        layout.addWidget(rename_btn)

        remove_btn = QtWidgets.QPushButton("Remove RFQ")
        remove_btn.clicked.connect(self._on_remove_clicked)
        remove_btn.setEnabled(len(self.existing_rfqs) > 0)
        layout.addWidget(remove_btn)

        manage_vendors_btn = QtWidgets.QPushButton("Manage RFQ Vendors")
        manage_vendors_btn.clicked.connect(self._on_manage_vendors_clicked)
        manage_vendors_btn.setEnabled(len(self.existing_rfqs) > 0)
        layout.addWidget(manage_vendors_btn)

        layout.addSpacing(20)

        # Close button
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()

        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _on_create_clicked(self):
        """Handle create button click."""
        self.result_action = "create"
        self.accept()

    def _on_rename_clicked(self):
        """Handle rename button click."""
        self.result_action = "rename"
        self.accept()

    def _on_remove_clicked(self):
        """Handle remove button click."""
        self.result_action = "remove"
        self.accept()

    def _on_manage_vendors_clicked(self):
        """Handle manage vendors button click."""
        self.result_action = "manage_vendors"
        self.accept()

    def get_action(self):
        """Get the selected action."""
        return self.result_action


class PackageManagerApp(QtWidgets.QMainWindow):
    """Main application window."""

    def __init__(self, sg_url, sg_script_name, sg_api_key, output_directory, parent=None):
        try:
            super().__init__(parent)

            self.sg_url = sg_url
            self.sg_script_name = sg_script_name
            self.sg_api_key = sg_api_key

            self.sg_session = ShotgridClient(
                site_url=self.sg_url,
                script_name=self.sg_script_name,
                api_key=self.sg_api_key
            )
            self.output_directory = output_directory or str(Path.home() / "shotgrid_packages")

            # Initialize app settings
            self.app_settings = AppSettings()

            # Track the current DPI scale to detect changes
            # This is also used by delegates during preview to get the live scale
            self._current_dpi_scale = self.app_settings.get_dpi_scale()

            # Make the current DPI scale accessible globally for delegates
            # Store it as a class variable so delegates can access it
            PackageManagerApp._active_dpi_scale = self._current_dpi_scale

            self.setWindowTitle("Fireframe Prodigy")
            self.setMinimumSize(1400, 700)

            self._build_ui()

            # Apply saved DPI scaling to the UI
            saved_dpi_scale = self.app_settings.get_dpi_scale()
            if saved_dpi_scale != 1.0:
                self._apply_app_font_scaling(saved_dpi_scale)

            # Auto-load the latest project on startup
            self._auto_load_latest_project()

            et = self.sg_session.get_vfx_breakdown_entity_type()


        except Exception as e:
            logger.error("=" * 60)
            logger.error(f"CRITICAL ERROR in __init__: {e}", exc_info=True)
            logger.error("=" * 60)
            raise

    @staticmethod
    def apply_dpi_scaling():
        """Apply DPI scaling from settings if configured.

        Note: This must be called before QApplication is created for full effect.
        If QApplication already exists, it will apply what it can.
        """
        try:
            settings = AppSettings()
            dpi_scale = settings.get_dpi_scale()

            if dpi_scale != 1.0:

                # Try to set Qt attributes (only works if QApplication not yet created)
                try:
                    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
                    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
                except RuntimeError:
                    pass

                # Set environment variable (works if set before Qt init)
                import os
                os.environ["QT_SCALE_FACTOR"] = str(dpi_scale)

            else:
                pass

            return dpi_scale
        except Exception as e:
            logger.error(f"Failed to apply DPI scaling: {e}")
            return 1.0

    @staticmethod
    def apply_dark_theme(app):
        """Apply dark theme stylesheet to the application.

        Args:
            app: QApplication instance
        """
        dark_stylesheet = """
        /* Main Window and Widgets */
        QMainWindow, QWidget {
            background-color: #2b2b2b;
            color: #e0e0e0;
            font-family: system-ui, -apple-system, Arial, sans-serif;
        }

        /* Group Box */
        QGroupBox {
            background-color: #353535;
            border: 1px solid #555555;
            border-radius: 6px;
            margin-top: 12px;
            padding-top: 10px;
            font-weight: bold;
            color: #e0e0e0;
        }

        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 10px;
            padding: 0 5px;
            color: #4a9eff;
        }

        /* Labels */
        QLabel {
            color: #e0e0e0;
            background-color: transparent;
        }

        /* Combo Box */
        QComboBox {
            background-color: #404040;
            border: 1px solid #555555;
            border-radius: 4px;
            padding: 5px 10px;
            color: #e0e0e0;
            min-height: 25px;
        }

        QComboBox:hover {
            border: 1px solid #4a9eff;
            background-color: #4a4a4a;
        }

        QComboBox:focus {
            border: 1px solid #4a9eff;
        }

        QComboBox::drop-down {
            border: none;
            width: 20px;
        }

        QComboBox::down-arrow {
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 5px solid #e0e0e0;
            margin-right: 5px;
        }

        QComboBox QAbstractItemView {
            background-color: #404040;
            border: 1px solid #555555;
            selection-background-color: #4a9eff;
            selection-color: #ffffff;
            color: #e0e0e0;
        }

        /* Line Edit */
        QLineEdit {
            background-color: #404040;
            border: 1px solid #555555;
            border-radius: 4px;
            padding: 5px 10px;
            color: #e0e0e0;
            min-height: 25px;
        }

        QLineEdit:hover {
            border: 1px solid #4a9eff;
        }

        QLineEdit:focus {
            border: 1px solid #4a9eff;
            background-color: #4a4a4a;
        }

        /* Push Button */
        QPushButton {
            background-color: #404040;
            border: 1px solid #555555;
            border-radius: 4px;
            padding: 6px 16px;
            color: #e0e0e0;
            font-weight: bold;
            min-height: 25px;
        }

        QPushButton:hover {
            background-color: #4a4a4a;
            border: 1px solid #4a9eff;
        }

        QPushButton:pressed {
            background-color: #353535;
        }

        QPushButton:disabled {
            background-color: #2b2b2b;
            color: #666666;
            border: 1px solid #444444;
        }

        /* Create Package Button - Override with green theme */
        QPushButton#createPackageBtn {
            background-color: #2d7a3e;
            border: 1px solid #3a9a50;
            color: white;
        }

        QPushButton#createPackageBtn:hover {
            background-color: #3a9a50;
            border: 1px solid #4db863;
        }

        QPushButton#createPackageBtn:pressed {
            background-color: #246832;
        }

        /* Check Box */
        QCheckBox {
            color: #e0e0e0;
            spacing: 8px;
        }

        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            border: 1px solid #555555;
            border-radius: 3px;
            background-color: #404040;
        }

        QCheckBox::indicator:hover {
            border: 1px solid #4a9eff;
        }

        QCheckBox::indicator:checked {
            background-color: #4a9eff;
            border: 1px solid #4a9eff;
        }

        QCheckBox::indicator:checked:hover {
            background-color: #5eb3ff;
        }

        /* Tab Widget */
        QTabWidget::pane {
            border: 1px solid #555555;
            background-color: #2b2b2b;
            border-radius: 4px;
        }

        QTabBar::tab {
            background-color: #353535;
            color: #e0e0e0;
            border: 1px solid #555555;
            border-bottom: none;
            padding: 8px 20px;
            margin-right: 2px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }

        QTabBar::tab:hover {
            background-color: #404040;
        }

        QTabBar::tab:selected {
            background-color: #4a9eff;
            color: #ffffff;
            font-weight: bold;
        }

        /* Tree Widget */
        QTreeWidget {
            background-color: #353535;
            border: 1px solid #555555;
            border-radius: 4px;
            color: #e0e0e0;
            selection-background-color: #4a9eff;
            selection-color: #ffffff;
            alternate-background-color: #3a3a3a;
        }

        QTreeWidget::item {
            padding: 4px;
            border: none;
        }

        QTreeWidget::item:hover {
            background-color: #404040;
        }

        QTreeWidget::item:selected {
            background-color: #4a9eff;
            color: #ffffff;
        }

        QHeaderView::section {
            background-color: #404040;
            color: #e0e0e0;
            padding: 6px;
            border: 1px solid #555555;
            font-weight: bold;
        }

        QHeaderView::section:hover {
            background-color: #4a4a4a;
        }

        /* Scroll Bar */
        QScrollBar:vertical {
            background-color: #2b2b2b;
            width: 14px;
            border: none;
        }

        QScrollBar::handle:vertical {
            background-color: #555555;
            border-radius: 7px;
            min-height: 30px;
        }

        QScrollBar::handle:vertical:hover {
            background-color: #666666;
        }

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }

        QScrollBar:horizontal {
            background-color: #2b2b2b;
            height: 14px;
            border: none;
        }

        QScrollBar::handle:horizontal {
            background-color: #555555;
            border-radius: 7px;
            min-width: 30px;
        }

        QScrollBar::handle:horizontal:hover {
            background-color: #666666;
        }

        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            width: 0px;
        }

        /* Splitter */
        QSplitter::handle {
            background-color: #555555;
        }

        QSplitter::handle:hover {
            background-color: #666666;
        }

        QSplitter::handle:horizontal {
            width: 2px;
        }

        QSplitter::handle:vertical {
            height: 2px;
        }

        /* Progress Dialog */
        QProgressDialog {
            background-color: #2b2b2b;
            color: #e0e0e0;
        }

        QProgressBar {
            background-color: #353535;
            border: 1px solid #555555;
            border-radius: 4px;
            text-align: center;
            color: #e0e0e0;
        }

        QProgressBar::chunk {
            background-color: #4a9eff;
            border-radius: 3px;
        }

        /* Message Box */
        QMessageBox {
            background-color: #2b2b2b;
            color: #e0e0e0;
        }

        QMessageBox QLabel {
            color: #e0e0e0;
        }

        QMessageBox QPushButton {
            min-width: 80px;
        }

        /* Menu and Context Menu */
        QMenu {
            background-color: #353535;
            border: 1px solid #555555;
            color: #e0e0e0;
        }

        QMenu::item {
            padding: 6px 25px;
        }

        QMenu::item:selected {
            background-color: #4a9eff;
            color: #ffffff;
        }

        QMenu::separator {
            height: 1px;
            background-color: #555555;
            margin: 4px 0px;
        }

        /* Tool Tip */
        QToolTip {
            background-color: #404040;
            color: #e0e0e0;
            border: 1px solid #555555;
            padding: 4px;
        }
        """

        app.setStyleSheet(dark_stylesheet)

    def _build_ui(self):
        try:
            central_widget = QtWidgets.QWidget()
            self.setCentralWidget(central_widget)
            main_layout = QtWidgets.QVBoxLayout(central_widget)

            # Top bar with Project, RFQ dropdowns, Current Bid, and Settings
            top_bar = self._create_top_bar()
            main_layout.addWidget(top_bar)

            # Stacked widget for view switching
            self.view_stack = QtWidgets.QStackedWidget()

            # Create Bidding view (contains VFX Breakdown, Assets, Rates, and Reports as nested tabs)
            bidding_view = self._create_bidding_tab()
            self.view_stack.addWidget(bidding_view)

            # Create Packages view
            packages_view = self._create_packages_tab()
            self.view_stack.addWidget(packages_view)

            # Create Delivery view
            delivery_view = self._create_delivery_tab()
            self.view_stack.addWidget(delivery_view)

            main_layout.addWidget(self.view_stack)

            # Restore last selected view
            last_view = self.app_settings.get("app/lastSelectedView", 0)
            if 0 <= last_view < self.view_selector.count():
                self.view_selector.setCurrentIndex(last_view)

        except Exception as e:
            logger.error(f"Error in _build_ui: {e}", exc_info=True)
            raise

    def _create_top_bar(self):
        """Create compact top bar with View selector, Project, RFQ dropdowns and Current Bid."""
        bar_widget = QtWidgets.QWidget()
        bar_layout = QtWidgets.QHBoxLayout(bar_widget)
        bar_layout.setContentsMargins(6, 6, 6, 6)

        # View selector (leftmost) - styled like tabs
        self.view_selector = QtWidgets.QComboBox()
        self.view_selector.setMinimumWidth(150)
        self.view_selector.setStyleSheet("""
            QComboBox {
                background-color: #4a9eff;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
                border: none;
            }
            QComboBox:hover {
                background-color: #5eb3ff;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid white;
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: #3a3a3a;
                color: white;
                selection-background-color: #4a9eff;
                selection-color: white;
                border: 1px solid #555555;
            }
        """)
        self.view_selector.addItem("Bidding", 0)
        self.view_selector.addItem("Packages", 1)
        self.view_selector.addItem("Delivery", 2)
        self.view_selector.currentIndexChanged.connect(self._on_view_changed)
        bar_layout.addWidget(self.view_selector)

        # Spacer
        bar_layout.addSpacing(20)

        # Project section
        self.sg_project_combo = QtWidgets.QComboBox()
        self.sg_project_combo.setToolTip("Project")
        self.sg_project_combo.setMinimumWidth(200)
        self.sg_project_combo.currentIndexChanged.connect(self._on_sg_project_changed)
        bar_layout.addWidget(self.sg_project_combo)

        load_sg_btn = QtWidgets.QPushButton()
        load_sg_btn.setToolTip("Load from ShotGrid")
        load_sg_btn.setIcon(create_icon_from_svg_path(CLOUD_DOWNLOAD_SVG_PATH, size=20, color="#e0e0e0"))
        load_sg_btn.setIconSize(QtCore.QSize(20, 20))
        load_sg_btn.setFixedSize(32, 32)
        load_sg_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #555555;
                border-radius: 4px;
                background-color: #2b2b2b;
            }
            QPushButton:hover {
                background-color: #3b3b3b;
                border-color: #0078d4;
            }
            QPushButton:pressed {
                background-color: #1b1b1b;
            }
        """)
        load_sg_btn.clicked.connect(self._load_sg_projects)
        bar_layout.addWidget(load_sg_btn)

        # Project Details button
        details_btn = QtWidgets.QPushButton()
        details_btn.setToolTip("Project Details")
        details_btn.setIcon(create_icon_from_svg_path(FILE_CHART_OUTLINE_SVG_PATH, size=20, color="#e0e0e0"))
        details_btn.setIconSize(QtCore.QSize(20, 20))
        details_btn.setFixedSize(32, 32)
        details_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #555555;
                border-radius: 4px;
                background-color: #2b2b2b;
            }
            QPushButton:hover {
                background-color: #3b3b3b;
                border-color: #0078d4;
            }
            QPushButton:pressed {
                background-color: #1b1b1b;
            }
        """)
        details_btn.clicked.connect(self._show_project_details)
        bar_layout.addWidget(details_btn)

        # Spacer
        bar_layout.addSpacing(20)

        # RFQ section
        self.rfq_combo = QtWidgets.QComboBox()
        self.rfq_combo.setToolTip("RFQ")
        self.rfq_combo.setMinimumWidth(200)
        self.rfq_combo.currentIndexChanged.connect(self._on_rfq_changed)
        bar_layout.addWidget(self.rfq_combo)

        # Config RFQs button
        config_rfqs_btn = QtWidgets.QPushButton()
        config_rfqs_btn.setToolTip("Config RFQs")
        config_rfqs_btn.setIcon(create_icon_from_svg_path(FILE_COG_SVG_PATH, size=20, color="#e0e0e0"))
        config_rfqs_btn.setIconSize(QtCore.QSize(20, 20))
        config_rfqs_btn.setFixedSize(32, 32)
        config_rfqs_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #555555;
                border-radius: 4px;
                background-color: #2b2b2b;
            }
            QPushButton:hover {
                background-color: #3b3b3b;
                border-color: #0078d4;
            }
            QPushButton:pressed {
                background-color: #1b1b1b;
            }
        """)
        config_rfqs_btn.clicked.connect(self._show_config_rfqs_dialog)
        bar_layout.addWidget(config_rfqs_btn)

        # Spacer
        bar_layout.addSpacing(20)

        # Current Bid section
        current_bid_label = QtWidgets.QLabel("Current Bid:")
        bar_layout.addWidget(current_bid_label)

        self.rfq_bid_label = QtWidgets.QLabel("-")
        self.rfq_bid_label.setStyleSheet("font-weight: bold; border: none;")
        bar_layout.addWidget(self.rfq_bid_label)

        bar_layout.addStretch()

        # Package Manager button (only visible when Packages view is selected)
        self.package_manager_btn = QtWidgets.QPushButton("Package Manager")
        self.package_manager_btn.setToolTip("Show/Hide Package Manager Panel")
        self.package_manager_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a9eff;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #5eb3ff;
            }
            QPushButton:pressed {
                background-color: #3a8eef;
            }
        """)
        self.package_manager_btn.clicked.connect(self._toggle_package_manager_panel)
        self.package_manager_btn.setVisible(False)  # Hidden by default
        bar_layout.addWidget(self.package_manager_btn)

        # Google Drive connection status (shown only in Delivery view)
        self.gdrive_status_label = QtWidgets.QLabel("Checking Google Drive...")
        self.gdrive_status_label.setStyleSheet("color: #888;")
        self.gdrive_status_label.setVisible(False)
        bar_layout.addWidget(self.gdrive_status_label)

        self.gdrive_action_btn = QtWidgets.QPushButton("Configure")
        self.gdrive_action_btn.setMaximumWidth(120)
        self.gdrive_action_btn.setToolTip("Configure or retry Google Drive connection")
        self.gdrive_action_btn.clicked.connect(self._on_gdrive_action_clicked)
        self.gdrive_action_btn.setVisible(False)
        bar_layout.addWidget(self.gdrive_action_btn)

        # Settings button (cog icon)
        self.settings_button = QtWidgets.QPushButton()
        self.settings_button.setToolTip("Application Settings")
        self.settings_button.setIcon(create_icon_from_svg_path(COG_OUTLINE_SVG_PATH, size=20, color="#e0e0e0"))
        self.settings_button.setIconSize(QtCore.QSize(20, 20))
        self.settings_button.setFixedSize(32, 32)
        self.settings_button.setStyleSheet("""
            QPushButton {
                border: 1px solid #555555;
                border-radius: 4px;
                background-color: #2b2b2b;
            }
            QPushButton:hover {
                background-color: #3b3b3b;
                border-color: #0078d4;
            }
            QPushButton:pressed {
                background-color: #1b1b1b;
            }
        """)
        self.settings_button.clicked.connect(self._show_settings_dialog)
        bar_layout.addWidget(self.settings_button)

        return bar_widget

    def _show_project_details(self):
        """Show the project details dialog."""
        # Get current project and RFQ data
        project = self.sg_project_combo.itemData(self.sg_project_combo.currentIndex())
        rfq = self.rfq_combo.itemData(self.rfq_combo.currentIndex())

        dialog = ProjectDetailsDialog(project, rfq, parent=self)
        dialog.exec()

    def _on_view_changed(self, index):
        """Handle view selection change."""
        view_index = self.view_selector.currentData()
        if view_index is not None:
            self.view_stack.setCurrentIndex(view_index)
            # Save the selected view
            self.app_settings.set("app/lastSelectedView", index)
            # Show/hide Package Manager button based on selected view
            # view_index 1 = Packages view
            self.package_manager_btn.setVisible(view_index == 1)
            # Show/hide Google Drive status based on selected view
            # view_index 2 = Delivery view
            is_delivery = view_index == 2
            self.gdrive_status_label.setVisible(is_delivery)
            self.gdrive_action_btn.setVisible(is_delivery)
            if is_delivery:
                self._check_gdrive_connection()

    def _toggle_package_manager_panel(self):
        """Toggle the Package Manager panel in the Packages tab."""
        if hasattr(self, 'packages_tab') and hasattr(self.packages_tab, '_toggle_package_manager_panel'):
            self.packages_tab._toggle_package_manager_panel()

    def _check_gdrive_connection(self):
        """Check Google Drive connection status and update the top bar UI."""
        gdrive = get_gdrive_service()

        if not GOOGLE_API_AVAILABLE:
            self.gdrive_status_label.setText("Google Drive: Libraries not installed")
            self.gdrive_status_label.setStyleSheet("color: #cc6666;")  # Red
            self.gdrive_action_btn.setText("View Instructions")
        elif not gdrive.has_credentials:
            self.gdrive_status_label.setText("Google Drive: Not configured")
            self.gdrive_status_label.setStyleSheet("color: #cc6666;")  # Red
            self.gdrive_action_btn.setText("Configure")
        elif not gdrive.is_authenticated:
            self.gdrive_status_label.setText("Google Drive: Not authenticated")
            self.gdrive_status_label.setStyleSheet("color: #cc6666;")  # Red
            self.gdrive_action_btn.setText("Authenticate")
        else:
            self.gdrive_status_label.setText("Google Drive: Connected")
            self.gdrive_status_label.setStyleSheet("color: #66cc66;")  # Green
            self.gdrive_action_btn.setText("Refresh Connection")

    def _on_gdrive_action_clicked(self):
        """Handle Google Drive action button click."""
        gdrive = get_gdrive_service()

        if not GOOGLE_API_AVAILABLE:
            QtWidgets.QMessageBox.information(
                self,
                "Google Drive Setup Required",
                "Google Drive libraries are not installed.\n\n"
                "To enable Google Drive integration, run the following command:\n\n"
                "pip install google-auth google-auth-oauthlib google-api-python-client"
            )
            return

        if not gdrive.has_credentials:
            credentials_path = gdrive.credentials_file
            QtWidgets.QMessageBox.information(
                self,
                "Google Drive Configuration Required",
                f"Google Drive credentials file not found.\n\n"
                f"To configure Google Drive:\n\n"
                f"1. Go to Google Cloud Console\n"
                f"2. Create OAuth 2.0 credentials\n"
                f"3. Download the credentials.json file\n"
                f"4. Place it in:\n   {credentials_path.parent}\n\n"
                f"After adding the file, click 'Retry Connection' to check again."
            )
            self.gdrive_action_btn.setText("Retry Connection")
            return

        # Try to authenticate
        self.gdrive_status_label.setText("Authenticating...")
        self.gdrive_status_label.setStyleSheet("color: #cccc66;")  # Yellow
        self.gdrive_action_btn.setEnabled(False)
        QtWidgets.QApplication.processEvents()

        try:
            success = gdrive.authenticate()
            if success:
                self.gdrive_status_label.setText("Google Drive: Connected")
                self.gdrive_status_label.setStyleSheet("color: #66cc66;")  # Green
                self.gdrive_action_btn.setText("Refresh Connection")
                # Refresh package tracking statuses in the delivery tab
                self._refresh_package_tracking_statuses()
            else:
                self.gdrive_status_label.setText("Google Drive: Authentication failed")
                self.gdrive_status_label.setStyleSheet("color: #cc6666;")  # Red
                self.gdrive_action_btn.setText("Retry")
        except Exception as e:
            logger.error(f"Google Drive authentication error: {e}")
            self.gdrive_status_label.setText("Google Drive: Error")
            self.gdrive_status_label.setStyleSheet("color: #cc6666;")  # Red
            self.gdrive_action_btn.setText("Retry")
        finally:
            self.gdrive_action_btn.setEnabled(True)

    def _show_config_rfqs_dialog(self):
        """Show the RFQ configuration dialog."""
        # Get current project
        project = self.sg_project_combo.itemData(self.sg_project_combo.currentIndex())
        if not project:
            QtWidgets.QMessageBox.warning(
                self,
                "No Project Selected",
                "Please select a project first."
            )
            return

        # Get existing RFQs for this project
        try:
            existing_rfqs = self.sg_session.get_rfqs(project['id'])
        except Exception as e:
            logger.error(f"Error loading RFQs: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to load RFQs: {str(e)}"
            )
            return

        # Show main config dialog
        config_dialog = ConfigRFQsDialog(existing_rfqs, parent=self)
        if config_dialog.exec() != QtWidgets.QDialog.Accepted:
            return

        action = config_dialog.get_action()

        if action == "create":
            self._handle_create_rfq(project['id'])
        elif action == "rename":
            self._handle_rename_rfq(existing_rfqs)
        elif action == "remove":
            self._handle_remove_rfq(existing_rfqs)
        elif action == "manage_vendors":
            self._handle_manage_rfq_vendors(project['id'], existing_rfqs)

    def _handle_create_rfq(self, project_id):
        """Handle creating a new RFQ."""
        dialog = CreateRFQDialog(parent=self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return

        rfq_name = dialog.get_rfq_name()
        if not rfq_name:
            QtWidgets.QMessageBox.warning(
                self,
                "Invalid Name",
                "Please enter a valid RFQ name."
            )
            return

        try:
            # Create the RFQ in ShotGrid
            new_rfq = self.sg_session.create_rfq(project_id, rfq_name)

            # Reload RFQs
            self._load_rfqs(project_id)

            # Select the newly created RFQ
            for index in range(self.rfq_combo.count()):
                rfq_data = self.rfq_combo.itemData(index)
                if rfq_data and rfq_data.get('id') == new_rfq['id']:
                    self.rfq_combo.setCurrentIndex(index)
                    break

            QtWidgets.QMessageBox.information(
                self,
                "Success",
                f"RFQ '{rfq_name}' created successfully."
            )

        except Exception as e:
            logger.error(f"Error creating RFQ: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to create RFQ: {str(e)}"
            )

    def _handle_rename_rfq(self, existing_rfqs):
        """Handle renaming an existing RFQ."""
        dialog = RenameRFQDialog(existing_rfqs, parent=self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return

        rfq = dialog.get_selected_rfq()
        new_name = dialog.get_new_name()

        if not rfq or not new_name:
            QtWidgets.QMessageBox.warning(
                self,
                "Invalid Selection",
                "Please select an RFQ and enter a valid name."
            )
            return

        try:
            # Update the RFQ in ShotGrid
            self.sg_session.update_rfq(rfq['id'], {"code": new_name})

            # Reload RFQs
            project = self.sg_project_combo.itemData(self.sg_project_combo.currentIndex())
            if project:
                self._load_rfqs(project['id'])

            QtWidgets.QMessageBox.information(
                self,
                "Success",
                f"RFQ renamed to '{new_name}' successfully."
            )

        except Exception as e:
            logger.error(f"Error renaming RFQ: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to rename RFQ: {str(e)}"
            )

    def _handle_remove_rfq(self, existing_rfqs):
        """Handle removing an RFQ."""
        dialog = RemoveRFQDialog(existing_rfqs, parent=self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return

        rfq = dialog.get_selected_rfq()
        delete_related = dialog.should_delete_related()

        if not rfq:
            QtWidgets.QMessageBox.warning(
                self,
                "Invalid Selection",
                "Please select an RFQ to remove."
            )
            return

        try:
            if delete_related:
                # Delete the RFQ and all related elements
                deleted_summary = self.sg_session.delete_rfq_and_related(rfq['id'])

                # Build success message with summary
                summary_parts = []
                if deleted_summary.get("rfq"):
                    summary_parts.append(f"RFQ: {deleted_summary['rfq']}")
                if deleted_summary.get("bids"):
                    summary_parts.append(f"Bids: {deleted_summary['bids']}")
                if deleted_summary.get("vfx_breakdowns"):
                    summary_parts.append(f"VFX Breakdowns: {deleted_summary['vfx_breakdowns']}")
                if deleted_summary.get("bidding_scenes"):
                    summary_parts.append(f"Bidding Scenes: {deleted_summary['bidding_scenes']}")
                if deleted_summary.get("bid_assets"):
                    summary_parts.append(f"Bid Assets: {deleted_summary['bid_assets']}")

                summary_text = "\n".join(summary_parts) if summary_parts else "No items deleted"

                # Reload RFQs
                project = self.sg_project_combo.itemData(self.sg_project_combo.currentIndex())
                if project:
                    self._load_rfqs(project['id'])

                QtWidgets.QMessageBox.information(
                    self,
                    "Success",
                    f"RFQ '{rfq.get('code', 'N/A')}' and related elements removed successfully.\n\nDeleted items:\n{summary_text}"
                )
            else:
                # Delete only the RFQ
                self.sg_session.delete_rfq(rfq['id'])

                # Reload RFQs
                project = self.sg_project_combo.itemData(self.sg_project_combo.currentIndex())
                if project:
                    self._load_rfqs(project['id'])

                QtWidgets.QMessageBox.information(
                    self,
                    "Success",
                    f"RFQ '{rfq.get('code', 'N/A')}' removed successfully."
                )

        except Exception as e:
            logger.error(f"Error removing RFQ: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to remove RFQ: {str(e)}"
            )

    def _handle_manage_rfq_vendors(self, project_id, existing_rfqs):
        """Handle managing vendors for an RFQ."""
        # Use the currently selected RFQ from the combo box
        rfq = self.rfq_combo.itemData(self.rfq_combo.currentIndex())

        if not rfq:
            QtWidgets.QMessageBox.warning(
                self,
                "No RFQ Selected",
                "Please select an RFQ first."
            )
            return

        try:
            # Get all vendors for the project
            all_vendors = self.sg_session.get_vendors(project_id)

            # Show the manage vendors dialog
            dialog = ManageRFQVendorsDialog(rfq, all_vendors, self.sg_session, parent=self)
            if dialog.exec() == QtWidgets.QDialog.Accepted:
                # Reload RFQs to get updated vendor assignments
                self._load_rfqs(project_id)

                # Refresh delivery tab if present
                if hasattr(self, 'delivery_tab'):
                    self.delivery_tab.refresh_vendors()

        except Exception as e:
            logger.error(f"Error managing RFQ vendors: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self,
                "Error",
                f"Failed to manage vendors: {str(e)}"
            )

    def _create_packages_tab(self):
        """Create the Packages tab content."""
        self.packages_tab = PackagesTab(self.sg_session, self.output_directory, parent=self)
        # Keep a reference to status_label for backward compatibility
        self.status_label = self.packages_tab.status_label
        return self.packages_tab

    def _create_delivery_tab(self):
        """Create the Delivery tab content."""
        self.delivery_tab = DeliveryTab(self.sg_session, self.output_directory, parent=self)
        return self.delivery_tab

    def _refresh_package_tracking_statuses(self):
        """Refresh package tracking statuses by checking Google Drive access.

        This reloads package tracking records and checks each one for
        Google Drive access, updating the status to 'Accessed' if detected.
        """
        print("=== _refresh_package_tracking_statuses called ===")
        logger.info("=== _refresh_package_tracking_statuses called ===")

        if not hasattr(self, 'delivery_tab'):
            print("  No delivery_tab attribute found")
            logger.warning("  No delivery_tab attribute found")
            return

        print(f"  delivery_tab exists: {self.delivery_tab}")
        print(f"  current_rfq: {getattr(self.delivery_tab, 'current_rfq', None)}")
        print(f"  vendors_list: {len(getattr(self.delivery_tab, 'vendors_list', []))} vendors")
        logger.info(f"  delivery_tab exists: {self.delivery_tab}")
        logger.info(f"  current_rfq: {getattr(self.delivery_tab, 'current_rfq', None)}")
        logger.info(f"  vendors_list: {len(getattr(self.delivery_tab, 'vendors_list', []))} vendors")

        try:
            print("  Calling _load_package_tracking_for_vendors...")
            logger.info("  Calling _load_package_tracking_for_vendors...")
            self.delivery_tab._load_package_tracking_for_vendors()
            print("  Package tracking statuses refreshed successfully")
            logger.info("  Package tracking statuses refreshed successfully")
        except Exception as e:
            print(f"  Error refreshing package tracking statuses: {e}")
            logger.error(f"  Error refreshing package tracking statuses: {e}", exc_info=True)

    def _create_bidding_tab(self):
        """Create the Bidding tab content."""
        self.bidding_tab = BiddingTab(self.sg_session, parent=self)
        return self.bidding_tab

    def _load_sg_projects(self):
        """Load Shotgrid projects."""
        self.sg_project_combo.clear()
        self.rfq_combo.clear()

        # Add empty items
        self.sg_project_combo.addItem("-- Select a project --", None)
        self.rfq_combo.addItem("-- Select RFQ --", None)

        try:
            projects = self.sg_session.get_projects(status="Bidding")

            for project in projects:
                # Beautify project name from snake_case to Title Case
                project_name = project['name'].replace('_', ' ').title()
                display_text = project_name
                self.sg_project_combo.addItem(display_text, project)

            self.status_label.setText(f"Loaded {len(projects)} Bidding projects")

        except Exception as e:
            logger.error(f"Error loading projects: {e}", exc_info=True)
            self.status_label.setText(f"Error loading projects: {str(e)}")

    def _auto_load_latest_project(self):
        """Automatically load the most recently created project on startup."""
        try:

            # Get projects with created_at field, sorted by newest first
            projects = self.sg_session.sg.find(
                "Project",
                [["sg_status", "is", "Bidding"]],
                ["id", "code", "name", "sg_status", "created_at"],
                order=[{"field_name": "created_at", "direction": "desc"}],
                limit=1
            )

            if projects:
                latest_project = projects[0]

                # Load all projects into combo box first
                self._load_sg_projects()

                # Find and select the latest project in the combo box
                for index in range(self.sg_project_combo.count()):
                    project_data = self.sg_project_combo.itemData(index)
                    if project_data and project_data.get('id') == latest_project['id']:
                        self.sg_project_combo.setCurrentIndex(index)
                        break
            else:
                self._load_sg_projects()

        except Exception as e:
            logger.error(f"Error auto-loading latest project: {e}", exc_info=True)
            # Fallback to just loading the projects normally
            self._load_sg_projects()

    def _on_sg_project_changed(self, index):
        """Handle SG project selection."""
        project = self.sg_project_combo.itemData(index)

        if project:
            # Load RFQs for this project
            self._load_rfqs(project['id'])

            # Load vendors for the delivery tab
            if hasattr(self, "delivery_tab"):
                self.delivery_tab.set_project(project['id'])
        else:
            self.rfq_combo.clear()
            self.rfq_combo.addItem("-- Select RFQ --", None)
            if hasattr(self, "packages_tab"):
                self.packages_tab.clear()
            if hasattr(self, "delivery_tab"):
                self.delivery_tab.clear()

        current_rfq = self.rfq_combo.itemData(self.rfq_combo.currentIndex())
        if hasattr(self, "vfx_breakdown_tab"):
            self.vfx_breakdown_tab.populate_vfx_breakdown_combo(current_rfq)

    def _load_rfqs(self, project_id):
        """Load RFQs for the selected project."""
        self.rfq_combo.clear()

        # Add empty item
        self.rfq_combo.addItem("-- Select RFQ --", None)

        try:
            rfqs = self.sg_session.get_rfqs(project_id,
                                            fields=["id", "code", "sg_status_list",
                                                    "sg_current_bid", "sg_current_bid.code", "sg_current_bid.sg_bid_type",
                                                    "sg_vendors", "created_at"])

            if rfqs:
                pass

            for rfq in rfqs:
                display_text = f"{rfq.get('code', 'N/A')}"
                self.rfq_combo.addItem(display_text, rfq)


            if len(rfqs) == 0:
                self.status_label.setText("No RFQs found for this project")
            else:
                self.status_label.setText(f"Loaded {len(rfqs)} RFQs")

                # Try to restore the last selected RFQ from settings
                last_rfq_id = self.app_settings.get_last_selected_rfq_id()
                rfq_index_to_select = 1  # Default to first RFQ (index 1, because 0 is "-- Select RFQ --")

                if last_rfq_id:
                    # Try to find the RFQ with this ID in the loaded RFQs
                    for index in range(1, self.rfq_combo.count()):  # Skip index 0
                        rfq_data = self.rfq_combo.itemData(index)
                        if rfq_data and rfq_data.get('id') == last_rfq_id:
                            rfq_index_to_select = index
                            logger.info(f"Restoring last selected RFQ: {rfq_data.get('code')}")
                            break

                # Select the RFQ (either the last selected one or the latest one)
                if len(rfqs) > 0:
                    self.rfq_combo.setCurrentIndex(rfq_index_to_select)

        except Exception as e:
            logger.error(f"Error loading RFQs: {e}", exc_info=True)
            self.status_label.setText(f"Error loading RFQs: {str(e)}")

    def _on_rfq_changed(self, index):
        """Handle RFQ selection: update labels, tree, and default-select its linked Breakdown."""
        rfq = self.rfq_combo.itemData(index)

        if rfq:
            # Show currently linked Bid under the RFQ selector
            linked_bid = rfq.get("sg_current_bid")

            if isinstance(linked_bid, dict):
                # ShotGrid returns 'name' field for linked entities, not 'code'
                bid_name = linked_bid.get("name") or linked_bid.get("code") or f"Bid {linked_bid.get('id')}"
                bid_type = linked_bid.get("sg_bid_type", "")
                label_text = f"{bid_name} ({bid_type})" if bid_type else bid_name
            elif isinstance(linked_bid, list) and linked_bid:
                item = linked_bid[0]
                # ShotGrid returns 'name' field for linked entities, not 'code'
                bid_name = item.get("name") or item.get("code") or f"Bid {item.get('id')}"
                bid_type = item.get("sg_bid_type", "")
                label_text = f"{bid_name} ({bid_type})" if bid_type else bid_name
            else:
                label_text = "-"
            if hasattr(self, "rfq_bid_label"):
                self.rfq_bid_label.setText(label_text)


            # Update the package data tree with RFQ data
            if hasattr(self, "packages_tab"):
                self.packages_tab.set_rfq(rfq)

            # Update the bidding tab with RFQ data (includes Reports nested tab)
            if hasattr(self, "bidding_tab"):
                self.bidding_tab.set_rfq(rfq)

            # Update the delivery tab with RFQ data
            if hasattr(self, "delivery_tab"):
                self.delivery_tab.set_rfq(rfq)
        else:
            if hasattr(self, "rfq_bid_label"):
                self.rfq_bid_label.setText("-")
            if hasattr(self, "packages_tab"):
                self.packages_tab.clear()
            if hasattr(self, "delivery_tab"):
                self.delivery_tab.clear()

    def _show_settings_dialog(self):
        """Show the application settings dialog."""
        # Store current DPI scale
        old_dpi_scale = self.app_settings.get_dpi_scale()

        # Get current project ID and ShotGrid client for vendor management
        project = self.sg_project_combo.itemData(self.sg_project_combo.currentIndex())
        project_id = project.get("id") if project else None
        sg_client = getattr(self, 'sg_session', None)

        dialog = SettingsDialog(self.app_settings, sg_client=sg_client, project_id=project_id, parent=self)
        result = dialog.exec()

        # Refresh vendor data in delivery tab (changes may have been made to vendors/client users)
        if hasattr(self, 'delivery_tab'):
            self.delivery_tab.refresh_vendors()

        if result == QtWidgets.QDialog.Accepted:
            # Get the new settings
            dpi_scale = dialog.get_dpi_scale()
            currency = dialog.get_currency()

            # Save to settings
            self.app_settings.set_dpi_scale(dpi_scale)
            self.app_settings.set_currency(currency)

            # Check if DPI scale changed
            if abs(dpi_scale - old_dpi_scale) > 0.01:
                # Scaling is already applied via real-time preview, just ensure it's set
                self._apply_app_font_scaling(dpi_scale)

                QtWidgets.QMessageBox.information(
                    self,
                    "Settings Saved",
                    f"Settings saved successfully!\n\nDPI scaling: {int(dpi_scale * 100)}%\n\nRestart the application for full effect."
                )
            else:
                QtWidgets.QMessageBox.information(
                    self,
                    "Settings Saved",
                    "Settings have been saved."
                )

    def _apply_app_font_scaling(self, scale_factor):
        """Apply font scaling to the entire application."""
        try:
            # Store original fonts for all widgets on first call
            if not hasattr(self, '_original_widget_fonts'):
                self._original_widget_fonts = {}
                self._store_original_fonts(self)

            # Apply scaled fonts to all widgets in the main window
            self._apply_scaled_fonts(self, scale_factor)

            # Update column widths in all tables to match new DPI scale
            self._update_table_column_widths(scale_factor)

        except Exception as e:
            logger.error(f"Failed to apply app font scaling: {e}", exc_info=True)

    def _update_table_column_widths(self, new_dpi_scale):
        """Update column widths in all tables after DPI scale change.

        Args:
            new_dpi_scale: The new DPI scale factor (e.g., 1.5 for 150%)
        """
        try:
            # Calculate the scale ratio
            if hasattr(self, '_current_dpi_scale') and self._current_dpi_scale > 0:
                scale_ratio = new_dpi_scale / self._current_dpi_scale
            else:
                scale_ratio = 1.0


            # Update the global scale for delegates to use (before updating columns)
            PackageManagerApp._active_dpi_scale = new_dpi_scale

            # Update package tree widget column widths
            if hasattr(self, 'packages_tab') and hasattr(self.packages_tab, 'package_tree'):
                tree_widget = self.packages_tab.package_tree.tree_widget
                # Block signals to prevent saving scaled widths
                tree_widget.header().blockSignals(True)
                for col in range(tree_widget.columnCount()):
                    current_width = tree_widget.columnWidth(col)
                    new_width = int(current_width * scale_ratio)
                    tree_widget.setColumnWidth(col, new_width)
                tree_widget.header().blockSignals(False)
                # Force repaint to update checkbox sizes
                tree_widget.viewport().update()

            # Update VFX breakdown widget column widths
            if hasattr(self, 'bidding_tab') and hasattr(self.bidding_tab, 'breakdown_widget'):
                breakdown_widget = self.bidding_tab.breakdown_widget
                if hasattr(breakdown_widget, 'table_view') and breakdown_widget.table_view:
                    table_view = breakdown_widget.table_view
                    header = table_view.horizontalHeader()
                    # Block signals to prevent saving scaled widths
                    header.blockSignals(True)
                    for col in range(table_view.model().columnCount() if table_view.model() else 0):
                        current_width = table_view.columnWidth(col)
                        new_width = int(current_width * scale_ratio)
                        table_view.setColumnWidth(col, new_width)
                    header.blockSignals(False)
                    # Force repaint to update checkbox sizes
                    table_view.viewport().update()

            # Update the tracked DPI scale
            self._current_dpi_scale = new_dpi_scale

        except Exception as e:
            logger.error(f"Failed to update table column widths: {e}", exc_info=True)

    def _store_original_fonts(self, widget):
        """Recursively store original font sizes for all widgets."""
        if widget not in self._original_widget_fonts:
            self._original_widget_fonts[widget] = widget.font().pointSize()

        for child in widget.findChildren(QtWidgets.QWidget):
            if child not in self._original_widget_fonts:
                self._original_widget_fonts[child] = child.font().pointSize()

    def _apply_scaled_fonts(self, widget, scale_factor):
        """Recursively apply scaled fonts to widget and all children."""
        # Get original font size and scale it
        original_size = self._original_widget_fonts.get(widget, 10)
        new_size = max(6, int(original_size * scale_factor))

        # Create and apply scaled font
        font = widget.font()
        font.setPointSize(new_size)
        widget.setFont(font)

        # Special handling for buttons - add minimum height
        if isinstance(widget, QtWidgets.QPushButton):
            min_height = int(24 * scale_factor)  # Base min height: 24px
            widget.setMinimumHeight(min_height)

        # Special handling for combo boxes
        if isinstance(widget, QtWidgets.QComboBox):
            min_height = int(24 * scale_factor)
            widget.setMinimumHeight(min_height)

        # Helper function to check if a widget is inside a SettingsDialog
        def is_inside_settings_dialog(w):
            parent = w.parent()
            while parent is not None:
                if isinstance(parent, SettingsDialog):
                    return True
                parent = parent.parent()
            return False

        # Recursively apply to all children
        for child in widget.findChildren(QtWidgets.QWidget):
            # Skip the settings dialog itself and all widgets inside it
            if isinstance(child, SettingsDialog) or is_inside_settings_dialog(child):
                continue

            original_size = self._original_widget_fonts.get(child, 10)
            new_size = max(6, int(original_size * scale_factor))
            font = child.font()
            font.setPointSize(new_size)
            child.setFont(font)

            # Special handling for child buttons
            if isinstance(child, QtWidgets.QPushButton):
                min_height = int(24 * scale_factor)
                child.setMinimumHeight(min_height)

            # Special handling for child combo boxes
            if isinstance(child, QtWidgets.QComboBox):
                min_height = int(24 * scale_factor)
                child.setMinimumHeight(min_height)

        # Force layout update
        widget.updateGeometry()
        if hasattr(widget, 'layout') and widget.layout():
            widget.layout().update()

    def showEvent(self, event):
        """Called when window is shown."""
        super().showEvent(event)

    def closeEvent(self, event):
        """Called when window is closed."""
        super().closeEvent(event)