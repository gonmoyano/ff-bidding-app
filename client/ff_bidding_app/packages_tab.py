from PySide6 import QtWidgets, QtCore
import json
import logging
from datetime import datetime
from pathlib import Path

try:
    from .package_data_treeview import PackageTreeView, CustomCheckBox
    from .logger import logger
    from .bid_selector_widget import CollapsibleGroupBox
    from .settings import AppSettings
    from .vfx_breakdown_widget import VFXBreakdownWidget
    from .image_viewer_widget import ImageViewerWidget
    from .sliding_overlay_panel import SlidingOverlayPanelWithBackground
except ImportError:
    from package_data_treeview import PackageTreeView, CustomCheckBox
    from bid_selector_widget import CollapsibleGroupBox
    from settings import AppSettings
    from vfx_breakdown_widget import VFXBreakdownWidget
    from image_viewer_widget import ImageViewerWidget
    from sliding_overlay_panel import SlidingOverlayPanelWithBackground
    logger = logging.getLogger("FFPackageManager")


class PackagesTab(QtWidgets.QWidget):
    """Packages tab widget for managing data packages."""

    def __init__(self, sg_session, output_directory, parent=None):
        """Initialize the Packages tab.

        Args:
            sg_session: ShotgridClient instance
            output_directory: Default output directory path
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
        self.current_bid = None
        self.field_schema = None

        # Package management
        self.packages = {}  # package_name -> package_data dict
        self.current_package_name = None

        # UI widgets
        self.package_data_tree = None
        self.status_label = None
        self.entity_type_checkboxes = {}
        self.output_path_input = None
        self.package_name_input = None
        self.content_stack = None
        self.view_selector_dropdown = None
        self.breakdown_widget = None
        self.package_selector_dropdown = None
        self.create_package_btn = None
        self.delete_package_btn = None
        self.rename_package_btn = None

        self._build_ui()
        self._load_field_schema()

    def _build_ui(self):
        """Build the Packages tab UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Collapsible bar with view selector and Package Manager button
        view_selector_group = CollapsibleGroupBox("View")
        view_selector_layout = QtWidgets.QHBoxLayout()

        # View selector dropdown
        view_selector_layout.addWidget(QtWidgets.QLabel("Show:"))
        self.view_selector_dropdown = QtWidgets.QComboBox()
        self.view_selector_dropdown.addItems(["Bid Tracker", "Documents", "Images"])
        self.view_selector_dropdown.currentIndexChanged.connect(self._on_view_changed)
        view_selector_layout.addWidget(self.view_selector_dropdown)

        view_selector_layout.addStretch()

        # Toggle button for Package Manager panel
        self.toggle_panel_btn = QtWidgets.QPushButton("Package Manager ▶")
        self.toggle_panel_btn.setToolTip("Show/Hide Package Manager Panel")
        self.toggle_panel_btn.setStyleSheet("""
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
        self.toggle_panel_btn.clicked.connect(self._toggle_package_manager_panel)
        view_selector_layout.addWidget(self.toggle_panel_btn)

        view_selector_group.addLayout(view_selector_layout)
        layout.addWidget(view_selector_group)

        # Main content area: Stacked widget for different views
        content_pane = self._create_content_pane()
        layout.addWidget(content_pane, 1)  # Give it stretch factor

        # Bottom section: Status + Create Package button
        bottom_layout = QtWidgets.QHBoxLayout()

        self.status_label = QtWidgets.QLabel("Ready")
        bottom_layout.addWidget(self.status_label)
        bottom_layout.addStretch()

        layout.addLayout(bottom_layout)

        # Create the sliding overlay panel for Package Manager (right pane)
        right_pane = self._create_right_pane()

        # Create overlay panel with background
        self.overlay_panel = SlidingOverlayPanelWithBackground(
            parent=self,
            panel_width=450,
            animation_duration=300,
            background_opacity=0.3,
            close_on_background_click=True
        )
        self.overlay_panel.set_title("Package Manager")
        self.overlay_panel.set_content(right_pane)

        # Connect panel signals to update toggle button
        self.overlay_panel.panel_shown.connect(self._on_panel_shown)
        self.overlay_panel.panel_hidden.connect(self._on_panel_hidden)

        # Restore last selected view
        last_view = self.app_settings.get("packagesTab/lastSelectedView", 0)
        if 0 <= last_view < self.view_selector_dropdown.count():
            self.view_selector_dropdown.setCurrentIndex(last_view)

    def _create_content_pane(self):
        """Create the content pane with stacked widget for different views."""
        # Stacked widget to switch between views
        self.content_stack = QtWidgets.QStackedWidget()

        # Bid Tracker view with VFX Breakdown widget
        bid_tracker_view = QtWidgets.QWidget()
        bid_tracker_layout = QtWidgets.QVBoxLayout(bid_tracker_view)
        bid_tracker_layout.setContentsMargins(0, 0, 0, 0)

        # Create VFX Breakdown selector group
        breakdown_selector_group = CollapsibleGroupBox("VFX Breakdown")

        # Create reusable VFX Breakdown widget
        self.breakdown_widget = VFXBreakdownWidget(
            self.sg_session,
            show_toolbar=True,
            entity_name="Bidding Scene",
            settings_key="packages_bid_tracker",
            parent=self
        )

        # Add search and sort toolbar to the selector group
        if self.breakdown_widget.toolbar_widget:
            breakdown_selector_group.addWidget(self.breakdown_widget.toolbar_widget)

        bid_tracker_layout.addWidget(breakdown_selector_group)
        bid_tracker_layout.addWidget(self.breakdown_widget)

        # Add button bar underneath the VFX breakdown table
        breakdown_button_layout = QtWidgets.QHBoxLayout()

        self.export_btn = QtWidgets.QPushButton("Export Selected to Excel")
        self.export_btn.clicked.connect(self._export_to_excel)
        breakdown_button_layout.addWidget(self.export_btn)

        self.create_bid_tracker_btn = QtWidgets.QPushButton("Create Bid Tracker")
        self.create_bid_tracker_btn.clicked.connect(self._create_bid_tracker)
        breakdown_button_layout.addWidget(self.create_bid_tracker_btn)

        breakdown_button_layout.addStretch()
        bid_tracker_layout.addLayout(breakdown_button_layout)

        # Documents view
        documents_view = QtWidgets.QWidget()
        documents_layout = QtWidgets.QVBoxLayout(documents_view)
        documents_label = QtWidgets.QLabel("Documents content coming soon...")
        documents_label.setAlignment(QtCore.Qt.AlignCenter)
        documents_layout.addWidget(documents_label)

        # Images view with thumbnail viewer
        images_view = QtWidgets.QWidget()
        images_layout = QtWidgets.QVBoxLayout(images_view)
        images_layout.setContentsMargins(0, 0, 0, 0)
        self.image_viewer = ImageViewerWidget(self.sg_session, images_view, packages_tab=self)
        images_layout.addWidget(self.image_viewer)

        # Connect folder pane package selection signal for synchronization
        if hasattr(self.image_viewer, 'folder_pane') and self.image_viewer.folder_pane:
            self.image_viewer.folder_pane.packageSelected.connect(self._on_folder_pane_package_selected)

        # Add views to stacked widget
        self.content_stack.addWidget(bid_tracker_view)  # Index 0
        self.content_stack.addWidget(documents_view)    # Index 1
        self.content_stack.addWidget(images_view)       # Index 2

        return self.content_stack

    def _create_right_pane(self):
        """Create the right pane with Package Selector, Package Data tree, and Output Settings."""
        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Package Selector collapsible group
        self.package_selector_group = self._create_package_selector_group()
        right_layout.addWidget(self.package_selector_group)

        # Package Data tree
        self.package_data_tree = PackageTreeView()
        self.package_data_tree.set_sg_session(self.sg_session)
        right_layout.addWidget(self.package_data_tree, 1)  # Give it stretch factor

        # Output Settings collapsible group
        self.output_settings_group = self._create_output_settings_group()
        right_layout.addWidget(self.output_settings_group)

        # Create Data Package button at bottom right
        create_package_btn_layout = QtWidgets.QHBoxLayout()
        create_package_btn_layout.addStretch()

        create_package_btn = QtWidgets.QPushButton("Create Data Package")
        create_package_btn.setObjectName("createPackageBtn")
        create_package_btn.setToolTip("Create a data package from selected items in the Package Manager")
        create_package_btn.clicked.connect(self._create_package)
        create_package_btn_layout.addWidget(create_package_btn)

        right_layout.addLayout(create_package_btn_layout)

        return right_widget

    def _create_package_selector_group(self):
        """Create the Package Selector collapsible group."""
        package_group = CollapsibleGroupBox("Package Manager")

        # Package selector dropdown
        selector_layout = QtWidgets.QHBoxLayout()
        selector_layout.addWidget(QtWidgets.QLabel("Current Package:"))

        self.package_selector_dropdown = QtWidgets.QComboBox()
        self.package_selector_dropdown.setMinimumWidth(200)
        self.package_selector_dropdown.addItem("(No Package)")
        self.package_selector_dropdown.currentTextChanged.connect(self._on_package_selected)
        selector_layout.addWidget(self.package_selector_dropdown, 1)

        package_group.addLayout(selector_layout)

        # Buttons row
        buttons_layout = QtWidgets.QHBoxLayout()

        self.create_package_btn = QtWidgets.QPushButton("Create")
        self.create_package_btn.setToolTip("Create a new package")
        self.create_package_btn.clicked.connect(self._create_new_package)
        buttons_layout.addWidget(self.create_package_btn)

        self.rename_package_btn = QtWidgets.QPushButton("Rename")
        self.rename_package_btn.setToolTip("Rename the current package")
        self.rename_package_btn.clicked.connect(self._rename_package)
        self.rename_package_btn.setEnabled(False)
        buttons_layout.addWidget(self.rename_package_btn)

        self.delete_package_btn = QtWidgets.QPushButton("Delete")
        self.delete_package_btn.setToolTip("Delete the current package")
        self.delete_package_btn.clicked.connect(self._delete_package)
        self.delete_package_btn.setEnabled(False)
        buttons_layout.addWidget(self.delete_package_btn)

        buttons_layout.addStretch()
        package_group.addLayout(buttons_layout)

        return package_group

    def _on_view_changed(self, index):
        """Handle view change to switch content and save the selection."""
        self.content_stack.setCurrentIndex(index)
        self.app_settings.set("packagesTab/lastSelectedView", index)

    def _toggle_package_manager_panel(self):
        """Toggle the Package Manager panel visibility."""
        self.overlay_panel.toggle()

    def _on_panel_shown(self):
        """Handle panel shown event - update toggle button."""
        self.toggle_panel_btn.setText("Package Manager ◀")

    def _on_panel_hidden(self):
        """Handle panel hidden event - update toggle button."""
        self.toggle_panel_btn.setText("Package Manager ▶")

    def _load_field_schema(self):
        """Load field schema for CustomEntity02 (Bidding Scenes)."""
        try:
            raw_schema = self.sg_session.sg.schema_field_read("CustomEntity02")
            self.field_schema = {}
            display_names = {}

            for field_name, field_info in raw_schema.items():
                self.field_schema[field_name] = field_info
                # Extract display name
                name_info = field_info.get("name", {})
                if isinstance(name_info, dict):
                    display_name = name_info.get("value", field_name)
                else:
                    display_name = str(name_info) if name_info else field_name
                display_names[field_name] = display_name

            # Override display name for 'id' field to show 'SG ID'
            if "id" in display_names:
                display_names["id"] = "SG ID"

            # Add display name for virtual export checkbox column
            display_names["_export_to_excel"] = "Export"

            # Update the model's column headers with display names
            if self.breakdown_widget and hasattr(self.breakdown_widget, 'model'):
                self.breakdown_widget.model.set_column_headers(display_names)

            logger.info(f"Loaded field schema for CustomEntity02 with {len(self.field_schema)} fields")
        except Exception as e:
            logger.error(f"Error loading field schema: {e}", exc_info=True)
            self.field_schema = {}

    def _load_breakdown_for_rfq(self, rfq):
        """Load VFX Breakdown bidding scenes for the bid linked to the RFQ.

        Args:
            rfq: RFQ data dict
        """
        if not rfq or not self.breakdown_widget:
            return

        try:
            # Get the bid linked to this RFQ (check Early Bid first, then Turnover Bid)
            linked_bid = rfq.get("sg_early_bid")
            if not linked_bid:
                linked_bid = rfq.get("sg_turnover_bid")

            if not linked_bid:
                logger.info("No bid linked to this RFQ")
                self.breakdown_widget.load_bidding_scenes([])
                return

            # Extract bid ID
            bid_id = None
            if isinstance(linked_bid, dict):
                bid_id = linked_bid.get("id")
            elif isinstance(linked_bid, list) and linked_bid:
                bid_id = linked_bid[0].get("id") if linked_bid[0] else None

            if not bid_id:
                logger.warning("Could not extract bid ID from RFQ")
                self.breakdown_widget.load_bidding_scenes([])
                return

            # Get the full bid data including sg_vfx_breakdown
            bid = self.sg_session.sg.find_one(
                "CustomEntity06",
                [["id", "is", bid_id]],
                ["id", "code", "sg_bid_type", "sg_vfx_breakdown"]
            )

            if not bid:
                logger.warning(f"Bid {bid_id} not found")
                self.breakdown_widget.load_bidding_scenes([])
                return

            self.current_bid = bid

            # Get the VFX Breakdown linked to this bid
            breakdown = bid.get("sg_vfx_breakdown")
            if not breakdown:
                logger.info(f"No VFX Breakdown linked to bid {bid.get('code', 'Unknown')}")
                self.breakdown_widget.load_bidding_scenes([])
                return

            # Extract breakdown ID
            breakdown_id = None
            if isinstance(breakdown, dict):
                breakdown_id = breakdown.get("id")
            elif isinstance(breakdown, list) and breakdown:
                breakdown_id = breakdown[0].get("id") if breakdown[0] else None

            if not breakdown_id:
                logger.warning("Could not extract breakdown ID from bid")
                self.breakdown_widget.load_bidding_scenes([])
                return

            logger.info(f"Loading bidding scenes for VFX Breakdown {breakdown_id}")

            # Fetch bidding scenes for this breakdown with all required fields
            # These fields match the column_fields in VFXBreakdownModel
            required_fields = [
                "id",
                "code",
                "sg_bid_assets",
                "sg_sequence_code",
                "sg_vfx_breakdown_scene",
                "sg_interior_exterior",
                "sg_number_of_shots",
                "sg_on_set_vfx_needs",
                "sg_page_eights",
                "sg_previs",
                "sg_script_excerpt",
                "sg_set",
                "sg_sim",
                "sg_sorting_priority",
                "sg_team_notes",
                "sg_time_of_day",
                "sg_unit",
                "sg_vfx_assumptions",
                "sg_vfx_description",
                "sg_vfx_questions",
                "sg_vfx_supervisor_notes",
                "sg_vfx_type",
                "sg_vfx_shot_work",
            ]
            bidding_scenes = self.sg_session.get_bidding_scenes_for_vfx_breakdown(
                breakdown_id,
                fields=required_fields
            )

            logger.info(f"Loaded {len(bidding_scenes)} bidding scenes")

            # Load into the breakdown widget
            self.breakdown_widget.load_bidding_scenes(bidding_scenes, field_schema=self.field_schema)

            # Update folder pane in image viewer
            if self.image_viewer:
                self.image_viewer.update_folder_pane()

        except Exception as e:
            logger.error(f"Error loading breakdown for RFQ: {e}", exc_info=True)
            self.breakdown_widget.load_bidding_scenes([])

    def _create_data_fetch_group(self):
        """Create the Data to Fetch collapsible group."""
        data_group = CollapsibleGroupBox("Data to Fetch")

        # Entity types
        entity_label = QtWidgets.QLabel("Entity Types:")
        entity_label.setStyleSheet("font-weight: bold;")
        data_group.addWidget(entity_label)

        # Define categories that will appear in the tree view
        categories = [
            "Bid Tracker",
            "Documents",
            "Images"
        ]

        # Create checkboxes dynamically
        for category in categories:
            checkbox = CustomCheckBox(category)
            checkbox.setChecked(True)
            # Connect to handler that will show/hide tree items
            checkbox.stateChanged.connect(lambda state, cat=category: self._on_entity_type_toggled(cat, state))
            data_group.addWidget(checkbox)
            self.entity_type_checkboxes[category] = checkbox

        return data_group

    def _create_output_settings_group(self):
        """Create the Output Settings collapsible group."""
        output_group = CollapsibleGroupBox("Output Settings")

        # Create a form layout for the output settings
        form_widget = QtWidgets.QWidget()
        output_layout = QtWidgets.QFormLayout(form_widget)

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

        output_group.addWidget(form_widget)

        return output_group

    def set_rfq(self, rfq):
        """Set the current RFQ and update the tree view and VFX Breakdown.

        Args:
            rfq: RFQ data dict
        """
        self.current_rfq = rfq

        if self.package_data_tree:
            self.package_data_tree.set_rfq(rfq)
            QtCore.QTimer.singleShot(0, self._apply_checkbox_states_to_tree)

        # Load VFX Breakdown for the bid linked to this RFQ
        self._load_breakdown_for_rfq(rfq)

        # Load packages attached to this RFQ from ShotGrid
        self._load_packages_from_shotgrid(rfq)

        # Load all image versions for the current project into the image viewer
        if self.image_viewer and self.parent_app and hasattr(self.parent_app, 'sg_project_combo'):
            current_project_index = self.parent_app.sg_project_combo.currentIndex()
            sg_project = self.parent_app.sg_project_combo.itemData(current_project_index)
            if sg_project:
                project_id = sg_project.get("id")
                if project_id:
                    logger.info(f"Loading all image versions for project {project_id}")
                    self.image_viewer.load_project_versions(project_id)

    def clear(self):
        """Clear the package data tree."""
        if self.package_data_tree:
            self.package_data_tree.clear()

    def set_status(self, message):
        """Set the status label text.

        Args:
            message: Status message to display
        """
        if self.status_label:
            self.status_label.setText(message)

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
        if not self.parent_app:
            QtWidgets.QMessageBox.warning(
                self, "Error",
                "Parent application not available."
            )
            return

        logger.info("_create_package() called")

        # Get selected project and RFQ from parent app
        current_project_index = self.parent_app.sg_project_combo.currentIndex()
        sg_project = self.parent_app.sg_project_combo.itemData(current_project_index)

        current_rfq_index = self.parent_app.rfq_combo.currentIndex()
        sg_rfq = self.parent_app.rfq_combo.itemData(current_rfq_index)

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

    def _export_to_excel(self):
        """Export selected bidding scenes to Excel file."""
        try:
            import pandas as pd
            from datetime import datetime

            # Get selected scenes from the model
            if not self.breakdown_widget or not self.breakdown_widget.model:
                QtWidgets.QMessageBox.warning(
                    self, "Warning",
                    "No VFX Breakdown data loaded."
                )
                return

            selected_scenes = self.breakdown_widget.model.get_scenes_selected_for_export()

            if not selected_scenes:
                QtWidgets.QMessageBox.warning(
                    self, "Warning",
                    "No scenes selected for export. Please check the 'Export' column to select scenes."
                )
                return

            # Prompt for save location
            default_filename = f"bid_tracker_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Export to Excel",
                default_filename,
                "Excel Files (*.xlsx);;All Files (*)"
            )

            if not file_path:
                return  # User cancelled

            # Get column visibility settings
            column_visibility = self.breakdown_widget.column_visibility

            # Prepare data for export (only visible columns, exclude _export_to_excel)
            export_data = []
            for scene in selected_scenes:
                row = {}
                for field in self.breakdown_widget.model.column_fields:
                    if field == "_export_to_excel":
                        continue  # Skip the export checkbox column

                    # Skip hidden columns
                    if not column_visibility.get(field, True):
                        continue

                    value = scene.get(field)

                    # Format the value for Excel
                    if value is None:
                        row[field] = ""
                    elif isinstance(value, dict):
                        # Handle ShotGrid entity references
                        row[field] = value.get("name", str(value))
                    elif isinstance(value, list):
                        # Handle multi-entity references
                        if value and isinstance(value[0], dict):
                            row[field] = ", ".join([item.get("name", str(item)) for item in value])
                        else:
                            row[field] = ", ".join([str(item) for item in value])
                    elif isinstance(value, bool):
                        row[field] = "Yes" if value else "No"
                    else:
                        row[field] = value

                export_data.append(row)

            # Create DataFrame
            df = pd.DataFrame(export_data)

            # Get column headers for display (only for visible columns)
            column_headers = {}
            for i, field in enumerate(self.breakdown_widget.model.column_fields):
                if field != "_export_to_excel" and column_visibility.get(field, True):
                    column_headers[field] = self.breakdown_widget.model.column_headers[i]

            # Rename columns to use display names
            df = df.rename(columns=column_headers)

            # Export to Excel
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Bid Tracker', index=False)

                # Auto-adjust column widths
                worksheet = writer.sheets['Bid Tracker']
                for idx, col in enumerate(df.columns):
                    max_length = max(
                        df[col].astype(str).map(len).max(),
                        len(str(col))
                    )
                    # Add some padding
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[chr(65 + idx)].width = adjusted_width

            QtWidgets.QMessageBox.information(
                self, "Success",
                f"Exported {len(selected_scenes)} scene(s) to:\n{file_path}"
            )

            logger.info(f"Exported {len(selected_scenes)} scenes to {file_path}")

        except ImportError as e:
            logger.error(f"Missing required library for Excel export: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self, "Error",
                f"Missing required library for Excel export.\n"
                f"Please install pandas and openpyxl:\n"
                f"pip install pandas openpyxl"
            )
        except Exception as e:
            logger.error(f"Error exporting to Excel: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self, "Error",
                f"Failed to export to Excel:\n{str(e)}"
            )

    def _create_bid_tracker(self):
        """Create a new bid tracker document, upload as version, and link to package."""
        try:
            import pandas as pd
            from datetime import datetime
            import tempfile
            import os

            # Check if a package is selected
            if not self.current_package_name:
                QtWidgets.QMessageBox.warning(
                    self, "No Package Selected",
                    "Please select a package before creating a Bid Tracker."
                )
                return

            # Get package data and ShotGrid ID
            package_data = self.packages.get(self.current_package_name)
            if not package_data:
                QtWidgets.QMessageBox.warning(
                    self, "Error",
                    "Package data not found."
                )
                return

            sg_package_id = package_data.get("sg_package_id")
            if not sg_package_id:
                QtWidgets.QMessageBox.warning(
                    self, "Error",
                    "Package not linked to ShotGrid. Please ensure package was created properly."
                )
                return

            # Check if RFQ is selected
            if not self.current_rfq:
                QtWidgets.QMessageBox.warning(
                    self, "No RFQ Selected",
                    "Please select an RFQ before creating a Bid Tracker."
                )
                return

            # Get selected scenes from the model
            if not self.breakdown_widget or not self.breakdown_widget.model:
                QtWidgets.QMessageBox.warning(
                    self, "Warning",
                    "No VFX Breakdown data loaded."
                )
                return

            selected_scenes = self.breakdown_widget.model.get_scenes_selected_for_export()

            if not selected_scenes:
                QtWidgets.QMessageBox.warning(
                    self, "Warning",
                    "No scenes selected for export. Please check the 'Export' column to select scenes."
                )
                return

            # Generate version name using nomenclature: bidtracker_lowercase(<RFQ Name>)_v###
            rfq_code = self.current_rfq.get("code", "rfq")
            rfq_code_lower = rfq_code.lower().replace(" ", "")  # Make lowercase and remove spaces
            version_prefix = f"bidtracker_{rfq_code_lower}"

            # Get next version number
            version_number = self.sg_session.get_latest_version_number(sg_package_id, version_prefix)
            version_string = f"v{version_number:03d}"
            version_code = f"{version_prefix}_{version_string}"

            logger.info(f"Creating Bid Tracker version: {version_code}")

            # Create temporary Excel file
            temp_dir = tempfile.gettempdir()
            file_path = os.path.join(temp_dir, f"{version_code}.xlsx")

            # Get column visibility settings
            column_visibility = self.breakdown_widget.column_visibility

            # Prepare data for export (reuse logic from _export_to_excel)
            export_data = []
            for scene in selected_scenes:
                row = {}
                for field in self.breakdown_widget.model.column_fields:
                    if field == "_export_to_excel":
                        continue  # Skip the export checkbox column

                    # Skip hidden columns
                    if not column_visibility.get(field, True):
                        continue

                    value = scene.get(field)

                    # Format the value for Excel
                    if value is None:
                        row[field] = ""
                    elif isinstance(value, dict):
                        # Handle ShotGrid entity references
                        row[field] = value.get("name", str(value))
                    elif isinstance(value, list):
                        # Handle multi-entity references
                        if value and isinstance(value[0], dict):
                            row[field] = ", ".join([item.get("name", str(item)) for item in value])
                        else:
                            row[field] = ", ".join([str(item) for item in value])
                    elif isinstance(value, bool):
                        row[field] = "Yes" if value else "No"
                    else:
                        row[field] = value

                export_data.append(row)

            # Create DataFrame
            df = pd.DataFrame(export_data)

            # Get column headers for display (only for visible columns)
            column_headers = {}
            for i, field in enumerate(self.breakdown_widget.model.column_fields):
                if field != "_export_to_excel" and column_visibility.get(field, True):
                    column_headers[field] = self.breakdown_widget.model.column_headers[i]

            # Rename columns to use display names
            df = df.rename(columns=column_headers)

            # Export to Excel
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Bid Tracker', index=False)

                # Auto-adjust column widths
                worksheet = writer.sheets['Bid Tracker']
                for idx, col in enumerate(df.columns):
                    max_length = max(
                        df[col].astype(str).map(len).max(),
                        len(str(col))
                    )
                    # Add some padding
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[chr(65 + idx)].width = adjusted_width

            logger.info(f"Created Excel file: {file_path}")

            # Get project ID
            if self.parent_app and hasattr(self.parent_app, 'sg_project_combo'):
                current_project_index = self.parent_app.sg_project_combo.currentIndex()
                sg_project = self.parent_app.sg_project_combo.itemData(current_project_index)
                project_id = sg_project.get("id") if sg_project else None
            else:
                project_id = None

            if not project_id:
                QtWidgets.QMessageBox.warning(
                    self, "Error",
                    "No project selected."
                )
                return

            # Create Version in ShotGrid
            version = self.sg_session.create_version(
                version_code=version_code,
                project_id=project_id,
                description=f"Bid Tracker created from VFX Breakdown with {len(selected_scenes)} scenes",
                sg_version_type="Bid Tracker"
            )

            logger.info(f"Created Version in ShotGrid: {version['id']}")

            # Upload Excel file to Version
            self.sg_session.upload_file_to_version(
                version_id=version["id"],
                file_path=file_path,
                field_name="sg_uploaded_movie"
            )

            logger.info(f"Uploaded file to Version {version['id']}")

            # Find and unlink existing Bid Tracker versions from package (only one allowed)
            existing_bid_trackers = self.sg_session.find_bid_tracker_versions_in_package(sg_package_id)

            if existing_bid_trackers:
                logger.info(f"Found {len(existing_bid_trackers)} existing Bid Tracker(s) in package")
                for old_tracker in existing_bid_trackers:
                    old_tracker_id = old_tracker.get("id")
                    old_tracker_code = old_tracker.get("code", "Unknown")
                    logger.info(f"Unlinking old Bid Tracker: {old_tracker_code} (ID: {old_tracker_id})")
                    self.sg_session.unlink_version_from_package(old_tracker_id, sg_package_id)
                logger.info("All existing Bid Trackers unlinked from package")

            # Link new Version to Package
            self.sg_session.link_version_to_package(version["id"], sg_package_id)

            logger.info(f"Linked new Version to Package {sg_package_id}")

            # Clean up temporary file
            try:
                os.remove(file_path)
                logger.info(f"Removed temporary file: {file_path}")
            except Exception as e:
                logger.warning(f"Could not remove temporary file: {e}")

            # Refresh the treeview to show the new version
            if self.package_data_tree:
                self.package_data_tree.load_package_versions(sg_package_id)

            # Build success message
            success_msg = f"Created Bid Tracker version: {version_code}\n"
            success_msg += f"Exported {len(selected_scenes)} scene(s)\n"
            if existing_bid_trackers:
                success_msg += f"Replaced {len(existing_bid_trackers)} existing Bid Tracker(s)\n"
            success_msg += "Uploaded to ShotGrid and linked to package."

            QtWidgets.QMessageBox.information(
                self, "Success",
                success_msg
            )

            logger.info(f"Successfully created Bid Tracker: {version_code}")

        except ImportError as e:
            logger.error(f"Missing required library: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self, "Error",
                f"Missing required library for Excel export.\n"
                f"Please install pandas and openpyxl:\n"
                f"pip install pandas openpyxl"
            )
        except Exception as e:
            logger.error(f"Error creating Bid Tracker: {e}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self, "Error",
                f"Failed to create Bid Tracker:\n{str(e)}"
            )

    def _on_entity_type_toggled(self, category, state):
        """Handle entity type checkbox toggle to show/hide tree categories."""
        # Don't rely on the state parameter - get the actual checkbox state
        checkbox = self.entity_type_checkboxes[category]
        is_checked = checkbox.isChecked()

        logger.info(f"Checkbox '{category}' toggled: state={state}, checkbox.isChecked()={is_checked}")

        # Tell the tree view to show/hide this category
        self.package_data_tree.set_category_visibility(category, is_checked)

    def _on_package_selected(self, package_name):
        """Handle package selection from dropdown."""
        if package_name == "(No Package)":
            self.current_package_name = None
            self.rename_package_btn.setEnabled(False)
            self.delete_package_btn.setEnabled(False)
            # Clear the package data tree (image viewer shows all project images)
            if self.package_data_tree:
                self.package_data_tree.clear()
            # Sync to folder pane and clear folders
            self._sync_selected_package_to_folder_pane(None)
            self._clear_folder_pane_images()
            logger.info("No package selected")
            return

        self.current_package_name = package_name
        self.rename_package_btn.setEnabled(True)
        self.delete_package_btn.setEnabled(True)

        # Sync to folder pane
        self._sync_selected_package_to_folder_pane(package_name)

        # Load package data
        if package_name in self.packages:
            package_data = self.packages[package_name]
            self._load_package_data(package_data)

            # Load versions from the package into the treeview
            sg_package_id = package_data.get("sg_package_id")
            if sg_package_id:
                logger.info(f"Loading versions for Package ID {sg_package_id}")
                if self.package_data_tree:
                    self.package_data_tree.load_package_versions(sg_package_id)

                # Load images into folder pane based on package folder assignments
                self._load_package_images_to_folders(sg_package_id)
            else:
                logger.info("No ShotGrid Package ID found, clearing tree")
                if self.package_data_tree:
                    self.package_data_tree.clear()
                self._clear_folder_pane_images()

            logger.info(f"Loaded package: {package_name}")
        else:
            logger.warning(f"Package not found: {package_name}")

    def _load_packages_from_shotgrid(self, rfq):
        """Load packages from ShotGrid that are linked to the RFQ.

        Args:
            rfq: RFQ data dict
        """
        if not rfq:
            return

        try:
            rfq_id = rfq.get("id")
            if not rfq_id:
                return

            # Query ShotGrid for packages linked to this RFQ
            logger.info(f"Loading packages for RFQ {rfq_id} from ShotGrid...")
            sg_packages = self.sg_session.get_packages_for_rfq(rfq_id, fields=["id", "code", "description", "created_at"])

            # Clear existing packages from dropdown (keep "(No Package)")
            self.package_selector_dropdown.blockSignals(True)  # Prevent triggering selection events
            while self.package_selector_dropdown.count() > 1:
                self.package_selector_dropdown.removeItem(1)

            # Add packages to dropdown and to self.packages dict
            for sg_package in sg_packages:
                package_name = sg_package.get("code", "Unnamed Package")

                # Store basic package data (will be populated with actual state when selected)
                # For now, we just store the ShotGrid metadata
                if package_name not in self.packages:
                    self.packages[package_name] = {
                        "created_at": sg_package.get("created_at", datetime.now().isoformat()),
                        "sg_package_id": sg_package.get("id"),
                        "export_selections": {},
                        "column_visibility": {},
                    }

                # Add to dropdown
                self.package_selector_dropdown.addItem(package_name)

            self.package_selector_dropdown.blockSignals(False)

            # Sync packages to folder pane dropdown
            self._sync_packages_to_folder_pane()

            logger.info(f"Loaded {len(sg_packages)} package(s) from ShotGrid")

        except Exception as e:
            logger.error(f"Error loading packages from ShotGrid: {e}")

    def _sync_packages_to_folder_pane(self):
        """Sync the package list to the folder pane dropdown."""
        if self.image_viewer and hasattr(self.image_viewer, 'folder_pane'):
            folder_pane = self.image_viewer.folder_pane
            if folder_pane:
                # Get package names from dropdown (skip "(No Package)")
                package_names = [
                    self.package_selector_dropdown.itemText(i)
                    for i in range(1, self.package_selector_dropdown.count())
                ]
                folder_pane.set_packages(package_names)
                # Sync current selection
                folder_pane.set_selected_package(self.current_package_name)

    def _sync_selected_package_to_folder_pane(self, package_name):
        """Sync the selected package to the folder pane dropdown.

        Args:
            package_name: Selected package name or None
        """
        if self.image_viewer and hasattr(self.image_viewer, 'folder_pane'):
            folder_pane = self.image_viewer.folder_pane
            if folder_pane:
                folder_pane.set_selected_package(package_name)

    def _clear_folder_pane_images(self):
        """Clear all images from folder pane folders."""
        if not self.image_viewer or not hasattr(self.image_viewer, 'folder_pane'):
            return

        folder_pane = self.image_viewer.folder_pane
        if not folder_pane:
            return

        # Clear all asset folders
        for folder_widget in folder_pane.asset_folders.values():
            folder_widget.image_ids.clear()
            folder_widget._update_count()

        # Clear all scene folders
        for folder_widget in folder_pane.scene_folders.values():
            folder_widget.image_ids.clear()
            folder_widget._update_count()

        logger.info("Cleared all images from folder pane")

    def _load_package_images_to_folders(self, package_id):
        """Load images from package into folder pane based on folder assignments.

        Args:
            package_id: ShotGrid Package ID
        """
        if not self.image_viewer or not hasattr(self.image_viewer, 'folder_pane'):
            return

        folder_pane = self.image_viewer.folder_pane
        if not folder_pane:
            return

        # First clear existing assignments
        self._clear_folder_pane_images()

        # Get versions with folder info from package
        try:
            versions_with_folders = self.sg_session.get_package_versions_with_folders(
                package_id,
                fields=["id", "code", "sg_version_type"]
            )

            logger.info(f"Loading {len(versions_with_folders)} versions into folders")

            # Process each version and its folder assignments
            for version in versions_with_folders:
                version_id = version.get('id')
                folders_str = version.get('_package_folders', '')

                if not version_id or not folders_str:
                    continue

                # Parse folder paths (can be multiple, separated by ";")
                folder_paths = [f.strip() for f in folders_str.split(';') if f.strip()]

                for folder_path in folder_paths:
                    # Parse path like "/assets/CRE/Concept Art" or "/scenes/Scene_001/Storyboard"
                    parts = [p for p in folder_path.split('/') if p]
                    if len(parts) < 2:
                        continue

                    folder_type = parts[0]  # 'assets' or 'scenes'
                    folder_name = parts[1]  # 'CRE' or 'Scene_001'

                    # Add to appropriate folder
                    if folder_type == 'assets' and folder_name in folder_pane.asset_folders:
                        folder_widget = folder_pane.asset_folders[folder_name]
                        folder_widget.image_ids.add(version_id)
                        folder_widget._update_count()
                        logger.debug(f"Added version {version_id} to asset folder {folder_name}")
                    elif folder_type == 'scenes' and folder_name in folder_pane.scene_folders:
                        folder_widget = folder_pane.scene_folders[folder_name]
                        folder_widget.image_ids.add(version_id)
                        folder_widget._update_count()
                        logger.debug(f"Added version {version_id} to scene folder {folder_name}")

            # Update the thumbnail states to reflect folder assignments
            if hasattr(self.image_viewer, 'update_thumbnail_states'):
                self.image_viewer.update_thumbnail_states()

            logger.info(f"Loaded package images into folders for package {package_id}")

        except Exception as e:
            logger.error(f"Error loading package images to folders: {e}", exc_info=True)

    def _on_folder_pane_package_selected(self, package_name):
        """Handle package selection from folder pane dropdown.

        Args:
            package_name: Selected package name or empty string for "(No Package)"
        """
        # Update the package selector dropdown to match
        if not package_name:
            self.package_selector_dropdown.setCurrentText("(No Package)")
        else:
            index = self.package_selector_dropdown.findText(package_name)
            if index >= 0:
                self.package_selector_dropdown.setCurrentIndex(index)

    def _get_next_package_version_for_rfq(self):
        """Get the next available version number for a package based on current RFQ.

        Returns:
            tuple: (version_number, version_string) e.g., (1, "v001")
        """
        if not self.current_rfq:
            return 1, "v001"

        try:
            # Get existing packages from ShotGrid for this RFQ
            rfq_id = self.current_rfq.get("id")
            existing_packages = self.sg_session.get_packages_for_rfq(rfq_id, fields=["code"])

            # Also check packages in memory
            rfq_code = self.current_rfq.get("code", "Package")
            prefix = f"Package-{rfq_code}--v"

            versions = []

            # Extract version numbers from ShotGrid packages
            for pkg in existing_packages:
                pkg_name = pkg.get("code", "")
                if pkg_name.startswith(prefix):
                    version_part = pkg_name[len(prefix):]
                    try:
                        version_num = int(version_part)
                        versions.append(version_num)
                    except ValueError:
                        continue

            # Extract version numbers from in-memory packages
            for pkg_name in self.packages.keys():
                if pkg_name.startswith(prefix):
                    version_part = pkg_name[len(prefix):]
                    try:
                        version_num = int(version_part)
                        versions.append(version_num)
                    except ValueError:
                        continue

            # Get next version
            if versions:
                next_version = max(versions) + 1
            else:
                next_version = 1

            version_string = f"v{next_version:03d}"
            return next_version, version_string

        except Exception as e:
            logger.error(f"Error getting next package version: {e}")
            return 1, "v001"

    def _create_new_package(self):
        """Create a new package."""
        # Check if an RFQ is selected
        if not self.current_rfq:
            QtWidgets.QMessageBox.warning(
                self,
                "No RFQ Selected",
                "Please select an RFQ before creating a package."
            )
            return

        # Generate prefilled package name using naming convention
        rfq_code = self.current_rfq.get("code", "Package")
        version_num, version_string = self._get_next_package_version_for_rfq()
        default_name = f"Package-{rfq_code}--{version_string}"

        # Prompt for package name with prefilled default
        name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Create Package",
            "Enter package name:",
            QtWidgets.QLineEdit.Normal,
            default_name
        )

        if not ok or not name.strip():
            return

        name = name.strip()

        # Check if package already exists
        if name in self.packages:
            QtWidgets.QMessageBox.warning(
                self,
                "Package Exists",
                f"A package named '{name}' already exists."
            )
            return

        # Create new package with current state
        package_data = self._capture_current_state()
        self.packages[name] = package_data

        # Create Package entity in ShotGrid and link to RFQ
        try:
            rfq_id = self.current_rfq.get("id")

            # Get project from parent app's combo box
            if self.parent_app and hasattr(self.parent_app, 'sg_project_combo'):
                current_project_index = self.parent_app.sg_project_combo.currentIndex()
                sg_project = self.parent_app.sg_project_combo.itemData(current_project_index)
                project_id = sg_project.get("id") if sg_project else None
            else:
                project_id = None

            if project_id:
                # Create the Package entity
                sg_package = self.sg_session.create_package(
                    package_name=name,
                    project_id=project_id,
                    description=f"Package created from FF Bidding App"
                )

                # Link the Package to the RFQ's sg_packages field
                self.sg_session.link_package_to_rfq(sg_package["id"], rfq_id)

                # Store the ShotGrid package ID in the package data
                package_data["sg_package_id"] = sg_package["id"]

                logger.info(f"Created Package entity in ShotGrid with ID: {sg_package['id']}")
            else:
                logger.warning("No project selected, package created locally only")

        except Exception as e:
            logger.error(f"Error creating Package in ShotGrid: {e}")
            QtWidgets.QMessageBox.warning(
                self,
                "ShotGrid Error",
                f"Package created locally but failed to create in ShotGrid: {str(e)}"
            )

        # Add to dropdown
        self.package_selector_dropdown.addItem(name)
        self.package_selector_dropdown.setCurrentText(name)

        logger.info(f"Created new package: {name}")
        self.set_status(f"Created package: {name}")

    def _rename_package(self):
        """Rename the current package."""
        if not self.current_package_name:
            return

        old_name = self.current_package_name

        # Prompt for new name
        new_name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Rename Package",
            "Enter new package name:",
            QtWidgets.QLineEdit.Normal,
            old_name
        )

        if not ok or not new_name.strip():
            return

        new_name = new_name.strip()

        # Check if name unchanged
        if new_name == old_name:
            return

        # Check if new name already exists
        if new_name in self.packages:
            QtWidgets.QMessageBox.warning(
                self,
                "Package Exists",
                f"A package named '{new_name}' already exists."
            )
            return

        # Get package data to check for ShotGrid ID
        package_data = self.packages.get(old_name, {})
        sg_package_id = package_data.get("sg_package_id")

        # Update in ShotGrid if package has a ShotGrid ID
        if sg_package_id:
            try:
                self.sg_session.update_package(sg_package_id, package_name=new_name)
                logger.info(f"Updated Package {sg_package_id} in ShotGrid with new name: {new_name}")
            except Exception as e:
                logger.error(f"Error updating Package in ShotGrid: {e}")
                QtWidgets.QMessageBox.warning(
                    self,
                    "ShotGrid Error",
                    f"Package renamed locally but failed to update in ShotGrid: {str(e)}"
                )

        # Rename package locally
        self.packages[new_name] = self.packages.pop(old_name)

        # Update dropdown
        current_index = self.package_selector_dropdown.currentIndex()
        self.package_selector_dropdown.setItemText(current_index, new_name)
        self.current_package_name = new_name

        logger.info(f"Renamed package from '{old_name}' to '{new_name}'")
        self.set_status(f"Renamed package to: {new_name}")

    def _delete_package(self):
        """Delete the current package."""
        if not self.current_package_name:
            return

        # Confirm deletion
        result = QtWidgets.QMessageBox.question(
            self,
            "Delete Package",
            f"Are you sure you want to delete package '{self.current_package_name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if result != QtWidgets.QMessageBox.Yes:
            return

        name = self.current_package_name

        # Get package data to check for ShotGrid ID
        package_data = self.packages.get(name, {})
        sg_package_id = package_data.get("sg_package_id")

        # Delete from ShotGrid if package has a ShotGrid ID
        if sg_package_id:
            try:
                # First unlink from RFQ if we have an RFQ context
                if self.current_rfq:
                    rfq_id = self.current_rfq.get("id")
                    self.sg_session.unlink_package_from_rfq(sg_package_id, rfq_id)
                    logger.info(f"Unlinked Package {sg_package_id} from RFQ {rfq_id}")

                # Then delete the package entity
                self.sg_session.delete_package(sg_package_id)
                logger.info(f"Deleted Package {sg_package_id} from ShotGrid")

            except Exception as e:
                logger.error(f"Error deleting Package from ShotGrid: {e}")
                QtWidgets.QMessageBox.warning(
                    self,
                    "ShotGrid Error",
                    f"Package deleted locally but failed to delete from ShotGrid: {str(e)}"
                )

        # Remove from packages dict
        if name in self.packages:
            del self.packages[name]

        # Remove from dropdown
        current_index = self.package_selector_dropdown.currentIndex()
        self.package_selector_dropdown.removeItem(current_index)

        # Reset to "(No Package)"
        self.package_selector_dropdown.setCurrentIndex(0)
        self.current_package_name = None

        logger.info(f"Deleted package: {name}")
        self.set_status(f"Deleted package: {name}")

    def _capture_current_state(self):
        """Capture the current UI state as package data.

        Returns:
            dict: Package data containing export selections and column visibility
        """
        package_data = {
            "created_at": datetime.now().isoformat(),
            "export_selections": {},
            "column_visibility": {},
        }

        # Capture export selections from the breakdown widget
        if self.breakdown_widget and self.breakdown_widget.model:
            package_data["export_selections"] = self.breakdown_widget.model.export_selection.copy()

        # Capture column visibility settings
        if self.breakdown_widget:
            package_data["column_visibility"] = self.breakdown_widget.column_visibility.copy()

        return package_data

    def _load_package_data(self, package_data):
        """Load package data into the UI.

        Args:
            package_data: dict containing package state
        """
        # Restore export selections
        if self.breakdown_widget and self.breakdown_widget.model:
            export_selections = package_data.get("export_selections", {})
            self.breakdown_widget.model.export_selection = export_selections.copy()

            # Emit data changed to refresh checkboxes
            if len(self.breakdown_widget.model.filtered_row_indices) > 0:
                top_left = self.breakdown_widget.model.index(0, 0)
                bottom_right = self.breakdown_widget.model.index(
                    len(self.breakdown_widget.model.filtered_row_indices) - 1, 0
                )
                self.breakdown_widget.model.dataChanged.emit(
                    top_left, bottom_right, [QtCore.Qt.CheckStateRole]
                )

        # Restore column visibility
        if self.breakdown_widget:
            column_visibility = package_data.get("column_visibility", {})
            if column_visibility:
                self.breakdown_widget.column_visibility = column_visibility.copy()

                # Apply visibility to table
                for i, field in enumerate(self.breakdown_widget.model.column_fields):
                    is_visible = column_visibility.get(field, True)
                    self.breakdown_widget.table_view.setColumnHidden(i, not is_visible)

        self.set_status(f"Loaded package: {self.current_package_name}")
