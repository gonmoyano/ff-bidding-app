"""Delivery tab widget for managing package delivery to vendors."""
from PySide6 import QtWidgets, QtCore, QtGui
from pathlib import Path
import logging
import json
import zipfile
import os

try:
    from .logger import logger
    from .bid_selector_widget import CollapsibleGroupBox
    from .settings import AppSettings
    from .gdrive_service import get_gdrive_service, GOOGLE_API_AVAILABLE
except ImportError:
    logger = logging.getLogger("FFPackageManager")
    from bid_selector_widget import CollapsibleGroupBox
    from settings import AppSettings
    from gdrive_service import get_gdrive_service, GOOGLE_API_AVAILABLE


class ZipWorker(QtCore.QThread):
    """Worker thread for zipping package directories."""

    progress = QtCore.Signal(int, str)  # (percent, current_file)
    finished = QtCore.Signal(str)  # zip_path
    error = QtCore.Signal(str)  # error_message

    def __init__(self, source_dir, zip_path, parent=None):
        """Initialize the zip worker.

        Args:
            source_dir: Path to the directory to zip
            zip_path: Path for the output zip file
            parent: Parent QObject
        """
        super().__init__(parent)
        self.source_dir = Path(source_dir)
        self.zip_path = Path(zip_path)

    # Files to exclude from the zip (keep in original folder but don't send to vendor)
    EXCLUDED_FILES = {'manifest.json'}

    def run(self):
        """Execute the zipping process."""
        try:
            # Count total files for progress (excluding manifest.json)
            all_files = []
            for root, dirs, files in os.walk(self.source_dir):
                for file in files:
                    if file not in self.EXCLUDED_FILES:
                        all_files.append(os.path.join(root, file))

            total_files = len(all_files)
            if total_files == 0:
                self.error.emit("No files to zip")
                return

            # Create zip file
            with zipfile.ZipFile(self.zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for idx, file_path in enumerate(all_files):
                    # Calculate relative path for archive
                    rel_path = os.path.relpath(file_path, self.source_dir)

                    # Update progress
                    percent = int((idx + 1) / total_files * 100)
                    self.progress.emit(percent, os.path.basename(file_path))

                    # Add file to archive
                    zipf.write(file_path, rel_path)

            self.finished.emit(str(self.zip_path))

        except Exception as e:
            self.error.emit(str(e))


class PackageShareWidget(QtWidgets.QWidget):
    """
    Widget for sharing packages with vendors.

    Provides UI for selecting packages and configuring delivery options.
    """

    packageSelected = QtCore.Signal(object)  # Emitted when a package is selected
    shareRequested = QtCore.Signal(dict)  # Emitted when share is requested with config

    def __init__(self, parent=None):
        super().__init__(parent)

        self.packages_list = []
        self.current_package = None

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Package selection
        package_group = QtWidgets.QGroupBox("Package to Deliver")
        package_layout = QtWidgets.QVBoxLayout(package_group)

        # Package dropdown
        pkg_select_layout = QtWidgets.QHBoxLayout()
        pkg_select_layout.addWidget(QtWidgets.QLabel("Select Package:"))
        self.package_combo = QtWidgets.QComboBox()
        self.package_combo.setMinimumWidth(200)
        self.package_combo.addItem("-- Select a package --", None)
        pkg_select_layout.addWidget(self.package_combo, 1)
        package_layout.addLayout(pkg_select_layout)

        # Package info display
        self.package_info_label = QtWidgets.QLabel("No package selected")
        self.package_info_label.setStyleSheet("color: #888; padding: 10px;")
        self.package_info_label.setWordWrap(True)
        package_layout.addWidget(self.package_info_label)

        layout.addWidget(package_group)

        # Vendor assignment (moved above delivery options)
        vendor_group = QtWidgets.QGroupBox("Vendor Assignment")
        vendor_layout = QtWidgets.QVBoxLayout(vendor_group)

        self.vendor_info_label = QtWidgets.QLabel(
            "Drag packages to vendor groups on the right panel to assign them, "
            "or select a vendor below:"
        )
        self.vendor_info_label.setWordWrap(True)
        self.vendor_info_label.setStyleSheet("color: #aaa;")
        vendor_layout.addWidget(self.vendor_info_label)

        # Vendor selection dropdown
        vendor_select_layout = QtWidgets.QHBoxLayout()
        vendor_select_layout.addWidget(QtWidgets.QLabel("Assign to Vendor:"))
        self.vendor_combo = QtWidgets.QComboBox()
        self.vendor_combo.setMinimumWidth(200)
        self.vendor_combo.addItem("-- Select a vendor --", None)
        vendor_select_layout.addWidget(self.vendor_combo, 1)
        vendor_layout.addLayout(vendor_select_layout)

        layout.addWidget(vendor_group)

        # Delivery options
        delivery_group = QtWidgets.QGroupBox("Delivery Options")
        delivery_layout = QtWidgets.QVBoxLayout(delivery_group)

        # Email sharing
        email_layout = QtWidgets.QHBoxLayout()
        email_layout.addWidget(QtWidgets.QLabel("Recipient Email:"))
        self.email_edit = QtWidgets.QLineEdit()
        self.email_edit.setPlaceholderText("vendor@example.com (optional)")
        email_layout.addWidget(self.email_edit)
        delivery_layout.addLayout(email_layout)

        # Permission level
        perm_layout = QtWidgets.QHBoxLayout()
        perm_layout.addWidget(QtWidgets.QLabel("Permission:"))
        self.permission_combo = QtWidgets.QComboBox()
        self.permission_combo.addItems(["View only", "Can comment", "Can edit"])
        perm_layout.addWidget(self.permission_combo)
        perm_layout.addStretch()
        delivery_layout.addLayout(perm_layout)

        # Link sharing checkbox
        self.link_check = QtWidgets.QCheckBox("Generate shareable link (anyone with link can access)")
        self.link_check.setChecked(True)
        delivery_layout.addWidget(self.link_check)

        # Notification message
        delivery_layout.addWidget(QtWidgets.QLabel("Notification message (optional):"))
        self.message_edit = QtWidgets.QTextEdit()
        self.message_edit.setPlaceholderText("Your data package is ready for download.")
        self.message_edit.setMaximumHeight(80)
        delivery_layout.addWidget(self.message_edit)

        layout.addWidget(delivery_group)

        # Progress bar for zipping
        self.progress_group = QtWidgets.QGroupBox("Progress")
        progress_layout = QtWidgets.QVBoxLayout(self.progress_group)
        self.progress_label = QtWidgets.QLabel("Ready")
        progress_layout.addWidget(self.progress_label)
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        self.progress_group.setVisible(False)
        layout.addWidget(self.progress_group)

        # Action buttons
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()

        # Google Drive connection status label
        self.gdrive_status_label = QtWidgets.QLabel()
        self.gdrive_status_label.setStyleSheet("color: gray;")
        self._update_gdrive_status()
        btn_layout.addWidget(self.gdrive_status_label)

        self.share_btn = QtWidgets.QPushButton("Share Package")
        self.share_btn.setEnabled(False)
        self.share_btn.setMinimumWidth(130)
        btn_layout.addWidget(self.share_btn)

        layout.addLayout(btn_layout)

        # Result display
        self.result_group = QtWidgets.QGroupBox("Share Result")
        result_layout = QtWidgets.QVBoxLayout(self.result_group)
        self.result_link = QtWidgets.QLineEdit()
        self.result_link.setReadOnly(True)
        self.result_link.setPlaceholderText("Shareable link will appear here...")
        self.copy_link_btn = QtWidgets.QPushButton("Copy Link")
        self.copy_link_btn.setEnabled(False)
        result_h = QtWidgets.QHBoxLayout()
        result_h.addWidget(self.result_link)
        result_h.addWidget(self.copy_link_btn)
        result_layout.addLayout(result_h)
        self.result_group.setVisible(False)
        layout.addWidget(self.result_group)

        layout.addStretch()

    def _connect_signals(self):
        self.package_combo.currentIndexChanged.connect(self._on_package_selected)
        self.vendor_combo.currentIndexChanged.connect(self._on_vendor_selected)
        self.email_edit.textChanged.connect(self._update_buttons)
        self.link_check.toggled.connect(self._update_buttons)
        self.share_btn.clicked.connect(self._on_share_clicked)
        self.copy_link_btn.clicked.connect(self._copy_link)

    def _update_gdrive_status(self):
        """Update the Google Drive connection status label."""
        gdrive = get_gdrive_service()

        if not GOOGLE_API_AVAILABLE:
            self.gdrive_status_label.setText("Google Drive: Libraries missing")
            self.gdrive_status_label.setStyleSheet("color: #cc6666;")  # Red
            self.gdrive_status_label.setToolTip("pip install google-auth google-auth-oauthlib google-api-python-client")
        elif not gdrive.has_credentials:
            self.gdrive_status_label.setText("Google Drive: Not configured")
            self.gdrive_status_label.setStyleSheet("color: #cc6666;")  # Red
            self.gdrive_status_label.setToolTip("credentials.json not found")
        elif not gdrive.is_authenticated:
            self.gdrive_status_label.setText("Google Drive: Not authenticated")
            self.gdrive_status_label.setStyleSheet("color: #cccc66;")  # Yellow
            self.gdrive_status_label.setToolTip("Click Share to authenticate with Google Drive")
        else:
            self.gdrive_status_label.setText("Google Drive: Connected")
            self.gdrive_status_label.setStyleSheet("color: #66cc66;")  # Green
            self.gdrive_status_label.setToolTip("Authenticated with Google Drive")

    def set_packages(self, packages_list):
        """Set the list of packages available for delivery.

        Args:
            packages_list: List of package dictionaries from ShotGrid
        """
        self.packages_list = packages_list

        # Update combo box
        self.package_combo.blockSignals(True)
        self.package_combo.clear()
        self.package_combo.addItem("-- Select a package --", None)

        for pkg in packages_list:
            pkg_name = pkg.get('code', f"Package {pkg.get('id', '?')}")
            self.package_combo.addItem(pkg_name, pkg)

        self.package_combo.blockSignals(False)

        # Reset selection
        self.current_package = None
        self._update_package_info()
        self._update_buttons()

    def set_vendors(self, vendors_list):
        """Set the list of vendors available for assignment.

        Args:
            vendors_list: List of vendor dictionaries from ShotGrid
        """
        self.vendor_combo.blockSignals(True)
        self.vendor_combo.clear()
        self.vendor_combo.addItem("-- Select a vendor --", None)

        for vendor in vendors_list:
            vendor_name = vendor.get('code', f"Vendor {vendor.get('id', '?')}")
            self.vendor_combo.addItem(vendor_name, vendor)

        self.vendor_combo.blockSignals(False)
        self._update_buttons()

    def _on_package_selected(self, index):
        """Handle package selection from dropdown."""
        self.current_package = self.package_combo.itemData(index)
        self._update_package_info()
        self._update_buttons()

        if self.current_package:
            self.packageSelected.emit(self.current_package)

    def _on_vendor_selected(self, index):
        """Handle vendor selection from dropdown.

        Pre-fills the recipient email field with emails from the vendor's sg_members.
        """
        vendor = self.vendor_combo.itemData(index)
        self._update_buttons()

        if vendor:
            # Extract member IDs from sg_members (Client User entity links)
            members = vendor.get('sg_members', []) or []
            member_ids = []

            for member in members:
                if isinstance(member, dict):
                    member_id = member.get('id')
                    if member_id:
                        member_ids.append(member_id)

            # Fetch ClientUser details to get emails
            if member_ids:
                try:
                    # Access sg_session from parent DeliveryTab
                    parent_tab = self.parent()
                    if parent_tab and hasattr(parent_tab, 'parent_app'):
                        delivery_tab = parent_tab.parent_app
                        if hasattr(delivery_tab, 'sg_session'):
                            # Actually parent_tab is DeliveryTab's details_pane, go up more
                            pass

                    # Try to get sg_session from the DeliveryTab
                    delivery_tab = self._get_delivery_tab()
                    if delivery_tab and hasattr(delivery_tab, 'sg_session'):
                        client_users = delivery_tab.sg_session.get_client_users(member_ids)
                        emails = [u.get('email') for u in client_users if u.get('email')]

                        # Pre-fill the email field with space-separated emails
                        if emails:
                            self.email_edit.setText(' '.join(emails))
                except Exception as e:
                    logger.warning(f"Could not fetch client user emails: {e}")

    def _get_delivery_tab(self):
        """Get the parent DeliveryTab widget.

        Returns:
            DeliveryTab instance or None
        """
        # Walk up the parent hierarchy to find DeliveryTab
        parent = self.parent()
        while parent:
            if isinstance(parent, DeliveryTab):
                return parent
            parent = parent.parent()
        return None

    def _update_package_info(self):
        """Update the package info display."""
        if self.current_package:
            pkg_name = self.current_package.get('code', 'Unknown')
            pkg_path = self.current_package.get('path', '')
            description = self.current_package.get('description', 'No description available')

            info_text = f"<b>{pkg_name}</b><br>"
            if pkg_path:
                info_text += f"Path: {pkg_path}<br>"
            if description:
                info_text += f"{description}"

            self.package_info_label.setText(info_text)
            self.package_info_label.setStyleSheet("color: #ddd; padding: 10px;")
        else:
            self.package_info_label.setText("No package selected")
            self.package_info_label.setStyleSheet("color: #888; padding: 10px;")

    def _update_buttons(self):
        """Update button enabled states."""
        has_package = self.current_package is not None
        has_target = bool(self.email_edit.text().strip()) or self.link_check.isChecked()

        self.share_btn.setEnabled(has_package and has_target)

    def _on_share_clicked(self):
        """Handle share button click.

        Uploads manifest to ShotGrid, sets package status to closed,
        then checks if a zip file exists for the package, creates one if not,
        and proceeds with sharing.
        """
        if not self.current_package:
            return

        package_path = self.current_package.get('path')
        if not package_path:
            logger.warning("No package path available")
            return

        package_dir = Path(package_path)
        zip_path = package_dir.with_suffix('.zip')

        # Upload manifest to ShotGrid and set status to closed
        self._update_package_in_shotgrid()

        # Check if zip already exists
        if zip_path.exists():
            logger.info(f"Zip file already exists: {zip_path}")
            self._complete_share(zip_path)
        else:
            # Need to create zip file
            self._start_zipping(package_dir, zip_path)

    def _update_package_in_shotgrid(self):
        """Upload manifest to ShotGrid and set package status to closed."""
        if not self.current_package:
            return

        package_name = self.current_package.get('code')
        manifest_data = self.current_package.get('manifest')

        if not package_name:
            logger.warning("No package name available for ShotGrid update")
            return

        if not manifest_data:
            logger.warning("No manifest data available for ShotGrid update")
            return

        try:
            delivery_tab = self._get_delivery_tab()
            if not delivery_tab or not hasattr(delivery_tab, 'sg_session'):
                logger.warning("Could not access ShotGrid session")
                return

            sg_session = delivery_tab.sg_session
            project_id = delivery_tab.current_project_id

            logger.info(f"Looking for package '{package_name}' in project {project_id}")

            # Find the package in ShotGrid by name
            sg_package = sg_session.get_package_by_name(package_name, project_id)

            if not sg_package:
                logger.warning(f"Package '{package_name}' not found in ShotGrid")
                return

            logger.info(f"Found package in ShotGrid with ID: {sg_package['id']}")
            logger.info(f"Uploading manifest ({len(json.dumps(manifest_data))} bytes) and setting status to closed")

            # Update the package with manifest and status
            result = sg_session.update_package(
                sg_package['id'],
                status='clsd',  # closed status
                manifest=manifest_data
            )

            if result:
                logger.info(f"Successfully updated package '{package_name}' in ShotGrid: status=closed, manifest uploaded")
            else:
                logger.warning(f"update_package returned None for '{package_name}'")

        except Exception as e:
            logger.error(f"Failed to update package in ShotGrid: {e}", exc_info=True)

    def _start_zipping(self, package_dir, zip_path):
        """Start the zipping process in a worker thread.

        Args:
            package_dir: Path to the package directory
            zip_path: Path for the output zip file
        """
        # Show progress UI
        self.progress_group.setVisible(True)
        self.progress_label.setText(f"Zipping {package_dir.name}...")
        self.progress_bar.setValue(0)
        self.share_btn.setEnabled(False)

        # Create and start worker thread
        self.zip_worker = ZipWorker(package_dir, zip_path)
        self.zip_worker.progress.connect(self._on_zip_progress)
        self.zip_worker.finished.connect(self._on_zip_finished)
        self.zip_worker.error.connect(self._on_zip_error)
        self.zip_worker.start()

    def _on_zip_progress(self, percent, current_file):
        """Handle zip progress updates.

        Args:
            percent: Progress percentage (0-100)
            current_file: Name of file currently being zipped
        """
        self.progress_bar.setValue(percent)
        self.progress_label.setText(f"Zipping: {current_file}")

    def _on_zip_finished(self, zip_path):
        """Handle zip completion.

        Args:
            zip_path: Path to the created zip file
        """
        self.progress_label.setText("Zipping complete!")
        self.progress_bar.setValue(100)
        self._update_buttons()

        # Hide progress after a short delay
        QtCore.QTimer.singleShot(1500, lambda: self.progress_group.setVisible(False))

        self._complete_share(Path(zip_path))

    def _on_zip_error(self, error_msg):
        """Handle zip error.

        Args:
            error_msg: Error message
        """
        self.progress_label.setText(f"Error: {error_msg}")
        self._update_buttons()
        logger.error(f"Zip error: {error_msg}")

        # Hide progress after a delay
        QtCore.QTimer.singleShot(3000, lambda: self.progress_group.setVisible(False))

    def _complete_share(self, zip_path):
        """Complete the share process after zip is ready.

        Args:
            zip_path: Path to the zip file
        """
        config = {
            'package': self.current_package,
            'zip_path': str(zip_path),
            'email': self.email_edit.text().strip() or None,
            'permission': self._get_permission_value(),
            'link_sharing': self.link_check.isChecked(),
            'message': self.message_edit.toPlainText().strip() or None,
            'vendor': self.vendor_combo.currentData()
        }

        self.shareRequested.emit(config)

        # Upload to Google Drive
        gdrive = get_gdrive_service()
        if not gdrive.is_available:
            QtWidgets.QMessageBox.warning(
                self, "Google Drive Error",
                "Google API libraries not installed.\n\n"
                "Run: pip install google-auth google-auth-oauthlib google-api-python-client"
            )
            return

        # Show progress
        self.progress_group.setVisible(True)
        self.progress_label.setText("Uploading to Google Drive...")
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.share_btn.setEnabled(False)
        QtWidgets.QApplication.processEvents()

        try:
            result = gdrive.upload_and_share(
                file_path=str(zip_path),
                email=config['email'],
                role=config['permission'],
                link_sharing=config['link_sharing']
            )

            if result and result.get('webViewLink'):
                self.result_link.setText(result['webViewLink'])
                self.copy_link_btn.setEnabled(True)
                self.result_group.setVisible(True)
                self.progress_label.setText("Upload complete!")
                logger.info(f"File shared successfully: {result['webViewLink']}")
            else:
                self.progress_label.setText("Upload failed - check logs")
                QtWidgets.QMessageBox.warning(
                    self, "Upload Failed",
                    "Failed to upload file to Google Drive. Check the logs for details."
                )
        except Exception as e:
            logger.error(f"Google Drive upload error: {e}")
            self.progress_label.setText(f"Error: {str(e)[:50]}")
            QtWidgets.QMessageBox.critical(
                self, "Upload Error",
                f"Error uploading to Google Drive:\n\n{str(e)}"
            )
        finally:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self._update_buttons()
            self._update_gdrive_status()
            QtCore.QTimer.singleShot(2000, lambda: self.progress_group.setVisible(False))

    def _get_permission_value(self):
        """Get the permission value from the combo box."""
        mapping = {
            "View only": "reader",
            "Can comment": "commenter",
            "Can edit": "writer"
        }
        return mapping.get(self.permission_combo.currentText(), "reader")

    def _copy_link(self):
        """Copy the shareable link to clipboard."""
        link = self.result_link.text()
        if link:
            QtWidgets.QApplication.clipboard().setText(link)
            # Brief visual feedback
            self.copy_link_btn.setText("Copied!")
            QtCore.QTimer.singleShot(1500, lambda: self.copy_link_btn.setText("Copy Link"))

    def get_selected_package(self):
        """Get the currently selected package data."""
        return self.current_package


class VendorCategoryView(QtWidgets.QWidget):
    """View widget for displaying vendors as collapsible groups."""

    vendorSelected = QtCore.Signal(object)  # Signal emitted when a vendor is selected (vendor_data)
    packageAssigned = QtCore.Signal(int, str)  # Signal emitted when a package is assigned to a vendor

    def __init__(self, parent=None):
        """Initialize the vendor view."""
        super().__init__(parent)
        self.vendors = {}  # vendor_id -> vendor_data
        self.vendor_groups = {}  # vendor_code -> CollapsibleGroupBox with droppable container
        self.assigned_packages = {}  # vendor_code -> set of package_ids
        self._selected_vendor_code = None

        self._setup_ui()

    def _setup_ui(self):
        """Setup the vendor view UI."""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # Scroll area for vendor groups
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        # Container for vendor groups
        container = QtWidgets.QWidget()
        self.groups_layout = QtWidgets.QVBoxLayout(container)
        self.groups_layout.setContentsMargins(5, 5, 5, 5)
        self.groups_layout.setSpacing(10)
        self.groups_layout.addStretch()

        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area)

    def set_vendors(self, vendors_list):
        """Set the vendors to display, each as a collapsible group.

        Args:
            vendors_list: List of vendor dictionaries from ShotGrid
        """
        # Clear existing groups
        for group_data in self.vendor_groups.values():
            group_data['group'].deleteLater()
        self.vendor_groups.clear()
        self.vendors.clear()
        self.assigned_packages.clear()

        # Remove all items from layout
        while self.groups_layout.count():
            item = self.groups_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        # Create a collapsible group for each vendor
        for vendor_data in vendors_list:
            vendor_id = vendor_data.get('id')
            vendor_code = vendor_data.get('code', 'Unknown')

            if vendor_id:
                self.vendors[vendor_id] = vendor_data
                self.assigned_packages[vendor_code] = set()

                # Create collapsible group with vendor name
                group = CollapsibleGroupBox(f"{vendor_code} (0 packages)")

                # Create droppable container inside the group
                drop_container = DroppableVendorContainer(vendor_data)
                drop_container.packageDropped.connect(self._on_package_dropped)
                group.addWidget(drop_container)

                self.groups_layout.addWidget(group)
                self.vendor_groups[vendor_code] = {
                    'group': group,
                    'container': drop_container,
                    'vendor_data': vendor_data
                }

        self.groups_layout.addStretch()

    def _on_package_dropped(self, package_id, vendor_code):
        """Handle package dropped on vendor container."""
        if vendor_code in self.assigned_packages:
            self.assigned_packages[vendor_code].add(package_id)
            # Update group title with package count
            if vendor_code in self.vendor_groups:
                count = len(self.assigned_packages[vendor_code])
                self.vendor_groups[vendor_code]['group'].setTitle(f"{vendor_code} ({count} package{'s' if count != 1 else ''})")

        self.packageAssigned.emit(package_id, vendor_code)

    def add_package_to_vendor(self, package_id, package_name, vendor_code):
        """Programmatically add a package to a vendor.

        Args:
            package_id: Package ID
            package_name: Package name/code
            vendor_code: Vendor code to add to
        """
        if vendor_code in self.vendor_groups:
            container = self.vendor_groups[vendor_code]['container']
            container._add_package_widget(package_id, package_name)

            # Update tracking
            if vendor_code in self.assigned_packages:
                self.assigned_packages[vendor_code].add(package_id)
                count = len(self.assigned_packages[vendor_code])
                self.vendor_groups[vendor_code]['group'].setTitle(f"{vendor_code} ({count} package{'s' if count != 1 else ''})")

    def get_vendor_mappings(self):
        """Get all package-to-vendor mappings.

        Returns:
            dict: {vendor_code: [package_id1, package_id2, ...]}
        """
        mappings = {}
        for vendor_code, package_ids in self.assigned_packages.items():
            if package_ids:
                mappings[vendor_code] = list(package_ids)
        return mappings


class DroppableVendorContainer(QtWidgets.QWidget):
    """Container widget inside a vendor group that accepts package drops."""

    packageDropped = QtCore.Signal(int, str)  # Signal emitted when a package is dropped (package_id, vendor_code)

    def __init__(self, vendor_data, parent=None):
        """Initialize the droppable vendor container.

        Args:
            vendor_data: Vendor data dictionary from ShotGrid
            parent: Parent widget
        """
        super().__init__(parent)
        self.vendor_data = vendor_data
        self.vendor_code = vendor_data.get('code', 'Unknown')
        self.package_widgets = {}  # package_id -> QWidget
        self._is_drag_over = False

        self.setAcceptDrops(True)
        self.setMinimumHeight(80)
        self._setup_ui()
        self._update_style()

    def _setup_ui(self):
        """Setup the container UI."""
        self.layout = QtWidgets.QGridLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)
        self.layout.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)

        # Placeholder label when empty
        self.placeholder_label = QtWidgets.QLabel("Drop packages here")
        self.placeholder_label.setStyleSheet("color: #666; font-style: italic;")
        self.placeholder_label.setAlignment(QtCore.Qt.AlignCenter)
        self.layout.addWidget(self.placeholder_label, 0, 0)

    def _update_style(self):
        """Update container styling based on state."""
        if self._is_drag_over:
            self.setStyleSheet("""
                DroppableVendorContainer {
                    background-color: rgba(74, 159, 255, 50);
                    border: 2px dashed #4a9eff;
                    border-radius: 4px;
                }
            """)
        else:
            self.setStyleSheet("""
                DroppableVendorContainer {
                    background-color: #2a2a2a;
                    border: 1px dashed #555;
                    border-radius: 4px;
                }
            """)

    def _add_package_widget(self, package_id, package_name):
        """Add a package widget to the container."""
        if package_id in self.package_widgets:
            return  # Already exists

        # Hide placeholder
        self.placeholder_label.hide()

        # Create package label
        package_widget = QtWidgets.QFrame()
        package_widget.setStyleSheet("""
            QFrame {
                background-color: #3a3a3a;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px;
            }
            QFrame:hover {
                background-color: #454545;
                border: 1px solid #666;
            }
        """)

        widget_layout = QtWidgets.QHBoxLayout(package_widget)
        widget_layout.setContentsMargins(8, 5, 8, 5)

        icon_label = QtWidgets.QLabel()
        icon_label.setPixmap(self.style().standardIcon(
            QtWidgets.QStyle.SP_DirIcon
        ).pixmap(24, 24))
        widget_layout.addWidget(icon_label)

        name_label = QtWidgets.QLabel(package_name)
        name_label.setStyleSheet("font-size: 11px; font-weight: bold;")
        widget_layout.addWidget(name_label)
        widget_layout.addStretch()

        self.package_widgets[package_id] = package_widget

        # Re-layout packages in grid
        self._relayout_packages()

    def _relayout_packages(self):
        """Re-layout package widgets in grid."""
        # Remove all widgets from layout except placeholder
        for i in reversed(range(self.layout.count())):
            item = self.layout.itemAt(i)
            if item.widget() and item.widget() != self.placeholder_label:
                self.layout.removeWidget(item.widget())

        # Add packages back in grid
        columns = 2  # Number of columns
        for idx, (package_id, widget) in enumerate(self.package_widgets.items()):
            row = idx // columns
            col = idx % columns
            self.layout.addWidget(widget, row, col)

    def dragEnterEvent(self, event):
        """Handle drag enter event."""
        if event.mimeData().hasFormat("application/x-package-id"):
            event.acceptProposedAction()
            self._is_drag_over = True
            self._update_style()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        """Handle drag leave event."""
        self._is_drag_over = False
        self._update_style()

    def dropEvent(self, event):
        """Handle drop event."""
        if event.mimeData().hasFormat("application/x-package-id"):
            # Get the dropped package ID
            package_id_bytes = event.mimeData().data("application/x-package-id")
            package_id = int(bytes(package_id_bytes).decode())

            # Get package name from mime data if available, or use ID
            package_name = f"Package {package_id}"
            if event.mimeData().hasFormat("application/x-package-name"):
                name_bytes = event.mimeData().data("application/x-package-name")
                package_name = bytes(name_bytes).decode()

            # Add package widget
            self._add_package_widget(package_id, package_name)

            event.acceptProposedAction()

            # Emit signal
            self.packageDropped.emit(package_id, self.vendor_code)

            # Remove highlight
            self._is_drag_over = False
            self._update_style()
        else:
            event.ignore()


class DeliveryTab(QtWidgets.QWidget):
    """Delivery tab widget for managing package delivery to vendors."""

    def __init__(self, sg_session, output_directory, parent=None):
        """Initialize the Delivery tab.

        Args:
            sg_session: ShotgridClient instance
            output_directory: Default output directory path for packages
            parent: Parent widget (PackageManagerApp)
        """
        super().__init__(parent)
        self.sg_session = sg_session
        self.output_directory = output_directory
        self.parent_app = parent

        # Settings
        self.app_settings = AppSettings()

        # Current context
        self.current_rfq = None
        self.current_project_id = None

        # Data
        self.packages_list = []
        self.vendors_list = []

        self._build_ui()

    def _build_ui(self):
        """Build the Delivery tab UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Main splitter for side-by-side panes (horizontal)
        self.main_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)

        # Left pane: Package share/delivery details
        details_pane = QtWidgets.QWidget()
        details_pane_layout = QtWidgets.QVBoxLayout(details_pane)
        details_pane_layout.setContentsMargins(0, 0, 0, 0)

        details_header = QtWidgets.QLabel("Package Delivery")
        details_header.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        details_pane_layout.addWidget(details_header)

        self.package_share_widget = PackageShareWidget(self)
        self.package_share_widget.packageSelected.connect(self._on_package_selected)
        self.package_share_widget.shareRequested.connect(self._on_share_requested)
        details_pane_layout.addWidget(self.package_share_widget)

        self.main_splitter.addWidget(details_pane)

        # Right pane: Vendor groups view
        vendors_pane = QtWidgets.QWidget()
        vendors_pane_layout = QtWidgets.QVBoxLayout(vendors_pane)
        vendors_pane_layout.setContentsMargins(0, 0, 0, 0)

        vendors_header = QtWidgets.QLabel("Vendors")
        vendors_header.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        vendors_pane_layout.addWidget(vendors_header)

        self.vendor_category_view = VendorCategoryView(self)
        self.vendor_category_view.packageAssigned.connect(self._on_package_assigned)
        vendors_pane_layout.addWidget(self.vendor_category_view)

        self.main_splitter.addWidget(vendors_pane)

        # Set initial splitter sizes (details pane narrower, vendors wider)
        self.main_splitter.setSizes([450, 550])

        layout.addWidget(self.main_splitter, 1)

        # Bottom section: Status
        bottom_layout = QtWidgets.QHBoxLayout()

        self.status_label = QtWidgets.QLabel("Ready")
        bottom_layout.addWidget(self.status_label)
        bottom_layout.addStretch()

        layout.addLayout(bottom_layout)

    def set_rfq(self, rfq):
        """Set the current RFQ and update the views.

        Args:
            rfq: RFQ data dict
        """
        self.current_rfq = rfq

        if not rfq:
            self.package_share_widget.set_packages([])
            self.status_label.setText("No RFQ selected")
            return

        # Load packages for this RFQ
        self._load_packages_for_rfq(rfq)

        self.status_label.setText(f"Loaded packages for RFQ: {rfq.get('code', 'Unknown')}")

    def set_project(self, project_id):
        """Set the current project and load vendors.

        Args:
            project_id: Project ID
        """
        self.current_project_id = project_id

        if not project_id:
            self.vendor_category_view.set_vendors([])
            self.package_share_widget.set_vendors([])
            return

        # Load vendors for this project
        self._load_vendors_for_project(project_id)

    def _get_output_directory(self):
        """Get the current output directory path.

        Returns the output directory from the packages tab if available,
        otherwise falls back to the default output directory.

        Returns:
            Path: The output directory path
        """
        # Try to get the current output directory from the packages tab
        if self.parent_app and hasattr(self.parent_app, 'packages_tab'):
            packages_tab = self.parent_app.packages_tab
            if hasattr(packages_tab, 'output_path_input'):
                return Path(packages_tab.output_path_input.text())

        return Path(self.output_directory)

    def _load_packages_for_rfq(self, rfq):
        """Load packages from the output directory filesystem.

        Only loads packages that exist in the filesystem.

        Args:
            rfq: RFQ data dict
        """
        if not rfq:
            self.packages_list = []
            self.package_share_widget.set_packages([])
            return

        try:
            output_dir = self._get_output_directory()

            if not output_dir.exists():
                logger.warning(f"Output directory does not exist: {output_dir}")
                self.packages_list = []
                self.package_share_widget.set_packages([])
                return

            # Scan the output directory for package folders with manifest.json
            packages_found = []

            for item in output_dir.iterdir():
                if item.is_dir():
                    manifest_path = item / "manifest.json"
                    if manifest_path.exists():
                        try:
                            with open(manifest_path, 'r', encoding='utf-8') as f:
                                manifest_data = json.load(f)

                            # Create a package dict with info from the manifest
                            package_info = {
                                'id': manifest_data.get('package_name', item.name),
                                'code': manifest_data.get('package_name', item.name),
                                'path': str(item),
                                'description': self._get_package_description(manifest_data),
                                'manifest': manifest_data
                            }
                            packages_found.append(package_info)
                            logger.debug(f"Found package: {item.name}")
                        except (json.JSONDecodeError, IOError) as e:
                            logger.warning(f"Could not read manifest for {item.name}: {e}")

            self.packages_list = packages_found
            self.package_share_widget.set_packages(self.packages_list)
            logger.info(f"Loaded {len(self.packages_list)} packages from filesystem")

        except Exception as e:
            logger.error(f"Error loading packages from filesystem: {e}", exc_info=True)
            self.packages_list = []
            self.package_share_widget.set_packages([])

    def _get_package_description(self, manifest_data):
        """Extract a description from manifest data.

        Args:
            manifest_data: Manifest dictionary

        Returns:
            str: Package description
        """
        summary = manifest_data.get('manifest', {}).get('summary', {})
        total_folders = summary.get('total_folders', 0)
        total_files = summary.get('total_files', 0)

        # Get RFQ info if available
        rfq_info = manifest_data.get('rfq', {})
        rfq_name = rfq_info.get('code', '')

        parts = []
        if rfq_name:
            parts.append(f"RFQ: {rfq_name}")
        parts.append(f"{total_folders} folders, {total_files} files")

        return " | ".join(parts)

    def _load_vendors_for_project(self, project_id):
        """Load vendors for the project.

        Args:
            project_id: Project ID
        """
        if not project_id:
            self.vendors_list = []
            self.vendor_category_view.set_vendors([])
            self.package_share_widget.set_vendors([])
            return

        try:
            self.vendors_list = self.sg_session.get_vendors(project_id)
            self.vendor_category_view.set_vendors(self.vendors_list)
            self.package_share_widget.set_vendors(self.vendors_list)
            logger.info(f"Loaded {len(self.vendors_list)} vendors for project {project_id}")
        except Exception as e:
            logger.error(f"Error loading vendors for project: {e}", exc_info=True)
            self.vendors_list = []
            self.vendor_category_view.set_vendors([])
            self.package_share_widget.set_vendors([])

    def _on_package_selected(self, package_data):
        """Handle package selection.

        Args:
            package_data: Selected package data
        """
        package_name = package_data.get('code', 'Unknown')
        self.status_label.setText(f"Selected package: {package_name}")

    def _on_share_requested(self, config):
        """Handle share request from the share widget.

        Args:
            config: Dictionary with share configuration
        """
        package = config.get('package', {})
        vendor = config.get('vendor')
        package_name = package.get('code', 'Unknown')
        package_id = package.get('id')

        if vendor:
            vendor_code = vendor.get('code', 'Unknown')
            # Add package to vendor in the right pane
            self.vendor_category_view.add_package_to_vendor(package_id, package_name, vendor_code)
            self.status_label.setText(f"Assigned '{package_name}' to vendor '{vendor_code}'")
            logger.info(f"Package {package_id} assigned to vendor {vendor_code}")
        else:
            self.status_label.setText(f"Share requested for package: {package_name}")
            logger.info(f"Share requested: {config}")

    def _on_package_assigned(self, package_id, vendor_code):
        """Handle package assigned to vendor via drag and drop.

        Args:
            package_id: ID of the assigned package
            vendor_code: Code of the vendor
        """
        # Find the package name
        package_name = "Unknown"
        for pkg in self.packages_list:
            if pkg.get('id') == package_id:
                package_name = pkg.get('code', 'Unknown')
                break

        self.status_label.setText(f"Assigned package '{package_name}' to vendor '{vendor_code}'")
        logger.info(f"Package {package_id} assigned to vendor {vendor_code}")

    def set_status(self, message):
        """Set the status label text.

        Args:
            message: Status message to display
        """
        if self.status_label:
            self.status_label.setText(message)

    def refresh_vendors(self):
        """Refresh vendor data from ShotGrid.

        Call this after making changes to vendors or client users in settings.
        """
        if self.current_project_id:
            self._load_vendors_for_project(self.current_project_id)
            logger.info("Refreshed vendor data")

    def clear(self):
        """Clear the delivery tab data."""
        self.packages_list = []
        self.vendors_list = []
        self.package_share_widget.set_packages([])
        self.vendor_category_view.set_vendors([])
        self.status_label.setText("Ready")
