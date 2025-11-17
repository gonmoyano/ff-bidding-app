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
except ImportError:
    from package_data_treeview import PackageTreeView, CustomCheckBox
    from bid_selector_widget import CollapsibleGroupBox
    from settings import AppSettings
    from vfx_breakdown_widget import VFXBreakdownWidget
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

        # UI widgets
        self.package_data_tree = None
        self.status_label = None
        self.entity_type_checkboxes = {}
        self.output_path_input = None
        self.package_name_input = None
        self.packages_tab_widget = None
        self.breakdown_widget = None

        self._build_ui()
        self._load_field_schema()

    def _build_ui(self):
        """Build the Packages tab UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Horizontal splitter for left and right panes
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)

        # Left pane: Bid selector + Tabs
        left_pane = self._create_left_pane()
        splitter.addWidget(left_pane)

        # Right pane: Data to Fetch, Output Settings, Package Data tree
        right_pane = self._create_right_pane()
        splitter.addWidget(right_pane)

        # Set initial sizes (30% left, 70% right)
        splitter.setSizes([300, 700])
        layout.addWidget(splitter)

        # Bottom section: Status + Create Package button
        bottom_layout = QtWidgets.QHBoxLayout()

        self.status_label = QtWidgets.QLabel("Ready")
        bottom_layout.addWidget(self.status_label)
        bottom_layout.addStretch()

        create_package_btn = QtWidgets.QPushButton("Create Data Package")
        create_package_btn.setObjectName("createPackageBtn")
        create_package_btn.clicked.connect(self._create_package)
        bottom_layout.addWidget(create_package_btn)

        layout.addLayout(bottom_layout)

        # Restore last selected tab
        last_tab = self.app_settings.get("packagesTab/lastSelectedTab", 0)
        if self.packages_tab_widget and 0 <= last_tab < self.packages_tab_widget.count():
            self.packages_tab_widget.setCurrentIndex(last_tab)

    def _create_left_pane(self):
        """Create the left pane with tabs."""
        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Tab widget for Bid Tracker, Concept, Script, References
        self.packages_tab_widget = QtWidgets.QTabWidget()
        self.packages_tab_widget.currentChanged.connect(self._on_tab_changed)

        # Bid Tracker tab with VFX Breakdown widget
        bid_tracker_tab = QtWidgets.QWidget()
        bid_tracker_layout = QtWidgets.QVBoxLayout(bid_tracker_tab)
        bid_tracker_layout.setContentsMargins(0, 0, 0, 0)

        self.breakdown_widget = VFXBreakdownWidget(
            self.sg_session,
            show_toolbar=True,
            entity_name="Bidding Scene",
            settings_key="packages_bid_tracker",
            parent=self
        )
        bid_tracker_layout.addWidget(self.breakdown_widget)

        # Placeholder tabs for other content
        concept_tab = QtWidgets.QWidget()
        concept_layout = QtWidgets.QVBoxLayout(concept_tab)
        concept_label = QtWidgets.QLabel("Concept content coming soon...")
        concept_label.setAlignment(QtCore.Qt.AlignCenter)
        concept_layout.addWidget(concept_label)

        script_tab = QtWidgets.QWidget()
        script_layout = QtWidgets.QVBoxLayout(script_tab)
        script_label = QtWidgets.QLabel("Script content coming soon...")
        script_label.setAlignment(QtCore.Qt.AlignCenter)
        script_layout.addWidget(script_label)

        references_tab = QtWidgets.QWidget()
        references_layout = QtWidgets.QVBoxLayout(references_tab)
        references_label = QtWidgets.QLabel("References content coming soon...")
        references_label.setAlignment(QtCore.Qt.AlignCenter)
        references_layout.addWidget(references_label)

        # Add tabs
        self.packages_tab_widget.addTab(bid_tracker_tab, "Bid Tracker")
        self.packages_tab_widget.addTab(concept_tab, "Concept")
        self.packages_tab_widget.addTab(script_tab, "Script")
        self.packages_tab_widget.addTab(references_tab, "References")

        left_layout.addWidget(self.packages_tab_widget, 1)  # Give it stretch factor

        return left_widget

    def _create_right_pane(self):
        """Create the right pane with Data to Fetch, Output Settings, and Package Data tree."""
        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Data to Fetch collapsible group
        self.data_fetch_group = self._create_data_fetch_group()
        right_layout.addWidget(self.data_fetch_group)

        # Output Settings collapsible group
        self.output_settings_group = self._create_output_settings_group()
        right_layout.addWidget(self.output_settings_group)

        # Package Data tree
        self.package_data_tree = PackageTreeView()
        self.package_data_tree.set_sg_session(self.sg_session)
        right_layout.addWidget(self.package_data_tree, 1)  # Give it stretch factor

        return right_widget

    def _on_tab_changed(self, index):
        """Handle tab change to save the selection."""
        self.app_settings.set("packagesTab/lastSelectedTab", index)

    def _load_field_schema(self):
        """Load field schema for CustomEntity02 (Bidding Scenes)."""
        try:
            raw_schema = self.sg_session.sg.schema_field_read("CustomEntity02")
            self.field_schema = {}
            for field_name, field_info in raw_schema.items():
                self.field_schema[field_name] = field_info
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

            # Fetch bidding scenes for this breakdown
            bidding_scenes = self.sg_session.get_bidding_scenes_for_vfx_breakdown(
                breakdown_id,
                fields=None  # Use default fields
            )

            logger.info(f"Loaded {len(bidding_scenes)} bidding scenes")

            # Load into the breakdown widget
            self.breakdown_widget.load_bidding_scenes(bidding_scenes, field_schema=self.field_schema)

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

    def _on_entity_type_toggled(self, category, state):
        """Handle entity type checkbox toggle to show/hide tree categories."""
        # Don't rely on the state parameter - get the actual checkbox state
        checkbox = self.entity_type_checkboxes[category]
        is_checked = checkbox.isChecked()

        logger.info(f"Checkbox '{category}' toggled: state={state}, checkbox.isChecked()={is_checked}")

        # Tell the tree view to show/hide this category
        self.package_data_tree.set_category_visibility(category, is_checked)
