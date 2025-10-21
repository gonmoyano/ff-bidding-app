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
    from .logger import logger
except ImportError:
    # Standalone mode - add to path and import
    import os

    current_dir = Path(__file__).parent
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))

    from shotgrid import ShotgridClient
    from package_data_treeview import PackageTreeView, CustomCheckBox

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

            # Cached schema information for VFX Breakdowns
            self.vfx_breakdown_entity_type = None
            self.vfx_breakdown_field_names = []
            self.vfx_breakdown_field_labels = {}

            # Fields to display for VFX Breakdown, in order
            self.vfx_breakdown_field_allowlist = [
                "id",
                "code",
                "sg_beat_id",
                "sg_vfx_breakdown_scene",
                "sg_page",
                "sg_script_excerpt",
                "description",
                "sg_vfx_type",
                "sg_complexity",
                "sg_category",
                "sg_vfx_description",
                "sg_numer_of_shots",  # your original spelling
                "sg_number_of_shots",  # fallback if schema uses this spelling
            ]

            # Human-friendly labels for the table
            self.vfx_breakdown_label_overrides = {
                "id": "ID",
                "code": "Code",
                "sg_beat_id": "Beat ID",
                "sg_vfx_breakdown_scene": "Scene",
                "sg_page": "Page",
                "sg_script_excerpt": "Script Excerpt",
                "description": "Description",
                "sg_vfx_type": "VFX Type",
                "sg_complexity": "Complexity",
                "sg_category": "Category",
                "sg_vfx_description": "VFX Description",
                "sg_numer_of_shots": "# Shots",
                "sg_number_of_shots": "# Shots",
            }

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

            # Create VFX Breakdown tab (left of Packages)
            vfx_breakdown_tab = self._create_vfx_breakdown_tab()
            self.tab_widget.addTab(vfx_breakdown_tab, "VFX Breakdown")

            # Create Packages tab (middle)
            packages_tab = self._create_packages_tab()
            self.tab_widget.addTab(packages_tab, "Packages")

            # Create Delivery tab (right of Packages)
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

        self.rfq_vfx_breakdown_label = QtWidgets.QLabel("-")
        rfq_info_layout.addRow("VFX Breakdown:", self.rfq_vfx_breakdown_label)

        rfq_layout.addLayout(rfq_info_layout)

        return rfq_group

    def _create_vfx_breakdown_tab(self):
        """Create the VFX Breakdown tab content."""
        vfx_breakdown_widget = QtWidgets.QWidget()
        vfx_breakdown_layout = QtWidgets.QVBoxLayout(vfx_breakdown_widget)
        vfx_breakdown_layout.setContentsMargins(6, 6, 6, 6)

        selector_group = QtWidgets.QGroupBox("VFX Breakdowns")
        selector_layout = QtWidgets.QVBoxLayout(selector_group)

        selector_row = QtWidgets.QHBoxLayout()
        selector_label = QtWidgets.QLabel("Select VFX Breakdown:")
        selector_row.addWidget(selector_label)

        self.vfx_breakdown_combo = QtWidgets.QComboBox()
        self.vfx_breakdown_combo.setMinimumWidth(250)
        self.vfx_breakdown_combo.currentIndexChanged.connect(self._on_vfx_breakdown_changed)
        selector_row.addWidget(self.vfx_breakdown_combo, stretch=1)

        self.vfx_breakdown_set_btn = QtWidgets.QPushButton("Set as Current")
        self.vfx_breakdown_set_btn.setEnabled(False)
        self.vfx_breakdown_set_btn.clicked.connect(self._on_set_current_vfx_breakdown)

        selector_row.addWidget(self.vfx_breakdown_set_btn)

        self.vfx_breakdown_refresh_btn = QtWidgets.QPushButton("Refresh")
        self.vfx_breakdown_refresh_btn.clicked.connect(self._refresh_vfx_breakdowns)
        selector_row.addWidget(self.vfx_breakdown_refresh_btn)

        selector_layout.addLayout(selector_row)

        self.vfx_breakdown_status_label = QtWidgets.QLabel("Select an RFQ to view VFX Breakdowns.")
        self.vfx_breakdown_status_label.setObjectName("vfxBreakdownStatusLabel")
        self.vfx_breakdown_status_label.setStyleSheet("color: #a0a0a0; padding: 2px 0;")
        selector_layout.addWidget(self.vfx_breakdown_status_label)

        vfx_breakdown_layout.addWidget(selector_group)

        self.vfx_breakdown_table = QtWidgets.QTableWidget()
        # Column order you requested:
        self.vfx_beat_columns = [
            "id", "code", "sg_beat_id", "sg_vfx_breakdown_scene", "sg_page",
            "sg_script_excerpt", "description", "sg_vfx_type", "sg_complexity",
            "sg_category", "sg_vfx_description", "sg_numer_of_shots",
            "updated_at", "updated_by"  # new
        ]

        headers = [
            "ID", "Code", "Beat ID", "Scene", "Page",
            "Script Excerpt", "Description", "VFX Type", "Complexity",
            "Category", "VFX Description", "# Shots",
            "Updated At", "Updated By"  # new
        ]

        self.vfx_breakdown_table = QtWidgets.QTableWidget()
        self.vfx_breakdown_table.setColumnCount(len(self.vfx_beat_columns))
        self.vfx_breakdown_table.setHorizontalHeaderLabels(headers)
        self.vfx_breakdown_table.horizontalHeader().setStretchLastSection(False)
        self.vfx_breakdown_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        self.vfx_breakdown_table.setAlternatingRowColors(False)
        self.vfx_breakdown_table.setWordWrap(True)

        self.vfx_breakdown_table.setAlternatingRowColors(False)  # no zebra

        hdr = self.vfx_breakdown_table.horizontalHeader()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)  # we'll set widths manually

        vfx_breakdown_layout.addWidget(self.vfx_breakdown_table)

        return vfx_breakdown_widget

    def _on_set_current_vfx_breakdown(self):
        """Set the selected VFX Breakdown as the current one for the selected RFQ."""
        rfq = self.rfq_combo.itemData(self.rfq_combo.currentIndex())
        if not rfq:
            QtWidgets.QMessageBox.warning(self, "No RFQ selected", "Please select an RFQ first.")
            return

        idx = self.vfx_breakdown_combo.currentIndex()
        breakdown = self.vfx_breakdown_combo.itemData(idx)
        if not breakdown:
            QtWidgets.QMessageBox.warning(self, "No Breakdown selected", "Please select a VFX Breakdown from the list.")
            return

        rfq_id = rfq["id"]
        br_id = breakdown.get("id")
        br_type = breakdown.get("type", "CustomEntity01")
        logger.info(f"Updating RFQ {rfq_id} sg_vfx_breakdown -> {br_type}({br_id})")

        try:
            # Update on ShotGrid (helper handles multi vs single payload)
            self.sg_session.update_rfq_vfx_breakdown(rfq_id, breakdown)
        except Exception as e:
            logger.error(f"Failed to update RFQ sg_vfx_breakdown: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to set current VFX Breakdown:\n{e}")
            return

        # Refresh this RFQ from SG to keep local data accurate (so reloads are correct)
        try:
            updated_rfq = self.sg_session.get_entity_by_id(
                "CustomEntity04",
                rfq_id,
                fields=["id", "code", "sg_vfx_breakdown", "sg_status_list", "created_at"]
            )
            # Replace combo item data with the fresh dict
            self.rfq_combo.setItemData(self.rfq_combo.currentIndex(), updated_rfq)
            rfq = updated_rfq  # use fresh one below
            logger.info(f"RFQ {rfq_id} refreshed with latest sg_vfx_breakdown link.")
        except Exception as e:
            logger.warning(f"Failed to refresh RFQ after update: {e}")

        # Update label under RFQ combo
        linked = rfq.get("sg_vfx_breakdown")
        if isinstance(linked, dict):
            label_text = linked.get("code") or linked.get("name") or f"ID {linked.get('id')}"
        elif isinstance(linked, list) and linked:
            item = linked[0]
            label_text = item.get("code") or item.get("name") or f"ID {item.get('id')}"
        else:
            label_text = "-"
        if hasattr(self, "rfq_vfx_breakdown_label"):
            self.rfq_vfx_breakdown_label.setText(label_text)

        # Re-run the RFQ change flow to sync combo default selection & Beats table
        self._on_rfq_changed(self.rfq_combo.currentIndex())

        QtWidgets.QMessageBox.information(self, "Updated", "Current VFX Breakdown set for this RFQ.")

    def _autosize_beat_columns(self, min_px=60, max_px=600, extra_padding=24):
        """Size each Beats table column to fit its content (header + cells)."""
        if not hasattr(self, "vfx_breakdown_table"):
            return

        table = self.vfx_breakdown_table
        fm = table.fontMetrics()
        header = table.horizontalHeader()

        # Loop columns
        for c in range(table.columnCount()):
            # Start with header text width
            header_text = table.horizontalHeaderItem(c).text() if table.horizontalHeaderItem(c) else ""
            max_w = fm.horizontalAdvance(header_text)

            # Consider all row items in this column
            for r in range(table.rowCount()):
                it = table.item(r, c)
                if it:
                    # account for multi-line text roughly by measuring each line
                    text = it.text()
                    # quick split on '\n' to avoid underestimating long wrapped cells
                    for line in text.splitlines() or [""]:
                        max_w = max(max_w, fm.horizontalAdvance(line))

            # Add padding for cell margins + sort indicator etc.
            target = max(min_px, min(max_w + extra_padding, max_px))
            table.setColumnWidth(c, target)

    def _create_packages_tab(self):
        """Create the Packages tab content."""
        packages_widget = QtWidgets.QWidget()
        packages_layout = QtWidgets.QVBoxLayout(packages_widget)
        packages_layout.setContentsMargins(0, 0, 0, 0)

        # Splitter for left and right panels
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)

        # Left panel: Data to Fetch + Output Settings
        left_panel = self._create_packages_left_panel()
        splitter.addWidget(left_panel)

        # Right panel: Package Data tree
        self.package_data_tree = PackageTreeView()
        self.package_data_tree.set_sg_session(self.sg_session)
        splitter.addWidget(self.package_data_tree)

        # Set initial sizes (40% left, 60% right)
        splitter.setSizes([400, 600])
        packages_layout.addWidget(splitter)

        # Bottom section: Status + Create Package button
        bottom_layout = QtWidgets.QHBoxLayout()

        self.status_label = QtWidgets.QLabel("Ready")
        bottom_layout.addWidget(self.status_label)
        bottom_layout.addStretch()

        create_package_btn = QtWidgets.QPushButton("Create Data Package")
        create_package_btn.setObjectName("createPackageBtn")
        create_package_btn.clicked.connect(self._create_package)
        bottom_layout.addWidget(create_package_btn)

        packages_layout.addLayout(bottom_layout)

        return packages_widget

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

    # ------------------------------------------------------------------
    # VFX Breakdown helpers
    # ------------------------------------------------------------------

    def _normalize_label(self, raw):
        if raw is None:
            return ""
        if isinstance(raw, str):
            return raw
        if isinstance(raw, dict):
            for k in ("label", "display_name", "name", "title", "value"):
                v = raw.get(k)
                if isinstance(v, str) and v.strip():
                    return v
            try:
                return json.dumps(raw, default=str)
            except Exception:
                return str(raw)
        return str(raw)

    def _refresh_vfx_breakdowns(self):
        """Reload the VFX Breakdown list for the current RFQ."""

        if not hasattr(self, "vfx_breakdown_combo"):
            return

        current_data = self.vfx_breakdown_combo.currentData()
        current_id = current_data.get("id") if isinstance(current_data, dict) else None

        rfq = self.rfq_combo.itemData(self.rfq_combo.currentIndex()) if self.rfq_combo else None
        self._populate_vfx_breakdown_combo(rfq, auto_select=False)

        if current_id:
            self._select_vfx_breakdown_by_id(current_id)

    def _select_vfx_breakdown_by_id(self, entity_id):
        if not entity_id or not hasattr(self, "vfx_breakdown_combo"):
            return False

        for index in range(self.vfx_breakdown_combo.count()):
            breakdown = self.vfx_breakdown_combo.itemData(index)
            if isinstance(breakdown, dict) and breakdown.get("id") == entity_id:
                self.vfx_breakdown_combo.setCurrentIndex(index)
                return True
        return False

    def _populate_vfx_breakdown_combo(self, _rfq=None, auto_select=True):
        if not hasattr(self, "vfx_breakdown_combo"):
            return

        self.vfx_breakdown_combo.blockSignals(True)
        self.vfx_breakdown_combo.clear()
        self.vfx_breakdown_combo.addItem("-- Select VFX Breakdown --", None)

        breakdowns = []
        try:
            proj = self.sg_project_combo.itemData(self.sg_project_combo.currentIndex())
            if proj:
                logger.info(f"Loading ALL VFX Breakdowns in Project {proj.get('code')} (ID {proj.get('id')})")
                breakdowns = self.sg_session.get_vfx_breakdowns(proj["id"], fields=["id", "code", "name", "updated_at"])
            else:
                logger.info("No project selected; cannot load project breakdowns.")
        except Exception as e:
            logger.error(f"Error populating VFX Breakdown list: {e}", exc_info=True)
            breakdowns = []

        for breakdown in breakdowns:
            label = breakdown.get("code") or breakdown.get("name") or f"ID {breakdown.get('id', 'N/A')}"
            self.vfx_breakdown_combo.addItem(label, breakdown)

        self.vfx_breakdown_combo.blockSignals(False)

        # Enable Set button only if there are options and an RFQ is selected
        if hasattr(self, "vfx_breakdown_set_btn"):
            rfq_selected = bool(self.rfq_combo.itemData(self.rfq_combo.currentIndex()))
            self.vfx_breakdown_set_btn.setEnabled(rfq_selected and len(breakdowns) > 0)

        # Status & selection
        if breakdowns:
            self._set_vfx_breakdown_status(f"Loaded {len(breakdowns)} VFX Breakdown(s) in project.")
            # Optionally auto-select the currently linked one if RFQ has it
            rfq = self.rfq_combo.itemData(self.rfq_combo.currentIndex())
            linked = (rfq or {}).get("sg_vfx_breakdown")
            linked_id = linked.get("id") if isinstance(linked, dict) else None
            if linked_id:
                # try select it
                if not self._select_vfx_breakdown_by_id(linked_id):
                    if auto_select and self.vfx_breakdown_combo.count() > 1:
                        self.vfx_breakdown_combo.setCurrentIndex(1)
            else:
                if auto_select and self.vfx_breakdown_combo.count() > 1:
                    self.vfx_breakdown_combo.setCurrentIndex(1)
        else:
            self._set_vfx_breakdown_status("No VFX Breakdowns found in this project.")
            self._clear_vfx_breakdown_table()

    def _set_vfx_breakdown_status(self, message, is_error=False):
        if not hasattr(self, "vfx_breakdown_status_label"):
            return

        color = "#ff8080" if is_error else "#a0a0a0"
        self.vfx_breakdown_status_label.setStyleSheet(f"color: {color}; padding: 2px 0;")
        self.vfx_breakdown_status_label.setText(message)

    def _clear_vfx_breakdown_table(self):
        if hasattr(self, "vfx_breakdown_table"):
            self.vfx_breakdown_table.setRowCount(0)

    def _on_vfx_breakdown_changed(self, index):
        if not hasattr(self, "vfx_breakdown_combo"):
            return

        breakdown = self.vfx_breakdown_combo.itemData(index)
        if not breakdown:
            self._clear_vfx_breakdown_table()
            if index == 0:
                self._set_vfx_breakdown_status("Select a VFX Breakdown to view its details.")
            return
        try:
            self._load_vfx_breakdown_details(breakdown)
        except Exception as exc:
            logger.error(f"Failed to load VFX Breakdown details: {exc}", exc_info=True)
            self._clear_vfx_breakdown_table()
            self._set_vfx_breakdown_status("Failed to load VFX Breakdown details.", is_error=True)

    def _get_vfx_breakdown_fields_to_fetch(self, entity_type):
        """Return the actual fields to fetch based on our allowlist and SG schema."""
        try:
            schema = self.sg_session.get_entity_schema(entity_type) or {}
        except Exception:
            schema = {}

        schema_fields = set(schema.keys())

        shots_field = None
        if "sg_numer_of_shots" in schema_fields:
            shots_field = "sg_numer_of_shots"
        elif "sg_number_of_shots" in schema_fields:
            shots_field = "sg_number_of_shots"

        fields_to_fetch = []
        for f in self.vfx_breakdown_field_allowlist:
            if f == "id":
                continue  # id is always returned
            if f in schema_fields:
                fields_to_fetch.append(f)

        if shots_field and shots_field not in fields_to_fetch:
            fields_to_fetch.append(shots_field)

        return fields_to_fetch, shots_field

    def _populate_vfx_breakdown_table_filtered(self, field_map, label_overrides=None):
        """Populate the table with only our selected fields."""
        self._clear_vfx_breakdown_table()
        if not hasattr(self, "vfx_breakdown_table"):
            return

        label_overrides = label_overrides or {}
        rows = []

        for field_name, value in field_map.items():
            if value is None:
                continue
            label = (
                    label_overrides.get(field_name)
                    or self.vfx_breakdown_field_labels.get(field_name)
                    or field_name
            )
            rows.append((label, self._format_sg_value(value)))

        self.vfx_breakdown_table.setRowCount(len(rows))
        for row_index, (field_label, value) in enumerate(rows):
            field_item = QtWidgets.QTableWidgetItem(field_label)
            field_item.setFlags(field_item.flags() ^ QtCore.Qt.ItemIsEditable)

            value_item = QtWidgets.QTableWidgetItem(value)
            value_item.setFlags(value_item.flags() ^ QtCore.Qt.ItemIsEditable)
            value_item.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

            self.vfx_breakdown_table.setItem(row_index, 0, field_item)
            self.vfx_breakdown_table.setItem(row_index, 1, value_item)

        display_name = self.vfx_breakdown_combo.currentText()
        self._set_vfx_breakdown_status(f"Loaded details for '{display_name}'.")
        self.vfx_breakdown_table.resizeColumnsToContents()
        self.vfx_breakdown_table.horizontalHeader().setStretchLastSection(True)

    def _ensure_vfx_breakdown_schema(self, breakdown):
        if not breakdown:
            return None

        entity_type = breakdown.get("type") or self.vfx_breakdown_entity_type
        if not entity_type:
            entity_type = self.sg_session.get_vfx_breakdown_entity_type()

        # Refresh cache if type changed or empty cache
        if entity_type != self.vfx_breakdown_entity_type or not self.vfx_breakdown_field_names:
            field_names, labels = self.sg_session.get_entity_fields_with_labels(entity_type)
            if not field_names:
                raise ValueError(f"No schema fields returned for entity type {entity_type}")

            labels = labels or {}
            # Normalize labels
            clean_labels = {str(k): self._normalize_label(v) for k, v in labels.items()}
            clean_field_names = [str(f) for f in field_names]

            def sort_key(field):
                return (clean_labels.get(field) or field).casefold()

            sorted_fields = sorted(clean_field_names, key=sort_key)

            self.vfx_breakdown_entity_type = entity_type
            self.vfx_breakdown_field_names = sorted_fields
            self.vfx_breakdown_field_labels = clean_labels

        return self.vfx_breakdown_entity_type

    def _load_vfx_breakdown_details(self, breakdown):
        if not breakdown or "id" not in breakdown:
            self._clear_vfx_breakdown_table()
            self._set_vfx_breakdown_status("Invalid VFX Breakdown selection.", is_error=True)
            return

        breakdown_id = int(breakdown["id"])

        base_fields = [
            "id", "code", "sg_beat_id", "sg_vfx_breakdown_scene", "sg_page",
            "sg_script_excerpt", "description", "sg_vfx_type", "sg_complexity",
            "sg_category", "sg_vfx_description", "sg_numer_of_shots", "sg_number_of_shots"
        ]
        extra_fields = ["updated_at", "updated_by"]  # new columns
        fields = base_fields + extra_fields

        order = [
            {"field_name": "sg_page", "direction": "asc"},
            {"field_name": "code", "direction": "asc"},
        ]

        # Log query
        logger.info("=" * 60)
        logger.info("Fetching Beats for VFX Breakdown…")
        logger.info(f"  Entity      : CustomEntity02")
        logger.info(f"  Parent field: sg_parent -> CustomEntity01({breakdown_id})")
        logger.info(f"  Fields      : {fields}")
        logger.info(f"  Order       : {order}")
        logger.info("=" * 60)

        beats = []
        try:
            beats = self.sg_session.get_beats_for_vfx_breakdown(breakdown_id, fields=fields, order=order)
        except Exception as e:
            logger.warning(f"Primary query failed ({e}). Retrying without extra fields…")
            try:
                beats = self.sg_session.get_beats_for_vfx_breakdown(breakdown_id, fields=base_fields, order=order)
                # if we reach here, likely a permission/schema issue with updated_*; table will still load
                # and those two columns will just show blank
            except Exception as e2:
                logger.error(f"ShotGrid query for Beats failed: {e2}", exc_info=True)
                self._clear_vfx_breakdown_table()
                self._set_vfx_breakdown_status("Failed to load Beats for this Breakdown.", is_error=True)
                return

        self._populate_beats_table(beats)

    def _populate_beats_table(self, beats):
        table = self.vfx_breakdown_table
        table.setRowCount(0)

        if not beats:
            self._set_vfx_breakdown_status("No Beats linked to this VFX Breakdown.")
            return

        table.setRowCount(len(beats))

        def _shots_value(row):
            val = row.get("sg_numer_of_shots")
            if val is None:
                val = row.get("sg_number_of_shots")
            return val

        for r, beat in enumerate(beats):
            for c, field in enumerate(self.vfx_beat_columns):
                if field == "sg_numer_of_shots":
                    value = _shots_value(beat)
                else:
                    value = beat.get(field)
                text = self._format_sg_value(value)

                it = QtWidgets.QTableWidgetItem(text)
                it.setFlags(it.flags() ^ QtCore.Qt.ItemIsEditable)

                # alignment
                if field in ("id", "sg_page", "sg_numer_of_shots"):
                    it.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                elif field == "updated_at":
                    it.setTextAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
                else:
                    it.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

                table.setItem(r, c, it)

        # no resizeColumnsToContents(); use our robust autosizer
        self._autosize_beat_columns(min_px=80, max_px=700, extra_padding=28)

        display_name = self.vfx_breakdown_combo.currentText()
        self._set_vfx_breakdown_status(f"Loaded {len(beats)} Beat(s) for '{display_name}'.")

    def _populate_vfx_breakdown_combo(self, rfq, auto_select=True):
        """
        Load ALL VFX Breakdowns in the current Project into the combo,
        then default-select the one linked on the RFQ (if any).
        """
        if not hasattr(self, "vfx_breakdown_combo"):
            return

        self.vfx_breakdown_combo.blockSignals(True)
        self.vfx_breakdown_combo.clear()
        self.vfx_breakdown_combo.addItem("-- Select VFX Breakdown --", None)

        breakdowns = []
        try:
            proj = self.sg_project_combo.itemData(self.sg_project_combo.currentIndex())
            if proj:
                logger.info(f"Loading ALL VFX Breakdowns in Project {proj.get('code')} (ID {proj.get('id')})")
                breakdowns = self.sg_session.get_vfx_breakdowns(
                    proj["id"],
                    fields=["id", "code", "name", "updated_at"]
                )
            else:
                logger.info("No project selected; cannot load project breakdowns.")
        except Exception as e:
            logger.error(f"Error populating VFX Breakdown list: {e}", exc_info=True)
            breakdowns = []

        for breakdown in breakdowns:
            label = breakdown.get("code") or breakdown.get("name") or f"ID {breakdown.get('id', 'N/A')}"
            self.vfx_breakdown_combo.addItem(label, breakdown)

        self.vfx_breakdown_combo.blockSignals(False)

        # Enable/disable Set button
        if hasattr(self, "vfx_breakdown_set_btn"):
            self.vfx_breakdown_set_btn.setEnabled(bool(rfq) and len(breakdowns) > 0)

        # Status
        if breakdowns:
            self._set_vfx_breakdown_status(f"Loaded {len(breakdowns)} VFX Breakdown(s) in project.")
        else:
            self._set_vfx_breakdown_status("No VFX Breakdowns found in this project.")
            self._clear_vfx_breakdown_table()
            return

        # Default-select the Breakdown currently linked to the RFQ (dict or list)
        linked_id = None
        if isinstance(rfq, dict):
            linked = rfq.get("sg_vfx_breakdown")
            if isinstance(linked, dict):
                linked_id = linked.get("id")
            elif isinstance(linked, list) and linked:
                linked_id = (linked[0] or {}).get("id")

        if linked_id and self._select_vfx_breakdown_by_id(linked_id):
            logger.info(f"Auto-selected RFQ-linked VFX Breakdown ID {linked_id}")
        elif auto_select and self.vfx_breakdown_combo.count() > 1:
            self.vfx_breakdown_combo.setCurrentIndex(1)

    def _format_sg_value(self, value):
        if value is None:
            return ""

        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")

        if isinstance(value, date):
            return value.strftime("%Y-%m-%d")

        if isinstance(value, list):
            formatted_items = [self._format_sg_value(item) for item in value if item is not None]
            formatted_items = [item for item in formatted_items if item]
            return ", ".join(formatted_items) if formatted_items else "-"

        if isinstance(value, dict):
            for key in ("name", "code", "content", "title", "description"):
                if key in value and value[key]:
                    return str(value[key])

            if "id" in value and "type" in value:
                return f"{value['type']} {value['id']}"

            try:
                return json.dumps(value, default=str)
            except TypeError:
                return str(value)

        if isinstance(value, bool):
            return "Yes" if value else "No"

        return str(value)

    def _create_packages_left_panel(self):
        """Create the left panel for the Packages tab."""
        left_panel = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_panel)
        left_layout.setContentsMargins(5, 5, 5, 5)

        # Data selection group
        data_group = QtWidgets.QGroupBox("Data to Fetch")
        data_layout = QtWidgets.QVBoxLayout(data_group)

        # Entity types
        entity_label = QtWidgets.QLabel("Entity Types:")
        entity_label.setStyleSheet("font-weight: bold;")
        data_layout.addWidget(entity_label)

        # Dictionary to store checkboxes by category name
        self.entity_type_checkboxes = {}

        # Define categories that will appear in the tree view
        categories = [
            "VFX Breakdown",
            "Script",
            "Concept Art",
            "Storyboard"
        ]

        # Create checkboxes dynamically
        for category in categories:
            checkbox = CustomCheckBox(category)
            checkbox.setChecked(True)
            # Connect to handler that will show/hide tree items
            checkbox.stateChanged.connect(lambda state, cat=category: self._on_entity_type_toggled(cat, state))
            data_layout.addWidget(checkbox)
            self.entity_type_checkboxes[category] = checkbox

        left_layout.addWidget(data_group)

        # Output settings group
        output_group = QtWidgets.QGroupBox("Output Settings")
        output_layout = QtWidgets.QFormLayout(output_group)

        output_path_row = QtWidgets.QHBoxLayout()
        self.output_path_input = QtWidgets.QLineEdit(self.output_directory)
        output_path_row.addWidget(self.output_path_input)

        browse_btn = QtWidgets.QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_output_directory)
        output_path_row.addWidget(browse_btn)

        output_layout.addRow("Output Directory:", output_path_row)

        self.package_name_input = QtWidgets.QLineEdit()
        self.package_name_input.setPlaceholderText("Auto-generated from RFQ")
        output_layout.addRow("Package Name:", self.package_name_input)

        left_layout.addWidget(output_group)
        left_layout.addStretch()

        return left_panel

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
            self.package_data_tree.clear()

        current_rfq = self.rfq_combo.itemData(self.rfq_combo.currentIndex())
        self._populate_vfx_breakdown_combo(current_rfq)

    def _load_rfqs(self, project_id):
        """Load RFQs for the selected project."""
        logger.info(f"_load_rfqs() started for project {project_id}")
        self.rfq_combo.clear()

        # Add empty item
        self.rfq_combo.addItem("-- Select RFQ --", None)

        try:
            rfqs = self.sg_session.get_rfqs(project_id,
                                            fields=["id", "code", "sg_status_list", "sg_vfx_breakdown", "created_at"])

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

        # Update VFX Breakdown combo (loads ALL breakdowns in project; selects linked one if present)
        self._populate_vfx_breakdown_combo(rfq, auto_select=True)

        if rfq:
            # Labels
            self.rfq_id_label.setText(str(rfq["id"]))
            self.rfq_status_label.setText(rfq.get("sg_status_list", "Unknown"))

            # Show currently linked Breakdown under the RFQ selector
            linked = rfq.get("sg_vfx_breakdown")
            if isinstance(linked, dict):
                label_text = linked.get("code") or linked.get("name") or f"ID {linked.get('id')}"
            elif isinstance(linked, list) and linked:
                item = linked[0]
                label_text = item.get("code") or item.get("name") or f"ID {item.get('id')}"
            else:
                label_text = "-"
            if hasattr(self, "rfq_vfx_breakdown_label"):
                self.rfq_vfx_breakdown_label.setText(label_text)

            logger.info(f"RFQ selected: {rfq.get('code', 'N/A')} (ID: {rfq['id']})")

            # Update the package data tree with RFQ data (unchanged behavior)
            self.package_data_tree.set_rfq(rfq)
            QtCore.QTimer.singleShot(0, self._apply_checkbox_states_to_tree)

            # Enable 'Set as Current' only if we have both an RFQ and breakdowns
            if hasattr(self, "vfx_breakdown_set_btn"):
                self.vfx_breakdown_set_btn.setEnabled(self.vfx_breakdown_combo.count() > 1)
        else:
            self.rfq_id_label.setText("-")
            self.rfq_status_label.setText("-")
            if hasattr(self, "rfq_vfx_breakdown_label"):
                self.rfq_vfx_breakdown_label.setText("-")
            self.package_data_tree.clear()

            if hasattr(self, "vfx_breakdown_set_btn"):
                self.vfx_breakdown_set_btn.setEnabled(False)

    def _apply_checkbox_states_to_tree(self):
        """Apply current checkbox states to the tree view."""
        for category, checkbox in self.entity_type_checkboxes.items():
            is_checked = checkbox.isChecked()
            self.package_data_tree.set_category_visibility(category, is_checked)

    def _browse_output_directory(self):
        """Browse for output directory."""
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            self.output_path_input.text()
        )

        if directory:
            self.output_path_input.setText(directory)
            logger.info(f"Output directory changed to: {directory}")

    def _serialize_for_json(self, obj):
        """
        Recursively convert objects to JSON-serializable format.
        Handles datetime objects and other non-serializable types.

        Args:
            obj: Object to serialize

        Returns:
            JSON-serializable object
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {key: self._serialize_for_json(value) for key, value in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._serialize_for_json(item) for item in obj]
        else:
            return obj

    def _get_next_package_version(self, output_dir, base_name):
        """
        Find the next available version number for a package.

        Args:
            output_dir: Path to the output directory
            base_name: Base name of the package (without version)

        Returns:
            Tuple of (version_number, version_string) e.g. (1, "v001")
        """
        version = 1

        # Look for existing packages with the same base name
        if output_dir.exists():
            pattern = f"{base_name}_v*.json"
            existing_files = list(output_dir.glob(pattern))

            if existing_files:
                # Extract version numbers from existing files
                versions = []
                for file in existing_files:
                    # Extract version from filename like "rfq_name_v001.json"
                    stem = file.stem  # Remove .json
                    parts = stem.split('_v')
                    if len(parts) == 2:
                        try:
                            ver_num = int(parts[1])
                            versions.append(ver_num)
                        except ValueError:
                            continue

                if versions:
                    version = max(versions) + 1

        version_string = f"v{version:03d}"
        logger.info(f"Next version for '{base_name}': {version_string}")
        return version, version_string

    def _create_package(self):
        """Create data package."""
        logger.info("_create_package() called")

        # Get selected project and RFQ
        current_project_index = self.sg_project_combo.currentIndex()
        sg_project = self.sg_project_combo.itemData(current_project_index)

        current_rfq_index = self.rfq_combo.currentIndex()
        sg_rfq = self.rfq_combo.itemData(current_rfq_index)

        if not sg_project:
            logger.warning("No project selected")
            QtWidgets.QMessageBox.warning(
                self, "Missing Selection",
                "Please select a Shotgrid project."
            )
            return

        if not sg_rfq:
            logger.warning("No RFQ selected")
            QtWidgets.QMessageBox.warning(
                self, "Missing Selection",
                "Please select an RFQ."
            )
            return

        logger.info(f"Creating package for SG project: {sg_project['code']}")
        logger.info(f"Including RFQ: {sg_rfq.get('code', 'N/A')}")

        # Get active versions from the tree
        active_versions = self.package_data_tree.get_active_version_data()
        active_version_ids = self.package_data_tree.get_active_version_ids()

        logger.info(f"Active versions selected: {len(active_versions)}")
        logger.info(f"Active version IDs: {active_version_ids}")

        if len(active_versions) == 0:
            result = QtWidgets.QMessageBox.question(
                self, "No Active Versions",
                "No versions are marked as active. Do you want to continue creating an empty package?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if result == QtWidgets.QMessageBox.No:
                return

        # Check if output directory exists
        output_dir = Path(self.output_path_input.text())
        if not output_dir.exists():
            result = QtWidgets.QMessageBox.question(
                self, "Directory Does Not Exist",
                f"The output directory does not exist:\n{output_dir}\n\n"
                f"Do you want to create it?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if result == QtWidgets.QMessageBox.No:
                logger.info("User chose not to create output directory")
                return

            try:
                output_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created output directory: {output_dir}")
            except Exception as e:
                logger.error(f"Failed to create directory: {e}", exc_info=True)
                QtWidgets.QMessageBox.critical(
                    self, "Error",
                    f"Failed to create directory:\n{str(e)}"
                )
                return

        # Generate package name from RFQ code
        # Convert to lowercase, replace spaces with underscores
        rfq_code = sg_rfq.get('code', 'rfq')
        base_name = rfq_code.lower().replace(' ', '_').replace('-', '_')

        # Get next version number
        version_num, version_string = self._get_next_package_version(output_dir, base_name)

        package_name = f"{base_name}_{version_string}"
        logger.info(f"Package name: {package_name}")

        progress = QtWidgets.QProgressDialog(
            "Creating data package...", "Cancel", 0, 100, self
        )
        progress.setWindowTitle("Creating Package")
        progress.setWindowModality(QtCore.Qt.WindowModal)
        progress.show()

        try:
            progress.setValue(20)
            QtCore.QCoreApplication.processEvents()

            # Collect selected data types based on visible categories
            data_types = []
            for category, checkbox in self.entity_type_checkboxes.items():
                if checkbox.isChecked():
                    # Convert category name to internal type name
                    type_name = category.lower().replace(" ", "_")
                    data_types.append(type_name)

            logger.info(f"Data types to include: {data_types}")

            progress.setValue(40)
            QtCore.QCoreApplication.processEvents()

            # Organize active versions by category
            entities = {
                "vfx_breakdown": [],
                "script": [],
                "concept_art": [],
                "storyboard": []
            }

            # Categorize active versions
            for version_data in active_versions:
                sg_version_type = version_data.get('sg_version_type', '')

                # Determine category based on version type
                if isinstance(sg_version_type, dict):
                    version_type_name = sg_version_type.get('name', '').lower()
                else:
                    version_type_name = str(sg_version_type).lower()

                # Categorize the version
                if 'vfx' in version_type_name or 'breakdown' in version_type_name:
                    entities["vfx_breakdown"].append(version_data)
                elif 'script' in version_type_name:
                    entities["script"].append(version_data)
                elif 'concept' in version_type_name or 'art' in version_type_name:
                    entities["concept_art"].append(version_data)
                elif 'storyboard' in version_type_name:
                    entities["storyboard"].append(version_data)
                else:
                    # Fallback: try to categorize by code/task
                    code = version_data.get('code', '').lower()
                    if 'script' in code:
                        entities["script"].append(version_data)
                    elif 'concept' in code:
                        entities["concept_art"].append(version_data)
                    elif 'storyboard' in code:
                        entities["storyboard"].append(version_data)
                    else:
                        # Default to vfx_breakdown if unsure
                        entities["vfx_breakdown"].append(version_data)

            progress.setValue(70)
            QtCore.QCoreApplication.processEvents()

            package_data = {
                "metadata": {
                    "source": "Shotgrid",
                    "sg_project_id": sg_project["id"],
                    "sg_project_code": sg_project["code"],
                    "sg_rfq_id": sg_rfq["id"],
                    "sg_rfq_code": sg_rfq["code"],
                    "created_by": "FF Package Manager",
                    "package_version": version_string,
                    "package_version_number": version_num,
                    "data_types": data_types,
                    "active_versions_count": len(active_versions),
                    "active_version_ids": active_version_ids
                },
                "project": sg_project,
                "rfq": sg_rfq,
                "fetched_at": datetime.now().isoformat(),
                "entities": entities
            }

            # Create filename
            filename = f"{package_name}.json"
            output_path = output_dir / filename

            logger.info(f"Writing package to: {output_path}")

            # Serialize the package data to handle datetime objects
            serialized_package_data = self._serialize_for_json(package_data)

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(serialized_package_data, f, indent=2)

            progress.setValue(100)

            # Count total entities by category
            entity_counts = {k: len(v) for k, v in entities.items() if isinstance(v, list) and len(v) > 0}
            entity_summary = "\n".join([f"  {k}: {v}" for k, v in entity_counts.items()])

            logger.info("Package created successfully")
            QtWidgets.QMessageBox.information(
                self, "Success",
                f"Package created successfully!\n\n"
                f"Package: {package_name}\n"
                f"Version: {version_string}\n"
                f"Project: {sg_project['code']}\n"
                f"RFQ: {sg_rfq.get('code', 'N/A')}\n"
                f"Active Versions: {len(active_versions)}\n"
                f"\nVersions by category:\n{entity_summary if entity_summary else '  (none)'}\n\n"
                f"Location:\n{output_path}"
            )

        except Exception as e:
            logger.error(f"Error creating package: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self, "Error",
                f"Failed to create package:\n{str(e)}"
            )
        finally:
            progress.close()

    def _on_entity_type_toggled(self, category, state):
        """Handle entity type checkbox toggle to show/hide tree categories."""
        # Don't rely on the state parameter - get the actual checkbox state
        checkbox = self.entity_type_checkboxes[category]
        is_checked = checkbox.isChecked()

        logger.info(f"Checkbox '{category}' toggled: state={state}, checkbox.isChecked()={is_checked}")

        # Tell the tree view to show/hide this category
        self.package_data_tree.set_category_visibility(category, is_checked)

    def showEvent(self, event):
        """Called when window is shown."""
        logger.info("showEvent() - Window is being shown")
        super().showEvent(event)

    def closeEvent(self, event):
        """Called when window is closed."""
        logger.info("closeEvent() - Window is being closed")
        super().closeEvent(event)