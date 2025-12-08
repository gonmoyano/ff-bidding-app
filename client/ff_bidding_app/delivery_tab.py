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

        # Check if package has already been shared to the selected vendor
        if self._check_duplicate_share():
            return  # Already shown warning to user

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

    def _check_duplicate_share(self):
        """Check if the package has already been shared to the selected vendor.

        Returns:
            bool: True if duplicate found (and warning shown), False otherwise
        """
        vendor = self.vendor_combo.currentData()
        if not vendor:
            return False  # No vendor selected, proceed

        package_name = self.current_package.get('code')
        if not package_name:
            return False

        try:
            delivery_tab = self._get_delivery_tab()
            if not delivery_tab or not hasattr(delivery_tab, 'sg_session'):
                return False

            sg_session = delivery_tab.sg_session
            current_rfq = delivery_tab.current_rfq

            if not current_rfq:
                return False

            rfq_id = current_rfq.get('id')
            vendor_id = vendor.get('id')
            vendor_name = vendor.get('code', 'Unknown')

            if not rfq_id or not vendor_id:
                return False

            # Check for existing share
            existing = sg_session.check_package_already_shared(
                package_name=package_name,
                vendor_id=vendor_id,
                rfq_id=rfq_id
            )

            if existing:
                # Format the date if available
                created_at = existing.get('created_at', '')
                if hasattr(created_at, 'strftime'):
                    date_str = created_at.strftime('%Y-%m-%d %H:%M')
                else:
                    date_str = str(created_at) if created_at else 'unknown date'

                QtWidgets.QMessageBox.warning(
                    self,
                    "Package Already Shared",
                    f"The package '{package_name}' has already been shared with "
                    f"vendor '{vendor_name}' on {date_str}.\n\n"
                    f"Each package can only be shared once per vendor."
                )
                logger.info(f"Duplicate share prevented: '{package_name}' already shared to '{vendor_name}'")
                return True

        except Exception as e:
            logger.error(f"Error checking for duplicate share: {e}", exc_info=True)
            # Don't block on error, proceed with share
            return False

        return False

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
                share_link = result['webViewLink']
                self.result_link.setText(share_link)
                self.copy_link_btn.setEnabled(True)
                self.result_group.setVisible(True)
                self.progress_label.setText("Upload complete!")
                logger.info(f"File shared successfully: {share_link}")

                # Create PackageTracking entity in ShotGrid
                self._create_package_tracking(config, share_link)
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
            QtCore.QTimer.singleShot(2000, lambda: self.progress_group.setVisible(False))

    def _create_package_tracking(self, config, share_link):
        """Create a PackageTracking entity in ShotGrid after successful share.

        Args:
            config: Share configuration dictionary with package and vendor info
            share_link: Google Drive share link
        """
        vendor = config.get('vendor')
        package = config.get('package', {})
        package_name = package.get('code', 'Unknown Package')

        if not vendor:
            logger.warning("No vendor selected, skipping PackageTracking creation")
            return

        try:
            delivery_tab = self._get_delivery_tab()
            if not delivery_tab:
                logger.warning("Could not access DeliveryTab for PackageTracking creation")
                return

            sg_session = delivery_tab.sg_session
            project_id = delivery_tab.current_project_id
            current_rfq = delivery_tab.current_rfq

            if not project_id or not current_rfq:
                logger.warning("Missing project_id or current_rfq for PackageTracking creation")
                return

            # Create the PackageTracking entity
            # Status codes: 'dlvr' = Delivered, 'dwnld' = Downloaded
            tracking = sg_session.create_package_tracking(
                project_id=project_id,
                package_name=package_name,
                share_link=share_link,
                vendor=vendor,
                rfq=current_rfq,
                status="dlvr"  # Delivered
            )

            if tracking:
                logger.info(f"Created PackageTracking {tracking.get('id')} for package '{package_name}' to vendor '{vendor.get('code')}'")
                # Refresh the vendor view to show the new tracking record
                delivery_tab._load_package_tracking_for_vendors()
            else:
                logger.warning("PackageTracking creation returned None")

        except Exception as e:
            logger.error(f"Failed to create PackageTracking: {e}", exc_info=True)

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


class PackageTrackingDetailsDialog(QtWidgets.QDialog):
    """Dialog for displaying package tracking details and allowing link copying."""

    def __init__(self, tracking_record, parent=None):
        """Initialize the dialog.

        Args:
            tracking_record: PackageTracking dictionary from ShotGrid
            parent: Parent widget
        """
        super().__init__(parent)
        self.tracking_record = tracking_record
        self.setWindowTitle("Package Details")
        self.setMinimumWidth(450)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)

        package_name = self.tracking_record.get('code', 'Unknown Package')
        # sg_share_link is a URL field stored as dict with 'url' and 'name' keys
        share_link_data = self.tracking_record.get('sg_share_link', {})
        if isinstance(share_link_data, dict):
            share_link = share_link_data.get('url', '')
        else:
            share_link = share_link_data or ''
        status = self.tracking_record.get('sg_status_list', 'Unknown')
        created_at = self.tracking_record.get('created_at', '')
        recipient = self.tracking_record.get('sg_recipient', {})
        recipient_name = recipient.get('name', 'Unknown') if isinstance(recipient, dict) else 'Unknown'

        # Header with package name and status
        header_layout = QtWidgets.QHBoxLayout()

        name_label = QtWidgets.QLabel(f"<b style='font-size: 16px;'>{package_name}</b>")
        header_layout.addWidget(name_label)
        header_layout.addStretch()

        # Map status codes to display names
        status_display = {
            'dlvr': 'Delivered',
            'dwnld': 'Downloaded',
            'acc': 'Accessed',
        }
        status_name = status_display.get(status, status)

        # Status badge with color based on status
        status_colors = {
            'dlvr': ('#2a4a2a', '#8fdf8f'),      # Delivered - green
            'dwnld': ('#2a4a5a', '#8fdfdf'),     # Downloaded - cyan
            'acc': ('#4a2a5a', '#df8fdf'),       # Accessed - purple
        }
        bg_color, text_color = status_colors.get(status, ('#3a3a3a', '#aaa'))

        status_badge = QtWidgets.QLabel(status_name)
        status_badge.setStyleSheet(f"""
            background-color: {bg_color};
            color: {text_color};
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        """)
        header_layout.addWidget(status_badge)
        layout.addLayout(header_layout)

        # Details section
        details_group = QtWidgets.QGroupBox("Details")
        details_layout = QtWidgets.QFormLayout(details_group)
        details_layout.setSpacing(8)

        # Recipient
        details_layout.addRow("Recipient:", QtWidgets.QLabel(recipient_name))

        # Created date
        if created_at:
            if hasattr(created_at, 'strftime'):
                date_str = created_at.strftime('%Y-%m-%d %H:%M')
            else:
                date_str = str(created_at)
            details_layout.addRow("Shared on:", QtWidgets.QLabel(date_str))

        layout.addWidget(details_group)

        # Share link section
        if share_link:
            link_group = QtWidgets.QGroupBox("Google Drive Share Link")
            link_layout = QtWidgets.QVBoxLayout(link_group)

            # Link display
            self.link_edit = QtWidgets.QLineEdit(share_link)
            self.link_edit.setReadOnly(True)
            self.link_edit.setStyleSheet("""
                QLineEdit {
                    background-color: #2a2a2a;
                    border: 1px solid #555;
                    border-radius: 4px;
                    padding: 8px;
                    color: #4a9eff;
                    font-size: 11px;
                }
            """)
            link_layout.addWidget(self.link_edit)

            # Button row
            btn_layout = QtWidgets.QHBoxLayout()
            btn_layout.addStretch()

            # Copy button
            self.copy_btn = QtWidgets.QPushButton("Copy Link")
            self.copy_btn.setMinimumWidth(100)
            self.copy_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4a6a4a;
                    border: 1px solid #5a7a5a;
                    border-radius: 4px;
                    padding: 8px 16px;
                    color: #ddd;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #5a7a5a;
                }
            """)
            self.copy_btn.clicked.connect(self._copy_link)
            btn_layout.addWidget(self.copy_btn)

            # Open button
            open_btn = QtWidgets.QPushButton("Open in Browser")
            open_btn.setMinimumWidth(120)
            open_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4a5a6a;
                    border: 1px solid #5a6a7a;
                    border-radius: 4px;
                    padding: 8px 16px;
                    color: #ddd;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #5a6a7a;
                }
            """)
            open_btn.clicked.connect(self._open_link)
            btn_layout.addWidget(open_btn)

            link_layout.addLayout(btn_layout)
            layout.addWidget(link_group)
        else:
            no_link_label = QtWidgets.QLabel("No share link available")
            no_link_label.setStyleSheet("color: #888; font-style: italic;")
            layout.addWidget(no_link_label)

        # Close button
        layout.addStretch()
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.setMinimumWidth(80)
        close_btn.clicked.connect(self.accept)

        close_layout = QtWidgets.QHBoxLayout()
        close_layout.addStretch()
        close_layout.addWidget(close_btn)
        layout.addLayout(close_layout)

    def _get_share_link_url(self):
        """Extract the URL from the share_link field.

        Returns:
            str: The share link URL or empty string
        """
        share_link_data = self.tracking_record.get('sg_share_link', {})
        if isinstance(share_link_data, dict):
            return share_link_data.get('url', '')
        return share_link_data or ''

    def _copy_link(self):
        """Copy the share link to clipboard."""
        share_link = self._get_share_link_url()
        if share_link:
            QtWidgets.QApplication.clipboard().setText(share_link)
            self.copy_btn.setText("Copied!")
            QtCore.QTimer.singleShot(1500, lambda: self.copy_btn.setText("Copy Link"))

    def _open_link(self):
        """Open the share link in the default browser."""
        share_link = self._get_share_link_url()
        if share_link:
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl(share_link))


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
        self.package_tracking = {}  # vendor_code -> list of PackageTracking records
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

    def set_package_tracking_for_vendor(self, vendor_code, tracking_records):
        """Set package tracking records for a vendor.

        Args:
            vendor_code: Code of the vendor
            tracking_records: List of PackageTracking dictionaries from ShotGrid
        """
        self.package_tracking[vendor_code] = tracking_records

        if vendor_code in self.vendor_groups:
            container = self.vendor_groups[vendor_code]['container']
            container.set_package_tracking(tracking_records)

            # Update group title with count
            count = len(tracking_records)
            self.vendor_groups[vendor_code]['group'].setTitle(
                f"{vendor_code} ({count} package{'s' if count != 1 else ''})"
            )

    def clear_all_tracking(self):
        """Clear all package tracking data from all vendors."""
        self.package_tracking.clear()
        for vendor_code, group_data in self.vendor_groups.items():
            container = group_data['container']
            container.clear_packages()
            group_data['group'].setTitle(f"{vendor_code} (0 packages)")


class ClickableFrame(QtWidgets.QFrame):
    """A QFrame that emits a clicked signal when clicked."""

    clicked = QtCore.Signal(object)  # Emits the tracking_record when clicked

    def __init__(self, tracking_record, parent=None):
        """Initialize the clickable frame.

        Args:
            tracking_record: PackageTracking dictionary to emit on click
            parent: Parent widget
        """
        super().__init__(parent)
        self.tracking_record = tracking_record

    def mousePressEvent(self, event):
        """Handle mouse press events."""
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit(self.tracking_record)
        super().mousePressEvent(event)


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
        self.package_widgets = {}  # package_id/tracking_id -> QWidget
        self.tracking_records = []  # List of PackageTracking records
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

    def set_package_tracking(self, tracking_records):
        """Set and display package tracking records from ShotGrid.

        Args:
            tracking_records: List of PackageTracking dictionaries from ShotGrid
        """
        self.clear_packages()
        self.tracking_records = tracking_records

        for record in tracking_records:
            self._add_tracking_widget(record)

    def clear_packages(self):
        """Clear all package widgets from the container."""
        # Remove all widgets
        for widget in list(self.package_widgets.values()):
            widget.deleteLater()
        self.package_widgets.clear()
        self.tracking_records = []

        # Show placeholder
        self.placeholder_label.show()

    def _add_tracking_widget(self, tracking_record):
        """Add a widget for a PackageTracking record.

        Args:
            tracking_record: PackageTracking dictionary from ShotGrid
        """
        tracking_id = tracking_record.get('id')
        if tracking_id in self.package_widgets:
            return  # Already exists

        # Hide placeholder
        self.placeholder_label.hide()

        package_name = tracking_record.get('code', 'Unknown Package')
        # sg_share_link is a URL field stored as dict with 'url' and 'name' keys
        share_link_data = tracking_record.get('sg_share_link', {})
        if isinstance(share_link_data, dict):
            share_link = share_link_data.get('url', '')
        else:
            share_link = share_link_data or ''
        status = tracking_record.get('sg_status_list', 'Unknown')

        # Map status codes to display names
        status_display = {
            'dlvr': 'Delivered',
            'dwnld': 'Downloaded',
            'acc': 'Accessed',
        }
        status_name = status_display.get(status, status)

        # Status-based colors (using status codes) - neutral background
        status_colors = {
            'dlvr': {  # Delivered - neutral with green badge
                'bg': '#3a3a3a', 'border': '#555', 'hover_bg': '#454545', 'hover_border': '#666',
                'badge_bg': '#2a4a2a', 'badge_text': '#8fdf8f'
            },
            'dwnld': {  # Downloaded - neutral with cyan badge
                'bg': '#3a3a3a', 'border': '#555', 'hover_bg': '#454545', 'hover_border': '#666',
                'badge_bg': '#2a4a5a', 'badge_text': '#8fdfdf'
            },
            'acc': {  # Accessed - neutral with purple badge
                'bg': '#3a3a3a', 'border': '#555', 'hover_bg': '#454545', 'hover_border': '#666',
                'badge_bg': '#4a2a5a', 'badge_text': '#df8fdf'
            },
        }
        colors = status_colors.get(status, status_colors['dlvr'])

        # Create clickable package widget
        package_widget = ClickableFrame(tracking_record)
        package_widget.clicked.connect(self._on_card_clicked)
        package_widget.setStyleSheet(f"""
            ClickableFrame {{
                background-color: {colors['bg']};
                border: 1px solid {colors['border']};
                border-radius: 4px;
                padding: 5px;
            }}
            ClickableFrame:hover {{
                background-color: {colors['hover_bg']};
                border: 1px solid {colors['hover_border']};
            }}
        """)
        package_widget.setCursor(QtCore.Qt.PointingHandCursor)

        widget_layout = QtWidgets.QVBoxLayout(package_widget)
        widget_layout.setContentsMargins(8, 5, 8, 5)
        widget_layout.setSpacing(3)

        # Top row: icon and name
        top_row = QtWidgets.QHBoxLayout()
        icon_label = QtWidgets.QLabel()
        icon_label.setPixmap(self.style().standardIcon(
            QtWidgets.QStyle.SP_DirIcon
        ).pixmap(20, 20))
        top_row.addWidget(icon_label)

        name_label = QtWidgets.QLabel(package_name)
        name_label.setStyleSheet("font-size: 11px; font-weight: bold; color: #ddd;")
        top_row.addWidget(name_label)
        top_row.addStretch()

        # Status badge with dynamic colors
        status_label = QtWidgets.QLabel(status_name)
        status_label.setStyleSheet(f"""
            background-color: {colors['badge_bg']};
            color: {colors['badge_text']};
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 9px;
            font-weight: bold;
        """)
        top_row.addWidget(status_label)

        widget_layout.addLayout(top_row)

        # Info row: click hint
        info_row = QtWidgets.QHBoxLayout()
        click_hint = QtWidgets.QLabel("Click for details")
        click_hint.setStyleSheet("color: #888; font-size: 9px; font-style: italic;")
        info_row.addWidget(click_hint)
        info_row.addStretch()

        # Share link indicator
        if share_link:
            link_indicator = QtWidgets.QLabel("🔗 Link available")
            link_indicator.setStyleSheet("color: #8fb8df; font-size: 9px;")
            info_row.addWidget(link_indicator)

        widget_layout.addLayout(info_row)

        self.package_widgets[tracking_id] = package_widget
        self._relayout_packages()

    def _on_card_clicked(self, tracking_record):
        """Handle package card click - open details dialog.

        Args:
            tracking_record: PackageTracking dictionary from ShotGrid
        """
        dialog = PackageTrackingDetailsDialog(tracking_record, self)
        dialog.exec()

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
            self.vendor_category_view.set_vendors([])
            self.package_share_widget.set_vendors([])
            self.status_label.setText("No RFQ selected")
            return

        # Load packages for this RFQ
        self._load_packages_for_rfq(rfq)

        # Load vendors assigned to this RFQ
        self._load_vendors_for_rfq(rfq)

        self.status_label.setText(f"Loaded packages for RFQ: {rfq.get('code', 'Unknown')}")

    def set_project(self, project_id):
        """Set the current project.

        Args:
            project_id: Project ID
        """
        self.current_project_id = project_id

        if not project_id:
            self.vendor_category_view.set_vendors([])
            self.package_share_widget.set_vendors([])
            return

        # Vendors are loaded when RFQ is set (from RFQ's sg_vendors field)

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

    def _load_vendors_for_rfq(self, rfq):
        """Load vendors assigned to the RFQ.

        Args:
            rfq: RFQ data dict with sg_vendors field
        """
        if not rfq:
            self.vendors_list = []
            self.vendor_category_view.set_vendors([])
            self.package_share_widget.set_vendors([])
            return

        try:
            # Get vendor IDs from RFQ's sg_vendors field
            sg_vendors = rfq.get("sg_vendors") or []
            vendor_ids = [v.get("id") for v in sg_vendors if isinstance(v, dict) and v.get("id")]

            if not vendor_ids:
                self.vendors_list = []
                self.vendor_category_view.set_vendors([])
                self.package_share_widget.set_vendors([])
                logger.info(f"No vendors assigned to RFQ {rfq.get('code', 'Unknown')}")
                return

            # Fetch full vendor data for the assigned vendors
            self.vendors_list = self.sg_session.get_vendors_by_ids(vendor_ids)
            self.vendor_category_view.set_vendors(self.vendors_list)
            self.package_share_widget.set_vendors(self.vendors_list)
            logger.info(f"Loaded {len(self.vendors_list)} vendors for RFQ {rfq.get('code', 'Unknown')}")

            # Load package tracking records for each vendor
            self._load_package_tracking_for_vendors()
        except Exception as e:
            logger.error(f"Error loading vendors for RFQ: {e}", exc_info=True)
            self.vendors_list = []
            self.vendor_category_view.set_vendors([])
            self.package_share_widget.set_vendors([])

    def _load_package_tracking_for_vendors(self):
        """Load PackageTracking records for each vendor and the current RFQ.

        This populates the vendor view with package cards that have been
        shared with each vendor, loaded from ShotGrid.
        Also checks Google Drive access and updates status to 'acc' if accessed.
        """
        if not self.current_rfq or not self.vendors_list:
            return

        rfq_id = self.current_rfq.get('id')
        if not rfq_id:
            return

        try:
            # Clear existing tracking data
            self.vendor_category_view.clear_all_tracking()

            # Get Google Drive service for access checking
            gdrive = get_gdrive_service()

            # Load tracking records for each vendor
            for vendor in self.vendors_list:
                vendor_id = vendor.get('id')
                vendor_code = vendor.get('code', 'Unknown')

                if not vendor_id:
                    continue

                # Get package tracking records for this vendor and RFQ
                tracking_records = self.sg_session.get_package_tracking_for_vendor_and_rfq(
                    vendor_id=vendor_id,
                    rfq_id=rfq_id
                )

                if tracking_records:
                    # Check Google Drive access for each record and update status if needed
                    updated_records = self._check_and_update_access_status(
                        tracking_records, gdrive
                    )
                    logger.info(f"Loaded {len(updated_records)} tracking records for vendor '{vendor_code}'")
                    self.vendor_category_view.set_package_tracking_for_vendor(vendor_code, updated_records)

        except Exception as e:
            logger.error(f"Error loading package tracking records: {e}", exc_info=True)

    def _check_and_update_access_status(self, tracking_records, gdrive):
        """Check Google Drive access for tracking records and update status.

        For each record with status 'dlvr' (Delivered), checks if the shared
        file has been accessed via Google Drive API. If accessed, updates
        the status to 'acc' (Accessed) in ShotGrid.

        Args:
            tracking_records: List of PackageTracking dictionaries
            gdrive: GoogleDriveService instance

        Returns:
            List of tracking records with potentially updated statuses
        """
        logger.info(f"=== Checking Google Drive access for {len(tracking_records)} tracking records ===")

        if not gdrive:
            logger.warning("Google Drive service is None")
            return tracking_records

        if not gdrive.is_available:
            logger.warning("Google Drive service not available (libraries not installed)")
            return tracking_records

        logger.info(f"Google Drive service available: {gdrive.is_available}")
        logger.info(f"Google Drive authenticated: {gdrive.is_authenticated}")

        updated_records = []

        for record in tracking_records:
            package_name = record.get('code', 'Unknown')
            current_status = record.get('sg_status_list', '')
            logger.info(f"--- Checking package '{package_name}' (current status: {current_status}) ---")

            # Only check access for 'dlvr' (Delivered) status
            # Don't re-check records that are already 'acc' or 'dwnld'
            if current_status != 'dlvr':
                logger.info(f"  Skipping: status is not 'dlvr' (is '{current_status}')")
                updated_records.append(record)
                continue

            # Extract share link URL
            share_link_data = record.get('sg_share_link', {})
            logger.info(f"  Share link data: {share_link_data}")
            if isinstance(share_link_data, dict):
                share_url = share_link_data.get('url', '')
            else:
                share_url = share_link_data or ''

            if not share_url:
                logger.warning(f"  No share URL found for package '{package_name}'")
                updated_records.append(record)
                continue

            logger.info(f"  Share URL: {share_url}")

            # Extract file ID from URL
            file_id = gdrive.extract_file_id_from_url(share_url)
            if not file_id:
                logger.warning(f"  Could not extract file ID from share link for record {record.get('id')}")
                updated_records.append(record)
                continue

            logger.info(f"  Extracted file ID: {file_id}")

            # Check if file has been accessed
            try:
                logger.info(f"  Calling check_file_accessed({file_id})...")
                access_info = gdrive.check_file_accessed(file_id)
                logger.info(f"  Access check result: {access_info}")

                if access_info and access_info.get('accessed'):
                    # Update status to 'acc' (Accessed) in ShotGrid
                    tracking_id = record.get('id')

                    logger.info(f"  Package '{package_name}' HAS BEEN ACCESSED!")
                    logger.info(f"    Access count: {access_info.get('access_count', 0)}")
                    logger.info(f"    Last access time: {access_info.get('access_time')}")
                    logger.info(f"  Updating ShotGrid status to 'acc'...")

                    try:
                        self.sg_session.update_package_tracking(
                            tracking_id,
                            {'sg_status_list': 'acc'}
                        )
                        # Update the local record to reflect the new status
                        record = dict(record)  # Make a copy to avoid modifying original
                        record['sg_status_list'] = 'acc'
                        logger.info(f"  SUCCESS: Updated tracking record {tracking_id} status to 'acc'")
                    except Exception as e:
                        logger.error(f"  FAILED to update tracking status in ShotGrid: {e}")
                else:
                    logger.info(f"  Package '{package_name}' has NOT been accessed yet")

            except Exception as e:
                logger.error(f"  ERROR checking Google Drive access for file {file_id}: {e}", exc_info=True)

            updated_records.append(record)

        logger.info(f"=== Finished checking Google Drive access ===")
        return updated_records

    def _load_vendors_for_project(self, project_id):
        """Load vendors for the project (used by refresh_vendors).

        Args:
            project_id: Project ID
        """
        # If we have a current RFQ, load vendors from it instead
        if self.current_rfq:
            self._load_vendors_for_rfq(self.current_rfq)
            return

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

        Call this after making changes to vendors, client users, or RFQ vendor assignments.
        """
        if self.current_rfq and self.current_rfq.get("id"):
            # Reload the RFQ to get updated sg_vendors field
            try:
                rfq_id = self.current_rfq["id"]
                updated_rfqs = self.sg_session.sg.find(
                    "CustomEntity04",
                    [["id", "is", rfq_id]],
                    ["id", "code", "sg_status_list", "sg_vfx_breakdown", "sg_vendors"]
                )
                if updated_rfqs:
                    self.current_rfq = updated_rfqs[0]
                    self._load_vendors_for_rfq(self.current_rfq)
                    logger.info("Refreshed vendor data from RFQ")
            except Exception as e:
                logger.error(f"Error refreshing RFQ vendor data: {e}", exc_info=True)
        elif self.current_project_id:
            self._load_vendors_for_project(self.current_project_id)
            logger.info("Refreshed vendor data")

    def clear(self):
        """Clear the delivery tab data."""
        self.packages_list = []
        self.vendors_list = []
        self.package_share_widget.set_packages([])
        self.vendor_category_view.set_vendors([])
        self.status_label.setText("Ready")
