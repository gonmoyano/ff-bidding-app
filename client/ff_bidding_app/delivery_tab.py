"""Delivery tab widget for managing package delivery to vendors."""
from PySide6 import QtWidgets, QtCore, QtGui
import logging

try:
    from .logger import logger
    from .bid_selector_widget import CollapsibleGroupBox
    from .settings import AppSettings
except ImportError:
    logger = logging.getLogger("FFPackageManager")
    from bid_selector_widget import CollapsibleGroupBox
    from settings import AppSettings


class PackageIconWidget(QtWidgets.QWidget):
    """Widget representing a package in the icon view."""

    clicked = QtCore.Signal(object)  # Signal emitted when package is clicked (package_data)
    doubleClicked = QtCore.Signal(object)  # Signal emitted when package is double-clicked (package_data)

    def __init__(self, package_data, parent=None, icon_size=64):
        """Initialize package icon widget.

        Args:
            package_data: Package data dictionary from ShotGrid
            parent: Parent widget
            icon_size: Size of the icon in pixels
        """
        super().__init__(parent)
        self.package_data = package_data
        self.icon_size = icon_size
        self._is_selected = False
        self._is_drag_source = False

        self.setAcceptDrops(False)  # Packages don't accept drops, vendors do
        self._setup_ui()

    def _setup_ui(self):
        """Setup the package icon UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        layout.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignCenter)

        # Package icon
        self.icon_label = QtWidgets.QLabel()
        self.icon_label.setAlignment(QtCore.Qt.AlignCenter)
        self._update_icon()
        layout.addWidget(self.icon_label)

        # Package name
        package_name = self.package_data.get('code', 'Unknown')
        self.name_label = QtWidgets.QLabel(package_name)
        self.name_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        self.name_label.setAlignment(QtCore.Qt.AlignCenter)
        self.name_label.setWordWrap(True)
        layout.addWidget(self.name_label)

        # Apply initial style
        self._update_style()

        # Enable drag
        self.setCursor(QtCore.Qt.OpenHandCursor)

    def _update_style(self):
        """Update the package widget styling based on current state."""
        if self._is_selected:
            self.setStyleSheet("""
                PackageIconWidget {
                    background-color: #2b3a4a;
                    border: 2px solid #4a9eff;
                    border-radius: 4px;
                }
            """)
        else:
            self.setStyleSheet("""
                PackageIconWidget {
                    background-color: #2b2b2b;
                    border: 1px solid #444;
                    border-radius: 4px;
                }
                PackageIconWidget:hover {
                    background-color: #353535;
                    border: 1px solid #555;
                }
            """)

    def _update_icon(self):
        """Update the package icon."""
        # Use a folder icon for packages
        self.icon_label.setPixmap(self.style().standardIcon(
            QtWidgets.QStyle.SP_DirIcon
        ).pixmap(self.icon_size, self.icon_size))

        # Apply border styling
        if self._is_selected:
            self.icon_label.setStyleSheet("""
                QLabel {
                    border: 3px solid #4a9eff;
                    border-radius: 4px;
                    padding: 2px;
                }
            """)
        else:
            self.icon_label.setStyleSheet("""
                QLabel {
                    border: 3px solid #2b2b2b;
                    border-radius: 4px;
                    padding: 2px;
                }
            """)

    def set_icon_size(self, size):
        """Set the icon size.

        Args:
            size: Icon size in pixels
        """
        self.icon_size = size
        self._update_icon()

    def set_selected(self, selected):
        """Set the selected state.

        Args:
            selected: True if selected, False otherwise
        """
        if self._is_selected != selected:
            self._is_selected = selected
            self._update_style()
            self._update_icon()

    def mousePressEvent(self, event):
        """Handle mouse press event."""
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_start_position = event.pos()
            self.clicked.emit(self.package_data)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Handle double-click event."""
        if event.button() == QtCore.Qt.LeftButton:
            self.doubleClicked.emit(self.package_data)
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move event for drag initiation."""
        if not (event.buttons() & QtCore.Qt.LeftButton):
            return

        if not hasattr(self, '_drag_start_position'):
            return

        # Check if we've moved enough to start a drag
        if (event.pos() - self._drag_start_position).manhattanLength() < QtWidgets.QApplication.startDragDistance():
            return

        # Start drag
        drag = QtGui.QDrag(self)
        mime_data = QtCore.QMimeData()

        # Store package ID and name in mime data
        package_id = self.package_data.get('id', 0)
        package_name = self.package_data.get('code', f'Package {package_id}')
        mime_data.setData("application/x-package-id", str(package_id).encode())
        mime_data.setData("application/x-package-name", package_name.encode())

        drag.setMimeData(mime_data)

        # Create drag pixmap
        pixmap = self.grab()
        drag.setPixmap(pixmap.scaled(80, 80, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        drag.setHotSpot(QtCore.QPoint(40, 40))

        self._is_drag_source = True
        self.setCursor(QtCore.Qt.ClosedHandCursor)

        # Execute drag
        drag.exec(QtCore.Qt.CopyAction)

        self._is_drag_source = False
        self.setCursor(QtCore.Qt.OpenHandCursor)


class PackageIconView(QtWidgets.QWidget):
    """Icon view widget for displaying packages."""

    packageSelected = QtCore.Signal(object)  # Signal emitted when a package is selected (package_data)
    packageDoubleClicked = QtCore.Signal(object)  # Signal emitted when a package is double-clicked

    def __init__(self, parent=None):
        """Initialize the package icon view."""
        super().__init__(parent)
        self.packages = {}  # package_id -> PackageIconWidget
        self.current_icon_size = 64
        self._selected_package_id = None

        # Load saved sizes from settings
        self.settings = QtCore.QSettings("FFBiddingApp", "DeliveryTab")
        self.current_icon_size = self.settings.value("package_icon_size", 64, type=int)

        # Debounce timer for resize events
        self.resize_timer = QtCore.QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self._relayout_packages)

        self._setup_ui()

    def _setup_ui(self):
        """Setup the package icon view UI."""
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # Toolbar with icon size slider
        toolbar_layout = QtWidgets.QHBoxLayout()

        toolbar_layout.addWidget(QtWidgets.QLabel("Icon Size:"))

        self.icon_size_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.icon_size_slider.setMinimum(32)
        self.icon_size_slider.setMaximum(128)
        self.icon_size_slider.setValue(self.current_icon_size)
        self.icon_size_slider.setTickPosition(QtWidgets.QSlider.NoTicks)
        self.icon_size_slider.setFixedWidth(150)
        self.icon_size_slider.valueChanged.connect(self._on_size_changed)
        toolbar_layout.addWidget(self.icon_size_slider)

        self.icon_size_label = QtWidgets.QLabel(str(self.current_icon_size))
        self.icon_size_label.setFixedWidth(30)
        self.icon_size_label.setAlignment(QtCore.Qt.AlignRight)
        toolbar_layout.addWidget(self.icon_size_label)

        toolbar_layout.addStretch()

        main_layout.addLayout(toolbar_layout)

        # Scroll area for packages
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        # Container for packages grid
        container = QtWidgets.QWidget()
        self.packages_layout = QtWidgets.QGridLayout(container)
        self.packages_layout.setSpacing(10)
        self.packages_layout.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)

        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area)

    def _on_size_changed(self, value):
        """Handle icon size slider change."""
        self.current_icon_size = value
        self.icon_size_label.setText(str(value))

        # Save to settings
        self.settings.setValue("package_icon_size", value)

        # Update all existing package icons
        for package_widget in self.packages.values():
            package_widget.set_icon_size(value)

        # Re-layout packages
        self._relayout_packages()

    def set_packages(self, packages_list):
        """Set the packages to display.

        Args:
            packages_list: List of package dictionaries from ShotGrid
        """
        # Clear existing packages
        for package_widget in self.packages.values():
            package_widget.deleteLater()
        self.packages.clear()

        # Clear existing layout
        while self.packages_layout.count():
            item = self.packages_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        # Add new packages
        for package_data in packages_list:
            package_id = package_data.get('id')
            if package_id:
                package_widget = PackageIconWidget(package_data, self, icon_size=self.current_icon_size)
                package_widget.clicked.connect(self._on_package_clicked)
                package_widget.doubleClicked.connect(self._on_package_double_clicked)
                self.packages[package_id] = package_widget

        # Schedule re-layout
        QtCore.QTimer.singleShot(50, self._relayout_packages)

    def _relayout_packages(self):
        """Re-layout packages in grid based on current pane width."""
        if not self.packages:
            return

        # Calculate columns based on pane width and icon size
        pane_width = self.width()
        if pane_width <= 0:
            pane_width = 250

        package_width = self.current_icon_size + 40
        columns = max(1, pane_width // package_width)

        # Get sorted package IDs
        package_ids = sorted(self.packages.keys())

        # Re-add all packages to grid
        for idx, package_id in enumerate(package_ids):
            package_widget = self.packages.get(package_id)
            if package_widget:
                # Remove from current position
                self.packages_layout.removeWidget(package_widget)
                # Add to new position
                row = idx // columns
                col = idx % columns
                self.packages_layout.addWidget(package_widget, row, col)
                package_widget.show()

    def resizeEvent(self, event):
        """Handle resize event to re-layout packages."""
        super().resizeEvent(event)
        if self.packages:
            self.resize_timer.stop()
            self.resize_timer.start(400)

    def _on_package_clicked(self, package_data):
        """Handle package click."""
        package_id = package_data.get('id')

        # Update selection state
        for pid, widget in self.packages.items():
            widget.set_selected(pid == package_id)

        self._selected_package_id = package_id
        self.packageSelected.emit(package_data)

    def _on_package_double_clicked(self, package_data):
        """Handle package double-click."""
        self.packageDoubleClicked.emit(package_data)

    def get_selected_package(self):
        """Get the currently selected package data."""
        if self._selected_package_id and self._selected_package_id in self.packages:
            return self.packages[self._selected_package_id].package_data
        return None


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
        columns = 3  # Number of columns
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

    def __init__(self, sg_session, parent=None):
        """Initialize the Delivery tab.

        Args:
            sg_session: ShotgridClient instance
            parent: Parent widget (PackageManagerApp)
        """
        super().__init__(parent)
        self.sg_session = sg_session
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

        # Left pane: Packages icon view
        packages_pane = QtWidgets.QWidget()
        packages_pane_layout = QtWidgets.QVBoxLayout(packages_pane)
        packages_pane_layout.setContentsMargins(0, 0, 0, 0)

        packages_header = QtWidgets.QLabel("Packages")
        packages_header.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        packages_pane_layout.addWidget(packages_header)

        self.package_icon_view = PackageIconView(self)
        self.package_icon_view.packageSelected.connect(self._on_package_selected)
        self.package_icon_view.packageDoubleClicked.connect(self._on_package_double_clicked)
        packages_pane_layout.addWidget(self.package_icon_view)

        self.main_splitter.addWidget(packages_pane)

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

        # Set initial splitter sizes (equal split)
        self.main_splitter.setSizes([400, 600])

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
            self.package_icon_view.set_packages([])
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
            return

        # Load vendors for this project
        self._load_vendors_for_project(project_id)

    def _load_packages_for_rfq(self, rfq):
        """Load packages linked to the RFQ.

        Args:
            rfq: RFQ data dict
        """
        if not rfq:
            self.packages_list = []
            self.package_icon_view.set_packages([])
            return

        try:
            rfq_id = rfq.get('id')
            if rfq_id:
                self.packages_list = self.sg_session.get_packages_for_rfq(rfq_id)
                self.package_icon_view.set_packages(self.packages_list)
                logger.info(f"Loaded {len(self.packages_list)} packages for RFQ {rfq_id}")
        except Exception as e:
            logger.error(f"Error loading packages for RFQ: {e}", exc_info=True)
            self.packages_list = []
            self.package_icon_view.set_packages([])

    def _load_vendors_for_project(self, project_id):
        """Load vendors for the project.

        Args:
            project_id: Project ID
        """
        if not project_id:
            self.vendors_list = []
            self.vendor_category_view.set_vendors([])
            return

        try:
            self.vendors_list = self.sg_session.get_vendors(project_id)
            self.vendor_category_view.set_vendors(self.vendors_list)
            logger.info(f"Loaded {len(self.vendors_list)} vendors for project {project_id}")
        except Exception as e:
            logger.error(f"Error loading vendors for project: {e}", exc_info=True)
            self.vendors_list = []
            self.vendor_category_view.set_vendors([])

    def _on_package_selected(self, package_data):
        """Handle package selection.

        Args:
            package_data: Selected package data
        """
        package_name = package_data.get('code', 'Unknown')
        self.status_label.setText(f"Selected package: {package_name}")

    def _on_package_double_clicked(self, package_data):
        """Handle package double-click.

        Args:
            package_data: Double-clicked package data
        """
        package_name = package_data.get('code', 'Unknown')
        logger.info(f"Package double-clicked: {package_name}")
        # Future: Could open package details dialog

    def _on_package_assigned(self, package_id, vendor_code):
        """Handle package assigned to vendor.

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

        # Future: Could save the assignment to ShotGrid

    def set_status(self, message):
        """Set the status label text.

        Args:
            message: Status message to display
        """
        if self.status_label:
            self.status_label.setText(message)

    def clear(self):
        """Clear the delivery tab data."""
        self.packages_list = []
        self.vendors_list = []
        self.package_icon_view.set_packages([])
        self.vendor_category_view.set_vendors([])
        self.status_label.setText("Ready")
