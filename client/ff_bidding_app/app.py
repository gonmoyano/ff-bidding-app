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
    from .bid_selector_widget import CollapsibleGroupBox
    from .settings import AppSettings
    from .settings_dialog import SettingsDialog
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
    from bid_selector_widget import CollapsibleGroupBox
    from settings import AppSettings
    from settings_dialog import SettingsDialog

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

    def get_action(self):
        """Get the selected action."""
        return self.result_action


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

            # Initialize app settings
            self.app_settings = AppSettings()
            logger.info("AppSettings initialized")

            self.setWindowTitle("Fireframe Prodigy")
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
    def apply_dpi_scaling():
        """Apply DPI scaling from settings if configured.

        Note: This must be called before QApplication is created for full effect.
        If QApplication already exists, it will apply what it can.
        """
        try:
            settings = AppSettings()
            dpi_scale = settings.get_dpi_scale()

            if dpi_scale != 1.0:
                logger.info(f"Applying DPI scaling: {dpi_scale}")

                # Try to set Qt attributes (only works if QApplication not yet created)
                try:
                    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
                    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
                except RuntimeError:
                    logger.info("QApplication already exists, cannot set Qt attributes")

                # Set environment variable (works if set before Qt init)
                import os
                os.environ["QT_SCALE_FACTOR"] = str(dpi_scale)

                logger.info(f"DPI scaling configured: {dpi_scale}x")
            else:
                logger.info("DPI scaling set to default (1.0x)")

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
            title_label = QtWidgets.QLabel("Fireframe Prodigy")
            title_font = title_label.font()
            title_font.setPointSize(16)
            title_font.setBold(True)
            title_label.setFont(title_font)
            header_layout.addWidget(title_label)
            header_layout.addStretch()

            # Settings button (cog icon, no text)
            self.settings_button = QtWidgets.QPushButton("⚙")  # Gear/cog Unicode character
            self.settings_button.setToolTip("Application Settings")
            settings_font = self.settings_button.font()
            settings_font.setPointSize(14)
            self.settings_button.setFont(settings_font)
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
            header_layout.addWidget(self.settings_button)

            main_layout.addLayout(header_layout)

            # Compact top bar with dropdowns and Current Bid (always visible)
            top_bar = self._create_top_bar()
            main_layout.addWidget(top_bar)

            # Tabbed section
            self.tab_widget = QtWidgets.QTabWidget()

            # Create Bidding tab (contains VFX Breakdown, Assets, Rates, and Reports as nested tabs)
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

    def _create_top_bar(self):
        """Create compact top bar with Project, RFQ dropdowns and Current Bid."""
        bar_widget = QtWidgets.QWidget()
        bar_widget.setObjectName("topBar")
        bar_widget.setStyleSheet("""
            QWidget#topBar {
                border: 1px solid #555555;
                border-radius: 4px;
            }
        """)
        bar_layout = QtWidgets.QHBoxLayout(bar_widget)
        bar_layout.setContentsMargins(6, 6, 6, 6)

        # Project section
        project_label = QtWidgets.QLabel("Project:")
        bar_layout.addWidget(project_label)

        self.sg_project_combo = QtWidgets.QComboBox()
        self.sg_project_combo.setMinimumWidth(200)
        self.sg_project_combo.currentIndexChanged.connect(self._on_sg_project_changed)
        bar_layout.addWidget(self.sg_project_combo)

        load_sg_btn = QtWidgets.QPushButton("Load from SG")
        load_sg_btn.clicked.connect(self._load_sg_projects)
        bar_layout.addWidget(load_sg_btn)

        # Spacer
        bar_layout.addSpacing(20)

        # RFQ section
        rfq_label = QtWidgets.QLabel("RFQ:")
        bar_layout.addWidget(rfq_label)

        self.rfq_combo = QtWidgets.QComboBox()
        self.rfq_combo.setMinimumWidth(200)
        self.rfq_combo.currentIndexChanged.connect(self._on_rfq_changed)
        bar_layout.addWidget(self.rfq_combo)

        # Config RFQs button
        config_rfqs_btn = QtWidgets.QPushButton("Config RFQs")
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

        # Project Details button
        details_btn = QtWidgets.QPushButton("Project Details")
        details_btn.clicked.connect(self._show_project_details)
        bar_layout.addWidget(details_btn)

        return bar_widget

    def _show_project_details(self):
        """Show the project details dialog."""
        # Get current project and RFQ data
        project = self.sg_project_combo.itemData(self.sg_project_combo.currentIndex())
        rfq = self.rfq_combo.itemData(self.rfq_combo.currentIndex())

        dialog = ProjectDetailsDialog(project, rfq, parent=self)
        dialog.exec()

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
            logger.info(f"Created new RFQ: {new_rfq}")

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
            logger.info(f"Renamed RFQ {rfq['id']} to '{new_name}'")

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
                logger.info(f"Deleted RFQ {rfq['id']} and related elements: {deleted_summary}")

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
                logger.info(f"Deleted RFQ {rfq['id']}")

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
                # Beautify project name from snake_case to Title Case
                project_name = project['name'].replace('_', ' ').title()
                display_text = project_name
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
            logger.info(f"SG project selected: {project['code']} (ID: {project['id']})")

            # Load RFQs for this project
            self._load_rfqs(project['id'])
        else:
            self.rfq_combo.clear()
            self.rfq_combo.addItem("-- Select RFQ --", None)
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

            logger.info(f"RFQ selected: {rfq.get('code', 'N/A')} (ID: {rfq['id']})")

            # Update the package data tree with RFQ data
            if hasattr(self, "packages_tab"):
                self.packages_tab.set_rfq(rfq)

            # Update the bidding tab with RFQ data (includes Reports nested tab)
            if hasattr(self, "bidding_tab"):
                self.bidding_tab.set_rfq(rfq)
        else:
            if hasattr(self, "rfq_bid_label"):
                self.rfq_bid_label.setText("-")
            if hasattr(self, "packages_tab"):
                self.packages_tab.clear()

    def _show_settings_dialog(self):
        """Show the application settings dialog."""
        # Store current DPI scale
        old_dpi_scale = self.app_settings.get_dpi_scale()

        dialog = SettingsDialog(self.app_settings, parent=self)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
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

            logger.info(f"Applied font scaling: {scale_factor}x")
        except Exception as e:
            logger.error(f"Failed to apply app font scaling: {e}", exc_info=True)

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

        # Recursively apply to all children
        for child in widget.findChildren(QtWidgets.QWidget):
            # Skip the settings dialog itself
            if isinstance(child, SettingsDialog):
                continue

            original_size = self._original_widget_fonts.get(child, 10)
            new_size = max(6, int(original_size * scale_factor))
            font = child.font()
            font.setPointSize(new_size)
            child.setFont(font)

        # Force layout update
        widget.updateGeometry()
        if hasattr(widget, 'layout') and widget.layout():
            widget.layout().update()

    def showEvent(self, event):
        """Called when window is shown."""
        logger.info("showEvent() - Window is being shown")
        super().showEvent(event)

    def closeEvent(self, event):
        """Called when window is closed."""
        logger.info("closeEvent() - Window is being closed")
        super().closeEvent(event)