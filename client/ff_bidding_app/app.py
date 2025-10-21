from PySide6 import QtWidgets, QtCore, QtGui
import json
import logging
from datetime import datetime
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

            self.setWindowTitle("Fireframe - Bidding Manager")
            self.setMinimumSize(1400, 700)

            self._build_ui()

            # Auto-load the latest project on startup
            logger.info("Auto-loading latest project...")
            self._auto_load_latest_project()

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

        rfq_layout.addLayout(rfq_info_layout)

        return rfq_group

    def _create_vfx_breakdown_tab(self):
        """Create the VFX Breakdown tab content."""
        vfx_breakdown_widget = QtWidgets.QWidget()
        vfx_breakdown_layout = QtWidgets.QVBoxLayout(vfx_breakdown_widget)

        # Placeholder content
        label = QtWidgets.QLabel("VFX Breakdown")
        label.setStyleSheet("font-size: 18px; font-weight: bold; padding: 20px;")
        vfx_breakdown_layout.addWidget(label)

        info_label = QtWidgets.QLabel("VFX Breakdown content will be displayed here.")
        info_label.setStyleSheet("padding: 20px;")
        vfx_breakdown_layout.addWidget(info_label)

        vfx_breakdown_layout.addStretch()

        return vfx_breakdown_widget

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
        """Handle RFQ selection."""
        rfq = self.rfq_combo.itemData(index)

        if rfq:
            self.rfq_id_label.setText(str(rfq['id']))
            self.rfq_status_label.setText(rfq.get('sg_status_list', 'Unknown'))
            logger.info(f"RFQ selected: {rfq.get('code', 'N/A')} (ID: {rfq['id']})")

            # Update the package data tree with RFQ data
            self.package_data_tree.set_rfq(rfq)

            # Apply checkbox states after tree is loaded
            QtCore.QTimer.singleShot(0, self._apply_checkbox_states_to_tree)
        else:
            self.rfq_id_label.setText("-")
            self.rfq_status_label.setText("-")
            self.package_data_tree.clear()

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