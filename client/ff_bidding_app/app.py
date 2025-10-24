from PySide6 import QtWidgets, QtCore, QtGui
import json
import logging
from datetime import datetime, date
from pathlib import Path
import sys

# Try relative imports first, fall back to absolute
try:
    from .shotgrid import ShotgridClient
    from .package_data_treeview import PackageTreeView, CustomCheckBox
    from .packages_tab import PackagesTab
    from .bidding_tab import BiddingTab
    from .logger import logger
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

    # Setup basic logger for standalone mode
    try:
        log_dir = Path(__file__).parent.parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"ff_package_manager_{timestamp}.log"

        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        logger = logging.getLogger("FFPackageManager")
        logger.info(f"Standalone mode - logging to: {log_file}")
    except Exception as e:
        print(f"Could not setup file logging: {e}")
        logging.basicConfig(level=logging.DEBUG)
        logger = logging.getLogger("FFPackageManager")


class PackageManagerApp(QtWidgets.QMainWindow):
    """Main application window."""

    def __init__(self, sg_url, sg_script_name, sg_api_key, output_directory, parent=None):
        try:
            logger.info("Calling super().__init__()...")
            super().__init__(parent)
            logger.info("super().__init__() completed")

            self.sg_url = sg_url
            self.sg_script_name = sg_script_name
            self.sg_api_key = sg_api_key

            self.sg_session = ShotgridClient(
                site_url=self.sg_url,
                script_name=self.sg_script_name,
                api_key=self.sg_api_key
            )
            logger.info(f"Shotgrid Session: {self.sg_session}")
            self.output_directory = output_directory or str(Path.home() / "shotgrid_packages")

            self.setWindowTitle("Fireframe - Bidding Manager")
            self.setMinimumSize(1400, 700)

            self._build_ui()

            # Auto-load the latest project on startup
            logger.info("Auto-loading latest project...")
            self._auto_load_latest_project()

            et = self.sg_session.get_vfx_breakdown_entity_type()
            logger.info(f"VFX Breakdown entity type resolved to: {et}")


        except Exception as e:
            logger.error("=" * 60)
            logger.error(f"CRITICAL ERROR in __init__: {e}", exc_info=True)
            logger.error("=" * 60)
            raise

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
            font-family: 'Segoe UI', Arial, sans-serif;
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
        logger.info("Dark theme applied to application")

    def _build_ui(self):
        try:
            central_widget = QtWidgets.QWidget()
            self.setCentralWidget(central_widget)
            main_layout = QtWidgets.QVBoxLayout(central_widget)

            # Header
            header_layout = QtWidgets.QHBoxLayout()
            title_label = QtWidgets.QLabel("Bidding Manager")
            title_font = title_label.font()
            title_font.setPointSize(16)
            title_font.setBold(True)
            title_label.setFont(title_font)
            header_layout.addWidget(title_label)
            header_layout.addStretch()
            main_layout.addLayout(header_layout)

            # Top section: SG Project and RFQ side by side
            top_section_layout = QtWidgets.QHBoxLayout()

            # Shotgrid Project Group
            sg_project_group = self._create_sg_project_group()
            top_section_layout.addWidget(sg_project_group)

            # Request for Quotation Group
            rfq_group = self._create_rfq_group()
            top_section_layout.addWidget(rfq_group)

            main_layout.addLayout(top_section_layout)

            # Tabbed section
            self.tab_widget = QtWidgets.QTabWidget()

            # Create Bidding tab (contains VFX Breakdown as nested tab)
            bidding_tab = self._create_bidding_tab()
            self.tab_widget.addTab(bidding_tab, "Bidding")

            # Create Packages tab
            packages_tab = self._create_packages_tab()
            self.tab_widget.addTab(packages_tab, "Packages")

            # Create Delivery tab
            delivery_tab = self._create_delivery_tab()
            self.tab_widget.addTab(delivery_tab, "Delivery")

            main_layout.addWidget(self.tab_widget)

            logger.info("_build_ui() completed successfully")

        except Exception as e:
            logger.error(f"Error in _build_ui: {e}", exc_info=True)
            raise

    def _create_sg_project_group(self):
        """Create the Shotgrid Project group."""
        sg_group = QtWidgets.QGroupBox("Shotgrid Project")
        sg_layout = QtWidgets.QVBoxLayout(sg_group)

        # Project selector row
        project_row = QtWidgets.QHBoxLayout()

        project_label = QtWidgets.QLabel("Select Project:")
        project_row.addWidget(project_label)

        self.sg_project_combo = QtWidgets.QComboBox()
        self.sg_project_combo.setMinimumWidth(200)
        self.sg_project_combo.currentIndexChanged.connect(self._on_sg_project_changed)
        project_row.addWidget(self.sg_project_combo)

        load_sg_btn = QtWidgets.QPushButton("Load from SG")
        load_sg_btn.clicked.connect(self._load_sg_projects)
        project_row.addWidget(load_sg_btn)

        project_row.addStretch()
        sg_layout.addLayout(project_row)

        # Project info display
        info_layout = QtWidgets.QFormLayout()

        self.sg_project_id_label = QtWidgets.QLabel("-")
        info_layout.addRow("Project ID:", self.sg_project_id_label)

        self.sg_project_status_label = QtWidgets.QLabel("-")
        info_layout.addRow("Status:", self.sg_project_status_label)

        sg_layout.addLayout(info_layout)

        return sg_group

    def _create_rfq_group(self):
        """Create the Request for Quotation group."""
        rfq_group = QtWidgets.QGroupBox("Request for Quotation")
        rfq_layout = QtWidgets.QVBoxLayout(rfq_group)

        # RFQ selector row
        rfq_row = QtWidgets.QHBoxLayout()

        rfq_label = QtWidgets.QLabel("Select RFQ:")
        rfq_row.addWidget(rfq_label)

        self.rfq_combo = QtWidgets.QComboBox()
        self.rfq_combo.setMinimumWidth(200)
        self.rfq_combo.currentIndexChanged.connect(self._on_rfq_changed)
        rfq_row.addWidget(self.rfq_combo)

        rfq_row.addStretch()
        rfq_layout.addLayout(rfq_row)

        # RFQ info display
        rfq_info_layout = QtWidgets.QFormLayout()

        self.rfq_id_label = QtWidgets.QLabel("-")
        rfq_info_layout.addRow("RFQ ID:", self.rfq_id_label)

        self.rfq_status_label = QtWidgets.QLabel("-")
        rfq_info_layout.addRow("RFQ Status:", self.rfq_status_label)

        self.rfq_bid_label = QtWidgets.QLabel("-")
        rfq_info_layout.addRow("Current Bid:", self.rfq_bid_label)

        rfq_layout.addLayout(rfq_info_layout)

        return rfq_group

    def _create_packages_tab(self):
        """Create the Packages tab content."""
        self.packages_tab = PackagesTab(self.sg_session, self.output_directory, parent=self)
        # Keep a reference to status_label for backward compatibility
        self.status_label = self.packages_tab.status_label
        return self.packages_tab

    def _create_delivery_tab(self):
        """Create the Delivery tab content."""
        delivery_widget = QtWidgets.QWidget()
        delivery_layout = QtWidgets.QVBoxLayout(delivery_widget)

        # Placeholder content
        label = QtWidgets.QLabel("Delivery")
        label.setStyleSheet("font-size: 18px; font-weight: bold; padding: 20px;")
        delivery_layout.addWidget(label)

        info_label = QtWidgets.QLabel("Delivery content will be displayed here.")
        info_label.setStyleSheet("padding: 20px;")
        delivery_layout.addWidget(info_label)

        delivery_layout.addStretch()

        return delivery_widget

    def _create_bidding_tab(self):
        """Create the Bidding tab content."""
        self.bidding_tab = BiddingTab(self.sg_session, parent=self)
        return self.bidding_tab

    def _load_sg_projects(self):
        """Load Shotgrid projects."""
        logger.info("_load_sg_projects() started")
        self.sg_project_combo.clear()
        self.rfq_combo.clear()

        # Add empty items
        self.sg_project_combo.addItem("-- Select a project --", None)
        self.rfq_combo.addItem("-- Select RFQ --", None)

        try:
            projects = self.sg_session.get_projects(status="Bidding")

            for project in projects:
                display_text = f"{project['code']} - {project['name']}"
                self.sg_project_combo.addItem(display_text, project)

            self.status_label.setText(f"Loaded {len(projects)} Bidding projects")
            logger.info(f"_load_sg_projects() completed - {len(projects)} projects")

        except Exception as e:
            logger.error(f"Error loading projects: {e}", exc_info=True)
            self.status_label.setText(f"Error loading projects: {str(e)}")

    def _auto_load_latest_project(self):
        """Automatically load the most recently created project on startup."""
        try:
            logger.info("Attempting to auto-load latest project...")

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
                logger.info(f"Latest project found: {latest_project['code']} (ID: {latest_project['id']})")

                # Load all projects into combo box first
                self._load_sg_projects()

                # Find and select the latest project in the combo box
                for index in range(self.sg_project_combo.count()):
                    project_data = self.sg_project_combo.itemData(index)
                    if project_data and project_data.get('id') == latest_project['id']:
                        self.sg_project_combo.setCurrentIndex(index)
                        logger.info(f"Auto-selected latest project at index {index}")
                        break
            else:
                logger.info("No Bidding projects found")
                self._load_sg_projects()

        except Exception as e:
            logger.error(f"Error auto-loading latest project: {e}", exc_info=True)
            # Fallback to just loading the projects normally
            self._load_sg_projects()

    def _on_sg_project_changed(self, index):
        """Handle SG project selection."""
        project = self.sg_project_combo.itemData(index)

        if project:
            self.sg_project_id_label.setText(str(project['id']))
            self.sg_project_status_label.setText(project.get('sg_status', 'Unknown'))
            logger.info(f"SG project selected: {project['code']} (ID: {project['id']})")

            # Load RFQs for this project
            self._load_rfqs(project['id'])
        else:
            self.sg_project_id_label.setText("-")
            self.sg_project_status_label.setText("-")
            self.rfq_combo.clear()
            self.rfq_combo.addItem("-- Select RFQ --", None)
            self.rfq_id_label.setText("-")
            self.rfq_status_label.setText("-")
            if hasattr(self, "packages_tab"):
                self.packages_tab.clear()

        current_rfq = self.rfq_combo.itemData(self.rfq_combo.currentIndex())
        if hasattr(self, "vfx_breakdown_tab"):
            self.vfx_breakdown_tab.populate_vfx_breakdown_combo(current_rfq)

    def _load_rfqs(self, project_id):
        """Load RFQs for the selected project."""
        logger.info(f"_load_rfqs() started for project {project_id}")
        self.rfq_combo.clear()

        # Add empty item
        self.rfq_combo.addItem("-- Select RFQ --", None)

        try:
            rfqs = self.sg_session.get_rfqs(project_id,
                                            fields=["id", "code", "sg_status_list",
                                                    "sg_early_bid", "sg_early_bid.code", "sg_early_bid.sg_bid_type",
                                                    "sg_turnover_bid", "sg_turnover_bid.code", "sg_turnover_bid.sg_bid_type",
                                                    "created_at"])

            if rfqs:
                logger.info(f"DEBUG: First RFQ data = {rfqs[0]}")

            for rfq in rfqs:
                display_text = f"{rfq.get('code', 'N/A')}"
                self.rfq_combo.addItem(display_text, rfq)

            logger.info(f"Loaded {len(rfqs)} RFQs for project {project_id}")

            if len(rfqs) == 0:
                self.status_label.setText("No RFQs found for this project")
            else:
                self.status_label.setText(f"Loaded {len(rfqs)} RFQs")

                # Auto-select the latest RFQ (first one since get_rfqs returns newest first)
                if len(rfqs) > 0:
                    self.rfq_combo.setCurrentIndex(1)  # Index 1 because index 0 is "-- Select RFQ --"
                    logger.info(f"Auto-selected latest RFQ: {rfqs[0].get('code', 'N/A')}")

        except Exception as e:
            logger.error(f"Error loading RFQs: {e}", exc_info=True)
            self.status_label.setText(f"Error loading RFQs: {str(e)}")

    def _on_rfq_changed(self, index):
        """Handle RFQ selection: update labels, tree, and default-select its linked Breakdown."""
        rfq = self.rfq_combo.itemData(index)

        if rfq:
            # Labels
            self.rfq_id_label.setText(str(rfq["id"]))
            self.rfq_status_label.setText(rfq.get("sg_status_list", "Unknown"))

            # Show currently linked Bid under the RFQ selector
            # Check Early Bid first, then Turnover Bid
            linked_bid = rfq.get("sg_early_bid")
            if not linked_bid:
                linked_bid = rfq.get("sg_turnover_bid")

            logger.info(f"DEBUG: linked_bid = {linked_bid}")
            logger.info(f"DEBUG: linked_bid type = {type(linked_bid)}")
            if linked_bid:
                if isinstance(linked_bid, dict):
                    logger.info(f"DEBUG: linked_bid keys = {list(linked_bid.keys())}")
                    logger.info(f"DEBUG: linked_bid['code'] = {linked_bid.get('code')}")
                    logger.info(f"DEBUG: linked_bid['sg_bid_type'] = {linked_bid.get('sg_bid_type')}")

            if isinstance(linked_bid, dict):
                bid_name = linked_bid.get("code") or f"Bid {linked_bid.get('id')}"
                bid_type = linked_bid.get("sg_bid_type", "")
                label_text = f"{bid_name} ({bid_type})" if bid_type else bid_name
            elif isinstance(linked_bid, list) and linked_bid:
                item = linked_bid[0]
                bid_name = item.get("code") or f"Bid {item.get('id')}"
                bid_type = item.get("sg_bid_type", "")
                label_text = f"{bid_name} ({bid_type})" if bid_type else bid_name
            else:
                label_text = "-"
            if hasattr(self, "rfq_bid_label"):
                self.rfq_bid_label.setText(label_text)

            logger.info(f"RFQ selected: {rfq.get('code', 'N/A')} (ID: {rfq['id']})")

            # Update the package data tree with RFQ data
            if hasattr(self, "packages_tab"):
                self.packages_tab.set_rfq(rfq)

            # Update the bidding tab with RFQ data
            if hasattr(self, "bidding_tab"):
                self.bidding_tab.set_rfq(rfq)
        else:
            self.rfq_id_label.setText("-")
            self.rfq_status_label.setText("-")
            if hasattr(self, "rfq_bid_label"):
                self.rfq_bid_label.setText("-")
            if hasattr(self, "packages_tab"):
                self.packages_tab.clear()

    def showEvent(self, event):
        """Called when window is shown."""
        logger.info("showEvent() - Window is being shown")
        super().showEvent(event)

    def closeEvent(self, event):
        """Called when window is closed."""
        logger.info("closeEvent() - Window is being closed")
        super().closeEvent(event)