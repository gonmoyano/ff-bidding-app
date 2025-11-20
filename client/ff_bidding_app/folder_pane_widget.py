from PySide6 import QtWidgets, QtCore, QtGui
import logging

try:
    from .logger import logger
    from .bid_selector_widget import CollapsibleGroupBox
except (ImportError, ValueError, SystemError):
    logger = logging.getLogger("FFPackageManager")
    from bid_selector_widget import CollapsibleGroupBox


class FolderWidget(QtWidgets.QWidget):
    """Widget representing a folder that can accept image drops."""

    def __init__(self, folder_name, folder_type, parent=None):
        """Initialize folder widget.

        Args:
            folder_name: Name of the folder (asset name or scene code)
            folder_type: Type of folder ('asset' or 'scene')
            parent: Parent widget
        """
        super().__init__(parent)
        self.folder_name = folder_name
        self.folder_type = folder_type
        self.image_ids = set()  # Set of image version IDs in this folder

        self.setAcceptDrops(True)
        self.setFixedHeight(70)

        self._setup_ui()

    def _setup_ui(self):
        """Setup the folder UI."""
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Folder icon
        icon_label = QtWidgets.QLabel()
        icon_label.setPixmap(self.style().standardIcon(
            QtWidgets.QStyle.SP_DirIcon
        ).pixmap(32, 32))
        layout.addWidget(icon_label)

        # Folder info (name and count)
        info_layout = QtWidgets.QVBoxLayout()
        info_layout.setSpacing(2)

        # Folder name
        self.name_label = QtWidgets.QLabel(self.folder_name)
        self.name_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        info_layout.addWidget(self.name_label)

        # Image count
        self.count_label = QtWidgets.QLabel("0 images")
        self.count_label.setStyleSheet("color: #888; font-size: 10px;")
        info_layout.addWidget(self.count_label)

        layout.addLayout(info_layout, 1)

        # Style for hover effect
        self.setStyleSheet("""
            FolderWidget {
                background-color: #2b2b2b;
                border: 1px solid #444;
                border-radius: 4px;
            }
            FolderWidget:hover {
                background-color: #353535;
                border: 1px solid #555;
            }
        """)

    def dragEnterEvent(self, event):
        """Handle drag enter event."""
        if event.mimeData().hasFormat("application/x-image-version-id"):
            event.acceptProposedAction()
            # Highlight on drag over
            self.setStyleSheet("""
                FolderWidget {
                    background-color: #3a5f8f;
                    border: 2px solid #4a9eff;
                    border-radius: 4px;
                }
            """)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        """Handle drag leave event."""
        # Remove highlight
        self.setStyleSheet("""
            FolderWidget {
                background-color: #2b2b2b;
                border: 1px solid #444;
                border-radius: 4px;
            }
            FolderWidget:hover {
                background-color: #353535;
                border: 1px solid #555;
            }
        """)

    def dropEvent(self, event):
        """Handle drop event."""
        if event.mimeData().hasFormat("application/x-image-version-id"):
            # Get the dropped image version ID
            image_id_bytes = event.mimeData().data("application/x-image-version-id")
            image_id = int(bytes(image_id_bytes).decode())

            # Add to this folder
            self.image_ids.add(image_id)
            self._update_count()

            event.acceptProposedAction()
            logger.info(f"Dropped image {image_id} into folder {self.folder_name}")

            # Remove highlight
            self.dragLeaveEvent(event)
        else:
            event.ignore()

    def _update_count(self):
        """Update the image count label."""
        count = len(self.image_ids)
        self.count_label.setText(f"{count} image{'s' if count != 1 else ''}")

    def add_image(self, image_id):
        """Add an image to this folder."""
        self.image_ids.add(image_id)
        self._update_count()

    def remove_image(self, image_id):
        """Remove an image from this folder."""
        self.image_ids.discard(image_id)
        self._update_count()

    def get_image_ids(self):
        """Get all image IDs in this folder."""
        return self.image_ids.copy()

    def set_image_ids(self, image_ids):
        """Set the image IDs in this folder."""
        self.image_ids = set(image_ids)
        self._update_count()


class FolderPaneWidget(QtWidgets.QWidget):
    """Widget displaying folders for Assets and Scenes."""

    def __init__(self, parent=None):
        """Initialize folder pane widget."""
        super().__init__(parent)
        self.asset_folders = {}  # asset_name -> FolderWidget
        self.scene_folders = {}  # scene_code -> FolderWidget

        self._setup_ui()

    def _setup_ui(self):
        """Setup the folder pane UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Title
        title_label = QtWidgets.QLabel("Organize Images")
        title_font = title_label.font()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Scroll area for folders
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        # Container for collapsible groups
        container = QtWidgets.QWidget()
        self.container_layout = QtWidgets.QVBoxLayout(container)
        self.container_layout.setContentsMargins(5, 5, 5, 5)
        self.container_layout.setSpacing(10)

        # Assets group
        self.assets_group = CollapsibleGroupBox("Assets")
        self.assets_layout = QtWidgets.QVBoxLayout()
        self.assets_layout.setSpacing(5)
        self.assets_group.addLayout(self.assets_layout)
        self.container_layout.addWidget(self.assets_group)

        # Scenes group
        self.scenes_group = CollapsibleGroupBox("Scenes")
        self.scenes_layout = QtWidgets.QVBoxLayout()
        self.scenes_layout.setSpacing(5)
        self.scenes_group.addLayout(self.scenes_layout)
        self.container_layout.addWidget(self.scenes_group)

        self.container_layout.addStretch()

        scroll_area.setWidget(container)
        layout.addWidget(scroll_area)

        # Set minimum width
        self.setMinimumWidth(250)

    def set_assets(self, asset_names):
        """Set the asset folders.

        Args:
            asset_names: List of unique asset names
        """
        # Clear existing asset folders
        for folder_widget in self.asset_folders.values():
            folder_widget.deleteLater()
        self.asset_folders.clear()

        # Clear layout
        while self.assets_layout.count():
            item = self.assets_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add new asset folders
        for asset_name in sorted(asset_names):
            folder = FolderWidget(asset_name, 'asset', self)
            self.assets_layout.addWidget(folder)
            self.asset_folders[asset_name] = folder

        # Update group title with count
        self.assets_group.setTitle(f"Assets ({len(asset_names)})")

    def set_scenes(self, scene_codes):
        """Set the scene folders.

        Args:
            scene_codes: List of unique scene codes
        """
        # Clear existing scene folders
        for folder_widget in self.scene_folders.values():
            folder_widget.deleteLater()
        self.scene_folders.clear()

        # Clear layout
        while self.scenes_layout.count():
            item = self.scenes_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add new scene folders
        for scene_code in sorted(scene_codes):
            folder = FolderWidget(scene_code, 'scene', self)
            self.scenes_layout.addWidget(folder)
            self.scene_folders[scene_code] = folder

        # Update group title with count
        self.scenes_group.setTitle(f"Scenes ({len(scene_codes)})")

    def get_folder_mappings(self):
        """Get all image-to-folder mappings.

        Returns:
            dict: {
                'assets': {asset_name: [image_id1, image_id2, ...]},
                'scenes': {scene_code: [image_id1, image_id2, ...]}
            }
        """
        mappings = {
            'assets': {},
            'scenes': {}
        }

        for asset_name, folder in self.asset_folders.items():
            image_ids = list(folder.get_image_ids())
            if image_ids:
                mappings['assets'][asset_name] = image_ids

        for scene_code, folder in self.scene_folders.items():
            image_ids = list(folder.get_image_ids())
            if image_ids:
                mappings['scenes'][scene_code] = image_ids

        return mappings

    def load_folder_mappings(self, mappings):
        """Load image-to-folder mappings.

        Args:
            mappings: dict in format {
                'assets': {asset_name: [image_id1, image_id2, ...]},
                'scenes': {scene_code: [image_id1, image_id2, ...]}
            }
        """
        if not mappings:
            return

        # Load asset mappings
        asset_mappings = mappings.get('assets', {})
        for asset_name, image_ids in asset_mappings.items():
            if asset_name in self.asset_folders:
                self.asset_folders[asset_name].set_image_ids(image_ids)

        # Load scene mappings
        scene_mappings = mappings.get('scenes', {})
        for scene_code, image_ids in scene_mappings.items():
            if scene_code in self.scene_folders:
                self.scene_folders[scene_code].set_image_ids(image_ids)
