from PySide6 import QtWidgets, QtCore, QtGui
import logging

try:
    from .logger import logger
except (ImportError, ValueError, SystemError):
    logger = logging.getLogger("FFPackageManager")


class ThumbnailWidget(QtWidgets.QWidget):
    """Widget for displaying a single image thumbnail."""

    clicked = QtCore.Signal(dict)  # Emits version data when clicked

    def __init__(self, version_data, parent=None):
        super().__init__(parent)
        self.version_data = version_data
        self.selected = False

        self.setFixedSize(180, 200)
        self.setCursor(QtCore.Qt.PointingHandCursor)

        self._setup_ui()

    def _setup_ui(self):
        """Setup the thumbnail UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Thumbnail image placeholder
        self.thumbnail_label = QtWidgets.QLabel()
        self.thumbnail_label.setFixedSize(170, 140)
        self.thumbnail_label.setAlignment(QtCore.Qt.AlignCenter)
        self.thumbnail_label.setStyleSheet("""
            QLabel {
                background-color: #2b2b2b;
                border: 2px solid #444;
                border-radius: 4px;
            }
        """)

        # Set placeholder or load thumbnail
        self.thumbnail_label.setText("No Preview")
        self.thumbnail_label.setStyleSheet(self.thumbnail_label.styleSheet() + "color: #888;")

        layout.addWidget(self.thumbnail_label)

        # Version name
        version_code = self.version_data.get('code', 'Unknown')
        name_label = QtWidgets.QLabel(version_code)
        name_label.setWordWrap(True)
        name_label.setMaximumWidth(170)
        name_label.setAlignment(QtCore.Qt.AlignCenter)
        name_label.setStyleSheet("font-size: 11px; color: #ddd;")
        layout.addWidget(name_label)

        # Version type
        version_type = self.version_data.get('sg_version_type', '')
        if isinstance(version_type, dict):
            version_type = version_type.get('name', '')
        type_label = QtWidgets.QLabel(version_type or 'Unknown Type')
        type_label.setAlignment(QtCore.Qt.AlignCenter)
        type_label.setStyleSheet("font-size: 9px; color: #888;")
        layout.addWidget(type_label)

    def mousePressEvent(self, event):
        """Handle mouse press to select thumbnail."""
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit(self.version_data)

    def set_selected(self, selected):
        """Set the selected state."""
        self.selected = selected
        if selected:
            self.thumbnail_label.setStyleSheet("""
                QLabel {
                    background-color: #2b2b2b;
                    border: 2px solid #4a9eff;
                    border-radius: 4px;
                }
            """)
        else:
            self.thumbnail_label.setStyleSheet("""
                QLabel {
                    background-color: #2b2b2b;
                    border: 2px solid #444;
                    border-radius: 4px;
                }
            """)


class ImageViewerWidget(QtWidgets.QWidget):
    """Widget for viewing image versions with thumbnails and grouping."""

    def __init__(self, sg_session, parent=None):
        super().__init__(parent)
        self.sg_session = sg_session
        self.current_project_id = None
        self.all_versions = []
        self.filtered_versions = []
        self.thumbnail_widgets = []
        self.selected_thumbnail = None

        # Filter states
        self.filter_states = {
            'Concept Art': True,
            'Storyboard': True,
            'Reference': True,
            'Video': True
        }

        # Grouping state
        self.grouping_mode = 'None'  # 'None', 'Asset', 'Scene'

        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI with two docks."""
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create splitter for two docks
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)

        # Left dock: Thumbnails with filters
        left_dock = self._create_thumbnail_dock()
        self.splitter.addWidget(left_dock)

        # Right dock: Grouping options
        right_dock = self._create_grouping_dock()
        self.splitter.addWidget(right_dock)

        # Set initial sizes (70% thumbnails, 30% grouping)
        self.splitter.setSizes([700, 300])
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)

        main_layout.addWidget(self.splitter)

    def _create_thumbnail_dock(self):
        """Create the left dock with thumbnails and filters."""
        dock_widget = QtWidgets.QWidget()
        dock_layout = QtWidgets.QVBoxLayout(dock_widget)
        dock_layout.setContentsMargins(5, 5, 5, 5)

        # Header with title and filter controls
        header_layout = QtWidgets.QHBoxLayout()

        title_label = QtWidgets.QLabel("Image Thumbnails")
        title_font = title_label.font()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # Filter label
        filter_label = QtWidgets.QLabel("Filter:")
        header_layout.addWidget(filter_label)

        # Filter checkboxes
        self.filter_checkboxes = {}
        for filter_type in ['Concept Art', 'Storyboard', 'Reference', 'Video']:
            checkbox = QtWidgets.QCheckBox(filter_type)
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(lambda state, ft=filter_type: self._on_filter_changed(ft, state))
            header_layout.addWidget(checkbox)
            self.filter_checkboxes[filter_type] = checkbox

        dock_layout.addLayout(header_layout)

        # Thumbnail scroll area
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        # Container for thumbnails
        self.thumbnail_container = QtWidgets.QWidget()
        self.thumbnail_layout = QtWidgets.QGridLayout(self.thumbnail_container)
        self.thumbnail_layout.setSpacing(10)
        self.thumbnail_layout.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)

        scroll_area.setWidget(self.thumbnail_container)
        dock_layout.addWidget(scroll_area)

        return dock_widget

    def _create_grouping_dock(self):
        """Create the right dock with grouping options."""
        dock_widget = QtWidgets.QWidget()
        dock_layout = QtWidgets.QVBoxLayout(dock_widget)
        dock_layout.setContentsMargins(5, 5, 5, 5)

        # Header
        title_label = QtWidgets.QLabel("Grouping & Details")
        title_font = title_label.font()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        dock_layout.addWidget(title_label)

        # Grouping options
        group_box = QtWidgets.QGroupBox("Group By")
        group_layout = QtWidgets.QVBoxLayout(group_box)

        self.grouping_buttons = QtWidgets.QButtonGroup()

        # None (no grouping)
        none_radio = QtWidgets.QRadioButton("None")
        none_radio.setChecked(True)
        none_radio.toggled.connect(lambda checked: checked and self._on_grouping_changed('None'))
        self.grouping_buttons.addButton(none_radio)
        group_layout.addWidget(none_radio)

        # Group by Asset
        asset_radio = QtWidgets.QRadioButton("Asset Name")
        asset_radio.toggled.connect(lambda checked: checked and self._on_grouping_changed('Asset'))
        self.grouping_buttons.addButton(asset_radio)
        group_layout.addWidget(asset_radio)

        # Group by Scene
        scene_radio = QtWidgets.QRadioButton("Scene")
        scene_radio.toggled.connect(lambda checked: checked and self._on_grouping_changed('Scene'))
        self.grouping_buttons.addButton(scene_radio)
        group_layout.addWidget(scene_radio)

        dock_layout.addWidget(group_box)

        # Selected image details
        details_box = QtWidgets.QGroupBox("Selected Image Details")
        details_layout = QtWidgets.QVBoxLayout(details_box)

        self.details_text = QtWidgets.QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(200)
        self.details_text.setText("No image selected")
        details_layout.addWidget(self.details_text)

        dock_layout.addWidget(details_box)

        dock_layout.addStretch()

        return dock_widget

    def _on_filter_changed(self, filter_type, state):
        """Handle filter checkbox changes."""
        self.filter_states[filter_type] = (state == QtCore.Qt.Checked)
        self._apply_filters()

    def _on_grouping_changed(self, grouping_mode):
        """Handle grouping mode changes."""
        self.grouping_mode = grouping_mode
        logger.info(f"Grouping mode changed to: {grouping_mode}")
        self._rebuild_thumbnails()

    def _apply_filters(self):
        """Apply current filters and rebuild thumbnails."""
        logger.info(f"Applying filters: {self.filter_states}")

        # Filter versions based on type
        self.filtered_versions = []
        for version in self.all_versions:
            version_type = self._get_version_type(version)
            if self.filter_states.get(version_type, True):
                self.filtered_versions.append(version)

        logger.info(f"Filtered versions: {len(self.filtered_versions)} of {len(self.all_versions)}")
        self._rebuild_thumbnails()

    def _get_version_type(self, version):
        """Get the type category for a version."""
        sg_version_type = version.get('sg_version_type', '')
        if isinstance(sg_version_type, dict):
            version_type = sg_version_type.get('name', '').lower()
        else:
            version_type = str(sg_version_type).lower()

        # Map to filter categories
        if 'concept' in version_type or 'art' in version_type:
            return 'Concept Art'
        elif 'storyboard' in version_type:
            return 'Storyboard'
        elif 'reference' in version_type or 'ref' in version_type:
            return 'Reference'
        elif 'video' in version_type or 'movie' in version_type:
            return 'Video'
        else:
            # Default to Concept Art if unknown
            return 'Concept Art'

    def _rebuild_thumbnails(self):
        """Rebuild the thumbnail grid."""
        # Clear existing thumbnails
        for thumbnail in self.thumbnail_widgets:
            thumbnail.deleteLater()
        self.thumbnail_widgets.clear()

        # Clear layout
        while self.thumbnail_layout.count():
            item = self.thumbnail_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add thumbnails based on grouping
        if self.grouping_mode == 'None':
            self._add_thumbnails_flat()
        elif self.grouping_mode == 'Asset':
            self._add_thumbnails_grouped_by_asset()
        elif self.grouping_mode == 'Scene':
            self._add_thumbnails_grouped_by_scene()

    def _add_thumbnails_flat(self):
        """Add thumbnails in a flat grid (no grouping)."""
        columns = 4  # Number of thumbnails per row

        for idx, version in enumerate(self.filtered_versions):
            row = idx // columns
            col = idx % columns

            thumbnail = ThumbnailWidget(version, self)
            thumbnail.clicked.connect(self._on_thumbnail_clicked)
            self.thumbnail_layout.addWidget(thumbnail, row, col)
            self.thumbnail_widgets.append(thumbnail)

    def _add_thumbnails_grouped_by_asset(self):
        """Add thumbnails grouped by asset name."""
        # Group versions by asset/entity
        grouped = {}
        for version in self.filtered_versions:
            entity = version.get('entity', {})
            if entity:
                entity_name = entity.get('name', 'Unknown')
            else:
                entity_name = 'No Asset'

            if entity_name not in grouped:
                grouped[entity_name] = []
            grouped[entity_name].append(version)

        # Add grouped thumbnails
        current_row = 0
        for asset_name in sorted(grouped.keys()):
            # Add asset header
            header_label = QtWidgets.QLabel(f"Asset: {asset_name}")
            header_label.setStyleSheet("font-weight: bold; font-size: 11px; padding: 5px; background-color: #3a3a3a;")
            self.thumbnail_layout.addWidget(header_label, current_row, 0, 1, 4)
            current_row += 1

            # Add thumbnails for this asset
            versions = grouped[asset_name]
            for idx, version in enumerate(versions):
                col = idx % 4
                if col == 0 and idx > 0:
                    current_row += 1

                thumbnail = ThumbnailWidget(version, self)
                thumbnail.clicked.connect(self._on_thumbnail_clicked)
                self.thumbnail_layout.addWidget(thumbnail, current_row, col)
                self.thumbnail_widgets.append(thumbnail)

            current_row += 1

    def _add_thumbnails_grouped_by_scene(self):
        """Add thumbnails grouped by scene."""
        # Group versions by task/scene
        grouped = {}
        for version in self.filtered_versions:
            task = version.get('sg_task', {})
            if task:
                scene_name = task.get('name', 'Unknown Scene')
            else:
                scene_name = 'No Scene'

            if scene_name not in grouped:
                grouped[scene_name] = []
            grouped[scene_name].append(version)

        # Add grouped thumbnails
        current_row = 0
        for scene_name in sorted(grouped.keys()):
            # Add scene header
            header_label = QtWidgets.QLabel(f"Scene: {scene_name}")
            header_label.setStyleSheet("font-weight: bold; font-size: 11px; padding: 5px; background-color: #3a3a3a;")
            self.thumbnail_layout.addWidget(header_label, current_row, 0, 1, 4)
            current_row += 1

            # Add thumbnails for this scene
            versions = grouped[scene_name]
            for idx, version in enumerate(versions):
                col = idx % 4
                if col == 0 and idx > 0:
                    current_row += 1

                thumbnail = ThumbnailWidget(version, self)
                thumbnail.clicked.connect(self._on_thumbnail_clicked)
                self.thumbnail_layout.addWidget(thumbnail, current_row, col)
                self.thumbnail_widgets.append(thumbnail)

            current_row += 1

    def _on_thumbnail_clicked(self, version_data):
        """Handle thumbnail click."""
        logger.info(f"Thumbnail clicked: {version_data.get('code')}")

        # Deselect previous
        if self.selected_thumbnail:
            self.selected_thumbnail.set_selected(False)

        # Select new
        for thumbnail in self.thumbnail_widgets:
            if thumbnail.version_data.get('id') == version_data.get('id'):
                thumbnail.set_selected(True)
                self.selected_thumbnail = thumbnail
                break

        # Update details
        self._update_details(version_data)

    def _update_details(self, version_data):
        """Update the details panel with version information."""
        details = f"<b>Version:</b> {version_data.get('code', 'Unknown')}<br>"
        details += f"<b>ID:</b> {version_data.get('id', 'N/A')}<br>"

        version_type = version_data.get('sg_version_type', '')
        if isinstance(version_type, dict):
            version_type = version_type.get('name', 'Unknown')
        details += f"<b>Type:</b> {version_type}<br>"

        status = version_data.get('sg_status_list', 'N/A')
        details += f"<b>Status:</b> {status}<br>"

        entity = version_data.get('entity', {})
        if entity:
            details += f"<b>Asset:</b> {entity.get('name', 'Unknown')}<br>"

        task = version_data.get('sg_task', {})
        if task:
            details += f"<b>Task:</b> {task.get('name', 'Unknown')}<br>"

        user = version_data.get('user', {})
        if user:
            details += f"<b>Created By:</b> {user.get('name', 'Unknown')}<br>"

        created_at = version_data.get('created_at', 'N/A')
        details += f"<b>Created:</b> {created_at}<br>"

        description = version_data.get('description', '')
        if description:
            details += f"<br><b>Description:</b><br>{description}"

        self.details_text.setHtml(details)

    def load_project_versions(self, project_id):
        """Load all image versions for the given project."""
        self.current_project_id = project_id

        if not project_id or not self.sg_session:
            logger.info("No project ID or SG session")
            self.all_versions = []
            self._rebuild_thumbnails()
            return

        logger.info(f"Loading image versions for project {project_id}")

        # Get all image versions for the project
        self.all_versions = self.sg_session.get_all_image_versions_for_project(project_id)
        logger.info(f"Loaded {len(self.all_versions)} image versions for project")

        # Apply filters and rebuild
        self._apply_filters()

    def _is_image_version(self, version):
        """Check if version is an image type."""
        sg_version_type = version.get('sg_version_type')

        if sg_version_type:
            if isinstance(sg_version_type, dict):
                version_type = sg_version_type.get('name', '').lower()
            else:
                version_type = str(sg_version_type).lower()

            # Check for image-related keywords
            return any(keyword in version_type for keyword in [
                'concept', 'art', 'storyboard', 'reference', 'image', 'ref', 'video', 'movie'
            ])

        # Fallback to task/code checking
        code = version.get('code', '').lower()
        task = version.get('sg_task', {})
        task_name = task.get('name', '').lower() if task else ''

        image_keywords = ['concept', 'art', 'storyboard', 'reference', 'image', 'ref', 'video', 'movie']
        return any(keyword in code or keyword in task_name for keyword in image_keywords)

    def clear(self):
        """Clear all thumbnails."""
        self.all_versions = []
        self.filtered_versions = []
        self._rebuild_thumbnails()
        self.details_text.setText("No image selected")
