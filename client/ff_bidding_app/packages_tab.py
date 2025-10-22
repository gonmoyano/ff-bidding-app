from PySide6 import QtWidgets, QtCore
import json
import logging
from datetime import datetime
from pathlib import Path

try:
    from .package_data_treeview import PackageTreeView, CustomCheckBox
    from .logger import logger
except ImportError:
    from package_data_treeview import PackageTreeView, CustomCheckBox
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

        # UI widgets
        self.package_data_tree = None
        self.status_label = None
        self.entity_type_checkboxes = {}
        self.output_path_input = None
        self.package_name_input = None

        self._build_ui()

    def _build_ui(self):
        """Build the Packages tab UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Splitter for left and right panels
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)

        # Left panel: Data to Fetch + Output Settings
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)

        # Right panel: Package Data tree
        self.package_data_tree = PackageTreeView()
        self.package_data_tree.set_sg_session(self.sg_session)
        splitter.addWidget(self.package_data_tree)

        # Set initial sizes (40% left, 60% right)
        splitter.setSizes([400, 600])
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

    def _create_left_panel(self):
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

    def set_rfq(self, rfq):
        """Set the current RFQ and update the tree view.

        Args:
            rfq: RFQ data dict
        """
        if self.package_data_tree:
            self.package_data_tree.set_rfq(rfq)
            QtCore.QTimer.singleShot(0, self._apply_checkbox_states_to_tree)

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
